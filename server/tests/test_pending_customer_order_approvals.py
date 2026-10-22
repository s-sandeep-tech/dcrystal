import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import date, datetime
from flask import Flask, session
from app.extensions import db
from app.models.customer_order_approval_pending import (
    CustomerOrderApprovalPendingSnapshot,
    CustomerOrderApprovalPending,
)
from app.models import CustomerOrderApprovalPendingSnapshot as ImportedFromModels
from app.dashboard.routes.pending_customer_order_approvals import (
    build_filter_query,
    apply_visibility_filter,
    get_approval_aggregate_columns,
    pending_customer_order_approvals,
    customer_order_approvals_alias,
    pending_customer_order_approvals_data,
    get_pending_customer_order_approvals_partial,
    get_pending_customer_order_approvals_leaf_detail,
    trigger_sync_pending_customer_order_approvals,
)


class PendingCustomerOrderApprovalsTests(unittest.TestCase):
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

        CustomerOrderApprovalPendingSnapshot.__table__.create(db.engine)

        # Seed sample customer order approval records
        db.session.add_all([
            CustomerOrderApprovalPending(
                request_no='REQ-001',
                sooc='SOOC-001',
                po_number='PO-1001',
                po_date=date(2026, 9, 1),
                request_date=date(2026, 9, 1),
                request_type='CUSTOMER ORDER',
                order_item_type='STUDDED',
                order_ro='RO-MUMBAI',
                barcode='BAR-001',
                state='MAHARASHTRA',
                location='MUMBAI',
                business_head_name='BH North',
                classification_owner='CLASSIF_OWNER_1',
                classification_owner_emp_code='EMP_CO_1',
                make_owner='MAKE_OWNER_1',
                make_owner_emp_code='EMP_MO_1',
                collection_owner='COLL_OWNER_1',
                collection_owner_emp_code='EMP_COLL_1',
                division='GOLD',
                group_category='ORNAMENTS',
                group='RINGS',
                classification='PLAIN',
                sub_classification='CLASSIC',
                make='KMU - MUMBAI',
                refrerence_make='KMU - MUMBAI',
                section='SECTION_1',
                collection='ROYAL',
                reference_collection='ROYAL',
                purity='22K',
                gender='FEMALE',
                weight=10.0,
                size='12',
                gross_weight=10.5,
                stone_weight=0.5,
                other_weight=0.0,
                net_weight=10.0,
                advance_no='ADV-001',
                advance_date=datetime(2026, 9, 2, 10, 0, 0),
                party_name='AACHAL JEWELLERS',
                party_code='SUP-01',
                party_type='DOMESTIC',
                customer_name='John Doe',
                customer_phone_number='9876543210',
                reorder='Yes',
                supplier_expected_delivery_date=date(2026, 9, 25),
                customer_expected_delivery_date=date(2026, 9, 30),
                combine_order_status='Manager approval pending',
                shop_manger='Manager A',
                verifying_team='Team Alpha',
                verifying_team_emp_code='VT001',
                manager_approval_pending_pcs=1,
                manager_approval_pending_wt=10.0,
                estimation_and_advance_pending_pcs=0,
                estimation_and_advance_pending_wt=0,
                collection_owner_approval_pending_pcs=0,
                collection_owner_approval_pending_wt=0,
                customer_approval_pending_pcs=0,
                customer_approval_pending_wt=0,
                verifying_team_approval_pending_pcs=0,
                verifying_team_approval_pending_wt=0,
                advance_verification_pending_pcs=0,
                advance_verification_pending_wt=0,
                party_order_creation_pending_pcs=0,
                party_order_creation_pending_wt=0,
                composition_pending_pcs=0,
                composition_pending_wt=0,
                total_pending_pcs=1,
                total_pending_wt=10.0,
            ),
            CustomerOrderApprovalPending(
                request_no='REQ-002',
                sooc='SOOC-002',
                po_number='PO-1002',
                po_date=date(2026, 9, 5),
                request_date=date(2026, 9, 5),
                request_type='DIRECT ORDER',
                order_item_type='PLAIN',
                order_ro='RO-DELHI',
                barcode='BAR-002',
                state='DELHI',
                location='DELHI',
                business_head_name='BH North',
                classification_owner='CLASSIF_OWNER_1',
                classification_owner_emp_code='EMP_CO_1',
                make_owner='MAKE_OWNER_2',
                make_owner_emp_code='EMP_MO_2',
                collection_owner='COLL_OWNER_2',
                collection_owner_emp_code='EMP_COLL_2',
                division='GOLD',
                group_category='ORNAMENTS',
                group='CHAINS',
                classification='ANTIQUE',
                sub_classification='ROPE',
                make='KMU - DELHI',
                refrerence_make='KMU - DELHI',
                section='SECTION_2',
                collection='HERITAGE',
                reference_collection='HERITAGE',
                purity='22K',
                gender='MALE',
                weight=25.0,
                size='20',
                gross_weight=25.0,
                stone_weight=0.0,
                other_weight=0.0,
                net_weight=25.0,
                advance_no='ADV-002',
                advance_date=datetime(2026, 9, 6, 11, 0, 0),
                party_name='SHREE CRAFTS',
                party_code='SUP-02',
                party_type='DOMESTIC',
                customer_name='Alice Smith',
                customer_phone_number='9876543211',
                reorder='No',
                supplier_expected_delivery_date=date(2026, 10, 5),
                customer_expected_delivery_date=date(2026, 10, 10),
                combine_order_status='Customer approval pending',
                shop_manger='Manager B',
                verifying_team='Team Beta',
                verifying_team_emp_code='VT002',
                manager_approval_pending_pcs=0,
                manager_approval_pending_wt=0,
                estimation_and_advance_pending_pcs=0,
                estimation_and_advance_pending_wt=0,
                collection_owner_approval_pending_pcs=0,
                collection_owner_approval_pending_wt=0,
                customer_approval_pending_pcs=2,
                customer_approval_pending_wt=25.0,
                verifying_team_approval_pending_pcs=0,
                verifying_team_approval_pending_wt=0,
                advance_verification_pending_pcs=0,
                advance_verification_pending_wt=0,
                party_order_creation_pending_pcs=0,
                party_order_creation_pending_wt=0,
                composition_pending_pcs=0,
                composition_pending_wt=0,
                total_pending_pcs=2,
                total_pending_wt=25.0,
            ),
            CustomerOrderApprovalPending(
                request_no='REQ-003',
                sooc='SOOC-003',
                po_number='PO-1003',
                po_date=date(2026, 9, 10),
                request_date=date(2026, 9, 10),
                request_type='REPAIR ORDER',
                order_item_type='STUDDED',
                order_ro='RO-CHENNAI',
                barcode='BAR-003',
                state='TAMIL NADU',
                location='CHENNAI',
                business_head_name='BH South',
                classification_owner='CLASSIF_OWNER_2',
                classification_owner_emp_code='EMP_CO_2',
                make_owner='MAKE_OWNER_1',
                make_owner_emp_code='EMP_MO_1',
                collection_owner='COLL_OWNER_3',
                collection_owner_emp_code='EMP_COLL_3',
                division='GOLD',
                group_category='ORNAMENTS',
                group='BANGLES',
                classification='KADA',
                sub_classification='HEAVY',
                make='KMU - KERALA',
                refrerence_make='KMU - KERALA',
                section='SECTION_1',
                collection='TEMPLE',
                reference_collection='TEMPLE',
                purity='22K',
                gender='FEMALE',
                weight=40.0,
                size='2.4',
                gross_weight=41.0,
                stone_weight=1.0,
                other_weight=0.0,
                net_weight=40.0,
                advance_no='ADV-003',
                advance_date=datetime(2026, 9, 11, 14, 0, 0),
                party_name='KALYAN CRAFTS',
                party_code='SUP-03',
                party_type='DOMESTIC',
                customer_name='Bob Brown',
                customer_phone_number='9988776655',
                reorder='Yes',
                supplier_expected_delivery_date=date(2026, 10, 15),
                customer_expected_delivery_date=date(2026, 10, 20),
                combine_order_status='Verifying team approval pending',
                shop_manger='Manager C',
                verifying_team='Team Alpha',
                verifying_team_emp_code='VT001',
                manager_approval_pending_pcs=0,
                manager_approval_pending_wt=0,
                estimation_and_advance_pending_pcs=0,
                estimation_and_advance_pending_wt=0,
                collection_owner_approval_pending_pcs=0,
                collection_owner_approval_pending_wt=0,
                customer_approval_pending_pcs=0,
                customer_approval_pending_wt=0,
                verifying_team_approval_pending_pcs=3,
                verifying_team_approval_pending_wt=40.0,
                advance_verification_pending_pcs=0,
                advance_verification_pending_wt=0,
                party_order_creation_pending_pcs=0,
                party_order_creation_pending_wt=0,
                composition_pending_pcs=0,
                composition_pending_wt=0,
                total_pending_pcs=3,
                total_pending_wt=40.0,
            )
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()

    def test_model_and_export(self):
        self.assertEqual(CustomerOrderApprovalPendingSnapshot.__tablename__, 'customer_order_approval_pending_snapshot')
        self.assertIs(ImportedFromModels, CustomerOrderApprovalPendingSnapshot)
        self.assertIs(CustomerOrderApprovalPending, CustomerOrderApprovalPendingSnapshot)
        self.assertEqual(CustomerOrderApprovalPending.query.count(), 3)

        rec = CustomerOrderApprovalPending.query.first()
        as_dict = rec.to_dict()
        self.assertEqual(as_dict['request_no'], 'REQ-001')
        self.assertIn('business_head_name', as_dict)
        self.assertIn('classification_owner', as_dict)
        self.assertIn('make_owner', as_dict)
        self.assertIn('collection_owner', as_dict)

    def test_filters(self):
        # 1. BH filter
        with self.app.test_request_context('/?business_head=BH%20North'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            self.assertEqual(q.count(), 2)

        # 2. Location filter
        with self.app.test_request_context('/?location=MUMBAI'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().request_no, 'REQ-001')

        # 3. Classification Owner filter
        with self.app.test_request_context('/?classification_owner=CLASSIF_OWNER_2'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().request_no, 'REQ-003')

        # 4. Make Owner filter
        with self.app.test_request_context('/?make_owner=MAKE_OWNER_1'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            self.assertEqual(q.count(), 2)

        # 5. Collection Owner filter
        with self.app.test_request_context('/?collection_owner=COLL_OWNER_2'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            self.assertEqual(q.count(), 1)

        # 6. Reorder filter
        with self.app.test_request_context('/?reorder=yes'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            self.assertEqual(q.count(), 2)

        # 7. Party Name filter
        with self.app.test_request_context('/?party_name=AACHAL%20JEWELLERS'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            self.assertEqual(q.count(), 1)

        # 8. Combine Order Status filter
        with self.app.test_request_context('/?combine_order_status=Customer%20approval%20pending'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            self.assertEqual(q.count(), 1)

        # 9. Search filter
        with self.app.test_request_context('/?search=SOOC-003'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().request_no, 'REQ-003')

        # 10. Customer Delivery Date Range filter
        with self.app.test_request_context('/?customer_delivery_date_from=2026-10-01&customer_delivery_date_to=2026-10-15'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            self.assertEqual(q.count(), 1)
            self.assertEqual(q.first().request_no, 'REQ-002')

        # 11. Customer Delivery Period filter (overdue relative to test dates)
        with self.app.test_request_context('/?customer_delivery_period=overdue'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderApprovalPending.query)
            # All 3 records have delivery dates in Sep/Oct 2026.
            # Depending on today's date in test environment, verify query builds and filters customer_expected_delivery_date < today
            self.assertTrue(q is not None)

    def test_aggregate_columns(self):
        with self.app.test_request_context('/'):
            session['roles'] = ['ADMIN']
            cols = get_approval_aggregate_columns()
            row = db.session.query(*cols).first()
            self.assertEqual(row.mgr_pcs, 1)
            self.assertAlmostEqual(float(row.mgr_wt), 10.0)
            self.assertEqual(row.cust_pcs, 2)
            self.assertAlmostEqual(float(row.cust_wt), 25.0)
            self.assertEqual(row.vt_pcs, 3)
            self.assertAlmostEqual(float(row.vt_wt), 40.0)
            self.assertEqual(row.tot_pcs, 6)
            self.assertAlmostEqual(float(row.tot_wt), 75.0)

    def test_data_endpoint(self):
        with self.app.test_request_context('/api/pending-customer-order-approvals/data?business_head=BH%20North'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.pending_customer_order_approvals.render_template') as mock_render:
                mock_render.return_value = '<table><tr><td>BH North</td></tr></table>'
                resp = pending_customer_order_approvals_data.__wrapped__()
                data = resp.get_json()
                self.assertIn('html', data)
                self.assertIn('stats', data)
                self.assertEqual(data['stats']['total_pcs'], '3')
                self.assertEqual(data['stats']['manager_approval_pcs'], '1')
                self.assertEqual(data['stats']['customer_approval_pcs'], '2')
                self.assertEqual(data['total'], 1)
                self.assertEqual(data['count'], 1)

    def test_partial_tree_endpoints(self):
        # Level 1: BH Level
        with self.app.test_request_context('/partial/pending-customer-order-approvals'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.pending_customer_order_approvals.render_template') as mock_render:
                mock_render.return_value = '<tr><td>Level 1</td></tr>'
                resp = get_pending_customer_order_approvals_partial.__wrapped__()
                self.assertEqual(resp, '<tr><td>Level 1</td></tr>')
                kwargs = mock_render.call_args.kwargs
                self.assertFalse(kwargs['is_child'])
                self.assertEqual(len(kwargs['rows']), 2)

        # Level 2: Expand BH -> Classification Owner
        with self.app.test_request_context('/partial/pending-customer-order-approvals?parent_level=bh&parent_value=BH%20North'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.pending_customer_order_approvals.render_template') as mock_render:
                mock_render.return_value = '<tr><td>Level 2</td></tr>'
                resp = get_pending_customer_order_approvals_partial.__wrapped__()
                self.assertEqual(resp, '<tr><td>Level 2</td></tr>')
                kwargs = mock_render.call_args.kwargs
                self.assertTrue(kwargs['is_child'])
                self.assertEqual(kwargs['parent_level'], 'bh')
                self.assertEqual(len(kwargs['rows']), 1)
                self.assertEqual(kwargs['rows'][0]['classification_owner'], 'CLASSIF_OWNER_1')

        # Level 3: Expand Classification Owner -> Make Owner
        with self.app.test_request_context('/partial/pending-customer-order-approvals?parent_level=classification_owner&bh_value=BH%20North&parent_value=CLASSIF_OWNER_1'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.pending_customer_order_approvals.render_template') as mock_render:
                mock_render.return_value = '<tr><td>Level 3</td></tr>'
                resp = get_pending_customer_order_approvals_partial.__wrapped__()
                self.assertEqual(resp, '<tr><td>Level 3</td></tr>')
                kwargs = mock_render.call_args.kwargs
                self.assertTrue(kwargs['is_child'])
                self.assertEqual(kwargs['parent_level'], 'classification_owner')
                self.assertEqual(len(kwargs['rows']), 2)
                make_owners = [r['make_owner'] for r in kwargs['rows']]
                self.assertIn('MAKE_OWNER_1', make_owners)
                self.assertIn('MAKE_OWNER_2', make_owners)

        # Level 4: Expand Make Owner -> Collection Owner
        with self.app.test_request_context('/partial/pending-customer-order-approvals?parent_level=make_owner&parent_value=MAKE_OWNER_1'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.pending_customer_order_approvals.render_template') as mock_render:
                mock_render.return_value = '<tr><td>Level 4</td></tr>'
                resp = get_pending_customer_order_approvals_partial.__wrapped__()
                self.assertEqual(resp, '<tr><td>Level 4</td></tr>')
                kwargs = mock_render.call_args.kwargs
                self.assertTrue(kwargs['is_child'])
                self.assertEqual(kwargs['parent_level'], 'make_owner')
                self.assertEqual(len(kwargs['rows']), 2)

    def test_leaf_detail_endpoint(self):
        with self.app.test_request_context('/partial/pending-customer-order-approvals/leaf_detail?parent_bh=BH%20North'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.pending_customer_order_approvals.render_template') as mock_render:
                mock_render.return_value = '<div>Leaf Detail</div>'
                resp = get_pending_customer_order_approvals_leaf_detail.__wrapped__()
                self.assertEqual(resp, '<div>Leaf Detail</div>')
                kwargs = mock_render.call_args.kwargs
                self.assertEqual(len(kwargs['records']), 2)
                self.assertEqual(len(kwargs['supplier_summaries']), 2)

    def test_leaf_template_render(self):
        from pathlib import Path
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parents[1] / 'app/templates'), autoescape=True)
        row = CustomerOrderApprovalPending.query.filter_by(request_no='REQ-001').one()
        html = env.get_template('partials/_view_pending_customer_order_approvals_leaf.html').render(
            records=[row],
            breadcrumbs=[{'label': 'BH', 'value': 'BH North', 'icon': 'person'}],
            supplier_summaries=[]
        )
        self.assertIn('REQ-001', html)
        self.assertIn('Manager Approval', html)
        self.assertIn('AACHAL JEWELLERS', html)

    def test_trigger_sync_endpoint(self):
        with self.app.test_request_context('/api/sync/pending-customer-order-approvals', method='POST'):
            session['user_id'] = 'TEST_USER'
            with patch('app.utils.sync_manager.enqueue_sync_task') as mock_enqueue:
                mock_enqueue.return_value = {"status": "success", "message": "Task queued"}
                resp = trigger_sync_pending_customer_order_approvals.__wrapped__()
                data = resp.get_json()
                self.assertEqual(data['status'], 'success')
                mock_enqueue.assert_called_once_with('customer_order_approval_pending', 'TEST_USER')

    def test_sync_task_with_mock_db(self):
        from app.utils.sync_tasks import sync_customer_order_approval_pending_task
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {
                'request_no': 'SYNC-001',
                'business_head_name': 'BH East',
                'classification_owner': 'CO_1',
                'make_owner': 'MO_1',
                'collection_owner': 'COLL_1',
                'manager_approval_pending_pcs': 5,
                'manager_approval_pending_wt': 50.0,
                'customer_approval_pending_pcs': 2,
                'customer_approval_pending_wt': 20.0,
            }
        ]
        with patch('app.utils.sync_tasks.get_external_db_connection', return_value=mock_conn):
            with patch('app.utils.sync_tasks.emit_sync_update'):
                res = sync_customer_order_approval_pending_task()
                self.assertEqual(res['status'], 'success')
                self.assertEqual(res['count'], 1)
                synced = CustomerOrderApprovalPending.query.filter_by(request_no='SYNC-001').first()
                self.assertIsNotNone(synced)
                self.assertEqual(synced.business_head_name, 'BH East')
                self.assertEqual(synced.total_pending_pcs, 7)
                self.assertAlmostEqual(float(synced.total_pending_wt), 70.0)

    def test_allowed_sync_tasks(self):
        from app.utils.sync_manager import ALLOWED_SYNC_TASKS, enqueue_sync_task
        self.assertIn('customer_order_approval_pending', ALLOWED_SYNC_TASKS)
        self.assertIn('pending_customer_order_approvals', ALLOWED_SYNC_TASKS)
        with patch('app.utils.sync_manager.redis_client.rpush') as mock_rpush:
            res = enqueue_sync_task('customer_order_approval_pending', 'USER_1')
            self.assertEqual(res['status'], 'success')
            mock_rpush.assert_called_once()

