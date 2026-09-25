from datetime import date
from decimal import Decimal
from sqlalchemy import String, case, cast, func
from app.extensions import db
from app.models.sales_stock_composition_analysis import SalesStockCompositionAnalysisSnapshot as S

HIERARCHY = ['section', 'classification', 'make', 'wide_range', 'collection', 'master_collection', 'purity']
FILTERS = ['branch_id', 'section', 'classification', 'make', 'wide_range', 'collection', 'master_collection', 'purity']


def dimension(name):
    return func.coalesce(func.nullif(func.trim(cast(getattr(S, name), String)), ''), '(Unspecified)')


def calculate_fy_factor(cutoff_date):
    """
    Factor = Inclusive FY days ÷ Inclusive elapsed FY days
    Indian FY: April 1 to March 31
    """
    if not cutoff_date:
        return 1.0, 365, 365, "FY"

    if cutoff_date.month >= 4:
        fy_start = date(cutoff_date.year, 4, 1)
        fy_end = date(cutoff_date.year + 1, 3, 31)
    else:
        fy_start = date(cutoff_date.year - 1, 4, 1)
        fy_end = date(cutoff_date.year, 3, 31)

    inclusive_fy_days = (fy_end - fy_start).days + 1
    inclusive_elapsed_days = max(1, (cutoff_date - fy_start).days + 1)
    factor = float(inclusive_fy_days) / float(inclusive_elapsed_days)
    fy_label = f"FY {fy_start.year}-{str(fy_end.year)[-2:]}"
    return factor, inclusive_fy_days, inclusive_elapsed_days, fy_label


def ratio(numerator, denominator):
    try:
        if numerator is not None and denominator is not None and Decimal(denominator) != 0:
            return float(Decimal(numerator) / Decimal(denominator) * 100)
    except Exception:
        pass
    return None


def turn_ratio(numerator_annualised, denominator):
    try:
        if numerator_annualised is not None and denominator is not None and Decimal(denominator) != 0:
            return float(Decimal(numerator_annualised) / Decimal(denominator))
    except Exception:
        pass
    return None


def composition_analysis_data(source_date, selections, path=None):
    if path is None:
        path = []

    cutoff_query = db.session.query(func.max(S.date)).filter(S.trans_type.in_(['INVOICE', 'SR']))
    if source_date:
        cutoff_query = cutoff_query.filter(S.date <= source_date)
    source_date = cutoff_query.scalar()
    factor, inclusive_fy_days, inclusive_elapsed_days, fy_label = calculate_fy_factor(source_date)
    fy_start = date(source_date.year if source_date.month >= 4 else source_date.year - 1, 4, 1) if source_date else None

    base = db.session.query(S)
    base = base.filter(S.date == source_date) if source_date else base.filter(False)

    dims = [dimension(k).label(k) for k in HIERARCHY]

    # Filter base query by selections
    sales = db.session.query(S).filter(S.trans_type.in_(['INVOICE', 'SR']))
    sales = sales.filter(S.date.between(fy_start, source_date)) if source_date else sales.filter(False)
    for name in FILTERS:
        values = selections.get(name)
        if values:
            if name == 'branch_id':
                branch_ids = [int(v) for v in values if str(v).isdigit()]
                if branch_ids:
                    sales = sales.filter(S.branch_id.in_(branch_ids))
            else:
                sales = sales.filter(dimension(name).in_(values))

    # Deduplicated stock subquery per (branch_id, item_definition_id)
    provision = func.max(func.coalesce(S.provision_weight, 0))
    # Repeated transaction rows must agree on a positive cutoff-date rate.
    valid_rate = (
        (func.count(S.purchase_board_rate) == func.count())
        & (func.min(S.purchase_board_rate) > 0)
        & (func.min(S.purchase_board_rate) == func.max(S.purchase_board_rate))
    )
    provision_value = case(
        (provision == 0, 0),
        (valid_rate, provision * func.max(S.purchase_board_rate)),
        else_=None,
    )
    stocks_q = base.with_entities(
        S.branch_id.label('branch_id'),
        S.item_definition_id.label('item_definition_id'),
        *[func.max(d).label(k) for k, d in zip(HIERARCHY, dims)],
        provision.label('provision'),
        provision_value.label('provision_value'),
    ).group_by(S.branch_id, S.item_definition_id).subquery()

    stock_filtered = db.session.query(stocks_q)
    for name in FILTERS:
        values = selections.get(name)
        if values:
            if name == 'branch_id':
                branch_ids = [int(v) for v in values if str(v).isdigit()]
                if branch_ids:
                    stock_filtered = stock_filtered.filter(stocks_q.c.branch_id.in_(branch_ids))
            else:
                stock_filtered = stock_filtered.filter(cast(getattr(stocks_q.c, name), String).in_(values))

    # Overall report totals (denominators)
    sales_totals = sales.with_entities(
        func.sum(func.coalesce(S.gross_weight, 0)),
        func.sum(func.coalesce(S.turn_over, 0)),
        func.sum(func.coalesce(S.total_tsk_plusit_charge, 0))
    ).one()

    total_sales_weight = float(sales_totals[0] or 0)
    total_turnover = float(sales_totals[1] or 0)
    total_tsk = float(sales_totals[2] or 0)

    stock_totals = stock_filtered.with_entities(
        func.sum(stocks_q.c.provision),
        func.sum(stocks_q.c.provision_value),
        func.count() - func.count(stocks_q.c.provision_value),
    ).one()

    total_stock_weight = float(stock_totals[0] or 0)
    total_stock_value = None if stock_totals[2] else float(stock_totals[1] or 0)

    # Filter by hierarchy path drill-down
    for name, value in zip(HIERARCHY, path):
        sales = sales.filter(dimension(name) == value)
        stock_filtered = stock_filtered.filter(getattr(stocks_q.c, name) == value)

    depth = len(path)
    current_level = HIERARCHY[depth] if depth < len(HIERARCHY) else HIERARCHY[-1]

    sales_group_rows = sales.with_entities(
        dimension(current_level),
        func.sum(func.coalesce(S.gross_weight, 0)),
        func.sum(func.coalesce(S.turn_over, 0)),
        func.sum(func.coalesce(S.total_tsk_plusit_charge, 0))
    ).group_by(dimension(current_level)).all()

    stock_group_rows = stock_filtered.with_entities(
        getattr(stocks_q.c, current_level),
        func.sum(stocks_q.c.provision),
        func.sum(stocks_q.c.provision_value),
        func.count() - func.count(stocks_q.c.provision_value),
    ).group_by(getattr(stocks_q.c, current_level)).all()

    groups = {}
    for r in sales_group_rows:
        lbl = r[0] or '(Unspecified)'
        groups[lbl] = {
            'sales_weight': float(r[1] or 0),
            'turnover': float(r[2] or 0),
            'tsk': float(r[3] or 0),
            'stock_weight': 0.0,
            'stock_value': 0.0
        }

    for r in stock_group_rows:
        lbl = r[0] or '(Unspecified)'
        if lbl not in groups:
            groups[lbl] = {
                'sales_weight': 0.0,
                'turnover': 0.0,
                'tsk': 0.0,
                'stock_weight': 0.0,
                'stock_value': 0.0
            }
        groups[lbl]['stock_weight'] = float(r[1] or 0)
        groups[lbl]['stock_value'] = None if r[3] else float(r[2] or 0)

    rows = []
    for lbl, g in sorted(groups.items(), key=lambda x: str(x[0])):
        sales_comp = ratio(g['sales_weight'], total_sales_weight)
        stock_comp = ratio(g['stock_weight'], total_stock_weight)
        
        # Annualise FY-to-cutoff signed sales, not only the cutoff day's transactions.
        turn_weight = turn_ratio(g['sales_weight'] * factor, g['stock_weight']) if source_date else None
        
        # Stock Turn in Value = Section net YTD turnover × Factor ÷ Section provision value
        turn_value = turn_ratio(g['turnover'] * factor, g['stock_value']) if source_date else None
        
        # TSK % = Section net TSK-plus-IT charges ÷ Section net turnover × 100
        tsk_pct = ratio(g['tsk'], g['turnover'])

        rows.append({
            'label': lbl,
            'sales_weight': g['sales_weight'],
            'stock_weight': g['stock_weight'],
            'turnover': g['turnover'],
            'provision_value': g['stock_value'],
            'sales_composition': sales_comp,
            'stock_composition': stock_comp,
            'weight_turn': turn_weight,
            'value_turn': turn_value,
            'tsk_pct': tsk_pct
        })

    # Overall Grand Total
    gt_turn_weight = turn_ratio(total_sales_weight * factor, total_stock_weight) if source_date else None
    gt_turn_value = turn_ratio(total_turnover * factor, total_stock_value) if source_date else None
    gt_tsk_pct = ratio(total_tsk, total_turnover)

    total_row = {
        'label': 'Grand Total',
        'sales_weight': total_sales_weight,
        'stock_weight': total_stock_weight,
        'turnover': total_turnover,
        'provision_value': total_stock_value,
        'sales_composition': 100.0 if total_sales_weight > 0 else None,
        'stock_composition': 100.0 if total_stock_weight > 0 else None,
        'weight_turn': gt_turn_weight,
        'value_turn': gt_turn_value,
        'tsk_pct': gt_tsk_pct
    }

    stats = {
        'sales_weight': total_sales_weight,
        'provision_weight': total_stock_weight,
        'turn_weight': gt_turn_weight,
        'turnover': total_turnover,
        'tsk_pct': gt_tsk_pct or 0.0,
        'factor': factor,
        'fy_label': fy_label,
        'inclusive_fy_days': inclusive_fy_days,
        'inclusive_elapsed_days': inclusive_elapsed_days,
        'cutoff_date': source_date.isoformat() if source_date else None,
        'fy_start_date': fy_start.isoformat() if fy_start else None,
    }

    return {
        'rows': rows,
        'total': total_row,
        'stats': stats,
        'level': current_level,
        'can_expand': depth < (len(HIERARCHY) - 1),
        'factor': factor,
        'fy_label': fy_label
    }
