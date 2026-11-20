import unittest
from flask import Flask, session
from app.extensions import db
from app.dashboard.routes import party_performance_matrix as report


class PartyMatrixAccessTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__)
        self.app.config.update(SECRET_KEY='test',SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
        db.init_app(self.app)
        self.context=self.app.app_context();self.context.push()
        for column in report.PARTY_SOURCES:
            column.class_.__table__.create(db.engine,checkfirst=True)
        self.model=report.PartyOrderAcceptCancelDeliverySnapshot
        for i in (1,2):
            db.session.add(self.model(id=i,supplier=f'Party {i}',make_owner_emp_code=str(i),
                collection_owner_emp_code=str(i),order_type=f'Type {i}',location=f'Location {i}',
                financial_quarter=f'FY2026-27 Q{i}',order_wt=i * 100))
        db.session.commit()

    def tearDown(self):
        db.session.remove();self.context.pop()

    def test_executive_matches_manager_matrix_and_dropdown_scope(self):
        with self.app.test_request_context('/'):
            session['user_id']='1'
            for role in ['MANAGER_2','EXECUTIVE_DIRECTOR','executive_director']:
                session['roles']=[role]
                self.assertIsNone(report.current_user_owner_condition(self.model))
                self.assertEqual(report.get_party_options(),['Party 1','Party 2'])
                self.assertEqual(report.get_common_options('location'),['Location 1','Location 2'])
                rows=report.build_matrix({'party':'','search':'','order_type':'','location':''})
                self.assertEqual(sorted(row['party'] for row in rows),['Party 1','Party 2'])
            filtered=report.build_matrix({'party':'Party 2','search':'','order_type':'','location':''})
            self.assertEqual([row['party'] for row in filtered],['Party 2'])

    def test_other_owner_scope_unchanged(self):
        with self.app.test_request_context('/'):
            session['roles']=['OWNER'];session['user_id']='1'
            self.assertEqual(report.get_party_options(),['Party 1'])
            rows=report.build_matrix({'party':'','search':'','order_type':'','location':''})
            self.assertEqual([row['party'] for row in rows],['Party 1'])


    def test_quarter_filters_matrix_and_keeps_owner_scoped_options(self):
        with self.app.test_request_context('/'):
            session['roles'] = ['MANAGER_2']
            session['user_id'] = '1'
            self.assertEqual(report.get_common_options('financial_quarter'),
                             ['FY2026-27 Q1', 'FY2026-27 Q2'])
            filters = {'party': '', 'search': '', 'order_type': '', 'location': '',
                       'financial_quarter': 'FY2026-27 Q2'}
            rows = report.build_matrix(filters)
            self.assertEqual([row['party'] for row in rows], ['Party 2'])
            self.assertEqual(report.aggregate_stats(rows)['order_wt'], 200)
            filters['financial_quarter'] = 'FY2026-27 Q1,FY2026-27 Q2'
            self.assertEqual(len(report.build_matrix(filters)), 2)
            session['roles'] = ['OWNER']
            self.assertEqual(report.get_common_options('financial_quarter'), ['FY2026-27 Q1'])
            filters['financial_quarter'] = 'FY2026-27 Q2'
            self.assertEqual(report.build_matrix(filters), [])

    def test_quarter_filter_applies_to_every_snapshot_source(self):
        with self.app.test_request_context('/'):
            session['roles'] = ['ADMIN']
            for party_column in report.PARTY_SOURCES:
                model = party_column.class_
                # Insert one row per quarter, filling mandatory source dimensions.
                for row_id, quarter in [(10, ' Q1 '), (11, 'Q2'), (12, None)]:
                    values = {column.name: 'test' for column in model.__table__.columns
                              if not column.nullable and column.name not in {
                                  'id', 'snapshot_date', 'source_file', 'imported_at'}}
                    if model is report.PartyDesignAverageDeliveryDaysSnapshot:
                        values.update(design_id=1, average_delivery_days=5)
                    values.update(id=row_id, financial_quarter=quarter)
                    db.session.add(model(**values))
                db.session.flush()
                filters = {'party': '', 'search': '', 'order_type': '', 'location': '',
                           'financial_quarter': 'Q1'}
                rows = report.apply_common_filters(model.query, model, party_column, filters).all()
                self.assertEqual([row.id for row in rows], [10], model.__name__)


if __name__=='__main__':
    unittest.main()
