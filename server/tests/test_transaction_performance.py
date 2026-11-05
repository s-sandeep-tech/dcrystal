import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, date, time
from flask import Flask
from sqlalchemy import func
from flask_jwt_extended import JWTManager, create_access_token

from app.extensions import db
from app.models.auth import User
from app.models.core import Notification
from app.models.rbac import Role, Permission, UserRole, RolePermission, Menu, RoleMenu
from app.models.akt_report import AKTTransactionPerformance
from app.dashboard import dashboard_bp
from app.dashboard.routes.transaction_performance import trigger_akt_sync, get_akt_transaction_data, sales_growth_comparison, SALES_COMPARISON_DATE


class TransactionPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY='test-only-secret-key-32-chars-long!',
            JWT_SECRET_KEY='test-only-jwt-secret-key-32-chars-long!',
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_BINDS={'akt_db': 'sqlite:///:memory:'},
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            JWT_TOKEN_LOCATION=['headers', 'cookies'],
        )
        db.init_app(self.app)
        JWTManager(self.app)
        self.app.register_blueprint(dashboard_bp)
        self.ctx = self.app.app_context()
        self.ctx.push()

        db.metadata.create_all(db.engine, tables=[m.__table__ for m in [User, Role, Permission, UserRole, RolePermission, Menu, RoleMenu, Notification]])
        akt_engine = db.engines['akt_db']
        db.metadata.create_all(akt_engine, tables=[AKTTransactionPerformance.__table__])

        self.perm = Permission(name='dashboard.view')
        self.role = Role(name='VIEWER', permissions=[self.perm])
        self.user = User(
            user_id='9999',
            username='akt_tester',
            email='akt@example.com',
            password_hash='dummy',
            is_active=True,
            roles=[self.role]
        )
        db.session.add_all([self.perm, self.role, self.user])
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def auth_headers(self):
        token = create_access_token(identity='9999')
        return {'Authorization': f'Bearer {token}'}

    @patch('app.dashboard.routes.transaction_performance.redis_client')
    @patch('app.dashboard.routes.transaction_performance.socketio')
    def test_trigger_akt_sync_broadcasts_socket_and_publishes_redis(self, mock_socketio, mock_redis):
        mock_redis.keys.return_value = [b'akt_perf_cache:1']
        response = self.client.post('/api/akt/trigger-sync', json={'message': 'Data refreshed'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'success')
        mock_redis.publish.assert_called_once()
        mock_socketio.emit.assert_called_once_with('aktPerformanceRefresh', {
            'action': 'refresh',
            'timestamp': unittest.mock.ANY,
            'message': 'Data refreshed'
        })

    @patch('app.dashboard.routes.transaction_performance.redis_client')
    @patch('app.dashboard.routes.transaction_performance.socketio')
    def test_trigger_akt_sync_handles_redis_failure(self, mock_socketio, mock_redis):
        mock_redis.keys.side_effect = Exception("Redis connection refused")
        mock_redis.publish.side_effect = Exception("Redis connection refused")
        response = self.client.post('/api/akt/trigger-sync', json={'message': 'Data refreshed'})
        self.assertEqual(response.status_code, 200)
        mock_socketio.emit.assert_called_once()

    @patch('app.dashboard.routes.transaction_performance.redis_client')
    def test_division_defaults_multiple_and_all(self, mock_redis):
        mock_redis.get.return_value = None
        mock_redis.exists.return_value = False
        mock_redis.set.return_value = True
        for index, division in enumerate(['GOLD', 'Diamond', 'SILVER']):
            for year, month, day, hour in [(2026, 11, 5, index + 10), (2025, 10, 18, index + 20)]:
                db.session.add(AKTTransactionPerformance(timepartt=hour, billtime=time(hour, 0),
                    country_actual='INDIA', date=datetime(year, month, day, hour), divisionname=division,
                    location='Store A', billcount=1, invoiceamt=100, turnover=90, perminutebillcount='1', hourlybillcount=1))
        db.session.commit()
        base='/api/akt/transaction-data?date=2026-11-05&country=India'
        cases=[('', {'GOLD', 'Diamond'}, 2),
               ('&division=gold&division=SILVER', {'GOLD', 'SILVER'}, 2),
               ('&division=diamond', {'Diamond'}, 1),
               ('&division=', {'GOLD', 'Diamond', 'SILVER'}, 3)]
        keys=[]
        for query, expected, prior_count in cases:
            response=self.client.get(base+query, headers=self.auth_headers())
            self.assertEqual(response.status_code, 200)
            data=response.get_json()
            self.assertEqual({row['division'] for row in data['division_sales']}, expected)
            self.assertEqual(len(data['efficiency_2025']), prior_count)
            keys.append(mock_redis.get.call_args.args[0])
        self.assertEqual(len(set(keys)), len(cases))

    def test_sales_growth_common_hour_and_unavailable_baseline(self):
        from sqlalchemy import func
        model = AKTTransactionPerformance
        for day, hour, amount in [(datetime(2026,11,5,10),10,100), (datetime(2026,11,5,11),11,150),
                                  (datetime(2025,10,18,10),10,100), (datetime(2025,10,18,12),12,900)]:
            db.session.add(model(date=day,timepartt=hour,billtime=time(hour),country_actual='INDIA',
                                 location='Store A',divisionname='GOLD',invoiceamt=amount,billcount=int(amount/10),netweight=amount*2))
        db.session.commit()
        common = [model.country_actual=='INDIA',model.location=='Store A',model.divisionname.in_(['GOLD','DIAMOND'])]
        current = common + [func.date(model.date)==date(2026,11,5)]
        previous = common + [func.date(model.date)==SALES_COMPARISON_DATE]
        result = sales_growth_comparison(current,previous)
        self.assertEqual(result['sales_growth_cutoff'],'11:00')
        self.assertEqual(result['sales_growth_yoy'],50)
        self.assertEqual(result['bills_growth_yoy'],50)
        self.assertEqual(result['avg_bill_growth_yoy'],0)
        self.assertEqual(result['avg_bill_growth_previous'],10)
        self.assertEqual(result['weight_growth_yoy'],50)
        self.assertEqual(result['bills_growth_previous'],10)
        self.assertEqual(result['weight_growth_previous'],0.2)
        self.assertEqual(result['sales_growth_previous'],100)  # Excludes later historical sales.
        self.assertEqual(result['sales_growth_comparison_date'],'2025-10-18')
        db.session.query(model).filter(model.date==datetime(2026,11,5,11)).update({model.billcount:12}, synchronize_session=False)
        db.session.commit()
        self.assertEqual(sales_growth_comparison(current,previous)['avg_bill_growth_yoy'],25)
        db.session.query(model).filter(*current).update({model.invoiceamt:0,model.billcount:0,model.netweight:0}, synchronize_session=False)
        db.session.commit()
        self.assertEqual(sales_growth_comparison(current,previous)['sales_growth_yoy'],-100)
        self.assertEqual(sales_growth_comparison(current,previous)['bills_growth_yoy'],-100)
        self.assertEqual(sales_growth_comparison(current,previous)['weight_growth_yoy'],-100)
        db.session.query(model).filter(*previous).update({model.invoiceamt:0,model.billcount:0,model.netweight:0}, synchronize_session=False)
        db.session.commit()
        self.assertIsNone(sales_growth_comparison(current,previous)['sales_growth_yoy'])
        self.assertIsNone(sales_growth_comparison(current,previous)['bills_growth_yoy'])
        self.assertIsNone(sales_growth_comparison(current,previous)['weight_growth_yoy'])
        self.assertIsNone(sales_growth_comparison(current,previous)['avg_bill_growth_yoy'])
        db.session.query(model).filter(*previous).delete(synchronize_session=False)
        db.session.commit()
        self.assertEqual(sales_growth_comparison(current,previous)['sales_growth_status'],'missing_data')

    @patch('app.dashboard.routes.transaction_performance.redis_client')
    def test_last_hour_comparison_matching_window_and_divisions(self, mock_redis):
        mock_redis.get.return_value = None
        mock_redis.exists.return_value = False
        mock_redis.set.return_value = True
        model = AKTTransactionPerformance
        for day, counts in [(date(2026,11,5), {'GOLD':(5,10),'DIAMOND':(2,6),'SILVER':(100,200)}),
                            (SALES_COMPARISON_DATE, {'GOLD':(4,8),'DIAMOND':(1,3),'SILVER':(100,500)})]:
            for division, values in counts.items():
                for hour, count in zip([9,10],values):
                    db.session.add(model(date=datetime.combine(day,time(hour)),timepartt=hour,billtime=time(hour),
                        country_actual='INDIA',location='Store A',divisionname=division,invoiceamt=count*100,billcount=count))
        db.session.commit()
        url='/api/akt/transaction-data?date=2026-11-05&country=India&location=Store+A'
        result=self.client.get(url,headers=self.auth_headers()).get_json()['kpis']
        self.assertEqual(result['hourly_growth_current'],9)
        self.assertEqual(result['hourly_growth_previous'],6)
        self.assertEqual(result['hourly_growth_yoy'],50)
        self.assertEqual(result['sales_growth_cutoff'],'10:00')
        self.assertEqual(result['hourly_comparison_start'],'09:00')
        result=self.client.get(url+'&division=diamond',headers=self.auth_headers()).get_json()['kpis']
        self.assertEqual(result['hourly_growth_yoy'],100)
        filters=[func.date(model.date)==date(2026,11,5), model.divisionname.in_(['GOLD','DIAMOND'])]
        prior=[func.date(model.date)==SALES_COMPARISON_DATE, model.divisionname.in_(['GOLD','DIAMOND'])]
        db.session.query(model).filter(*filters).update({model.billcount:0},synchronize_session=False)
        db.session.commit()
        self.assertEqual(sales_growth_comparison(filters,prior)['hourly_growth_yoy'],-100)
        db.session.query(model).filter(*prior).update({model.billcount:0},synchronize_session=False)
        db.session.commit()
        self.assertIsNone(sales_growth_comparison(filters,prior)['hourly_growth_yoy'])
        db.session.query(model).filter(*prior,model.billtime==time(9)).delete(synchronize_session=False)
        db.session.commit()
        self.assertIsNone(sales_growth_comparison(filters,prior)['hourly_growth_previous'])

    def test_get_akt_transaction_data_requires_auth(self):
        response = self.client.get('/api/akt/transaction-data')
        self.assertEqual(response.status_code, 401)

    @patch('app.dashboard.routes.transaction_performance.redis_client')
    def test_get_akt_transaction_data_handles_redis_failure(self, mock_redis):
        mock_redis.get.side_effect = Exception("Redis connection timeout")
        mock_redis.exists.side_effect = Exception("Redis connection timeout")
        mock_redis.set.side_effect = Exception("Redis connection timeout")
        mock_redis.setex.side_effect = Exception("Redis connection timeout")

        response = self.client.get('/api/akt/transaction-data?country=India', headers=self.auth_headers())
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'success')

    @patch('app.dashboard.routes.transaction_performance.redis_client')
    def test_case_insensitive_country_and_hourly_revenue_delta(self, mock_redis):
        mock_redis.get.return_value = None
        mock_redis.exists.return_value = False
        mock_redis.set.return_value = True

        test_date = date(2026, 11, 5)
        dt = datetime(2026, 11, 5, 10, 0, 0)
        dt2 = datetime(2026, 11, 5, 11, 0, 0)

        # Seed 2 hourly rows where country_actual is uppercase 'INDIA'
        row1 = AKTTransactionPerformance(
            timepartt=10,
            billtime=time(10, 0, 0),
            country_actual='INDIA',
            date=dt,
            location='Store A',
            divisionname='GOLD',
            state='State A',
            region='South',
            subledger='Sub 1',
            billcount=10,
            hourlybillcount=10,
            perminutebillcount='0.5',
            invoiceamt=100000.0,
            turnover=90000.0,
            grossweight=50.0,
            netweight=45.0,
        )
        row2 = AKTTransactionPerformance(
            timepartt=11,
            billtime=time(11, 0, 0),
            country_actual='INDIA',
            date=dt2,
            location='Store A',
            divisionname='GOLD',
            state='State A',
            region='South',
            subledger='Sub 1',
            billcount=25,
            hourlybillcount=15,
            perminutebillcount='0.75',
            invoiceamt=250000.0,
            turnover=220000.0,
            grossweight=120.0,
            netweight=110.0,
        )
        # Seed a 2025 comparison row on 18.10.2025 (2025-10-18)
        row_2025 = AKTTransactionPerformance(
            timepartt=10,
            billtime=time(10, 0, 0),
            country_actual='INDIA',
            date=datetime(2025, 10, 18, 10, 0, 0),
            location='Store A',
            divisionname='GOLD',
            state='State A',
            region='South',
            subledger='Sub 1',
            billcount=8,
            hourlybillcount=8,
            perminutebillcount='0.4',
            invoiceamt=80000.0,
            turnover=70000.0,
            grossweight=40.0,
            netweight=35.0,
        )
        db.session.add_all([row1, row2, row_2025])
        db.session.commit()

        # Query with lowercase/mixed-case country='India'
        response = self.client.get(
            f'/api/akt/transaction-data?country=India&date={test_date.isoformat()}',
            headers=self.auth_headers()
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['kpis']['total_bills'], 25)
        self.assertEqual(data['kpis']['sales_growth_yoy'], 25)
        self.assertEqual(data['kpis']['bills_growth_yoy'], 25)
        self.assertAlmostEqual(data['kpis']['weight_growth_yoy'], 100 * (45-35)/35)
        self.assertEqual(data['kpis']['bills_growth_previous'], 8)
        self.assertEqual(data['kpis']['avg_bill_growth_previous'], 10000)
        self.assertEqual(data['kpis']['avg_bill_growth_current'], 10000)
        self.assertEqual(data['kpis']['avg_bill_growth_yoy'], 0)
        self.assertEqual(data['kpis']['weight_growth_previous'], 0.035)
        self.assertEqual(data['kpis']['sales_growth_cutoff'], '10:00')
        self.assertAlmostEqual(data['kpis']['total_net_weight'], 0.11, places=3)
        self.assertAlmostEqual(data['kpis']['total_net_weight_kg'], 0.11, places=3)
        self.assertEqual(data['kpis']['total_net_weight_grams'], 110.0)

        # Hourly delta check for revenue:
        # Hour 10: cum_rev = 100,000, delta = 100,000
        # Hour 11: cum_rev = 250,000, delta = 150,000
        eff = data['efficiency']
        self.assertEqual(len(eff), 2)
        self.assertEqual(eff[0]['sum_hourly'], 10)
        self.assertEqual(eff[0]['sum_revenue'], 100000.0)
        self.assertEqual(eff[1]['sum_hourly'], 15)
        self.assertEqual(eff[1]['sum_revenue'], 150000.0)
        self.assertEqual(eff[1]['cum_revenue'], 250000.0)

        # Trends hourly delta check
        trends = data['trends']
        self.assertEqual(len(trends), 2)
        self.assertEqual(trends[0]['sum_revenue'], 100000.0)
        self.assertEqual(trends[1]['sum_revenue'], 150000.0)
        self.assertEqual(trends[1]['cum_revenue'], 250000.0)

        # 2025 comparison check (18.10.2025)
        eff_2025 = data.get('efficiency_2025', [])
        self.assertEqual(len(eff_2025), 1)
        self.assertEqual(eff_2025[0]['time'], '10')
        self.assertEqual(eff_2025[0]['sum_hourly'], 8)
        self.assertEqual(eff_2025[0]['cum_bills'], 8)
        self.assertEqual(data['weight_analysis_2025']['gross'], 40.0)
        self.assertEqual(data['weight_analysis_2025']['net'], 35.0)


if __name__ == '__main__':
    unittest.main()
