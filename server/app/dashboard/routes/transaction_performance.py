from flask import render_template, session, redirect, url_for, request, jsonify
from app.dashboard import dashboard_bp
from app.models.akt_report import AKTTransactionPerformance
from app.models import Notification
from app.extensions import db, socketio, redis_client
from app.utils.decorators import require_perm
from sqlalchemy import func, cast, Numeric, case
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import logging
import json
import time

logger = logging.getLogger(__name__)

SALES_COMPARISON_DATE = date(2025, 10, 18)


def selected_divisions(args):
    # An absent filter uses report defaults; an explicit empty value means all.
    values = args.getlist('division') if 'division' in args else ['Gold', 'Diamond']
    return sorted({value.strip().upper() for item in values for value in item.split(',') if value.strip()})


def sales_growth_comparison(current_filters, comparison_filters):
    """Compare cumulative invoice sales through the latest common reporting hour."""
    model = AKTTransactionPerformance
    result = {'sales_growth_yoy': None, 'sales_growth_current': None,
              'sales_growth_previous': None, 'sales_growth_cutoff': None,
              'sales_growth_comparison_date': SALES_COMPARISON_DATE.isoformat(),
              'sales_growth_status': 'missing_data'}
    for metric in ('bills', 'weight', 'avg_bill', 'hourly'):
        result.update({f'{metric}_growth_yoy': None, f'{metric}_growth_current': None, f'{metric}_growth_previous': None})
    valid = model.invoiceamt.isnot(None)
    current_hour = db.session.query(func.max(model.billtime)).filter(*current_filters, valid).scalar()
    prior_hour = db.session.query(func.max(model.billtime)).filter(*comparison_filters, valid).scalar()
    if current_hour is None or prior_hour is None:
        return result
    cutoff = min(current_hour, prior_hour)
    result['sales_growth_cutoff'] = cutoff.strftime('%H:%M')
    def cumulative(conditions):
        grouped = db.session.query(func.max(model.invoiceamt).label('sales'),
                                   func.max(model.billcount).label('bills'),
                                   func.max(model.netweight).label('weight')).filter(
            *conditions, model.billtime <= cutoff
        ).group_by(model.location, model.divisionname, model.state).subquery()
        return db.session.query(func.sum(grouped.c.sales).label('sales'),
                                func.sum(grouped.c.bills).label('bills'),
                                func.sum(grouped.c.weight).label('weight')).first()
    current_totals, previous_totals = cumulative(current_filters), cumulative(comparison_filters)
    for metric in ('sales', 'bills', 'weight'):
        current, previous = getattr(current_totals, metric), getattr(previous_totals, metric)
        divisor = 1000 if metric == 'weight' else 1
        result[f'{metric}_growth_current'] = float(current / divisor) if current is not None else None
        result[f'{metric}_growth_previous'] = float(previous / divisor) if previous is not None else None
        if current is not None and previous is not None and previous > 0:
            result[f'{metric}_growth_yoy'] = float((current - previous) / previous * 100)
            if metric == 'sales': result['sales_growth_status'] = 'available'
        elif metric == 'sales' and previous is not None and previous <= 0:
            result['sales_growth_status'] = 'nonpositive_baseline'
    current_avg = (current_totals.sales / current_totals.bills
                   if current_totals.sales is not None and current_totals.bills is not None and current_totals.bills > 0 else None)
    previous_avg = (previous_totals.sales / previous_totals.bills
                    if previous_totals.sales is not None and previous_totals.bills is not None and previous_totals.bills > 0 else None)
    result['avg_bill_growth_current'] = float(current_avg) if current_avg is not None else None
    result['avg_bill_growth_previous'] = float(previous_avg) if previous_avg is not None else None
    if current_avg is not None and previous_avg is not None and previous_avg > 0:
        result['avg_bill_growth_yoy'] = float((current_avg - previous_avg) / previous_avg * 100)
    # Require two consecutive snapshots; a missing hour is not zero activity.
    if cutoff.hour > 0:
        start_hour = (datetime.combine(SALES_COMPARISON_DATE, cutoff) - timedelta(hours=1)).time()
        result['hourly_comparison_start'] = start_hour.strftime('%H:%M')
        def hourly_bills(conditions):
            groups = db.session.query(
                func.max(case((model.billtime == start_hour, model.billcount))).label('before'),
                func.max(case((model.billtime == cutoff, model.billcount))).label('after')
            ).filter(*conditions, model.billtime.in_([start_hour, cutoff])).group_by(
                model.location, model.divisionname, model.state).all()
            if not groups or any(row.before is None or row.after is None for row in groups):
                return None
            return sum(max(0, row.after - row.before) for row in groups)
        current_hourly, previous_hourly = hourly_bills(current_filters), hourly_bills(comparison_filters)
        result['hourly_growth_current'] = current_hourly
        result['hourly_growth_previous'] = previous_hourly
        if current_hourly is not None and previous_hourly is not None and previous_hourly > 0:
            result['hourly_growth_yoy'] = (current_hourly - previous_hourly) / previous_hourly * 100
    return result


@dashboard_bp.route('/transaction-performance')
@require_perm('dashboard.view')
def transaction_performance():
    if not session.get('user_id'):
        return redirect(url_for('dashboard.login'))

    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    
    return render_template('transaction_performance.html', 
                         unread_count=unread_count,
                         sync_time=sync_time)

@dashboard_bp.route('/api/akt/trigger-sync', methods=['POST', 'GET'])
def trigger_akt_sync():
    """Public endpoint to trigger a data refresh for the AKT dashboard via Redis relay."""
    try:
        import json
        # Try to get custom message from JSON body
        request_data = request.get_json(silent=True) or {}
        custom_message = request_data.get('message', 'Latest transaction data is available')
        
        payload = {
            "action": "refresh",
            "timestamp": datetime.now().isoformat(),
            "message": custom_message
        }
        # Proactively clear AKT cache keys to prevent thundering herd stale reads
        try:
            if redis_client:
                keys = redis_client.keys('akt_perf_cache*')
                if keys:
                    redis_client.delete(*keys)
                    logger.info(f"Cleared {len(keys)} AKT cache keys during sync trigger")
        except Exception as cache_err:
            logger.error(f"Error clearing cache during sync: {str(cache_err)}")

        # Publish to the dedicated AKT channel
        try:
            if redis_client:
                redis_client.publish('akt_performance_updates', json.dumps(payload))
        except Exception as pub_err:
            logger.warning(f"Error publishing to Redis channel akt_performance_updates: {str(pub_err)}")

        # Also emit directly via SocketIO to connected web clients
        try:
            socketio.emit('aktPerformanceRefresh', payload)
            logger.info("Emitted aktPerformanceRefresh event via SocketIO")
        except Exception as ws_err:
            logger.warning(f"Error emitting SocketIO event: {str(ws_err)}")
        
        return jsonify({"status": "success", "message": f"AKT sync signal ('{custom_message}') published and broadcast"}), 200
    except Exception as e:
        logger.error(f"Error publishing AKT sync signal: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@dashboard_bp.route('/api/akt/transaction-data')
@require_perm('dashboard.view')
def get_akt_transaction_data():
    try:
        # perminutebillcount is VARCHAR in DB, so it needs explicit casting for aggregates
        def cast_pmbc(col): return cast(col, Numeric)
        def coal(col, default=0): return func.coalesce(col, default)

        # 0. Caching Logic
        divisions = selected_divisions(request.args)
        cache_key_parts = []
        for param in ['date', 'country', 'region', 'state', 'location', 'division', 'subledger']:
            val = json.dumps(divisions) if param == 'division' else request.args.get(param, '')
            cache_key_parts.append(f"{param}={val}")
        
        cache_key = f"akt_perf_cache_v7:{':'.join(cache_key_parts)}"
        lock_key = f"lock:{cache_key}"
        bypass_cache = request.args.get('bypass_cache', 'false').lower() == 'true'

        lock_acquired = False
        if not bypass_cache and redis_client:
            try:
                for attempt in range(2): # Quick check if locked or cached
                    cached_data = redis_client.get(cache_key)
                    if cached_data:
                        data = json.loads(cached_data)
                        data['cached'] = True
                        return jsonify(data), 200, {'Content-Type': 'application/json'}
                    
                    if redis_client.exists(lock_key):
                        time.sleep(0.5)
                        continue
                    else:
                        break

                lock_acquired = bool(redis_client.set(lock_key, "1", nx=True, ex=30))
                if not lock_acquired:
                    time.sleep(0.5)
                    cached_data = redis_client.get(cache_key)
                    if cached_data:
                        data = json.loads(cached_data)
                        data['cached'] = True
                        return jsonify(data), 200, {'Content-Type': 'application/json'}
            except Exception as cache_err:
                logger.warning(f"Redis cache check failed, proceeding to query DB directly: {cache_err}")
                lock_acquired = False
        
        try:
            # Applying all global filters
            filters = []
            
            filter_configs = {
                'date': func.date(AKTTransactionPerformance.date),
                'country': AKTTransactionPerformance.country_actual,
                'region': AKTTransactionPerformance.region,
                'state': AKTTransactionPerformance.state,
                'location': AKTTransactionPerformance.location,
                'division': AKTTransactionPerformance.divisionname,
                'subledger': AKTTransactionPerformance.subledger
            }

            for param, field in filter_configs.items():
                if param == 'division':
                    if divisions:
                        filters.append(func.upper(func.trim(field)).in_(divisions))
                    continue
                val = request.args.get(param)
                if val:
                    if param == 'country':
                        filters.append(func.upper(field) == val.upper())
                    else:
                        filters.append(field == val)
            
            # Per user request: Only consider hourly snapshots (Minute = 0)
            from sqlalchemy import extract
            filters.append(extract('minute', AKTTransactionPerformance.billtime) == 0)

            # 1. Master Snapshot: Latest values per Location/Division
            # This is the "Gold Source" for all cumulative metrics (KPIs, State, Division, Composition)
            kpi_sub = db.session.query(
                AKTTransactionPerformance.location,
                AKTTransactionPerformance.divisionname,
                AKTTransactionPerformance.state,
                func.max(cast_pmbc(AKTTransactionPerformance.perminutebillcount)).label('max_avg_per_min'),
                func.max(AKTTransactionPerformance.hourlybillcount).label('max_hourly'),
                func.max(AKTTransactionPerformance.invoiceamt).label('max_sales'),
                func.max(AKTTransactionPerformance.turnover).label('max_turnover'),
                func.max(coal(AKTTransactionPerformance.mcprofit) + coal(AKTTransactionPerformance.stonevalueprofit)).label('max_profit'),
                func.max(AKTTransactionPerformance.netweight).label('max_net_wt'),
                func.max(AKTTransactionPerformance.billcount).label('max_bills'),
                # Composition columns (cumulative)
                func.max(AKTTransactionPerformance.metalvalue).label('max_metal'),
                func.max(AKTTransactionPerformance.netstonevalue).label('max_stone'),
                func.max(AKTTransactionPerformance.netdiamondvalue).label('max_diamond'),
                func.max(AKTTransactionPerformance.netcolourstonevalue).label('max_color_stone'),
                func.max(AKTTransactionPerformance.netmcvalue).label('max_mc'),
                # Weight columns (cumulative)
                func.max(AKTTransactionPerformance.grossweight).label('max_gross_wt'),
                func.max(AKTTransactionPerformance.diamondcarat).label('max_diamond_carat'),
                func.max(AKTTransactionPerformance.colourstonecarat).label('max_color_carat')
            ).filter(*filters).group_by(
                AKTTransactionPerformance.location, 
                AKTTransactionPerformance.divisionname,
                AKTTransactionPerformance.state
            ).subquery()

            kpi_query = db.session.query(
                coal(func.avg(kpi_sub.c.max_avg_per_min)).label('avg_per_min'),
                coal(func.sum(kpi_sub.c.max_hourly)).label('total_hourly'),
                coal(func.sum(kpi_sub.c.max_sales)).label('total_sales'),
                coal(func.sum(kpi_sub.c.max_profit)).label('total_profit'),
                coal(func.sum(kpi_sub.c.max_net_wt)).label('total_net_weight'),
                coal(func.sum(kpi_sub.c.max_bills)).label('total_bills')
            )
            
            kpi_data = kpi_query.first()
            total_bills = kpi_data.total_bills if kpi_data else 0

            # 2. Billing Efficiency Data (by timepartt)
            # Get max cumulative per (hour, store, division)
            eff_sub = db.session.query(
                AKTTransactionPerformance.timepartt,
                AKTTransactionPerformance.location,
                AKTTransactionPerformance.divisionname,
                func.max(AKTTransactionPerformance.billcount).label('max_bills'),
                func.max(AKTTransactionPerformance.invoiceamt).label('max_rev'),
                func.max(AKTTransactionPerformance.turnover).label('max_turnover'),
                func.max(cast_pmbc(AKTTransactionPerformance.perminutebillcount)).label('max_per_min')
            ).filter(*filters).group_by(AKTTransactionPerformance.timepartt, AKTTransactionPerformance.location, AKTTransactionPerformance.divisionname).subquery()

            efficiency_raw = db.session.query(
                eff_sub.c.timepartt,
                coal(func.avg(eff_sub.c.max_per_min)).label('avg_per_min'),
                coal(func.sum(eff_sub.c.max_bills)).label('cum_bills'),
                coal(func.sum(eff_sub.c.max_rev)).label('cum_rev')
            ).group_by(eff_sub.c.timepartt).order_by(eff_sub.c.timepartt).all()

            efficiency_data = []
            prev_bills = 0
            prev_rev = 0.0
            for row in efficiency_raw:
                curr_bills = float(row.cum_bills or 0)
                curr_rev = float(row.cum_rev or 0)
                hourly_delta = max(0, curr_bills - prev_bills)
                hourly_rev_delta = max(0.0, curr_rev - prev_rev)
                efficiency_data.append({
                    "time": str(row.timepartt),
                    "avg_per_min": float(row.avg_per_min or 0),
                    "sum_hourly": int(hourly_delta),
                    "sum_revenue": float(hourly_rev_delta),
                    "cum_revenue": float(curr_rev),
                    "cum_bills": int(row.cum_bills or 0)
                })
                prev_bills = curr_bills
                prev_rev = curr_rev

            # 2.1. 2025 Comparison Data (Specifically for Hourly Billing Count, Dhanteras: 18.10.2025)
            filters_2025 = []
            for param, field in filter_configs.items():
                if param == 'date':
                    filters_2025.append(field == SALES_COMPARISON_DATE)
                elif param == 'division':
                    if divisions:
                        filters_2025.append(func.upper(func.trim(field)).in_(divisions))
                else:
                    val = request.args.get(param)
                    if val:
                        if param == 'country':
                            filters_2025.append(func.upper(field) == val.upper())
                        else:
                            filters_2025.append(field == val)
            
            # Add minute constraint to 2025 as well
            filters_2025.append(extract('minute', AKTTransactionPerformance.billtime) == 0)

            eff_sub_2025 = db.session.query(
                AKTTransactionPerformance.timepartt,
                func.max(AKTTransactionPerformance.billcount).label('max_bills')
            ).filter(*filters_2025).group_by(AKTTransactionPerformance.timepartt, AKTTransactionPerformance.location, AKTTransactionPerformance.divisionname).subquery()

            efficiency_raw_2025 = db.session.query(
                eff_sub_2025.c.timepartt,
                coal(func.sum(eff_sub_2025.c.max_bills)).label('cum_bills')
            ).group_by(eff_sub_2025.c.timepartt).order_by(eff_sub_2025.c.timepartt).all()

            efficiency_2025 = []
            prev_bills_2025 = 0
            for row in efficiency_raw_2025:
                curr_bills = float(row.cum_bills or 0)
                hourly_delta = max(0, curr_bills - prev_bills_2025)
                efficiency_2025.append({
                    "time": str(row.timepartt),
                    "sum_hourly": int(hourly_delta),
                    "cum_bills": int(row.cum_bills or 0)
                })
                prev_bills_2025 = curr_bills

            # 2.2. 2025 Weights Comparison
            kpi_sub_2025 = db.session.query(
                func.max(AKTTransactionPerformance.grossweight).label('max_gross_wt'),
                func.max(AKTTransactionPerformance.netweight).label('max_net_wt')
            ).filter(*filters_2025).group_by(AKTTransactionPerformance.location, AKTTransactionPerformance.divisionname).subquery()

            weights_raw_2025 = db.session.query(
                coal(func.sum(kpi_sub_2025.c.max_gross_wt)).label('total_gross'),
                coal(func.sum(kpi_sub_2025.c.max_net_wt)).label('total_net')
            ).first()

            weight_analysis_2025 = {
                "gross": float(weights_raw_2025.total_gross or 0) if weights_raw_2025 else 0,
                "net": float(weights_raw_2025.total_net or 0) if weights_raw_2025 else 0
            }

            # 3. Location Performance
            location_data = db.session.query(
                kpi_sub.c.location,
                coal(func.avg(kpi_sub.c.max_avg_per_min)).label('avg_per_min'),
                coal(func.sum(kpi_sub.c.max_hourly)).label('sum_hourly'),
                coal(func.sum(kpi_sub.c.max_sales)).label('sum_revenue'),
                coal(func.sum(kpi_sub.c.max_bills)).label('sum_bills'),
                coal(func.sum(kpi_sub.c.max_profit)).label('total_profit')
            ).group_by(kpi_sub.c.location).all()

            # 4. State Performance
            state_data = db.session.query(
                kpi_sub.c.state,
                coal(func.sum(kpi_sub.c.max_sales)).label('sum_revenue')
            ).group_by(kpi_sub.c.state).order_by(coal(func.sum(kpi_sub.c.max_sales)).desc()).all()

            # 5. Trends (Hourly)
            # Same delta logic as efficiency for the trend chart
            trend_raw = db.session.query(
                eff_sub.c.timepartt.label('hour'),
                coal(func.sum(eff_sub.c.max_bills)).label('cum_bills'),
                coal(func.sum(eff_sub.c.max_rev)).label('cum_rev'),
                coal(func.sum(eff_sub.c.max_turnover)).label('cum_turnover')
            ).group_by(eff_sub.c.timepartt).order_by(eff_sub.c.timepartt).all()

            trend_data = []
            prev_trend_bills = 0
            prev_trend_rev = 0.0
            prev_trend_turnover = 0.0
            for row in trend_raw:
                curr_bills = float(row.cum_bills or 0)
                curr_rev = float(row.cum_rev or 0)
                curr_turnover = float(row.cum_turnover or 0)
                delta = max(0, curr_bills - prev_trend_bills)
                delta_rev = max(0.0, curr_rev - prev_trend_rev)
                delta_turnover = max(0.0, curr_turnover - prev_trend_turnover)
                trend_data.append({
                    "hour": row.hour,
                    "sum_hourly": int(delta),
                    "sum_revenue": float(delta_rev),
                    "cum_revenue": float(curr_rev),
                    "sum_turnover": float(delta_turnover),
                    "cum_turnover": float(curr_turnover)
                })
                prev_trend_bills = curr_bills
                prev_trend_rev = curr_rev
                prev_trend_turnover = curr_turnover

            # 6. Division Data
            division_data = db.session.query(
                kpi_sub.c.divisionname,
                coal(func.sum(kpi_sub.c.max_sales)).label('sum_revenue')
            ).group_by(kpi_sub.c.divisionname).all()

            # 7. Revenue Composition & Weight
            comp_query = db.session.query(
                coal(func.sum(kpi_sub.c.max_metal)).label('metal'),
                coal(func.sum(kpi_sub.c.max_stone)).label('stone'),
                coal(func.sum(kpi_sub.c.max_diamond)).label('diamond'),
                coal(func.sum(kpi_sub.c.max_color_stone)).label('color_stone'),
                coal(func.sum(kpi_sub.c.max_mc)).label('mc'),
                coal(func.sum(kpi_sub.c.max_gross_wt)).label('gross_wt'),
                coal(func.sum(kpi_sub.c.max_net_wt)).label('net_wt'),
                coal(func.sum(kpi_sub.c.max_diamond_carat)).label('diamond_carat'),
                coal(func.sum(kpi_sub.c.max_color_carat)).label('color_carat')
            )
            
            composition = comp_query.first()

            # 8. Heatmap Data (Activity density using hourly delta)
            # Use sum(max) to prevent double-counting if multiple snapshots exist in one hour
            heat_sub = db.session.query(
                func.date(AKTTransactionPerformance.date).label('d'),
                AKTTransactionPerformance.timepartt,
                AKTTransactionPerformance.location,
                AKTTransactionPerformance.divisionname,
                func.max(AKTTransactionPerformance.hourlybillcount).label('max_h_bills')
            ).filter(*filters).group_by(
                func.date(AKTTransactionPerformance.date), 
                AKTTransactionPerformance.timepartt,
                AKTTransactionPerformance.location,
                AKTTransactionPerformance.divisionname
            ).subquery()

            heatmap_raw = db.session.query(
                heat_sub.c.d,
                heat_sub.c.timepartt,
                coal(func.sum(heat_sub.c.max_h_bills)).label('bill_count')
            ).group_by(heat_sub.c.d, heat_sub.c.timepartt).all()

            # 9. Unique filter values (Cascading Hierarchy)
            # Each level narrows down the next: Country -> Region -> State -> Location
            unique_vals = {}
            
            country_val = request.args.get('country')
            region_val = request.args.get('region')
            state_val = request.args.get('state')
            location_val = request.args.get('location')

            def get_distinct(field, current_filters):
                return [r[0] for r in db.session.query(field).filter(*current_filters).distinct().all() if r[0]]

            # Hierarchy filters
            f_country = []
            f_region = [func.upper(AKTTransactionPerformance.country_actual) == country_val.upper()] if country_val else []
            f_state = f_region + ([AKTTransactionPerformance.region == region_val] if region_val else [])
            f_loc = f_state + ([AKTTransactionPerformance.state == state_val] if state_val else [])
            f_div = f_loc + ([AKTTransactionPerformance.location == location_val] if location_val else [])

            unique_vals = {
                "countries": get_distinct(AKTTransactionPerformance.country_actual, f_country),
                "regions": get_distinct(AKTTransactionPerformance.region, f_region),
                "states": get_distinct(AKTTransactionPerformance.state, f_state),
                "locations": get_distinct(AKTTransactionPerformance.location, f_loc),
                "divisions": get_distinct(AKTTransactionPerformance.divisionname, f_div),
                "subledgers": get_distinct(AKTTransactionPerformance.subledger, f_div)
            }

            # Safety Fallbacks for KPIs
            net_wt_grams = float(kpi_data.total_net_weight) if kpi_data and kpi_data.total_net_weight else 0.0
            kpi_res = {
                "avg_per_min": float(kpi_data.avg_per_min) if kpi_data and kpi_data.avg_per_min else 0,
                "total_hourly": efficiency_data[-1]["sum_hourly"] if efficiency_data else 0,
                "total_sales": float(kpi_data.total_sales) if kpi_data and kpi_data.total_sales else 0,
                "total_bills": int(total_bills),
                "avg_bill_value": 0,
                "total_profit": float(kpi_data.total_profit) if kpi_data and kpi_data.total_profit else 0,
                "total_net_weight": round(net_wt_grams / 1000.0, 3),
                "total_net_weight_kg": round(net_wt_grams / 1000.0, 3),
                "total_net_weight_grams": net_wt_grams
            }
            growth_filters = list(filters)
            if not request.args.get('date'):
                growth_filters.append(func.date(AKTTransactionPerformance.date) == datetime.now(ZoneInfo('Asia/Kolkata')).date())
            kpi_res.update(sales_growth_comparison(growth_filters, filters_2025))
            if kpi_res["total_bills"] > 0:
                kpi_res["avg_bill_value"] = kpi_res["total_sales"] / kpi_res["total_bills"]

            result = {
                "status": "success",
                "cached": False,
                "kpis": kpi_res,
                "efficiency": efficiency_data,
                "efficiency_2025": efficiency_2025,
                "location_performance": [{
                    "location": d.location or "Unknown",
                    "avg_per_min": float(d.avg_per_min or 0),
                    "sum_hourly": int(d.sum_hourly or 0),
                    "sum_revenue": float(d.sum_revenue or 0),
                    "total_profit": float(d.total_profit or 0),
                    "avg_bill_value": float(d.sum_revenue or 0) / int(d.sum_bills or 1),
                    "profit_margin": (float(d.total_profit or 0) / float(d.sum_revenue or 1)) * 100
                } for d in location_data],
                "state_performance": [{"state": d.state or "Unknown", "value": float(d.sum_revenue or 0)} for d in state_data],
                "trends": trend_data,
                "division_sales": [{"division": d.divisionname or "Unknown", "value": float(d.sum_revenue or 0)} for d in division_data],
                "composition": {
                    "Metal": float(composition.metal or 0) if composition else 0,
                    "Stone": float(composition.stone or 0) if composition else 0,
                    "Diamond": float(composition.diamond or 0) if composition else 0,
                    "Colour Stone": float(composition.color_stone or 0) if composition else 0,
                    "MC": float(composition.mc or 0) if composition else 0
                },
                "weight_analysis": {
                    "gross": float(composition.gross_wt or 0) if composition else 0,
                    "net": float(composition.net_wt or 0) if composition else 0,
                    "diamond": float(composition.diamond_carat or 0) if composition else 0,
                    "stone": float(composition.color_carat or 0) if composition else 0
                },
                "weight_analysis_2025": weight_analysis_2025,
                "heatmap": [{"date": str(h.d), "hour": h.timepartt, "value": int(h.bill_count or 0)} for h in heatmap_raw],
                "filter_options": unique_vals
            }

            # Cache the result for 15 minutes (900 seconds)
            if redis_client:
                try:
                    redis_client.setex(cache_key, 900, json.dumps(result))
                except Exception as cache_err:
                    logger.error(f"Failed to cache data for {cache_key}: {str(cache_err)}")

            return jsonify(result)
        finally:
            # Release the lock if we held it
            if lock_acquired and redis_client:
                try:
                    redis_client.delete(lock_key)
                except Exception as del_err:
                    logger.warning(f"Error releasing Redis lock {lock_key}: {del_err}")
    except Exception as e:
        logger.exception("Final exception in AKT Data API")
        return jsonify({
            "status": "error", 
            "message": f"Database error on {AKTTransactionPerformance.__tablename__}: {str(e)}",
            "db_bind": "akt_db"
        }), 500
