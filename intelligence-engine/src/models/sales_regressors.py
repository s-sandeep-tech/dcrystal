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
                if (group == 'gold' and day - timedelta(days=7) <= dt < day) or (group != 'gold' and dt == day):
                    eligible.append((dt, available, row))
            if not eligible:
                return None
            row = max(eligible, key=lambda item: (item[0], item[1], item[2]['id']))[2]
            result.extend(float(row['values_json'][field]) for field in FIELDS[group])
        return result


def external_forecast(series, index, groups, origin, horizon=3):
    def design(day, external):
        return [int(day.dayofweek == i) for i in range(7)] + [(day - series.index[0]).days / 30] + external
    x, y = [], []
    for day, target in series.items():
        values = index.vector(day, origin, groups)
        if values is not None:
            x.append(design(day, values)); y.append(target)
    if len(x) < 42 or len(x) < len(series) * .8:
        raise ValueError('Insufficient point-in-time feature history (42 days and 80% coverage required)')
    external_start = 8
    if not np.any(np.std(np.array(x)[:, external_start:], axis=0) > 1e-8):
        raise ValueError('External features have no historical variation')
    future = []
    for offset in range(1, horizon + 1):
        day = series.index[-1] + timedelta(days=offset)
        values = index.vector(day, origin, groups, future=True)
        if values is None:
            raise ValueError('Missing point-in-time forecast features')
        future.append(design(day, values))
    model = make_pipeline(StandardScaler(), Ridge(alpha=10))
    model.fit(x, y)
    return model.predict(future)
