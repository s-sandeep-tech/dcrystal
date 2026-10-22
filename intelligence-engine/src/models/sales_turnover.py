"""Three-day net turnover forecasts selected by rolling historical validation."""
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from sqlalchemy import text
from ..db.connection import get_db_session
from ..db.writer import DatabaseWriter
from ..external.sales_context import sales_context
from ..external.sales_features import store_context, load_features, save_inputs
from .sales_regressors import FeatureIndex, external_forecast


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


def forecast_daily(rows, use_prophet=True, feature_rows=None, forecast_origin=None):
    forecast_origin = forecast_origin or datetime.now(ZoneInfo('Asia/Kolkata'))
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
    index = FeatureIndex(feature_rows or [])
    groups = {'external_weather': ['weather'], 'external_gold': ['gold'],
              'external_festivals': ['festivals'], 'external_combined': ['weather', 'gold', 'festivals'],
              'external_regional_festivals': ['regional_festivals'], 'external_weddings': ['weddings'],
              'external_regional_calendar': ['regional_festivals', 'weddings'],
              'external_all': ['weather', 'gold', 'festivals', 'regional_festivals', 'weddings']}
    if feature_rows is not None:
        for name, fields in groups.items():
            candidates[name] = lambda train, horizon, fields=fields: external_forecast(train, index, fields,
                datetime.combine((train.index[-1] + timedelta(days=1)).date(), time.min,
                                 tzinfo=ZoneInfo('Asia/Kolkata')), horizon)
    offsets = (18, 15, 12, 9, 6, 3) if len(series) >= 90 else (9, 6, 3)
    scores, residuals, failures = {}, {}, {}
    for name, predict in candidates.items():
        errors = []
        try:
            for offset in offsets:
                train = series.iloc[:-offset]
                actual = series.iloc[-offset:][:3].values
                estimate = predict(train, 3)
                if not np.isfinite(estimate).all():
                    raise ValueError('Model returned non-finite predictions')
                errors.extend((actual - estimate).tolist())
            scores[name] = float(np.mean(np.abs(errors)))
            residuals[name] = errors
        except Exception as error:
            failures[name] = str(error) if name.startswith('external_') else type(error).__name__
    if not scores:
        raise ValueError('No forecast method passed validation')
    baseline = min((name for name in scores if not name.startswith('external_')), key=scores.get)
    eligible = [name for name in scores if name.startswith('external_') and scores[name] < scores[baseline] * .95]
    method = min(eligible, key=scores.get) if eligible else baseline
    fallback_reason = None if eligible else ('No external model improved baseline MAE by at least 5%' if feature_rows is not None else 'External features disabled')
    if feature_rows is not None and not any(name.startswith('external_') for name in scores):
        fallback_reason = 'Insufficient point-in-time external history or forecast coverage; baseline retained'
    try:
        if method in groups:
            values = external_forecast(series, index, groups[method],
                forecast_origin or datetime.now(ZoneInfo('Asia/Kolkata')), 3)
        else:
            values = candidates[method](series, 3)
        if not np.isfinite(values).all():
            raise ValueError('Non-finite forecast')
    except Exception:
        fallback_reason = 'Selected model could not produce complete future inputs or predictions'
        method = baseline
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
                    'unavailable_methods': failures, 'backtest_days': len(offsets) * 3, 'historical_days': len(series),
                    'external_features_used': groups.get(method, []), 'fallback_reason': fallback_reason,
                    'baseline_engine': baseline, 'baseline_mae': scores[baseline],
                    'feature_forecast_origin': forecast_origin.isoformat(),
                    'zero_filled_days': len(series) - observed_days,
                    'interval_method': f'90th percentile absolute backtest error; indicative, {len(offsets) * 3} observations'},
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
        branch_details = None
        if branch_id is not None:
            metadata = session.execute(text('''SELECT MAX(state_name) AS state_name,
                COUNT(DISTINCT NULLIF(UPPER(TRIM(state_name)), '')) AS states
                FROM sales_turnover_daily_snapshots WHERE run_id = :run AND branch_id = :branch'''),
                {'run': snapshot, 'branch': branch_id}).mappings().one()
            branch_details = {'branch_id': branch_id, 'location_name': location,
                              'state_name': metadata['state_name'] if metadata['states'] == 1 else None,
                              'country': 'India'}
        context = {'status': 'disabled'}
        feature_rows = None
        if request['include_external']:
            last_date = max(r['ds'] for r in rows)
            context = sales_context(location, (last_date + timedelta(days=1)).isoformat(),
                (last_date + timedelta(days=3)).isoformat(),
                allow_gemini_fallback=bool(request.get('allow_gemini_fallback', False)), task_id=task_id,
                branch_details=branch_details)
            store_context(session, context, branch_id)
            feature_rows = load_features(session, branch_id, min(r['ds'] for r in rows), last_date + timedelta(days=3))
        now = datetime.now(ZoneInfo('Asia/Kolkata'))
        last_sales_date = max(r['ds'] for r in rows)
        origin = now if last_sales_date >= now.date() - timedelta(days=1) else datetime.combine(
            last_sales_date + timedelta(days=1), time.min, tzinfo=ZoneInfo('Asia/Kolkata'))
        result = forecast_daily(rows, feature_rows=feature_rows, forecast_origin=origin)
        save_inputs(session, task_id, feature_rows or [], result['metrics'])
        cutoff = datetime.fromisoformat(result['cutoff_date']).date()
        today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        result.update(snapshot_run_id=snapshot, branch_id=branch_id, location=location,
                      generated_at=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),
                      stale_days=max(0, (today - cutoff).days - 1), currency='INR',
                      missing_days_policy=run['diagnostics'].get('missing_days_policy'),
                      external_context=context)
        result['external_context']['affects_forecast'] = bool(result['metrics']['external_features_used'])
        DatabaseWriter.save_forecasts(task_id, 'sales_net_turnover', result['forecast'],
                                      dimension=f'branch:{branch_id}' if branch_id else 'all_locations')
        for row in result['forecast']:
            ds_val = row['ds']
            ds_date = datetime.strptime(ds_val[:10], '%Y-%m-%d').date() if isinstance(ds_val, str) else ds_val
            val = float(row.get('baseline_yhat', row.get('yhat', 0.0)))
            lower = float(row['yhat_lower']) if row.get('yhat_lower') is not None else None
            upper = float(row['yhat_upper']) if row.get('yhat_upper') is not None else None
            if branch_id is not None:
                session.execute(text('''
                    INSERT INTO sales_predictions (branch_id, sales_date, predicted_turnover, yhat_lower, yhat_upper, task_id, created_at)
                    VALUES (:branch, :ds, :pred, :lower, :upper, :task, :created)
                    ON CONFLICT (branch_id, sales_date) WHERE branch_id IS NOT NULL
                    DO UPDATE SET
                        predicted_turnover = EXCLUDED.predicted_turnover,
                        yhat_lower = EXCLUDED.yhat_lower,
                        yhat_upper = EXCLUDED.yhat_upper,
                        task_id = EXCLUDED.task_id,
                        created_at = EXCLUDED.created_at
                    WHERE sales_predictions.created_at <= EXCLUDED.created_at
                '''), {'branch': branch_id, 'ds': ds_date, 'pred': val, 'lower': lower, 'upper': upper, 'task': task_id,
                       'created': request['created_at']})
            else:
                session.execute(text('''
                    INSERT INTO sales_predictions (branch_id, sales_date, predicted_turnover, yhat_lower, yhat_upper, task_id, created_at)
                    VALUES (NULL, :ds, :pred, :lower, :upper, :task, :created)
                    ON CONFLICT (sales_date) WHERE branch_id IS NULL
                    DO UPDATE SET
                        predicted_turnover = EXCLUDED.predicted_turnover,
                        yhat_lower = EXCLUDED.yhat_lower,
                        yhat_upper = EXCLUDED.yhat_upper,
                        task_id = EXCLUDED.task_id,
                        created_at = EXCLUDED.created_at
                    WHERE sales_predictions.created_at <= EXCLUDED.created_at
                '''), {'ds': ds_date, 'pred': val, 'lower': lower, 'upper': upper, 'task': task_id,
                       'created': request['created_at']})
        import json
        session.execute(text('UPDATE sales_turnover_forecast_runs SET result_json = CAST(:result AS json) WHERE task_id = :id'),
                        {'id': task_id, 'result': json.dumps(result)})
        return result
