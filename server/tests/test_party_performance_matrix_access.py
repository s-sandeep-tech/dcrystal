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
                collection_owner_emp_code=str(i),order_type=f'Type {i}',location=f'Location {i}'))
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


if __name__=='__main__':
    unittest.main()
