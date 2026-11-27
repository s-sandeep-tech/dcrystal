from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.dashboard.routes import location_physical_stock_status as report


class PhysicalStockDesignImageTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_preview_authorizes_physical_report_access_and_matches_uid(self):
        menu = SimpleNamespace(url='/location-physical-stock-status', permission_required=None)
        actor = SimpleNamespace(is_active=True, username='viewer', is_admin=False,
                                roles=[SimpleNamespace(name='STOCK_VIEWER', permissions=[], menus=[menu])])
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            'uid-A', 'DESIGN-A', '/images/A.jpg')
        with self.app.test_request_context('/api/location-physical-stock-status/design-image?design_uid=uid-A'), patch(
            'app.utils.decorators.verify_jwt_in_request'
        ), patch('app.utils.decorators.get_jwt_identity', return_value='1'), patch(
            'app.extensions.db.session.get', return_value=actor
        ), patch.object(report, 'get_external_db_connection', return_value=connection):
            response = report.get_location_physical_stock_design_image()
        self.assertEqual(response.json['image_url'], 'https://crystal.kalyanjewellers.company/images/A.jpg')
        cursor = connection.cursor.return_value.__enter__.return_value
        self.assertIn('WHERE design_uid = %s', cursor.execute.call_args.args[0])
        self.assertEqual(cursor.execute.call_args.args[1], ('uid-A',))
        connection.close.assert_called_once()

    def test_preview_requires_physical_report_permission(self):
        actor = SimpleNamespace(is_active=True, username='viewer', is_admin=False,
                                roles=[SimpleNamespace(name='READER', permissions=[], menus=[])])
        with self.app.test_request_context('/api/location-physical-stock-status/design-image?design_uid=A'), patch(
            'app.utils.decorators.verify_jwt_in_request'
        ), patch('app.utils.decorators.get_jwt_identity', return_value='1'), patch(
            'app.extensions.db.session.get', return_value=actor
        ), patch.object(report, 'get_external_db_connection') as connect:
            _, status = report.get_location_physical_stock_design_image()
        self.assertEqual(status, 403)
        connect.assert_not_called()

    def test_barcode_design_cell_has_hover_icon_with_escaped_uid(self):
        root = Path(report.__file__).resolve().parents[2] / 'templates'
        env = Environment(loader=FileSystemLoader(root), autoescape=select_autoescape())
        template = env.get_template('partials/_view_location_physical_stock_in_shop_details.html')
        row = dict(design_no='A"<B', design_uid='uid"A', weight=8, pieces=1, gross_wt=8.613)
        def render():
            return template.render(rows=[row], total_records=1, total_pieces=1, total_gross_wt=8.613,
                                   page=1, total_pages=1)
        html = render()
        self.assertIn('data-design-preview="A&#34;&lt;B"', html)
        self.assertIn('data-design-uid="uid&#34;A"', html)
        row['design_uid'] = None
        self.assertNotIn('data-design-preview=', render())


if __name__ == '__main__':
    unittest.main()
