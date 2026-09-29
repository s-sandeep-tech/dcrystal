import os
import unittest
from unittest.mock import patch
from datetime import date, datetime
from flask import Flask, session
from app.extensions import db
from app.models.customer_order_analysis import CustomerOrderAnalysisSnapshot, CustomerOrderAnalysis
from app.models import CustomerOrderAnalysisSnapshot as ImportedFromModels
from app.models.snapshots import BranchAuthoritySnapshot
from app.dashboard.routes.customer_order_analysis import (
    build_filter_query,
    apply_visibility_filter,
    mask_supplier_data,
    get_customer_order_analysis_leaf_detail,
)


class CustomerOrderAnalysisTests(unittest.TestCase):
    def setUp(self):
        os.environ['TESTING'] = 'true'
        self.app = Flask(__name__, template_folder='../app/templates')
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SECRET_KEY='test-secret-key-at-least-32-chars-long'
        )
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()

        CustomerOrderAnalysis.__table__.create(db.engine)
        BranchAuthoritySnapshot.__table__.create(db.engine)

        # Seed sample customer orders
        db.session.add_all([
            CustomerOrderAnalysis(
                request_no='REQ-001',
                sooc='SOOC-1',
                state='MAHARASHTRA',
                location='MUMBAI',
                request_date=date(2026, 9, 1),
                expected_delivery_date=datetime(2026, 9, 30, 18, 0, 0),
                division='GOLD',
                group_category='ORNAMENTS',
                group='RINGS',
                classification='PLAIN',
                sub_classification='CLASSIC',
                make='MAKE_A',
                section='SECTION_1',
                collection='ROYAL',
                purity='22K',
                gender='FEMALE',
                weight=12.500,
                gross_weight=13.000,
                net_weight=12.500,
                advance_no='ADV-101',
                party_name='AACHAL JEWELLERS',
                party_code='SUP-01',
                party_type='DOMESTIC',
                customer_name='John Doe',
                customer_phone_number='9876543210',
                order_status='PENDING',
                customer_order_type='CUSTOM',
                branch_type='MAIN',
                is_msme=True,
                re_order=False,
                order_ro='RO-MUMBAI',
                business_head_name='BH North',
                bh_emp_code='BH001',
                branch_id=10,
                make_owner='OWNER_A',
                collection_wner='OWNER_B',
                pending_to_accepted_pcs=1,
                pending_to_accepted_wt=12.500,
                process_pending_pcs=0,
                process_pending_wt=0,
                barcode_pending_pcs=0,
                barcode_pending_wt=0,
                hallmark_pending_pcs=0,
                hallmark_pending_wt=0,
                qc_issue_pending_pcs=0,
                qc_issue_pending_wt=0,
                qc_complete_pending_pcs=0,
                qc_complete_pending_wt=0,
                invoice_pending_pcs=0,
                invoice_pending_wt=0,
                receipt_pending_pcs=0,
                receipt_pending_wt=0,
                total_pending_pcs=1,
                total_pending_wt=12.500
            ),
            CustomerOrderAnalysis(
                request_no='REQ-002',
                sooc='SOOC-2',
                state='DELHI',
                location='DELHI',
                request_date=date(2026, 9, 10),
                expected_delivery_date=datetime(2026, 10, 15, 18, 0, 0),
                division='DIAMOND',
                group_category='STUDDED',
                group='NECKLACE',
                classification='STUDDED',
                sub_classification='MODERN',
                make='MAKE_B',
                section='SECTION_2',
                collection='HERITAGE',
                purity='18K',
                gender='UNISEX',
                weight=25.000,
                gross_weight=26.500,
                net_weight=25.000,
                advance_no='ADV-102',
                party_name='SHREE JEWELS',
                party_code='SUP-02',
                party_type='EXPORT',
                customer_name='Alice Smith',
                customer_phone_number='9123456780',
                order_status='IN_PROCESS',
                customer_order_type='STOCK',
                branch_type='SUB',
                is_msme=False,
                re_order=True,
                order_ro='RO-DELHI',
                business_head_name='BH South',
                bh_emp_code='BH002',
                branch_id=20,
                make_owner='OWNER_C',
                collection_wner='OWNER_D',
                pending_to_accepted_pcs=0,
                pending_to_accepted_wt=0,
                process_pending_pcs=2,
                process_pending_wt=25.000,
                barcode_pending_pcs=0,
                barcode_pending_wt=0,
                hallmark_pending_pcs=0,
                hallmark_pending_wt=0,
                qc_issue_pending_pcs=0,
                qc_issue_pending_wt=0,
                qc_complete_pending_pcs=0,
                qc_complete_pending_wt=0,
                invoice_pending_pcs=0,
                invoice_pending_wt=0,
                receipt_pending_pcs=0,
                receipt_pending_wt=0,
                total_pending_pcs=2,
                total_pending_wt=25.000
            ),
            CustomerOrderAnalysis(
                request_no='REQ-003',
                sooc='SOOC-3',
                state='TAMIL NADU',
                location='CHENNAI',
                request_date=date(2026, 9, 15),
                expected_delivery_date=datetime(2026, 10, 5, 12, 0, 0),
                division='GOLD',
                group_category='ORNAMENTS',
                group='BANGLES',
                classification='ANTIQUE',
                sub_classification='TRADITIONAL',
                make='KMU - KERALA',
                section='SECTION_1',
                collection='VINTAGE',
                purity='22K',
                gender='FEMALE',
                weight=40.000,
                gross_weight=40.500,
                net_weight=40.000,
                advance_no='ADV-103',
                party_name='KALYAN CRAFTS',
                party_code='SUP-03',
                party_type='DOMESTIC',
                customer_name='Bob Brown',
                customer_phone_number='9988776655',
                order_status='PENDING',
                customer_order_type='REPAIR',
                branch_type='MAIN',
                is_msme=True,
                re_order=False,
                order_ro='RO-CHENNAI',
                business_head_name='BH South',
                bh_emp_code='BH002',
                branch_id=30,
                make_owner='OWNER_A',
                collection_wner='OWNER_D',
                pending_to_accepted_pcs=0,
                pending_to_accepted_wt=0,
                process_pending_pcs=0,
                process_pending_wt=0,
                barcode_pending_pcs=0,
                barcode_pending_wt=0,
                hallmark_pending_pcs=3,
                hallmark_pending_wt=40.000,
                qc_issue_pending_pcs=0,
                qc_issue_pending_wt=0,
                qc_complete_pending_pcs=0,
                qc_complete_pending_wt=0,
                invoice_pending_pcs=0,
                invoice_pending_wt=0,
                receipt_pending_pcs=0,
                receipt_pending_wt=0,
                total_pending_pcs=3,
                total_pending_wt=40.000
            )
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()

    def test_snapshot_table_name_and_export(self):
        self.assertEqual(CustomerOrderAnalysisSnapshot.__tablename__, 'customer_order_analysis_snapshot')
        self.assertIs(ImportedFromModels, CustomerOrderAnalysisSnapshot)
        self.assertIs(CustomerOrderAnalysis, CustomerOrderAnalysisSnapshot)
        self.assertEqual(CustomerOrderAnalysisSnapshot.query.count(), 3)

    def test_admin_sees_all(self):
        with self.app.test_request_context('/'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 3)

    def test_filter_by_location(self):
        with self.app.test_request_context('/?location=MUMBAI'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            results = q.all()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].location, 'MUMBAI')

    def test_filter_by_multi_location(self):
        with self.app.test_request_context('/?location=MUMBAI,DELHI'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 2)

    def test_filter_by_is_msme(self):
        with self.app.test_request_context('/?is_msme=true'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 2)

        with self.app.test_request_context('/?is_msme=false'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().request_no, 'REQ-002')

    def test_filter_by_re_order(self):
        with self.app.test_request_context('/?re_order=true'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().request_no, 'REQ-002')

    def test_filter_by_date_range(self):
        with self.app.test_request_context('/?request_date_from=2026-09-05&request_date_to=2026-09-12'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().request_no, 'REQ-002')

    def test_filter_by_search(self):
        with self.app.test_request_context('/?search=Alice'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().customer_name, 'Alice Smith')

    def test_business_head_visibility(self):
        with self.app.test_request_context('/'):
            session['roles'] = ['BUSINESS_HEAD']
            session['user_id'] = 'BH001'
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().request_no, 'REQ-001')

    def test_showroom_manager_branch_visibility(self):
        db.session.add(BranchAuthoritySnapshot(branch_id=20, emp_code=999))
        db.session.commit()

        with self.app.test_request_context('/'):
            session['roles'] = ['SHOWROOM_MANAGER']
            session['user_id'] = '999'
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().request_no, 'REQ-002')

    def test_manager_kmu_visibility(self):
        with self.app.test_request_context('/'):
            session['roles'] = ['MANAGER_KMU']
            session['user_id'] = 'KMU01'
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().make, 'KMU - KERALA')

    def test_supplier_masking(self):
        with self.app.test_request_context('/'):
            session['roles'] = ['SHOWROOM_MANAGER']
            self.assertTrue(mask_supplier_data())

        with self.app.test_request_context('/'):
            session['roles'] = ['ADMIN']
            self.assertFalse(mask_supplier_data())

    def test_leaf_detail_modal_rendering(self):
        with self.app.test_request_context('/?parent_location=MUMBAI&parent_make=MAKE_A'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = 'RENDERED_OK'
                resp = get_customer_order_analysis_leaf_detail.__wrapped__()
                self.assertEqual(resp, 'RENDERED_OK')
                kwargs = mock_render.call_args.kwargs
                self.assertEqual(kwargs['parent_location'], 'MUMBAI')
                self.assertEqual(kwargs['parent_make'], 'MAKE_A')
                self.assertEqual(len(kwargs['supplier_summaries']), 1)
                self.assertEqual(kwargs['supplier_summaries'][0]['supplier'], 'AACHAL JEWELLERS')

    def test_customer_order_analysis_data_endpoint(self):
        from app.dashboard.routes.customer_order_analysis import customer_order_analysis_data
        with self.app.test_request_context('/api/customer-order-analysis/data?location=MUMBAI'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = '<table><tr><td>MUMBAI</td></tr></table>'
                resp = customer_order_analysis_data.__wrapped__()
                data = resp.get_json()
                self.assertIn('html', data)
                self.assertIn('stats', data)
                self.assertEqual(data['stats']['accept_pcs'], '1')
                self.assertEqual(data['count'], 1)
                self.assertEqual(data['total'], 1)

    def test_customer_order_analysis_partial_endpoint(self):
        from app.dashboard.routes.customer_order_analysis import get_customer_order_analysis_partial
        with self.app.test_request_context('/partial/customer-order-analysis?parent_level=location&parent_value=MUMBAI'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = '<tr><td>MAKE_A</td></tr>'
                resp = get_customer_order_analysis_partial.__wrapped__()
                self.assertEqual(resp, '<tr><td>MAKE_A</td></tr>')
                kwargs = mock_render.call_args.kwargs
                self.assertTrue(kwargs['is_child'])
                self.assertEqual(len(kwargs['rows']), 1)
                self.assertEqual(kwargs['rows'][0]['make'], 'MAKE_A')

    def test_trigger_sync_customer_order_analysis(self):
        from app.dashboard.routes.customer_order_analysis import trigger_sync_customer_order_analysis
        with self.app.test_request_context('/api/sync/customer-order-analysis', method='POST'):
            session['user_id'] = 'TEST_USER'
            with patch('app.utils.sync_manager.enqueue_sync_task') as mock_enqueue:
                mock_enqueue.return_value = {'status': 'success', 'message': 'Sync task queued.'}
                resp = trigger_sync_customer_order_analysis.__wrapped__()
                data = resp.get_json()
                self.assertEqual(data['status'], 'success')
                mock_enqueue.assert_called_once_with('customer_order_analysis', 'TEST_USER')

    def test_sorting_customer_order_analysis_data(self):
        from app.dashboard.routes.customer_order_analysis import customer_order_analysis_data
        with self.app.test_request_context('/api/customer-order-analysis/data?sort_by=accept_wt&sort_order=desc'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = '<table></table>'
                resp = customer_order_analysis_data.__wrapped__()
                self.assertEqual(resp.status_code, 200)
                kwargs = mock_render.call_args.kwargs
                self.assertEqual(kwargs['sort_by'], 'accept_wt')
                self.assertEqual(kwargs['sort_order'], 'desc')
                rows = kwargs['rows']
                # BANGALORE (20.0), MUMBAI (12.5), DELHI (8.0)
                self.assertEqual([r['primary_value'] for r in rows], ['BANGALORE', 'MUMBAI', 'DELHI'])

        with self.app.test_request_context('/api/customer-order-analysis/data?sort_by=accept_wt&sort_order=asc'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = '<table></table>'
                resp = customer_order_analysis_data.__wrapped__()
                self.assertEqual(resp.status_code, 200)
                kwargs = mock_render.call_args.kwargs
                rows = kwargs['rows']
                # DELHI (8.0), MUMBAI (12.5), BANGALORE (20.0)
                self.assertEqual([r['primary_value'] for r in rows], ['DELHI', 'MUMBAI', 'BANGALORE'])


if __name__ == '__main__':
    unittest.main()

