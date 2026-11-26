import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.dashboard.routes import online_provision_stock_status as report


class OnlineStockDesignImageTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def lookup(self, row, design='FONOR0296'):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = row
        with self.app.test_request_context('/?design_no=' + design), patch.object(
            report, 'get_external_db_connection', return_value=connection
        ):
            response = report.get_online_provision_stock_design_image.__wrapped__()
        return response, connection, cursor

    def test_direct_readonly_external_lookup_uses_bound_design_number(self):
        response, connection, cursor = self.lookup((123, 'FONOR0296', 'https://images.example/design.jpg'))
        self.assertEqual(response.json, dict(design_no='FONOR0296', image_url='https://images.example/design.jpg'))
        sql, params = cursor.execute.call_args.args
        self.assertIn('FROM ext_view.vw_design_attachment WHERE design_no = %s', sql)
        self.assertEqual(params, ('FONOR0296',))
        self.assertNotIn('FONOR0296', sql)
        connection.set_session.assert_called_once_with(readonly=True)
        connection.close.assert_called_once()
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_no_attachment_empty_and_unsafe_urls_return_no_image(self):
        for row in (None, (1, 'A', None), (1, 'A', ' '), (1, 'A', 'javascript:alert(1)'),
                    (1, 'A', 'file:///tmp/image.png')):
            with self.subTest(row=row):
                response, connection, _ = self.lookup(row)
                self.assertIsNone(response.json['image_url'])
                connection.close.assert_called_once()

    def test_relative_attachment_paths_use_crystal_domain(self):
        for path in ('attachments/design.jpg', '/attachments/design.jpg'):
            with self.subTest(path=path):
                response, _, _ = self.lookup((1, 'A', path))
                self.assertEqual(response.json['image_url'],
                                 'https://crystal.kalyanjewellers.company/attachments/design.jpg')

    def test_blank_design_rejected_without_external_connection(self):
        with self.app.test_request_context('/?design_no=%20'), patch.object(report, 'get_external_db_connection') as connect:
            response, status = report.get_online_provision_stock_design_image.__wrapped__()
        self.assertEqual(status, 400)
        connect.assert_not_called()

    def test_source_error_closes_connection_and_hides_database_details(self):
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.execute.side_effect = RuntimeError('private database details')
        with self.app.test_request_context('/?design_no=A'), patch.object(
            report, 'get_external_db_connection', return_value=connection
        ), self.assertLogs(report.logger, level='ERROR'):
            response, status = report.get_online_provision_stock_design_image.__wrapped__()
        self.assertEqual(status, 503)
        self.assertNotIn('private', response.get_data(as_text=True))
        connection.close.assert_called_once()

    def test_api_requires_report_authentication(self):
        with self.app.test_request_context('/api/online-provision-stock-status/design-image?design_no=A'), patch.object(
            report, 'get_external_db_connection'
        ) as connect:
            _, status = report.get_online_provision_stock_design_image()
        self.assertEqual(status, 401)
        connect.assert_not_called()

    def test_only_real_design_leaf_labels_become_escaped_links(self):
        templates = Path(report.__file__).resolve().parents[2] / 'templates'
        env = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
        template = env.get_template('partials/_view_online_provision_stock_drilldown.html')
        module = template.make_module(dict(include_design_hierarchy=True, include_purity_hierarchy=True))
        row = dict(level_id=6, section='BANGLE', purity=750, type='4 SET', wide_range='LIGHT',
                   range_weight=8, design_no='A"<B', prov_pcs=1, prov_gr_wt=8, in_shop_wt=0,
                   ordered_wt=8, in_transit_wt=0, short_excess_pcs=-1, short_excess_wt=-8, percent=-100)
        html = str(module.render_drilldown_row(row, {}))
        self.assertIn('data-design-image="A&#34;&lt;B"', html)
        for design in (None, '', ' '):
            row['design_no'] = design
            self.assertNotIn('data-design-image=', str(module.render_drilldown_row(row, {})))


if __name__ == '__main__':
    unittest.main()
