"""Daily stock balances and common-date period closing balances, never flow sums."""
from datetime import date, timedelta
from decimal import Decimal
from flask import session
from sqlalchemy import func, false
from app.extensions import db
from app.models.nip_stock_trend import NIPStockTrendSnapshot as S, BOOL_FIELDS
from app.models.snapshots import BranchAuthoritySnapshot, ProvisionStockRawSnapshot

DIMENSIONS = ('location', 'division', 'group_name', 'purity', 'classification',
              'sub_classification', 'make', 'master_collection', 'collection',
              'section', 'sub_section', 'type', 'gender', 'wide_range', 'branch_type')
FILTER_FIELDS = DIMENSIONS + ('prov_type',)
INTERVALS = ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')


def scoped_query():
    query = S.query
    roles = {str(r).upper() for r in session.get('roles', [])}
    if roles.intersection({'ADMIN', 'MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'}):
        return query
    employee = str(session.get('user_id') or '')
    if 'BUSINESS_HEAD' in roles:
        branches = db.session.query(ProvisionStockRawSnapshot.branch_id).filter(
            ProvisionStockRawSnapshot.business_head_emp_code == employee)
        return query.filter(S.branch_id.in_(branches))
    if 'SHOWROOM_MANAGER' in roles:
        if not employee.isdigit():
            return query.filter(false())
        branches = db.session.query(BranchAuthoritySnapshot.branch_id).filter(
            BranchAuthoritySnapshot.emp_code == int(employee))
        return query.filter(S.branch_id.in_(branches))
    return query


def filter_query(query, args):
    for name in FILTER_FIELDS:
        values = args.getlist(name)
        if values:
            query = query.filter(getattr(S, name).in_(values))
    for name in BOOL_FIELDS[1:]:
        value = args.get(name, '')
        if value not in ('', 'true', 'false'):
            raise ValueError('Invalid boolean filter')
        if value:
            query = query.filter(getattr(S, name).is_(value == 'true'))
    start = date.fromisoformat(args['from_date']) if args.get('from_date') else None
    end = date.fromisoformat(args['to_date']) if args.get('to_date') else None
    if start and end and start > end:
        raise ValueError('From Date must not be after To Date')
    if start:
        query = query.filter(S.date >= start)
    if end:
        query = query.filter(S.date <= end)
    return query


def period_start(day, interval):
    if interval == 'weekly':
        return day - timedelta(days=day.weekday())
    if interval == 'monthly':
        return day.replace(day=1)
    if interval == 'quarterly':
        return day.replace(month=((day.month - 1) // 3) * 3 + 1, day=1)
    if interval == 'yearly':
        return day.replace(month=1, day=1)
    return day


def prepare_trend(daily, interval):
    dates = sorted({row[0] for row in daily})
    groups = sorted({row[1] for row in daily})
    lookup = {(day, group): Decimal(str(value)) if value is not None else None for day, group, value in daily}
    totals = {day: (None if any(lookup.get((day, g)) is None for g in groups if (day, g) in lookup)
                    else sum((lookup[(day, g)] for g in groups if (day, g) in lookup), Decimal(0))) for day in dates}
    closes = {}
    for day in dates:
        closes[period_start(day, interval)] = day
    periods = sorted(closes)
    series = [{'name': group, 'values': [float(lookup[(closes[p], group)])
                if lookup.get((closes[p], group)) is not None else None for p in periods]} for group in groups]
    opening = totals[dates[0]] if dates else None
    closing = totals[dates[-1]] if dates else None
    change = closing - opening if closing is not None and opening is not None else None
    valid = list(totals.values())
    average = sum(valid) / len(valid) if valid and all(v is not None for v in valid) else None
    values = {'opening': opening, 'closing': closing, 'change': change,
              'change_pct': change / opening * 100 if change is not None and opening else None,
              'average': average}
    return {'periods': [p.isoformat() for p in periods],
            'balance_dates': [closes[p].isoformat() for p in periods], 'series': series,
            'stats': {k: float(v) if v is not None else None for k, v in values.items()},
            'first_date': dates[0].isoformat() if dates else None,
            'last_date': dates[-1].isoformat() if dates else None, 'observed_days': len(dates)}


def trend_data(args):
    metric, group, interval = args.get('metric', 'gross_wt'), args.get('group_by', 'division'), args.get('interval', 'daily')
    limiter, order = args.get('limiter', 'top'), args.get('order', 'desc')
    rank_by = args.get('rank_by', 'total')
    if metric not in ('gross_wt', 'pieces') or group not in DIMENSIONS or interval not in INTERVALS:
        raise ValueError('Invalid graph configuration')
    if limiter not in ('all', 'top', 'middle', 'bottom') or order not in ('asc', 'desc') or rank_by not in ('total', 'nip', 'excess'):
        raise ValueError('Invalid data limiter or order')
    query = filter_query(scoped_query(), args)
    # Missing measures are unknown, not zero. Never silently omit a null measure.
    measure = getattr(S, metric)
    divisor = 1000 if metric == 'gross_wt' else 1
    expressions = [func.sum(measure) / divisor, func.count() - func.count(measure)]
    for flag in (S.is_nip, S.is_excess):
        expressions.extend([func.coalesce(func.sum(measure).filter(flag.is_(True)), 0) / divisor,
                            func.count().filter(flag.is_(True)) - func.count(measure).filter(flag.is_(True))])
    group_column = func.coalesce(func.nullif(func.trim(getattr(S, group)), ''), '(Unspecified)')
    rows = query.with_entities(S.date, group_column, *expressions).group_by(
        S.date, group_column).order_by(S.date, group_column).all()
    kinds = [('total', 'Total Stock'), ('nip', 'NIP Stock'), ('excess', 'Excess Stock')]
    prepared = {kind: prepare_trend([(r[0], r[1], None if r[3 + i * 2] else r[2 + i * 2])
                for r in rows], interval) for i, (kind, _) in enumerate(kinds)}
    data = dict(prepared['total'])
    totals = prepared['total']['series']
    ranking = prepared[rank_by]['series']
    ranked = sorted((i for i, series in enumerate(ranking) if series['values'] and series['values'][-1] is not None),
                    key=lambda i: -ranking[i]['values'][-1])
    if limiter == 'top':
        selected = ranked[:16]
    elif limiter == 'bottom':
        selected = ranked[-16:]
    elif limiter == 'middle':
        start = max(0, (len(ranked) - 16) // 2)
        selected = ranked[start:start + 16]
    else:
        selected = list(range(len(totals)))
    # Stable alphabetical ties and unknown closing balances last in either direction.
    selected.sort(key=lambda i: totals[i]['name'])
    known = [i for i in selected if ranking[i]['values'][-1] is not None]
    unknown = [i for i in selected if ranking[i]['values'][-1] is None]
    selected = sorted(known, key=lambda i: ranking[i]['values'][-1], reverse=order == 'desc') + unknown
    # Headline statistics use total stock only; NIP and Excess are overlapping subsets.
    data['series'] = [{**prepared[kind]['series'][i], 'group': series['name'], 'kind': kind,
                       'name': series['name'] + ' - ' + label}
                      for i in selected for series in [totals[i]] for kind, label in kinds]
    data['table_rows'] = [dict(period=period, balance_date=data['balance_dates'][p], group=series['name'],
                              **{kind: prepared[kind]['series'][i]['values'][p] for kind, _ in kinds})
                          for p, period in enumerate(data['periods'])
                          for i in selected for series in [totals[i]]]
    data.update(metric=metric, group_by=group, interval=interval,
                unit='kg' if metric == 'gross_wt' else 'Nos.',
                missing_measure_rows=sum(r[3] for r in rows), limiter=limiter, order=order, rank_by=rank_by,
                displayed_groups=len(selected), total_groups=len(totals))
    return data
