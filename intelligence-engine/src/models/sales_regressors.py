"""Point-in-time ridge candidates. Missing future regressors reject a candidate."""
from datetime import datetime, time, timezone, timedelta
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from zoneinfo import ZoneInfo
from ..external.sales_features import FIELDS


class FeatureIndex:
    def __init__(self, rows):
        self.rows = []
        for row in rows:
            if row['feature_group'] == 'weather' and row.get('provider', '').startswith('NASA POWER historical observations'):
                row = {**row, 'feature_group': 'weather_observations'}
            if row['feature_group'] == 'gold' and set(row['values_json']) == {'price_inr_oz'}:
                row = {**row, 'values_json': {'price_inr_g': float(row['values_json']['price_inr_oz']) / 31.1034768}}
            self.rows.append(row)

    def vector(self, day, origin, groups, future=False):
        day = day.date() if hasattr(day, 'date') else day
        # Feature values for training dates must also have been known before that day.
        asof = origin if future else min(origin, datetime.combine(day, time.min, tzinfo=ZoneInfo('Asia/Kolkata')))
        result = []
        for group in groups:
            eligible = []
            for row in self.rows:
                if row['feature_group'] != group:
                    continue
                if set(row['values_json']) != set(FIELDS[group]):
                    continue  # Legacy USD vintages cannot be mixed with INR features.
                dt = row['feature_date']
                if isinstance(dt, str):
                    dt = datetime.fromisoformat(dt).date()
                available = row['available_at']
                if isinstance(available, str):
                    available = datetime.fromisoformat(available)
                if available > asof:
                    continue
                observation_day = asof.astimezone(ZoneInfo('Asia/Kolkata')).date()
                if (group == 'gold' and observation_day - timedelta(days=7) <= dt < min(day, observation_day)) or (group != 'gold' and dt == day):
                    eligible.append((dt, available, row))
            if not eligible:
                return None
            row = max(eligible, key=lambda item: (item[0], item[1], item[2]['id']))[2]
            result.extend(float(row['values_json'][field]) for field in FIELDS[group])
        return result

    def observations(self, origin, groups):
        """Only past days actually released by origin; freeze across all three horizons."""
        day = origin.astimezone(ZoneInfo('Asia/Kolkata')).date()
        values, ids = [], []
        for group in groups:
            eligible = []
            for row in self.rows:
                if row['feature_group'] != group or set(row['values_json']) != set(FIELDS[group]):
                    continue
                dt = row['feature_date']
                dt = datetime.fromisoformat(dt).date() if isinstance(dt, str) else dt
                available = row['available_at']
                available = datetime.fromisoformat(available) if isinstance(available, str) else available
                if available.tzinfo is None:
                    continue
                if day - timedelta(days=7) <= dt < day and available <= origin:
                    eligible.append((dt, available, row['id'], row))
            if not eligible:
                return None, []
            row = max(eligible, key=lambda r: r[:3])[-1]
            values.extend(float(row['values_json'][f]) for f in FIELDS[group])
            ids.append(row['id'])
        return values, ids

    def timing_summary(self):
        groups = {}
        for row in self.rows:
            group = groups.setdefault(row['feature_group'], {'rows': 0, 'available_after_feature_day': 0})
            group['rows'] += 1
            day = row['feature_date']
            day = datetime.fromisoformat(day).date() if isinstance(day, str) else day
            available = row['available_at']
            available = datetime.fromisoformat(available) if isinstance(available, str) else available
            end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone.utc)
            if available >= end:
                group['available_after_feature_day'] += 1
        return groups


def external_forecast(series, index, groups, origin, horizon=3):
    def design(day, external):
        return [int(day.dayofweek == i) for i in range(7)] + [(day - series.index[0]).days / 30] + external
    estimates = []
    for lead in range(1, horizon + 1):
        x, y = [], []
        for day, target in series.items():
            historical_origin = datetime.combine((day - timedelta(days=lead - 1)).date(), time.min,
                                                 tzinfo=ZoneInfo('Asia/Kolkata'))
            values = index.vector(day, min(origin, historical_origin), groups, future=True)
            if values is not None:
                x.append(design(day, values)); y.append(target)
        if len(x) < 42 or len(x) < len(series) * .8:
            raise ValueError('Insufficient point-in-time feature history (42 days and 80% coverage required)')
        if not np.any(np.std(np.array(x)[:, 8:], axis=0) > 1e-8):
            raise ValueError('External features have no historical variation')
        day = series.index[-1] + timedelta(days=lead)
        values = index.vector(day, origin, groups, future=True)
        if values is None:
            raise ValueError('Missing point-in-time forecast features')
        model = make_pipeline(StandardScaler(), Ridge(alpha=10))
        model.fit(x, y)
        estimates.append(float(model.predict([design(day, values)])[0]))
    return np.asarray(estimates)


def observation_forecast(series, index, groups, origin, horizon=3):
    """Direct horizon models with training inputs frozen at each historical origin."""
    def design(target, values):
        return [int(target.dayofweek == i) for i in range(7)] + [(target - series.index[0]).days / 30] + values
    current, _ = index.observations(origin, groups)
    if current is None:
        raise ValueError('No released observations within seven days of prediction origin')
    estimates = []
    for lead in range(1, horizon + 1):
        x, y = [], []
        for position in range(lead, len(series)):
            target = series.index[position]
            training_origin = datetime.combine((target - timedelta(days=lead - 1)).date(), time.min,
                                                tzinfo=ZoneInfo('Asia/Kolkata'))
            values, _ = index.observations(min(origin, training_origin), groups)
            if values is not None:
                x.append(design(target, values)); y.append(series.iloc[position])
        if len(x) < 42 or len(x) < (len(series) - lead) * .8:
            raise ValueError('Released historical observations insufficient (42 samples and 80% coverage per horizon required)')
        if not np.any(np.std(np.asarray(x)[:, 8:], axis=0) > 1e-8):
            raise ValueError('Observation history has no variation')
        model = make_pipeline(StandardScaler(), Ridge(alpha=10))
        model.fit(x, y)
        target = series.index[-1] + timedelta(days=lead)
        estimates.append(float(model.predict([design(target, current)])[0]))
    return np.asarray(estimates)
