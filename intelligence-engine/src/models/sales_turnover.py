"""Three-day net turnover forecasts selected by rolling historical validation."""
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from sqlalchemy import text
from ..db.connection import get_db_session
from ..db.writer import DatabaseWriter
from ..external.sales_context import sales_context


def weekday_forecast(series, horizon=3):
    dates = pd.date_range(series.index[-1] + pd.Timedelta(days=1), periods=horizon)
    recent = series.iloc[-56:]
    return np.array([float(recent[recent.index.dayofweek == day.dayofweek].tail(8).mean()) for day in dates])


def prophet_forecast(series, horizon=3):
    from prophet import Prophet
    model = Prophet(weekly_seasonality=True, yearly_seasonality=False, daily_seasonality=False)
    model.fit(pd.DataFrame({'ds': series.index, 'y': series.values}))
    future = pd.DataFrame({'ds': pd.date_range(series.index[-1] + pd.Timedelta(days=1), periods=horizon)})
    return model.predict(future)['yhat'].to_numpy()


def forecast_daily(rows, use_prophet=True):
    if not rows:
        raise ValueError('No daily turnover history is available for this scope')
    dates = pd.to_datetime([r['ds'] for r in rows])
    if dates.duplicated().any():
        raise ValueError('Duplicate dates in forecast input')
    series = pd.Series([float(r['y']) for r in rows], index=dates).sort_index()
    if not np.isfinite(series.values).all():
        raise ValueError('Non-finite turnover values')
    observed_days = len(series)
    series = series.reindex(pd.date_range(series.index[0], series.index[-1]), fill_value=0.0)
    if len(series) < 65 or observed_days < 28:
        raise ValueError('At least 65 calendar days and 28 sales dates are required')
    candidates = {'weekday_average': weekday_forecast}
    if use_prophet:
        candidates['prophet'] = prophet_forecast
    scores, residuals, failures = {}, {}, {}
    for name, predict in candidates.items():
        errors = []
        try:
            for offset in (9, 6, 3):
                train = series.iloc[:-offset]
                actual = series.iloc[-offset:][:3].values
                estimate = predict(train, 3)
                if not np.isfinite(estimate).all():
                    raise ValueError('Model returned non-finite predictions')
                errors.extend((actual - estimate).tolist())
            scores[name] = float(np.mean(np.abs(errors)))
            residuals[name] = errors
        except Exception as error:
            failures[name] = type(error).__name__
    if not scores:
        raise ValueError('No forecast method passed validation')
    method = min(scores, key=scores.get)
    try:
        values = candidates[method](series, 3)
    except Exception:
        method = 'weekday_average'
        values = weekday_forecast(series, 3)
    if not np.isfinite(values).all():
        raise ValueError('Model returned non-finite predictions')
    radius = float(np.quantile(np.abs(residuals[method]), 0.90))
    forecast = [{'ds': day.date().isoformat(), 'baseline_yhat': round(float(value), 2),
                 'yhat_lower': round(float(value) - radius, 2), 'yhat_upper': round(float(value) + radius, 2)}
                for day, value in zip(pd.date_range(series.index[-1] + pd.Timedelta(days=1), periods=3), values)]
    return {
        'forecast': forecast, 'history': [{'ds': d.date().isoformat(), 'y': float(v)} for d, v in series.items()],
        'metrics': {'engine': method, 'backtest_mae': scores[method], 'candidate_mae': scores,
                    'unavailable_methods': failures, 'backtest_days': 9, 'historical_days': len(series),
                    'zero_filled_days': len(series) - observed_days,
                    'interval_method': '90th percentile absolute backtest error; indicative, 9 observations'},
        'cutoff_date': series.index[-1].date().isoformat(),
        'three_day_total': round(float(sum(values)), 2)
    }


def run_sales_turnover_forecast(task_id, payload):
    snapshot = str(payload.get('snapshot_run_id', ''))
    branch_id = payload.get('branch_id')
    with get_db_session() as session:
        request = session.execute(text('SELECT * FROM sales_turnover_forecast_runs WHERE task_id = :id'), {'id': task_id}).mappings().first()
        if not request or request['snapshot_run_id'] != snapshot or request['branch_id'] != branch_id:
            raise ValueError('Forecast request does not match the registered scope')
        run = session.execute(text('SELECT * FROM sales_prediction_sync_runs WHERE id = :id'), {'id': snapshot}).mappings().first()
        if not run:
            raise ValueError('Sales snapshot is unavailable; run Sales Prediction Data Sync')
        rows = session.execute(text('''SELECT sales_date AS ds, SUM(net_turnover) AS y
            FROM sales_turnover_daily_snapshots WHERE run_id = :run
            AND (:branch IS NULL OR branch_id = :branch)
            GROUP BY sales_date ORDER BY sales_date'''), {'run': snapshot, 'branch': branch_id}).mappings().all()
        location = session.execute(text('''SELECT MAX(location_name) FROM sales_turnover_daily_snapshots
            WHERE run_id = :run AND branch_id = :branch'''), {'run': snapshot, 'branch': branch_id}).scalar() if branch_id else 'All locations'
        result = forecast_daily(rows)
        cutoff = datetime.fromisoformat(result['cutoff_date']).date()
        today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        result.update(snapshot_run_id=snapshot, branch_id=branch_id, location=location,
                      generated_at=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),
                      stale_days=max(0, (today - cutoff).days - 1), currency='INR',
                      missing_days_policy=run['diagnostics'].get('missing_days_policy'),
                      external_context={'status': 'disabled'})
        if request['include_external']:
            result['external_context'] = sales_context(location, result['forecast'][0]['ds'], result['forecast'][-1]['ds'])
        DatabaseWriter.save_forecasts(task_id, 'sales_net_turnover', result['forecast'],
                                      dimension=f'branch:{branch_id}' if branch_id else 'all_locations')
        import json
        session.execute(text('UPDATE sales_turnover_forecast_runs SET result_json = CAST(:result AS json) WHERE task_id = :id'),
                        {'id': task_id, 'result': json.dumps(result)})
        return result
