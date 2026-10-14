import unittest
from unittest.mock import patch

from flask import Flask, session
from app.dashboard.routes.location_physical_stock_status import get_location_physical_stock_in_shop_details


class InShopBarcodeFilterTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test'

    def capture_query(self, args, roles=None):
        with self.app.test_request_context('/?' + args):
            session['roles'] = roles or ['ADMIN']
            session['user_id'] = '1235'
            with patch('app.dashboard.routes.location_physical_stock_status.db') as database, patch(
                'app.dashboard.routes.location_physical_stock_status.render_template', return_value='OK'
            ):
                database.session.execute.return_value = []
                response = get_location_physical_stock_in_shop_details.__wrapped__()
                self.assertEqual(response, 'OK')
                sql, params = database.session.execute.call_args.args
                return str(sql), params

    def test_shared_filters_apply_to_both_source_tables(self):
        sql, params = self.capture_query(
            'drill_section_ids=1&location=BANGALORE&classification=BRAND&make=MUDHRA'
            '&collection=EMPIRE&section=NECKLACE&prov_type=Individual&branch_type=SHOP&purity=920'
            '&state=KARNATAKA&business_head=HEAD&provision_mode=Fixed&branch_status=ACTIVE'
        )
        for field in ['location', 'classification', 'make', 'collection', 'section', 'prov_type', 'branch_type', 'purity']:
            self.assertIn('p.' + field, sql)
            self.assertIn('b.' + field, sql)
            self.assertIsNotNone(params[field])
        for field in ['state', 'business_head', 'provision_mode', 'branch_status']:
            self.assertIsNotNone(params[field])
        self.assertIn('p.provision_mode_filter', sql)
        self.assertIn('p.business_head_name', sql)
        self.assertIn('p.branch_id = b.branch_id', sql)

    def test_franchise_scope_also_applies_to_barcode_rows(self):
        sql, params = self.capture_query('drill_section_ids=1&branch_type=OTHER', ['FRANCHISE_INDIA_HEAD'])
        self.assertEqual(params['branch_type'], 'FRANCHISE_SHOP')
        self.assertIn('b.branch_type', sql)

    def test_pagination_keeps_filter_parameters(self):
        _, params = self.capture_query('drill_section_ids=1&prov_type=Individual&page=2')
        self.assertEqual(params['prov_type'], 'Individual')
        self.assertEqual(params['offset'], 100)


if __name__ == '__main__':
    unittest.main()
