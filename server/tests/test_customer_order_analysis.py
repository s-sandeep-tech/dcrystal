import os
import unittest
from unittest.mock import patch
from datetime import date, datetime, timedelta
from flask import Flask, session
from app.extensions import db
from app.models.customer_order_analysis import CustomerOrderAnalysisSnapshot, CustomerOrderAnalysis
from app.models import CustomerOrderAnalysisSnapshot as ImportedFromModels
from app.models.snapshots import BranchAuthoritySnapshot
from app.dashboard.routes.customer_order_analysis import (
    build_filter_query,
    apply_visibility_filter,
    mask_supplier_data,
    get_stage_aggregate_columns,
    get_customer_order_analysis_leaf_detail,
)


class CustomerOrderAnalysisTests(unittest.TestCase):
    def test_new_status_filters_and_pending_metrics(self):
        row = CustomerOrderAnalysis.query.filter_by(request_no='REQ-001').one()
        row.customer_order_status = 'Awaiting approval'
        row.customer_order_receipt_status = 'Not received'
        row.customer_order_approval_pending_pcs = 2
        row.customer_order_approval_pending_wt = 12.345
        row.customer_delivery_pending_pcs = 3
        row.customer_delivery_pending_wt = 23.456
        db.session.commit()
        with self.app.test_request_context('/?customer_order_status=Awaiting%20approval&customer_order_receipt_status=Not%20received'):
            session['roles'] = ['ADMIN']
            query = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(query.count(), 1)
            metrics = build_filter_query(db.session.query(*get_stage_aggregate_columns())).one()
            self.assertEqual(metrics.approval_pcs, 2)
            self.assertAlmostEqual(float(metrics.approval_wt), 12.345)
            self.assertEqual(metrics.delivery_pcs, 3)
            self.assertAlmostEqual(float(metrics.delivery_wt), 23.456)

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
                total_pending_wt=12.500,
                snapshot_date=date(2026, 9, 29)
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
                advance_no=None,
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
                total_pending_wt=25.000,
                snapshot_date=date(2026, 9, 29)
            ),
            CustomerOrderAnalysis(
                request_no='REQ-003',
                sooc='SOOC-3',
                state='TAMIL NADU',
                location='CHENNAI',
                request_date=date(2026, 9, 20),
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
                total_pending_wt=40.000,
                snapshot_date=date(2026, 9, 29)
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

    def test_removed_msme_filter_is_ignored(self):
        with self.app.test_request_context('/?is_msme=true'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 3)

        with self.app.test_request_context('/?is_msme=false'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            self.assertEqual(q.count(), 3)

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

    def test_privileged_role_bypasses_match_reference(self):
        for role in ['ADMIN', 'MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR']:
            with self.app.test_request_context('/'):
                session['roles'] = [role, 'BUSINESS_HEAD', 'SHOWROOM_MANAGER']
                session['user_id'] = 'unmapped'
                self.assertEqual(apply_visibility_filter(CustomerOrderAnalysis.query).count(), 3)
                self.assertTrue(mask_supplier_data())

    def test_missing_identity_and_branch_mapping_deny_access(self):
        for role, identity in [('BUSINESS_HEAD', None), ('SHOWROOM_MANAGER', 'invalid'),
                               ('SHOWROOM_MANAGER', '12345'), ('READER', None)]:
            with self.app.test_request_context('/'):
                session['roles'] = [role]
                session['user_id'] = identity
                self.assertEqual(apply_visibility_filter(CustomerOrderAnalysis.query).count(), 0)

    def test_owner_names_limit_data_and_options(self):
        with self.app.test_request_context('/'):
            session['roles'] = ['READER']
            session['user_id'] = '123'
            with patch('app.dashboard.routes.customer_order_analysis.get_owner_names_by_emp_code',
                       return_value=(('OWNER_A',), ())):
                for scope in (apply_visibility_filter, build_filter_query):
                    rows = scope(CustomerOrderAnalysis.query).all()
                    self.assertEqual(len(rows), 2)
                    self.assertTrue(all(r.make_owner == 'OWNER_A' for r in rows))
            with patch('app.dashboard.routes.customer_order_analysis.get_owner_names_by_emp_code', return_value=((), ())):
                self.assertEqual(apply_visibility_filter(CustomerOrderAnalysis.query).count(), 0)

    def test_masked_supplier_cannot_be_searched_or_filtered(self):
        for role in ['BUSINESS_HEAD', 'SHOWROOM_MANAGER']:
            with self.app.test_request_context('/?supplier=NONEXISTENT'):
                session['roles'] = ['ADMIN', role]
                self.assertEqual(build_filter_query(CustomerOrderAnalysis.query).count(), 3)
            with self.app.test_request_context('/?search=AACHAL'):
                session['roles'] = ['ADMIN', role]
                self.assertEqual(build_filter_query(CustomerOrderAnalysis.query).count(), 0)

    def test_leaf_detail_modal_rendering(self):
        with self.app.test_request_context('/?parent_location=MUMBAI&parent_make=MAKE_A'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = 'RENDERED_OK'
                resp = get_customer_order_analysis_leaf_detail.__wrapped__()
                self.assertEqual(resp, 'RENDERED_OK')
                self.assertEqual(mock_render.call_args.args[0], 'partials/_view_customer_order_analysis_leaf_cards.html')
                kwargs = mock_render.call_args.kwargs
                self.assertEqual(kwargs['parent_location'], 'MUMBAI')
                self.assertEqual(kwargs['parent_make'], 'MAKE_A')
                self.assertEqual(len(kwargs['supplier_summaries']), 1)
                self.assertEqual(kwargs['supplier_summaries'][0]['supplier'], 'AACHAL JEWELLERS')

    def test_supplier_identity_masked_in_modal(self):
        from pathlib import Path
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parents[1] / 'app/templates'), autoescape=True)
        for role in ['BUSINESS_HEAD', 'SHOWROOM_MANAGER']:
            with self.app.test_request_context('/?parent_location=MUMBAI&parent_make=MAKE_A'):
                session['roles'] = ['ADMIN', role]
                with patch('app.dashboard.routes.customer_order_analysis.render_template') as render:
                    get_customer_order_analysis_leaf_detail.__wrapped__()
                    context = render.call_args.kwargs
                self.assertTrue(context['mask_suppliers'])
                self.assertEqual(context['supplier_summaries'][0]['supplier'], 'XXX')
                self.assertEqual(context['supplier_summaries'][0]['party_code'], 'XXX')
                html = env.get_template('partials/_view_customer_order_analysis_leaf_cards.html').render(**context)
                self.assertIn('XXX', html)
                self.assertNotIn('AACHAL JEWELLERS', html)
                for record in context['records']:
                    if record.party_code:
                        self.assertNotIn(record.party_code, html)
                self.assertIn('data-co-panel="cards"', html)
                self.assertIn('data-co-panel="grid"', html)
                self.assertIn('Stage-wise Pending Quantities', html)
                self.assertIn('Grand Total', html)

    def test_leaf_cards_keep_pending_metrics_and_escape_values(self):
        from pathlib import Path
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parents[1] / 'app/templates'), autoescape=True)
        row = CustomerOrderAnalysis.query.filter_by(request_no='REQ-001').one()
        row.customer_order_approval_pending_pcs = 2
        row.customer_order_approval_pending_wt = 12.345
        row.customer_name = '<script>bad()</script>'
        html = env.get_template('partials/_view_customer_order_analysis_leaf_cards.html').render(
            records=[row], breadcrumbs=[], mask_suppliers=False)
        self.assertIn('12.345', html)
        self.assertIn('Approval Pending', html)
        self.assertNotIn('<script>bad()</script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('QC Passed', html)

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
                # MUMBAI has 12.500 accept_wt, while CHENNAI and DELHI have 0.000
                self.assertEqual(rows[0]['primary_value'], 'MUMBAI')

        with self.app.test_request_context('/api/customer-order-analysis/data?sort_by=accept_wt&sort_order=asc'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = '<table></table>'
                resp = customer_order_analysis_data.__wrapped__()
                self.assertEqual(resp.status_code, 200)
                kwargs = mock_render.call_args.kwargs
                rows = kwargs['rows']
                # Ascending order: MUMBAI with highest accept_wt comes last
                self.assertEqual(rows[-1]['primary_value'], 'MUMBAI')

    def test_filter_advance_linked(self):
        from app.dashboard.routes.customer_order_analysis import customer_order_analysis_data
        # With advance: REQ-001 (MUMBAI) and REQ-003 (CHENNAI)
        with self.app.test_request_context('/api/customer-order-analysis/data?advance_linked=with'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = '<table></table>'
                resp = customer_order_analysis_data.__wrapped__()
                self.assertEqual(resp.status_code, 200)
                kwargs = mock_render.call_args.kwargs
                locs = {r['primary_value'] for r in kwargs['rows']}
                self.assertIn('MUMBAI', locs)
                self.assertIn('CHENNAI', locs)
                self.assertNotIn('DELHI', locs)

        # Without advance: REQ-002 (DELHI)
        with self.app.test_request_context('/api/customer-order-analysis/data?advance_linked=without'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = '<table></table>'
                resp = customer_order_analysis_data.__wrapped__()
                self.assertEqual(resp.status_code, 200)
                kwargs = mock_render.call_args.kwargs
                locs = {r['primary_value'] for r in kwargs['rows']}
                self.assertIn('DELHI', locs)
                self.assertNotIn('MUMBAI', locs)
                self.assertNotIn('CHENNAI', locs)

    def test_filter_order_age(self):
        from sqlalchemy.dialects import postgresql
        with self.app.test_request_context('/api/customer-order-analysis/data?order_age=0-15'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            sql = str(q.statement.compile(dialect=postgresql.dialect()))
            self.assertIn('request_date', sql)
            self.assertIn('snapshot_date', sql)

        with self.app.test_request_context('/api/customer-order-analysis/data?order_age=120+'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(CustomerOrderAnalysis.query)
            sql = str(q.statement.compile(dialect=postgresql.dialect()))
            self.assertIn('request_date', sql)
            self.assertIn('snapshot_date', sql)

    def test_filter_delivery_period(self):
        from app.dashboard.routes.customer_order_analysis import customer_order_analysis_data
        today = date.today()
        # Set REQ-001 expected_delivery_date to today
        r1 = CustomerOrderAnalysis.query.filter_by(request_no='REQ-001').first()
        r1.expected_delivery_date = datetime.combine(today, datetime.min.time())

        # Set REQ-002 expected_delivery_date to past (overdue)
        r2 = CustomerOrderAnalysis.query.filter_by(request_no='REQ-002').first()
        r2.expected_delivery_date = datetime.combine(today - timedelta(days=20), datetime.min.time())

        # Set REQ-003 expected_delivery_date to next month
        if today.month == 12:
            nm = date(today.year + 1, 1, 15)
        else:
            nm = date(today.year, today.month + 1, 15)
        r3 = CustomerOrderAnalysis.query.filter_by(request_no='REQ-003').first()
        r3.expected_delivery_date = datetime.combine(nm, datetime.min.time())
        db.session.commit()

        # Test due today
        with self.app.test_request_context('/api/customer-order-analysis/data?delivery_period=today'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = '<table></table>'
                resp = customer_order_analysis_data.__wrapped__()
                self.assertEqual(resp.status_code, 200)
                kwargs = mock_render.call_args.kwargs
                locs = {r['primary_value'] for r in kwargs['rows']}
                self.assertEqual(locs, {'MUMBAI'})

        # Test overdue
        with self.app.test_request_context('/api/customer-order-analysis/data?delivery_period=overdue'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = '<table></table>'
                resp = customer_order_analysis_data.__wrapped__()
                self.assertEqual(resp.status_code, 200)
                kwargs = mock_render.call_args.kwargs
                locs = {r['primary_value'] for r in kwargs['rows']}
                self.assertEqual(locs, {'DELHI'})

        # Test next month
        with self.app.test_request_context('/api/customer-order-analysis/data?delivery_period=next_month'):
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.customer_order_analysis.render_template') as mock_render:
                mock_render.return_value = '<table></table>'
                resp = customer_order_analysis_data.__wrapped__()
                self.assertEqual(resp.status_code, 200)
                kwargs = mock_render.call_args.kwargs
                locs = {r['primary_value'] for r in kwargs['rows']}
                self.assertEqual(locs, {'CHENNAI'})


if __name__ == '__main__':
    unittest.main()
