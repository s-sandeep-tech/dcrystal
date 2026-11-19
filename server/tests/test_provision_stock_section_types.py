import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask

from app.dashboard.routes import provision_stock_status as report


def section_row(label, parent, weight, section='BANGLE'):
    return dict(location='SUMMARY', report_section='Section Wise', report_label=label,
                classification=None, sub_classification=None, collection=None, sub_section=None,
                sec_name=section, typ_name=None, is_parent=parent, prov_pcs=weight,
                prov_gr_wt=weight, in_shop_wt=weight, ordered_wt=0, in_transit_wt=0,
                short_excess_wt=0, percent=0, section_sort=7, row_sort=1)


class SectionProvisionTypesTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder=str(Path(report.__file__).resolve().parents[2] / 'templates'))
        self.app.secret_key = 'test-secret'
        self.app.add_url_rule('/partial', view_func=report.get_provision_stock_status_partial.__wrapped__)

    def test_filtered_grouping_sorting_and_parent_only_grand_total(self):
        rows = [section_row('BANGLE', 1, 30), section_row('Regular', 0, 20),
                section_row('Custom', 0, 10), section_row('CHAIN', 1, 5, 'CHAIN'),
                section_row('Unspecified', 0, 5, 'CHAIN')]
        database = MagicMock()
        database.session.execute.return_value = [SimpleNamespace(_mapping=row) for row in rows]
        with patch.object(report, 'db', database), patch.object(report, 'redis_client') as redis:
            redis.get.return_value = None
            client = self.app.test_client()
            with client.session_transaction() as user:
                user.update(roles=['BUSINESS_HEAD'], user_id='123')
            response = client.get('/partial?division=Gold&prov_type=Regular&sort_by=prov_pcs&sort_order=asc')
            html = response.get_data(as_text=True)
            statement, params = database.session.execute.call_args.args
            self.assertIn('GROUP BY GROUPING SETS ((section), (section,', str(statement))
            self.assertEqual(params['bh_emp_code'], '123')
            self.assertEqual(params['prov_type'], 'Regular')
            self.assertEqual(params['division'], 'Gold')
            self.assertLess(html.index('>CHAIN</span>'), html.index('>BANGLE</span>'))
            self.assertLess(html.index('>Custom</span>'), html.index('>Regular</span>'))
            self.assertIn('toggleSectionProvisionTypes(this)', html)
            self.assertEqual(html.count('aria-expanded="false"'), 2)
            self.assertEqual(html.count('title="Click to see drill-down"'), 2)
            self.assertIn('>35</td>', html)
            self.assertNotIn('>70</td>', html)
            self.assertIn('prov_stock_status_partial_v4_section_provision', redis.setex.call_args.args[0])
            groups = []

            class SectionParser(HTMLParser):
                def handle_starttag(self, tag, attrs):
                    attributes = dict(attrs)
                    if tag == 'tr' and 'data-section-provision' in attributes:
                        groups.append(attributes['data-section-provision'])

            parser = SectionParser()
            parser.feed(html)
            self.assertEqual(groups, ['"CHAIN"', '"CHAIN"', '"BANGLE"', '"BANGLE"', '"BANGLE"'])

    def test_null_section_has_expandable_group(self):
        rows = [section_row(None, 1, 4, None), section_row('Unspecified', 0, 4, None)]
        database = MagicMock()
        database.session.execute.return_value = [SimpleNamespace(_mapping=row) for row in rows]
        with patch.object(report, 'db', database), patch.object(report, 'redis_client') as redis:
            redis.get.return_value = None
            html = self.app.test_client().get('/partial').get_data(as_text=True)
        self.assertIn('data-section-provision="null"', html)
        self.assertIn('Expand Provision Types for Unspecified', html)
        self.assertIn('child-row hidden', html)
