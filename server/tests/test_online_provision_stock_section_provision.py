import json
import sqlite3
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask

from app.dashboard.routes import online_provision_stock_status as report


TITLE = 'Section Details – Pro. Type'


def stock_row(label, parent, weight, section='BANGLE', title=TITLE):
    return dict(location='SUMMARY', report_section=title, report_label=label,
                classification=None, collection=None, sec_name=section, is_parent=parent,
                prov_pcs=weight, prov_gr_wt=weight, in_shop_wt=weight, ordered_wt=0,
                in_transit_wt=0, short_excess_wt=0, percent=0, section_sort=10, row_sort=1)


class SectionProvisionTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder=str(Path(report.__file__).resolve().parents[2] / 'templates'))
        self.app.secret_key = 'test'
        self.app.add_url_rule('/partial', view_func=report.get_online_provision_stock_status_partial.__wrapped__)

    def render_report(self, rows, query=''):
        database = MagicMock()
        database.session.execute.return_value = [SimpleNamespace(_mapping=row) for row in rows]
        with patch.object(report, 'db', database), patch.object(report, 'redis_client') as redis:
            redis.get.return_value = None
            client = self.app.test_client()
            with client.session_transaction() as user:
                user.update(roles=['BUSINESS_HEAD'], user_id='123')
            response = client.get('/partial?' + query)
            self.assertEqual(response.status_code, 200)
            sql, params = database.session.execute.call_args.args
            self.assertEqual(params['bh_emp_code'], '123')
            self.assertIn('online_provision_stock_status_partial_v3_section_provision', redis.setex.call_args.args[0])
            return response.get_data(as_text=True), str(sql), params

    def test_sorting_total_filters_and_existing_table(self):
        rows = [stock_row('BANGLE', 1, 30), stock_row('Regular', 0, 20),
                stock_row('Custom', 0, 10), stock_row('CHAIN', 1, 5, 'CHAIN'),
                stock_row('Unspecified', 0, 5, 'CHAIN'),
                stock_row('BANGLE', 1, 30, title='Section Details')]
        html, sql, params = self.render_report(rows, 'division=Gold&prov_type=Regular&sort_by=prov_pcs&sort_order=asc')
        self.assertEqual(params['prov_type'], 'Regular')
        self.assertEqual(params['division'], 'Gold')
        tables = [chunk.split('</table>', 1)[0] for chunk in html.split('<table')[1:]]
        new_table = next(table for table in tables if TITLE in table)
        self.assertLess(new_table.index('>CHAIN</span>'), new_table.index('>BANGLE</span>'))
        self.assertLess(new_table.index('>Custom</span>'), new_table.index('>Regular</span>'))
        self.assertIn('>35</td>', new_table)
        self.assertNotIn('>70</td>', new_table)
        self.assertNotIn('analytics', new_table)
        self.assertNotIn('data-section-detail=', new_table)
        self.assertEqual(new_table.count('child-row hidden'), 3)
        self.assertIn('onlineToggleAllSectionProvisionTypes(this)', new_table)
        old_table = next(table for table in tables if 'id="expand-shrink-all-secd"' in table)
        self.assertIn('analytics', old_table)
        self.assertIn('data-section-detail="BANGLE"', old_table)

    def test_special_and_null_section_names_have_safe_group_keys(self):
        section = 'A "quoted" / [section]'
        rows = [stock_row(section, 1, 4, section), stock_row('Regular', 0, 4, section),
                stock_row(None, 1, 2, None), stock_row('Unspecified', 0, 2, None)]
        html, _, _ = self.render_report(rows)
        groups = []

        class RowsParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'tr' and 'data-section-provision' in attrs:
                    groups.append(json.loads(attrs['data-section-provision']))

        RowsParser().feed(html)
        self.assertEqual(groups, [section, section, None, None])
        self.assertIn('Expand Provision Types for Unspecified', html)

    def test_sql_aggregates_provision_types_and_reconciles_parents(self):
        _, query, _ = self.render_report([])
        start = query.index('section_provision_details_wise AS (')
        cte = query[start:query.index('make_wise AS (', start)].rstrip().rstrip(',')
        # This isolated aggregation uses portable SQL once PostgreSQL text casts are removed.
        cte = cte.replace('::text', '')
        with sqlite3.connect(':memory:') as database:
            database.row_factory = sqlite3.Row
            database.create_function('BTRIM', 1, lambda value: value.strip() if value else value)
            database.execute('CREATE TABLE base (section TEXT, prov_type TEXT, prov_pieces NUMERIC, prov_gr_wt NUMERIC, in_shop_wt NUMERIC, order_only_wt NUMERIC, req_only NUMERIC, in_transit_wt NUMERIC)')
            database.executemany('INSERT INTO base VALUES (?, ?, ?, ?, ?, ?, ?, ?)', [
                ('BANGLE', 'Regular', 2, 20, 12, 1, 2, 3),
                ('BANGLE', 'Regular', 1, 10, 8, 2, 1, 1),
                ('BANGLE', 'Custom', 1, 5, 3, 0, 0, 1),
                ('CHAIN', None, 1, 4, 2, 0, 0, 0),
                ('CHAIN', '  ', 1, 6, 3, 0, 0, 0),
            ])
            rows = list(database.execute('WITH ' + cte + ' SELECT * FROM section_provision_details_wise'))
        for parent in [row for row in rows if row['is_parent'] == 1]:
            children = [row for row in rows if row['is_parent'] == 0 and row['sec_name'] == parent['sec_name']]
            for key in ['prov_pcs', 'prov_gr_wt', 'in_shop_wt', 'ordered_wt', 'in_transit_wt', 'short_excess_wt']:
                self.assertEqual(parent[key], sum(row[key] for row in children))
            self.assertEqual(parent['short_excess_wt'], parent['in_shop_wt'] + parent['in_transit_wt'] - parent['prov_gr_wt'])
        self.assertEqual(len([row for row in rows if row['typ_name'] == 'Unspecified']), 1)


if __name__ == '__main__':
    unittest.main()
