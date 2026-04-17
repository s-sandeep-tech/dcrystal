from flask import render_template, session, redirect, url_for, request, jsonify
from app.dashboard import dashboard_bp
from app.models.akt_report import AKTTransactionPerformance
from app.models import Notification
from app.extensions import db
from app.utils.decorators import require_perm
from sqlalchemy import func
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

@dashboard_bp.route('/api/akt/transaction-data')
# @require_perm('dashboard.view')
def get_akt_transaction_data():
    try:
        # Applying all global filters
        filters = []
        
        filter_configs = {
            'date': AKTTransactionPerformance.Date,
            'country': AKTTransactionPerformance.Country_Actual,
            'region': AKTTransactionPerformance.Region,
            'state': AKTTransactionPerformance.State,
            'location': AKTTransactionPerformance.Location,
            'division': AKTTransactionPerformance.DivisionName,
            'subledger': AKTTransactionPerformance.Subledger
        }

        for param, field in filter_configs.items():
            val = request.args.get(param)
            if val:
                filters.append(field == val)

        # 1. Top KPI Strip Data
        kpi_data = db.session.query(
            func.avg(AKTTransactionPerformance.PerMinuteBillCount).label('avg_per_min'),
            func.sum(AKTTransactionPerformance.HourlyBillCount).label('total_hourly'),
            func.sum(AKTTransactionPerformance.InvoiceAmt).label('total_sales'),
            func.sum(AKTTransactionPerformance.BillCount).label('total_bills'),
            func.sum(AKTTransactionPerformance.MCprofit + AKTTransactionPerformance.StoneVAlueProfit).label('total_profit'),
            func.sum(AKTTransactionPerformance.NetWeight).label('total_net_weight')
        ).filter(*filters).first()

        # 2. Billing Efficiency Data (by TimePartt)
        efficiency_data = db.session.query(
            AKTTransactionPerformance.TimePartt,
            func.avg(AKTTransactionPerformance.PerMinuteBillCount).label('avg_per_min'),
            func.sum(AKTTransactionPerformance.HourlyBillCount).label('sum_hourly'),
            func.sum(AKTTransactionPerformance.InvoiceAmt).label('sum_revenue')
        ).filter(*filters).group_by(AKTTransactionPerformance.TimePartt).order_by(AKTTransactionPerformance.TimePartt).all()

        # 3. Location Performance (Aggregated for all charts)
        location_data = db.session.query(
            AKTTransactionPerformance.Location,
            func.avg(AKTTransactionPerformance.PerMinuteBillCount).label('avg_per_min'),
            func.sum(AKTTransactionPerformance.HourlyBillCount).label('sum_hourly'),
            func.sum(AKTTransactionPerformance.InvoiceAmt).label('sum_revenue'),
            func.sum(AKTTransactionPerformance.BillCount).label('sum_bills'),
            func.sum(AKTTransactionPerformance.MCprofit + AKTTransactionPerformance.StoneVAlueProfit).label('total_profit')
        ).filter(*filters).group_by(AKTTransactionPerformance.Location).order_by(func.sum(AKTTransactionPerformance.InvoiceAmt).desc()).all()

        # 4. State Performance
        state_data = db.session.query(
            AKTTransactionPerformance.State,
            func.sum(AKTTransactionPerformance.InvoiceAmt).label('sum_revenue')
        ).filter(*filters).group_by(AKTTransactionPerformance.State).order_by(func.sum(AKTTransactionPerformance.InvoiceAmt).desc()).all()

        # 5. Trends (Daily)
        trend_data = db.session.query(
            AKTTransactionPerformance.Date,
            func.avg(AKTTransactionPerformance.PerMinuteBillCount).label('avg_per_min'),
            func.sum(AKTTransactionPerformance.HourlyBillCount).label('sum_hourly'),
            func.sum(AKTTransactionPerformance.InvoiceAmt).label('sum_revenue'),
            func.sum(AKTTransactionPerformance.Turnover).label('sum_turnover')
        ).filter(*filters).group_by(AKTTransactionPerformance.Date).order_by(AKTTransactionPerformance.Date).all()

        # 6. Division Data
        division_data = db.session.query(
            AKTTransactionPerformance.DivisionName,
            func.sum(AKTTransactionPerformance.InvoiceAmt).label('sum_revenue')
        ).filter(*filters).group_by(AKTTransactionPerformance.DivisionName).all()

        # 7. Revenue Composition & Weight
        composition = db.session.query(
            func.sum(AKTTransactionPerformance.MetalValue).label('metal'),
            func.sum(AKTTransactionPerformance.NetStoneValue).label('stone'),
            func.sum(AKTTransactionPerformance.NetDiamondValue).label('diamond'),
            func.sum(AKTTransactionPerformance.NetColourStoneValue).label('color_stone'),
            func.sum(AKTTransactionPerformance.NetMCValue).label('mc'),
            func.sum(AKTTransactionPerformance.GrossWeight).label('gross_wt'),
            func.sum(AKTTransactionPerformance.NetWeight).label('net_wt'),
            func.sum(AKTTransactionPerformance.DiamondCarat).label('diamond_carat'),
            func.sum(AKTTransactionPerformance.ColourStoneCarat).label('color_carat')
        ).filter(*filters).first()

        # 8. Heatmap Data (Date vs TimePartt)
        heatmap_raw = db.session.query(
            AKTTransactionPerformance.Date,
            AKTTransactionPerformance.TimePartt,
            func.sum(AKTTransactionPerformance.BillCount).label('bill_count')
        ).filter(*filters).group_by(AKTTransactionPerformance.Date, AKTTransactionPerformance.TimePartt).all()

        # 9. Unique filter values for populating dropdowns
        unique_vals = {}
        if not filters: # Only fetch once or when no specific filter is selected to avoid recursion issues
            unique_vals = {
                "countries": [r[0] for r in db.session.query(AKTTransactionPerformance.Country_Actual).distinct().all()],
                "regions": [r[0] for r in db.session.query(AKTTransactionPerformance.Region).distinct().all()],
                "states": [r[0] for r in db.session.query(AKTTransactionPerformance.State).distinct().all()],
                "locations": [r[0] for r in db.session.query(AKTTransactionPerformance.Location).distinct().all()],
                "divisions": [r[0] for r in db.session.query(AKTTransactionPerformance.DivisionName).distinct().all()],
                "subledgers": [r[0] for r in db.session.query(AKTTransactionPerformance.Subledger).distinct().all()]
            }

        return jsonify({
            "status": "success",
            "kpis": {
                "avg_per_min": float(kpi_data.avg_per_min or 0),
                "total_hourly": int(kpi_data.total_hourly or 0),
                "total_sales": float(kpi_data.total_sales or 0),
                "total_bills": int(kpi_data.total_bills or 0),
                "avg_bill_value": float(kpi_data.total_sales or 0) / int(kpi_data.total_bills or 1),
                "total_profit": float(kpi_data.total_profit or 0),
                "total_net_weight": float(kpi_data.total_net_weight or 0)
            },
            "efficiency": [{
                "time": str(d.TimePartt),
                "avg_per_min": float(d.avg_per_min or 0),
                "sum_hourly": int(d.sum_hourly or 0),
                "sum_revenue": float(d.sum_revenue or 0)
            } for d in efficiency_data],
            "location_performance": [{
                "location": d.Location,
                "avg_per_min": float(d.avg_per_min or 0),
                "sum_hourly": int(d.sum_hourly or 0),
                "sum_revenue": float(d.sum_revenue or 0),
                "total_profit": float(d.total_profit or 0),
                "avg_bill_value": float(d.sum_revenue or 0) / int(d.sum_bills or 1),
                "profit_margin": (float(d.total_profit or 0) / float(d.sum_revenue or 1)) * 100
            } for d in location_data],
            "state_performance": [{
                "state": d.State,
                "value": float(d.sum_revenue or 0)
            } for d in state_data],
            "trends": [{
                "date": str(d.Date),
                "avg_per_min": float(d.avg_per_min or 0),
                "sum_hourly": int(d.sum_hourly or 0),
                "sum_revenue": float(d.sum_revenue or 0),
                "sum_turnover": float(d.sum_turnover or 0)
            } for d in trend_data],
            "division_sales": [{
                "division": d.DivisionName,
                "value": float(d.sum_revenue or 0)
            } for d in division_data],
            "composition": {
                "Metal": float(composition.metal or 0),
                "Stone": float(composition.stone or 0),
                "Diamond": float(composition.diamond or 0),
                "Colour Stone": float(composition.color_stone or 0),
                "MC": float(composition.mc or 0)
            },
            "weight_analysis": {
                "gross": float(composition.gross_wt or 0),
                "net": float(composition.net_wt or 0),
                "diamond": float(composition.diamond_carat or 0),
                "stone": float(composition.color_carat or 0)
            },
            "heatmap": [{
                "date": str(h.Date),
                "hour": h.TimePartt,
                "value": int(h.bill_count or 0)
            } for h in heatmap_raw],
            "filter_options": unique_vals
        })
    except Exception as e:
        logger.error(f"Error fetching AKT data: {str(e)}")
        return jsonify({"status": "error", "message": f"Cross-DB Connectivity Error: {str(e)}"}), 500
