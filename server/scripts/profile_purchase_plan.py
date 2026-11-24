"""Read-only SQL profiling for Purchase Plan; optionally execute EXPLAIN ANALYZE.

Run from server with PYTHONPATH=. and SQLALCHEMY_DATABASE_URI configured.
No cache entries are cleared and no application data is changed.
"""
import argparse
import json
import os
import time
from datetime import date

from flask import Flask
from sqlalchemy import event

from app.extensions import db
from app.services.purchase_plan_cache import cached_purchase_plan_data, cached_purchase_plan_value
from app.services.sales_stock_composition_analysis_for_purchase_plan import (
    HIERARCHY, fetch_purchase_plan_composition_data, get_purchase_plan_options,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', type=date.fromisoformat)
    parser.add_argument('--filters', type=json.loads, default={})
    parser.add_argument('--path', type=json.loads, default=None)
    parser.add_argument('--root', choices=HIERARCHY, default='section')
    parser.add_argument('--explain', action='store_true', help='Execute captured uncached report SELECTs again with EXPLAIN ANALYZE')
    args = parser.parse_args()
    uri = os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not uri:
        parser.error('Set SQLALCHEMY_DATABASE_URI to the application snapshot database.')
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
    db.init_app(app)
    with app.app_context():
        if db.engine.dialect.name != 'postgresql' or db.engine.dialect.driver != 'psycopg2':
            parser.error('This profiler requires PostgreSQL with psycopg2.')
        event.listen(db.engine, 'connect', lambda connection, _: connection.set_session(readonly=True))
        statements = []
        event.listen(db.engine, 'before_cursor_execute',
                     lambda conn, cursor, statement, params, context, many: statements.append((statement, params)))

        def measure(name, build):
            statements.clear()
            started = time.perf_counter()
            with app.test_request_context():
                result = build()
            captured = list(statements)
            print(json.dumps({'operation': name, 'elapsed_ms': round((time.perf_counter() - started) * 1000, 2),
                              'sql_queries': len(captured)}))
            return result, captured

        def calculate(path=None, shared=False, contributors=False):
            return fetch_purchase_plan_composition_data(
                args.date, args.filters, path=path, hierarchy_root=args.root,
                cache_shared=shared, contributors=contributors)

        def cached_main():
            return cached_purchase_plan_data(args.date, args.filters, [], 'label', 'asc', args.root,
                                             lambda: calculate(shared=True))

        measure('options_uncached', get_purchase_plan_options)
        measure('options_cached_first', lambda: cached_purchase_plan_value('options', [], get_purchase_plan_options))
        measure('options_cached_repeat', lambda: cached_purchase_plan_value('options', [], get_purchase_plan_options))
        baseline, captured = measure('main_uncached', calculate)
        first, _ = measure('main_cached_first', cached_main)
        repeated, _ = measure('main_cached_repeat', cached_main)
        assert baseline == first == repeated, 'Cached main report differs from uncached result'
        path = args.path if args.path is not None else ([baseline['rows'][0]['label']] if baseline['rows'] else [])
        branch, _ = measure('branch_uncached', lambda: calculate(path))
        shared, _ = measure('branch_shared_totals', lambda: calculate(path, shared=True))
        assert branch == shared, 'Shared totals changed branch values'
        measure('contributors_uncached', lambda: calculate(path, contributors=True))
        if args.explain:
            connection = db.session.connection().connection
            with connection.cursor() as cursor:
                for index, (statement, params) in enumerate(captured, 1):
                    if statement.lstrip().upper().startswith('SELECT'):
                        cursor.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + statement, params)
                        print(json.dumps({'query': index, 'plan': cursor.fetchone()[0]}, default=str))
        db.session.rollback()


if __name__ == '__main__':
    main()
