"""Design drilldown aggregation, popup scope and non-destructive schema upgrade."""
import inspect
import re
import unittest
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from flask import Flask, session
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import text
from app.extensions import db
from app.dashboard.routes import online_provision_stock_status as report
from app.models.online_provision_stock import OnlineProvisionStockRawSnapshot as S
from app.utils import online_provision_stock_sync as sync


class IdAggregate:
    def __init__(self): self.values = []
    def step(self, value): self.values.append(str(value))
    def finalize(self): return ','.join(self.values)


class DesignHierarchyTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY='test', SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
        db.init_app(self.app)
        self.ctx = self.app.app_context(); self.ctx.push()
        sync.ensure_online_tables()
        raw = db.session.connection().connection.driver_connection
        raw.create_aggregate('array_agg', 1, IdAggregate)
        raw.create_function('array_to_string', 2, lambda values, separator: values)
        raw.create_function('string_to_array', 2, lambda values, separator: values)
        raw.create_function('ANY', 1, lambda values: values)
        for i, design in enumerate(['A-100', 'A-100', 'B "quoted" [x]', None], 1):
            db.session.add(S(id=i, section='BANGLE', purity=750, type='4 SET', wide_range='LIGHT',
                range_weight=8, design_no=design, section_id=1, purity_id=2, type_id=3, wide_range_id=4,
                prov_pieces=i, prov_gr_wt=i*10, in_shop_wt=i*3, in_shop_pcs=i,
                in_transit=0, in_transit_wt=i, order_only_wt=i*2, req_only=i,
                snapshot_date=datetime(2026,11,25)))
        db.session.commit()

    def tearDown(self):
        db.session.remove(); self.ctx.pop()

    def hierarchy(self):
        execute = db.session.execute
        def portable(statement, params):
            sql = re.sub(r'::(?:numeric|text|bigint|integer)(?:\[\])?', '', str(statement))
            return execute(text(sql), params)
        with self.app.test_request_context('/?drill_section=BANGLE'), patch.object(
                report.db.session, 'execute', side_effect=portable), patch.object(
                report, 'render_template', side_effect=lambda template, **context: context):
            session['roles'] = ['ADMIN']
            return inspect.unwrap(report.get_online_provision_stock_status_drilldown)()

    def test_design_totals_reconcile_with_every_unchanged_parent(self):
        result = self.hierarchy()
        self.assertIsInstance(result, dict)
        self.assertEqual([r['level_id'] for r in result['rows'][:5]], [1,2,3,4,5])
        leaf = [row for row in result['rows'] if row['level_id'] == 6]
        self.assertEqual({r['design_no'] for r in leaf}, {'A-100', 'B "quoted" [x]', None})
        for metric in ['prov_pcs', 'prov_gr_wt', 'in_shop_wt', 'ordered_wt',
                       'in_transit_wt', 'short_excess_pcs', 'short_excess_wt']:
            total = sum(row[metric] for row in leaf)
            for parent in result['rows'][:5]: self.assertAlmostEqual(total, parent[metric])
            self.assertAlmostEqual(total, result['modal_totals'][metric])
        self.assertEqual(result['modal_totals']['prov_gr_wt'], 100)
        self.assertEqual(result['modal_totals']['ordered_wt'], 30)
        self.assertEqual(result['modal_totals']['short_excess_wt'], -60)
        self.assertEqual(result['modal_totals']['percent'], -60)

    def test_weight_parent_expands_to_design_and_design_links_keep_scope(self):
        result = self.hierarchy()
        env = Environment(loader=FileSystemLoader(Path(report.__file__).resolve().parents[2] / 'templates'), autoescape=True)
        html = env.get_template('partials/_view_online_provision_stock_drilldown.html').render(**result)
        self.assertIn('Range&nbsp;Weight > Design No', html)
        class Parser(HTMLParser):
            def __init__(self): super().__init__(); self.rows=[]; self.links=[]
            def handle_starttag(self, tag, attrs):
                a=dict(attrs)
                if tag=='tr' and 'data-tree-row' in a: self.rows.append(a)
                if tag=='a' and a.get('data-level')=='6': self.links.append(a)
        parsed=Parser(); parsed.feed(html)
        weight=next(row for row in parsed.rows if row['data-level']=='5')
        designs=[row for row in parsed.rows if row['data-level']=='6']
        self.assertEqual(len(designs),3)
        self.assertTrue(all(row['data-parent-id']==weight['data-node-id'] for row in designs))
        self.assertEqual(len({row['data-node-id'] for row in designs}),3)
        self.assertTrue(any(link['data-design-no']=='B "quoted" [x]' for link in parsed.links))
        self.assertTrue(any(link['data-design-is-null']=='true' for link in parsed.links))

    def test_provision_popup_filters_exact_design_including_null(self):
        base='drill_level=6&drill_section_ids=1&drill_purity_ids=2&drill_type_ids=3&drill_wide_range_ids=4&drill_range_weight=8'
        for query, expected in [('drill_design_no=A-100',30), ('drill_design_is_null=true',40)]:
            execute=db.session.execute
            def portable(statement, params):
                sql=re.sub(r'::(?:numeric|text|bigint|integer)(?:\[\])?', '', str(statement))
                return execute(text(sql),params)
            with self.app.test_request_context('/?'+base+'&'+query), patch.object(
                    report.db.session,'execute',side_effect=portable), patch.object(
                    report,'render_template',side_effect=lambda template,**context:context):
                session['roles']=['ADMIN']
                result=inspect.unwrap(report.get_online_provision_stock_provision_details)()
            self.assertIsInstance(result,dict)
            self.assertAlmostEqual(float(result['total_gross_wt']),expected)

    def test_design_persists_from_source(self):
        row={name:None for name in sync.source_columns()}
        row['design_no']='B "quoted" [x]'
        self.assertEqual(sync.map_source_row(row,datetime(2026,11,25))['design_no'],row['design_no'])

    def test_schema_upgrade_preserves_existing_rows(self):
        # Simulate an existing deployment with both tables missing the new column.
        db.session.execute(text('ALTER TABLE online_provision_stock_raw_snapshot DROP COLUMN design_no'))
        db.session.execute(text('ALTER TABLE online_provision_stock_raw_staging DROP COLUMN design_no'))
        db.session.commit()
        sync.ensure_online_tables()
        sync.ensure_online_tables()
        self.assertEqual(S.query.count(),4)
        self.assertEqual(sum(row.prov_gr_wt for row in S.query),100)
        self.assertTrue(all(row.design_no is None for row in S.query))
