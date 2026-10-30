"""Service for Sales & Stock Composition Analysis for Purchase Plan.

Reuses only the existing data model (SalesStockCompositionAnalysisSnapshot).
All calculations, hierarchy logic, and sorting are implemented independently.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import String, case, cast, func, or_

from app.extensions import db
from app.models.sales_stock_composition_analysis import SalesStockCompositionAnalysisSnapshot as Snapshot

HIERARCHY: List[str] = [
    'section',
    'classification',
    'make',
    'wide_range',
    'collection',
    'master_collection',
    'purity',
]

FILTERS: List[str] = [
    'branch_id',
    'division',
    'section',
    'classification',
    'make',
    'wide_range',
    'collection',
    'master_collection',
    'purity',
]

SORT_KEYS: Tuple[str, ...] = ('label', 'sales_composition', 'stock_composition', 'weight_turn')


def dimension_expr(name: str):
    """Return SQL expression for a hierarchy dimension column."""
    if name == 'design_no':
        name = 'barcode'
    col = getattr(Snapshot, name)
    return func.coalesce(func.nullif(func.trim(cast(col, String)), ''), '(Unspecified)')


def calculate_fy_factor(cutoff_date: Optional[date]) -> Tuple[float, int, int, str]:
    """Calculate annualisation factor based on Indian financial year (April 1 - March 31).

    Factor = Total inclusive FY days / Elapsed inclusive FY days
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


def compute_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Calculate percentage ratio safely."""
    try:
        if numerator is not None and denominator is not None and Decimal(str(denominator)) != 0:
            return float(Decimal(str(numerator)) / Decimal(str(denominator)) * 100)
    except Exception:
        pass
    return None


def compute_turn_ratio(annualised_sales: Optional[float], provision: Optional[float]) -> Optional[float]:
    """Calculate stock turn ratio safely."""
    try:
        if annualised_sales is not None and provision is not None and Decimal(str(provision)) != 0:
            return float(Decimal(str(annualised_sales)) / Decimal(str(provision)))
    except Exception:
        pass
    return None


def sort_purchase_plan_rows(rows: List[Dict[str, Any]], sort_by: str = 'label', sort_order: str = 'asc') -> List[Dict[str, Any]]:
    """Sort rows by chosen column, keeping None values at the bottom."""
    key = sort_by if sort_by in SORT_KEYS else 'label'
    is_desc = (sort_order == 'desc')

    alphabetical = sorted(
        rows,
        key=lambda r: (str(r.get('label') or '').casefold(), str(r.get('label') or ''))
    )

    if key == 'label':
        return list(reversed(alphabetical)) if is_desc else alphabetical

    with_val = [r for r in alphabetical if r.get(key) is not None]
    without_val = [r for r in alphabetical if r.get(key) is None]

    return sorted(with_val, key=lambda r: r[key], reverse=is_desc) + without_val


def get_purchase_plan_options() -> Dict[str, Any]:
    """Fetch filter dropdown options directly from snapshot table."""
    locations = [
        {'value': str(r[0]), 'label': r[1] or str(r[0])}
        for r in db.session.query(Snapshot.branch_id, func.max(Snapshot.location_name))
        .filter(Snapshot.branch_id.isnot(None))
        .group_by(Snapshot.branch_id)
        .order_by(func.max(Snapshot.location_name))
    ]

    divisions = [
        r[0] for r in db.session.query(dimension_expr('division'))
        .distinct().order_by(dimension_expr('division')) if r[0] and r[0] != '(Unspecified)'
    ]

    sections = [
        r[0] for r in db.session.query(dimension_expr('section'))
        .distinct().order_by(dimension_expr('section')) if r[0] and r[0] != '(Unspecified)'
    ]

    classifications = [
        r[0] for r in db.session.query(dimension_expr('classification'))
        .distinct().order_by(dimension_expr('classification')) if r[0] and r[0] != '(Unspecified)'
    ]

    makes = [
        r[0] for r in db.session.query(dimension_expr('make'))
        .distinct().order_by(dimension_expr('make')) if r[0] and r[0] != '(Unspecified)'
    ]

    purities = [
        r[0] for r in db.session.query(dimension_expr('purity'))
        .distinct().order_by(dimension_expr('purity')) if r[0] and r[0] != '(Unspecified)'
    ]

    dates = [
        r[0].isoformat() for r in db.session.query(Snapshot.date)
        .filter(Snapshot.date.isnot(None)).distinct().order_by(Snapshot.date.desc())
    ]

    return {
        'dates': dates,
        'locations': locations,
        'divisions': divisions,
        'sections': sections,
        'classifications': classifications,
        'makes': makes,
        'purities': purities,
    }


def fetch_purchase_plan_composition_data(
    source_date: Optional[date],
    selections: Dict[str, List[str]],
    path: Optional[List[str]] = None,
    contributors: bool = False,
    sort_by: str = 'label',
    sort_order: str = 'asc'
) -> Dict[str, Any]:
    """Calculate Sales & Stock Composition Analysis specifically for Purchase Plan.

    Includes only:
    - Product Hierarchy
    - Sales Composition %
    - Stock Composition %
    - Stock Turn in Weight %
    """
    if path is None:
        path = []

    selected_date = source_date
    effective_date = selected_date or db.session.query(func.max(Snapshot.date)).scalar()
    factor, inclusive_fy_days, inclusive_elapsed_days, fy_label = calculate_fy_factor(effective_date)

    # Base sales query
    sales_q = db.session.query(Snapshot)
    if selected_date:
        sales_q = sales_q.filter(Snapshot.date <= selected_date)

    for name in FILTERS:
        vals = selections.get(name)
        if vals:
            if name == 'branch_id':
                b_ids = [int(v) for v in vals if str(v).isdigit()]
                if b_ids:
                    sales_q = sales_q.filter(Snapshot.branch_id.in_(b_ids))
            elif name == 'division':
                upper_vals = [v.upper() for v in vals]
                sales_q = sales_q.filter(func.upper(dimension_expr('division')).in_(upper_vals))
            else:
                sales_q = sales_q.filter(dimension_expr(name).in_(vals))

    # Top contributors for modal pie chart
    if contributors:
        for name, value in zip(HIERARCHY, path):
            sales_q = sales_q.filter(dimension_expr(name) == value)

        depth = len(path)
        level_name = HIERARCHY[depth] if depth < len(HIERARCHY) else 'design_no'
        level_expr = dimension_expr(level_name)
        weight_sum = func.sum(func.coalesce(Snapshot.gross_weight, 0))

        grouped = sales_q.with_entities(level_expr.label('lbl'), weight_sum.label('wt')).group_by(level_expr).subquery()
        pos_total, neg_total = db.session.query(
            func.sum(case((grouped.c.wt > 0, grouped.c.wt), else_=0)),
            func.sum(case((grouped.c.wt < 0, grouped.c.wt), else_=0))
        ).one()

        top_rows = db.session.query(grouped).filter(grouped.c.wt > 0).order_by(
            grouped.c.wt.desc(), grouped.c.lbl
        ).limit(10).all()

        items = [{'label': r.lbl, 'weight': float(r.wt)} for r in top_rows]
        others = float(pos_total or 0) - sum(i['weight'] for i in items)
        if others > 0.000001:
            items.append({'label': 'Others', 'weight': others})

        # Query stock contributors
        stock_c_q = db.session.query(Snapshot)
        if selected_date:
            stock_c_q = stock_c_q.filter(or_(Snapshot.date <= selected_date, Snapshot.date.is_(None)))
        for name in FILTERS:
            vals = selections.get(name)
            if vals:
                if name == 'branch_id':
                    b_ids = [int(v) for v in vals if str(v).isdigit()]
                    if b_ids:
                        stock_c_q = stock_c_q.filter(Snapshot.branch_id.in_(b_ids))
                elif name == 'division':
                    upper_vals = [v.upper() for v in vals]
                    stock_c_q = stock_c_q.filter(func.upper(dimension_expr('division')).in_(upper_vals))
                else:
                    stock_c_q = stock_c_q.filter(dimension_expr(name).in_(vals))

        for name, value in zip(HIERARCHY, path):
            stock_c_q = stock_c_q.filter(dimension_expr(name) == value)

        stock_weight_sum = func.sum(func.coalesce(Snapshot.provision_weight, 0))
        stock_grouped = stock_c_q.with_entities(level_expr.label('lbl'), stock_weight_sum.label('wt')).group_by(level_expr).subquery()
        stock_pos_total, stock_neg_total = db.session.query(
            func.sum(case((stock_grouped.c.wt > 0, stock_grouped.c.wt), else_=0)),
            func.sum(case((stock_grouped.c.wt < 0, stock_grouped.c.wt), else_=0))
        ).one()

        stock_top_rows = db.session.query(stock_grouped).filter(stock_grouped.c.wt > 0).order_by(
            stock_grouped.c.wt.desc(), stock_grouped.c.lbl
        ).limit(10).all()

        stock_items = [{'label': r.lbl, 'weight': float(r.wt)} for r in stock_top_rows]
        stock_others = float(stock_pos_total or 0) - sum(i['weight'] for i in stock_items)
        if stock_others > 0.000001:
            stock_items.append({'label': 'Others', 'weight': stock_others})

        return {
            'level': level_name,
            'cutoff': effective_date.isoformat() if effective_date else None,
            'items': items,
            'negative_weight': float(neg_total or 0),
            'net_weight': float(pos_total or 0) + float(neg_total or 0),
            'sales': {
                'items': items,
                'negative_weight': float(neg_total or 0),
                'net_weight': float(pos_total or 0) + float(neg_total or 0),
                'total_positive_weight': float(pos_total or 0),
            },
            'stock': {
                'items': stock_items,
                'negative_weight': float(stock_neg_total or 0),
                'net_weight': float(stock_pos_total or 0) + float(stock_neg_total or 0),
                'total_positive_weight': float(stock_pos_total or 0),
            }
        }

    # Resolve location dates and factors
    location_key_expr = case(
        (Snapshot.branch_id.isnot(None), 'branch:' + cast(Snapshot.branch_id, String)),
        else_='location:' + dimension_expr('location_name')
    )

    location_dates_q = db.session.query(
        location_key_expr,
        func.max(Snapshot.date),
        func.min(Snapshot.min_trans_date)
    ).group_by(location_key_expr)

    if selected_date:
        location_dates_q = location_dates_q.filter(Snapshot.date <= selected_date)

    branch_ids = [int(v) for v in selections.get('branch_id', []) if str(v).isdigit()]
    if branch_ids:
        location_dates_q = location_dates_q.filter(Snapshot.branch_id.in_(branch_ids))

    location_factors: List[Dict[str, Any]] = []
    factors_by_loc: Dict[str, float] = {}
    late_locations = set()

    for loc_key, loc_date, first_sales_date in location_dates_q.all():
        if loc_date is None:
            continue
        loc_fac, l_days, l_elapsed, l_label = calculate_fy_factor(loc_date)
        loc_fy_start = date(loc_date.year if loc_date.month >= 4 else loc_date.year - 1, 4, 1)
        if first_sales_date and first_sales_date > loc_fy_start:
            late_locations.add(loc_key)

        factors_by_loc[loc_key] = loc_fac
        location_factors.append({
            'location_key': loc_key,
            'date': loc_date.isoformat(),
            'first_sales_date': first_sales_date.isoformat() if first_sales_date else None,
            'turn_na_b': loc_key in late_locations,
            'factor': loc_fac,
            'fy_label': l_label,
            'inclusive_fy_days': l_days,
            'inclusive_elapsed_days': l_elapsed
        })

    def aggregate_sales_weights(query, group_dim=None):
        keys = [location_key_expr] if group_dim is None else [group_dim, location_key_expr]
        results = query.with_entities(
            *keys,
            func.sum(func.coalesce(Snapshot.gross_weight, 0))
        ).group_by(*keys).all()

        aggregates: Dict[Any, List[float]] = {}
        for res in results:
            grp_lbl = None if group_dim is None else res[0]
            loc_k, wt = res[-2:]
            # [sales_weight, annualised_sales_weight, missing_factor_count, late_location_count]
            t = aggregates.setdefault(grp_lbl, [0.0, 0.0, 0.0, 0.0])
            if loc_k in late_locations:
                t[3] += 1
            f = factors_by_loc.get(loc_k)
            t[0] += float(wt or 0)
            if f is None:
                t[2] += 1
            else:
                t[1] += float(wt or 0) * f
        return aggregates

    # Stock query
    filter_dims = {
        k: dimension_expr(k).label(k)
        for k in (HIERARCHY + [f for f in FILTERS if f not in HIERARCHY and f != 'branch_id'])
    }
    dims = list(filter_dims.values())
    prov_expr = func.coalesce(Snapshot.provision_weight, 0)
    stock_subq = db.session.query(
        Snapshot.branch_id.label('branch_id'),
        Snapshot.date.label('date'),
        *dims,
        prov_expr.label('provision')
    ).subquery()

    stock_q = db.session.query(stock_subq)
    if selected_date:
        stock_q = stock_q.filter(or_(stock_subq.c.date <= selected_date, stock_subq.c.date.is_(None)))

    for name in FILTERS:
        vals = selections.get(name)
        if vals:
            if name == 'branch_id':
                b_ids = [int(v) for v in vals if str(v).isdigit()]
                if b_ids:
                    stock_q = stock_q.filter(stock_subq.c.branch_id.in_(b_ids))
            elif name == 'division':
                upper_vals = [v.upper() for v in vals]
                stock_q = stock_q.filter(func.upper(cast(getattr(stock_subq.c, 'division'), String)).in_(upper_vals))
            else:
                stock_q = stock_q.filter(cast(getattr(stock_subq.c, name), String).in_(vals))

    # Overall totals
    total_sales_agg = aggregate_sales_weights(sales_q).get(None, [0.0, 0.0, 0.0, 0.0])
    grand_sales_weight = float(total_sales_agg[0] or 0)
    grand_na_b = bool(total_sales_agg[3])
    grand_annual_sales_wt = None if (total_sales_agg[2] or grand_na_b) else float(total_sales_agg[1] or 0)

    grand_stock_weight = float(stock_q.with_entities(func.sum(stock_subq.c.provision)).scalar() or 0)

    grand_turn_weight = compute_turn_ratio(grand_annual_sales_wt, grand_stock_weight)

    # Drilldown filtering
    for name, value in zip(HIERARCHY, path):
        sales_q = sales_q.filter(dimension_expr(name) == value)
        stock_q = stock_q.filter(getattr(stock_subq.c, name) == value)

    depth = len(path)
    cur_level = HIERARCHY[depth] if depth < len(HIERARCHY) else HIERARCHY[-1]
    can_expand = depth < (len(HIERARCHY) - 1)

    sales_group_map = aggregate_sales_weights(sales_q, dimension_expr(cur_level))

    stock_group_rows = stock_q.with_entities(
        getattr(stock_subq.c, cur_level),
        func.sum(stock_subq.c.provision)
    ).group_by(getattr(stock_subq.c, cur_level)).all()

    combined_groups: Dict[str, Dict[str, Any]] = {}

    for lbl, totals in sales_group_map.items():
        clean_lbl = lbl or '(Unspecified)'
        is_na_b = bool(totals[3])
        ann_wt = None if (totals[2] or is_na_b) else totals[1]
        combined_groups[clean_lbl] = {
            'sales_weight': totals[0],
            'annualised_sales_weight': ann_wt,
            'provision_weight': 0.0,
            'turn_na_b': is_na_b
        }

    for row in stock_group_rows:
        lbl = row[0] or '(Unspecified)'
        pw = float(row[1] or 0)
        if lbl not in combined_groups:
            combined_groups[lbl] = {
                'sales_weight': 0.0,
                'annualised_sales_weight': 0.0,
                'provision_weight': pw,
                'turn_na_b': False
            }
        else:
            combined_groups[lbl]['provision_weight'] = pw

    rows: List[Dict[str, Any]] = []
    for lbl, data in combined_groups.items():
        sw = data['sales_weight']
        pw = data['provision_weight']
        ann_wt = data['annualised_sales_weight']
        is_na_b = data['turn_na_b']

        s_comp = compute_ratio(sw, grand_sales_weight)
        st_comp = compute_ratio(pw, grand_stock_weight)
        w_turn = None if is_na_b else compute_turn_ratio(ann_wt, pw)

        rows.append({
            'label': lbl,
            'sales_weight': sw,
            'provision_weight': pw,
            'sales_composition': s_comp,
            'stock_composition': st_comp,
            'weight_turn': w_turn,
            'turn_na_b': is_na_b
        })

    sorted_rows = sort_purchase_plan_rows(rows, sort_by=sort_by, sort_order=sort_order)

    unique_dates = {i['date'] for i in location_factors}
    effective_factor = location_factors[0]['factor'] if len(unique_dates) == 1 else None

    return {
        'rows': sorted_rows,
        'total': {
            'sales_weight': grand_sales_weight,
            'provision_weight': grand_stock_weight,
            'sales_composition': 100.0 if grand_sales_weight > 0 else 0.0,
            'stock_composition': 100.0 if grand_stock_weight > 0 else 0.0,
            'weight_turn': grand_turn_weight,
            'turn_na_b': grand_na_b
        },
        'stats': {
            'sales_weight': grand_sales_weight,
            'provision_weight': grand_stock_weight,
            'turn_weight': grand_turn_weight,
            'turn_na_b': grand_na_b,
            'factor': effective_factor,
            'cutoff_date': effective_date.isoformat() if effective_date else None,
            'fy_label': fy_label,
            'inclusive_fy_days': inclusive_fy_days,
            'inclusive_elapsed_days': inclusive_elapsed_days,
            'location_factors': location_factors,
            'missing_factor': any(f is None for f in factors_by_loc.values())
        },
        'level': cur_level,
        'can_expand': can_expand,
        'factor': effective_factor or 1.0,
        'fy_label': fy_label,
    }

