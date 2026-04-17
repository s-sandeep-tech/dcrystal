from flask import render_template, session, redirect, url_for, request, jsonify
from app.dashboard import dashboard_bp
from app.models.akt_report import AKTTransactionPerformance
from app.models import Notification
from app.extensions import db, socketio, redis_client
from app.utils.decorators import require_perm
from sqlalchemy import func, cast, Numeric
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

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
        # Publish to the dedicated AKT channel
        redis_client.publish('akt_performance_updates', json.dumps(payload))
        
        return jsonify({"status": "success", "message": f"AKT sync signal ('{custom_message}') published to Redis"}), 200
    except Exception as e:
        logger.error(f"Error publishing AKT sync signal: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@dashboard_bp.route('/api/akt/transaction-data')
# @require_perm('dashboard.view')
def get_akt_transaction_data():
    try:
        # perminutebillcount is VARCHAR in DB, so it needs explicit casting for aggregates
        def cast_pmbc(col): return cast(col, Numeric)
        def coal(col, default=0): return func.coalesce(col, default)

        # Applying all global filters
        filters = []
        
        filter_configs = {
            'date': AKTTransactionPerformance.date,
            'country': AKTTransactionPerformance.country_actual,
            'region': AKTTransactionPerformance.region,
            'state': AKTTransactionPerformance.state,
            'location': AKTTransactionPerformance.location,
            'division': AKTTransactionPerformance.divisionname,
            'subledger': AKTTransactionPerformance.subledger
        }

        for param, field in filter_configs.items():
            val = request.args.get(param)
            if val:
                filters.append(field == val)

        # 1. Top KPI Strip Data
        kpi_query = db.session.query(
            coal(func.avg(cast_pmbc(AKTTransactionPerformance.perminutebillcount))).label('avg_per_min'),
            coal(func.sum(AKTTransactionPerformance.hourlybillcount)).label('total_hourly'),
            coal(func.sum(AKTTransactionPerformance.invoiceamt)).label('total_sales'),
            coal(func.sum(AKTTransactionPerformance.billcount)).label('total_bills'),
            coal(func.sum(coal(AKTTransactionPerformance.mcprofit) + coal(AKTTransactionPerformance.stonevalueprofit))).label('total_profit'),
            coal(func.sum(AKTTransactionPerformance.netweight)).label('total_net_weight')
        ).filter(*filters)
        
        kpi_data = kpi_query.first()

        # 2. Billing Efficiency Data (by timepartt)
        efficiency_data = db.session.query(
            AKTTransactionPerformance.timepartt,
            coal(func.avg(cast_pmbc(AKTTransactionPerformance.perminutebillcount))).label('avg_per_min'),
            coal(func.sum(AKTTransactionPerformance.hourlybillcount)).label('sum_hourly'),
            coal(func.sum(AKTTransactionPerformance.invoiceamt)).label('sum_revenue')
        ).filter(*filters).group_by(AKTTransactionPerformance.timepartt).order_by(AKTTransactionPerformance.timepartt).all()

        # 3. Location Performance
        location_data = db.session.query(
            AKTTransactionPerformance.location,
            coal(func.avg(cast_pmbc(AKTTransactionPerformance.perminutebillcount))).label('avg_per_min'),
            coal(func.sum(AKTTransactionPerformance.hourlybillcount)).label('sum_hourly'),
            coal(func.sum(AKTTransactionPerformance.invoiceamt)).label('sum_revenue'),
            coal(func.sum(AKTTransactionPerformance.billcount)).label('sum_bills'),
            coal(func.sum(coal(AKTTransactionPerformance.mcprofit) + coal(AKTTransactionPerformance.stonevalueprofit))).label('total_profit')
        ).filter(*filters).group_by(AKTTransactionPerformance.location).order_by(func.sum(AKTTransactionPerformance.invoiceamt).desc()).all()

        # 4. State Performance
        state_data = db.session.query(
            AKTTransactionPerformance.state,
            func.sum(AKTTransactionPerformance.invoiceamt).label('sum_revenue')
        ).filter(*filters).group_by(AKTTransactionPerformance.state).order_by(func.sum(AKTTransactionPerformance.invoiceamt).desc()).all()

        # 5. Trends (Daily)
        trend_data = db.session.query(
            func.date(AKTTransactionPerformance.date).label('d'),
            coal(func.avg(cast_pmbc(AKTTransactionPerformance.perminutebillcount))).label('avg_per_min'),
            coal(func.sum(AKTTransactionPerformance.hourlybillcount)).label('sum_hourly'),
            coal(func.sum(AKTTransactionPerformance.invoiceamt)).label('sum_revenue'),
            coal(func.sum(AKTTransactionPerformance.turnover)).label('sum_turnover')
        ).filter(*filters).group_by(func.date(AKTTransactionPerformance.date)).order_by(func.date(AKTTransactionPerformance.date)).all()

        # 6. Division Data
        division_data = db.session.query(
            AKTTransactionPerformance.divisionname,
            func.sum(AKTTransactionPerformance.invoiceamt).label('sum_revenue')
        ).filter(*filters).group_by(AKTTransactionPerformance.divisionname).all()

        # 7. Revenue Composition & Weight
        comp_query = db.session.query(
            coal(func.sum(AKTTransactionPerformance.metalvalue)).label('metal'),
            coal(func.sum(AKTTransactionPerformance.netstonevalue)).label('stone'),
            coal(func.sum(AKTTransactionPerformance.netdiamondvalue)).label('diamond'),
            coal(func.sum(AKTTransactionPerformance.netcolourstonevalue)).label('color_stone'),
            coal(func.sum(AKTTransactionPerformance.netmcvalue)).label('mc'),
            coal(func.sum(AKTTransactionPerformance.grossweight)).label('gross_wt'),
            coal(func.sum(AKTTransactionPerformance.netweight)).label('net_wt'),
            coal(func.sum(AKTTransactionPerformance.diamondcarat)).label('diamond_carat'),
            coal(func.sum(AKTTransactionPerformance.colourstonecarat)).label('color_carat')
        ).filter(*filters)
        
        composition = comp_query.first()

        # 8. Heatmap Data (date vs timepartt)
        heatmap_raw = db.session.query(
            func.date(AKTTransactionPerformance.date).label('d'),
            AKTTransactionPerformance.timepartt,
            func.sum(AKTTransactionPerformance.billcount).label('bill_count')
        ).filter(*filters).group_by(func.date(AKTTransactionPerformance.date), AKTTransactionPerformance.timepartt).all()

        # 9. Unique filter values
        unique_vals = {}
        if not filters:
            unique_vals = {
                "countries": [r[0] for r in db.session.query(AKTTransactionPerformance.country_actual).distinct().all() if r[0]],
                "regions": [r[0] for r in db.session.query(AKTTransactionPerformance.region).distinct().all() if r[0]],
                "states": [r[0] for r in db.session.query(AKTTransactionPerformance.state).distinct().all() if r[0]],
                "locations": [r[0] for r in db.session.query(AKTTransactionPerformance.location).distinct().all() if r[0]],
                "divisions": [r[0] for r in db.session.query(AKTTransactionPerformance.divisionname).distinct().all() if r[0]],
                "subledgers": [r[0] for r in db.session.query(AKTTransactionPerformance.subledger).distinct().all() if r[0]]
            }

        # Safety Fallbacks for KPIs
        kpi_res = {
            "avg_per_min": float(kpi_data.avg_per_min) if kpi_data and kpi_data.avg_per_min else 0,
            "total_hourly": int(kpi_data.total_hourly) if kpi_data and kpi_data.total_hourly else 0,
            "total_sales": float(kpi_data.total_sales) if kpi_data and kpi_data.total_sales else 0,
            "total_bills": int(kpi_data.total_bills) if kpi_data and kpi_data.total_bills else 0,
            "avg_bill_value": 0,
            "total_profit": float(kpi_data.total_profit) if kpi_data and kpi_data.total_profit else 0,
            "total_net_weight": float(kpi_data.total_net_weight) if kpi_data and kpi_data.total_net_weight else 0
        }
        if kpi_res["total_bills"] > 0:
            kpi_res["avg_bill_value"] = kpi_res["total_sales"] / kpi_res["total_bills"]

        return jsonify({
            "status": "success",
            "kpis": kpi_res,
            "efficiency": [{
                "time": str(d.timepartt),
                "avg_per_min": float(d.avg_per_min or 0),
                "sum_hourly": int(d.sum_hourly or 0),
                "sum_revenue": float(d.sum_revenue or 0)
            } for d in efficiency_data],
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
            "trends": [{
                "date": str(d.d),
                "avg_per_min": float(d.avg_per_min or 0),
                "sum_hourly": int(d.sum_hourly or 0),
                "sum_revenue": float(d.sum_revenue or 0),
                "sum_turnover": float(d.sum_turnover or 0)
            } for d in trend_data],
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
            "heatmap": [{"date": str(h.d), "hour": h.timepartt, "value": int(h.bill_count or 0)} for h in heatmap_raw],
            "filter_options": unique_vals
        })
    except Exception as e:
        logger.exception("Final exception in AKT Data API")
        return jsonify({
            "status": "error", 
            "message": f"Database error on {AKTTransactionPerformance.__tablename__}: {str(e)}",
            "db_bind": "akt_db"
        }), 500
