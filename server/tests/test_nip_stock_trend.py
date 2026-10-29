import unittest
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from unittest.mock import MagicMock
from types import SimpleNamespace
from flask import Flask, session
from flask_jwt_extended import JWTManager, create_access_token
from werkzeug.datastructures import MultiDict
from openpyxl import load_workbook
from app.extensions import db
from app.models.nip_stock_trend import NIPStockTrendSnapshot as S
from app.models.snapshots import BranchAuthoritySnapshot
from app.services.nip_stock_trend import prepare_trend, period_start, trend_data, scoped_query
from app.dashboard.routes.nip_stock_trend import nip_stock_trend_data, export_nip_stock_trend


class StockTrendTests(unittest.TestCase):
    def test_period_closing_not_sum_and_synchronized_dates(self):
        rows=[(date(2026,10,1),'Gold',100),(date(2026,10,2),'Gold',150),
              (date(2026,10,1),'Silver',20)]
        data=prepare_trend(rows,'monthly')
        self.assertEqual(data['series'][0]['values'],[150])
        self.assertEqual(data['series'][1]['values'],[None])
        self.assertEqual(data['balance_dates'],['2026-10-02'])
        self.assertEqual(data['stats']['opening'],120)
        self.assertEqual(data['stats']['closing'],150)
        self.assertEqual(data['stats']['average'],135)

    def test_boundaries(self):
        day=date(2026,10,28)
        self.assertEqual(period_start(day,'weekly'),date(2026,10,26))
        self.assertEqual(period_start(day,'quarterly'),date(2026,10,1))
        self.assertEqual(period_start(day,'yearly'),date(2026,1,1))
        self.assertEqual(period_start(day,'monthly'),date(2026,10,1))

    def test_empty_zero_and_missing_measure(self):
        self.assertIsNone(prepare_trend([],'daily')['stats']['opening'])
        data=prepare_trend([(date(2026,1,1),'Gold',0),(date(2026,1,2),'Gold',10)],'daily')
        self.assertIsNone(data['stats']['change_pct'])
        data=prepare_trend([(date(2026,1,1),'Gold',None)],'daily')
        self.assertIsNone(data['stats']['opening'])


class StockTrendDataTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__)
        self.app.config.update(TESTING=True,SECRET_KEY='test-secret-at-least-32-characters',
            JWT_SECRET_KEY='test-jwt-secret-at-least-32-characters',SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
        db.init_app(self.app);JWTManager(self.app)
        self.ctx=self.app.app_context();self.ctx.push()
        S.__table__.create(db.engine);BranchAuthoritySnapshot.__table__.create(db.engine)
        self.app.add_url_rule('/api/data',view_func=nip_stock_trend_data.__wrapped__)
        self.app.add_url_rule('/api/export',view_func=export_nip_stock_trend.__wrapped__)
        for i,(day,branch,weight,pieces,nip) in enumerate([
            (1,20,1000,2,True),(2,20,2000,3,True),(2,2,5000,4,True),(2,20,9999,20,False)
        ],1):
            db.session.add(S(id=i,uid=str(i),date=date(2026,10,day),branch_id=branch,
                location='ERNAKULAM' if branch==20 else 'THRISSUR ROUND',division='Gold',
                gross_wt=weight,pieces=pieces,is_nip=nip,is_excess=branch==20))
        db.session.add(BranchAuthoritySnapshot(branch_id=20,emp_code=1235));db.session.commit()

    def tearDown(self):
        db.session.remove();self.ctx.pop()

    def test_metric_conversion_and_location_multi_select(self):
        with self.app.test_request_context('/?location=ERNAKULAM'):
            session['roles']=['ADMIN']
            data=trend_data(MultiDict([('location','ERNAKULAM')]))
            self.assertEqual(data['series'][0]['values'],[1,11.999])
            self.assertEqual(data['series'][1]['values'],[1,2])
            self.assertEqual(data['series'][2]['values'],[1,11.999])
            self.assertEqual(data['stats']['total_nip'],2)
            self.assertEqual(data['stats']['total_stock'],11.999)
            self.assertAlmostEqual(data['stats']['nip_pct'],2/11.999*100)
            self.assertEqual(data['stats']['excess_pct'],100)
            self.assertAlmostEqual(data['stats']['excess_change_pct'],1099.9)
            self.assertEqual(data['stats']['total_excess'],11.999)
            self.assertAlmostEqual(data['stats']['change'],10.999)
            self.assertEqual([s['kind'] for s in data['series']],['total','nip','excess'])
            all_locations=trend_data(MultiDict([('location','ERNAKULAM'),('location','THRISSUR ROUND'),('metric','pieces')]))
            self.assertEqual(all_locations['stats']['closing'],27)

    def test_date_boolean_and_scope(self):
        with self.app.test_request_context('/'):
            session['roles']=['SHOWROOM_MANAGER'];session['user_id']='1235'
            data=trend_data(MultiDict([('from_date','2026-10-02'),('is_excess','true')]))
            self.assertEqual(data['stats']['closing'],11.999)
            session['user_id']='999'
            self.assertEqual(scoped_query().count(),0)

    def test_percentage_stats_zero_missing_and_reduction(self):
        S.query.delete()
        first=S(uid='first',date=date(2026,10,1),division='Gold',gross_wt=0,pieces=0,is_nip=True,is_excess=True)
        last=S(uid='last',date=date(2026,10,2),division='Gold',gross_wt=1000,pieces=1,is_nip=True,is_excess=True)
        db.session.add_all([first,last]);db.session.commit()
        with self.app.test_request_context('/'):
            session['roles']=['ADMIN']
            stats=trend_data(MultiDict())['stats']
            self.assertEqual(stats['nip_pct'],100)
            self.assertIsNone(stats['excess_change_pct'])
            zero=trend_data(MultiDict({'to_date':'2026-10-01'}))['stats']
            self.assertIsNone(zero['nip_pct']);self.assertIsNone(zero['excess_pct'])
            first.gross_wt=2000;db.session.commit()
            self.assertEqual(trend_data(MultiDict())['stats']['excess_change_pct'],-50)
            last.gross_wt=None;db.session.commit()
            missing=trend_data(MultiDict())['stats']
            for key in ['nip_pct','excess_pct','excess_change_pct']:self.assertIsNone(missing[key])

    def test_invalid_parameters(self):
        with self.app.test_request_context('/'):
            session['roles']=['ADMIN']
            for args in [{'metric':'weight'},{'group_by':'uid'},{'interval':'hourly'},
                         {'from_date':'2026-10-02','to_date':'2026-10-01'},{'is_excess':'invalid'},
                         {'limiter':'invalid'},{'order':'invalid'},{'rank_by':'invalid'}]:
                with self.assertRaises(ValueError):trend_data(MultiDict(args))

    def test_rank_by_stock_type(self):
        S.query.delete()
        for i in range(1,26):
            nip=(26-i)*100
            excess=(13-abs(13-i))*100
            for kind,weight in [('base',i*10000-nip-excess),('nip',nip),('excess',excess)]:
                db.session.add(S(uid=f'{i}-{kind}',date=date(2026,10,2),division=f'Group {i:02}',
                                 gross_wt=weight,pieces=weight,is_nip=kind=='nip',is_excess=kind=='excess'))
        db.session.commit()
        with self.app.test_request_context('/'):
            session['roles']=['ADMIN']
            for kind,first in [('total','Group 25'),('nip','Group 01'),('excess','Group 13')]:
                result=trend_data(MultiDict({'limiter':'top','rank_by':kind}))
                self.assertEqual(result['series'][0]['group'],first)
                self.assertEqual(result['rank_by'],kind)
                self.assertEqual(result['displayed_groups'],16)
                self.assertEqual(result['stats']['closing'],3250)
                self.assertEqual(result['stats']['total_nip'],32.5)
                self.assertEqual(result['stats']['total_excess'],16.9)
            for limiter,first in [('middle','Group 05'),('bottom','Group 10')]:
                result=trend_data(MultiDict({'limiter':limiter,'rank_by':'nip'}))
                self.assertEqual(result['series'][0]['group'],first)
            ascending=trend_data(MultiDict({'limiter':'top','rank_by':'nip','order':'asc'}))
            self.assertEqual(ascending['series'][0]['group'],'Group 16')

    def test_group_limiter_and_order_use_latest_total_not_history_sum(self):
        S.query.delete()
        for i in range(1,26):
            db.session.add(S(uid=str(i),date=date(2026,10,2),division=f'Group {i:02}',
                             gross_wt=i*1000,pieces=26-i,is_nip=True,is_excess=False))
        db.session.add(S(uid='old',date=date(2026,10,1),division='Group 01',gross_wt=999999,pieces=1))
        db.session.add(S(uid='stale',date=date(2026,10,1),division='Stale',gross_wt=999999,pieces=1))
        db.session.commit()
        with self.app.test_request_context('/'):
            session['roles']=['ADMIN']
            default=trend_data(MultiDict())
            self.assertEqual((default['limiter'],default['order'],default['displayed_groups']),('top','desc',16))
            for limiter, expected in [('top',list(range(25,9,-1))),
                                      ('middle',list(range(21,5,-1))),
                                      ('bottom',list(range(16,0,-1)))]:
                result=trend_data(MultiDict({'limiter':limiter}))
                self.assertEqual([s['group'] for s in result['series'][::3]],
                                 [f'Group {i:02}' for i in expected])
                self.assertEqual(result['displayed_groups'],16)
                self.assertEqual(result['stats']['closing'],325)
                self.assertEqual(len(result['table_rows']),32)
            ascending=trend_data(MultiDict({'limiter':'top','order':'asc'}))
            self.assertEqual(ascending['series'][0]['group'],'Group 10')
            pieces=trend_data(MultiDict({'limiter':'top','metric':'pieces'}))
            self.assertEqual(pieces['series'][0]['group'],'Group 01')
            all_groups=trend_data(MultiDict({'limiter':'all','order':'asc'}))
            self.assertEqual(all_groups['series'][-1]['group'],'Stale')

    def test_export_numeric_values_and_period_dates(self):
        token=create_access_token(identity='1')
        with self.app.test_request_context('/api/export?location=ERNAKULAM&interval=monthly',headers={'Authorization':'Bearer '+token}):
            session['roles']=['ADMIN']
            with patch('app.utils.decorators.get_user_permissions',return_value={'report.export'}):
                response=export_nip_stock_trend.__wrapped__()
            response.direct_passthrough=False
            workbook=load_workbook(BytesIO(response.get_data()))
            self.assertEqual(workbook.active['D2'].value,11.999)
            self.assertEqual(workbook.active['E2'].value,2)
            self.assertEqual(workbook.active['F2'].value,11.999)
            self.assertEqual(workbook.active['D2'].data_type,'n')
            self.assertEqual(workbook.active['B2'].value.date(),date(2026,10,2))
            workbook.close()

    def test_subset_filter_zero_and_overlapping_flags(self):
        with self.app.test_request_context('/'):
            session['roles']=['ADMIN']
            data=trend_data(MultiDict([('location','THRISSUR ROUND')]))
            self.assertEqual([s['values'] for s in data['series']],[[5],[5],[0]])
            filtered=trend_data(MultiDict([('location','ERNAKULAM'),('is_excess','true')]))
            self.assertEqual(filtered['stats']['closing'],11.999)
            self.assertEqual(filtered['table_rows'][-1]['total'],11.999)
            self.assertEqual(filtered['table_rows'][-1]['nip'],2)
            self.assertEqual(filtered['table_rows'][-1]['excess'],11.999)

    def _nip_source(self, fail=False, changed=False, corrupt=False):
        conn=MagicMock()
        records=[{'uid':'00000000-0000-0000-0000-000000000001','date':date(2026,10,2),
                  'gross_wt':1000,'pieces':1,'is_nip':True,'_source_hash':'0'*31+'1'},
                 {'uid':'00000000-0000-0000-0000-000000000002','date':date(2026,10,2),
                  'gross_wt':2000,'pieces':2,'is_nip':True,'_source_hash':'0'*31+'2'}]
        manifests, pages=0,0
        def cursor(*args,**kwargs):
            self.assertNotIn('name',kwargs)
            cur=MagicMock()
            def execute(query,params=None):
                cur.query=query;cur.params=params
            def fetchall():
                nonlocal manifests,pages
                if 'GROUP BY date' in cur.query:
                    manifests+=1
                    return [(date(2026,10,2),2,0,0,3000,3,0,4 if changed and manifests>1 else 3)]
                pages+=1
                self.assertIn('ORDER BY date, uid LIMIT %s',cur.query)
                self.assertEqual(cur.params[-1],1)
                if fail and pages==2:raise RuntimeError('source stream interrupted')
                if len(cur.params)==3:
                    self.assertIn('(date, uid) > (%s::date, %s::uuid)',cur.query)
                    batch=[r for r in records if (r['date'],r['uid'])>cur.params[:2]][:1]
                else:batch=records[:1]
                if corrupt and batch:return [{**batch[0],'_source_hash':'0'*31+'9'}]
                return batch
            cur.execute.side_effect=execute;cur.fetchall.side_effect=fetchall
            context=MagicMock();context.__enter__.return_value=cur
            return context
        conn.cursor.side_effect=cursor
        return conn

    def test_sync_retains_older_dates_and_rolls_back_failed_refresh(self):
        from app.utils.nip_stock_trend_sync import sync_nip_stock_trend_task
        execute = db.session.execute
        def execute_with_lock(statement, *args, **kwargs):
            if str(statement).startswith('SELECT pg_try_advisory_xact_lock'):
                return SimpleNamespace(scalar=lambda: True)
            return execute(statement, *args, **kwargs)
        with patch('app.utils.sync_tasks.emit_sync_update'), patch('app.utils.nip_stock_trend_sync.time.sleep'), \
             patch('app.utils.nip_stock_trend_sync.BATCH_SIZE',1), patch.object(db.session,'execute',side_effect=execute_with_lock):
            healthy=self._nip_source()
            with patch('app.utils.sync_tasks.get_external_db_connection',return_value=healthy):
                self.assertEqual(sync_nip_stock_trend_task()['status'],'success')
                healthy.set_session.assert_called_once_with(isolation_level='READ COMMITTED',readonly=True,autocommit=True)
            self.assertEqual(S.query.count(),3)
            self.assertEqual(S.query.filter(S.date==date(2026,10,1)).count(),1)
            with patch('app.utils.sync_tasks.get_external_db_connection',side_effect=lambda: self._nip_source(fail=True)) as source:
                self.assertEqual(sync_nip_stock_trend_task()['status'],'error')
                self.assertEqual(source.call_count,3)
            self.assertEqual(S.query.count(),3)
            self.assertEqual(S.query.filter_by(uid='00000000-0000-0000-0000-000000000002').count(),1)
            interrupted, healthy=self._nip_source(fail=True),self._nip_source()
            with patch('app.utils.sync_tasks.get_external_db_connection',side_effect=[interrupted,healthy]):
                self.assertEqual(sync_nip_stock_trend_task()['status'],'success')
                interrupted.close.assert_called_once()
                healthy.close.assert_called_once()
            self.assertEqual(S.query.count(),3)

    def test_sync_rejects_changed_source_and_staging_checksum_mismatch(self):
        from app.utils.nip_stock_trend_sync import _sync_nip_stock_trend_attempt
        execute=db.session.execute
        def execute_with_lock(statement,*args,**kwargs):
            if str(statement).startswith('SELECT pg_try_advisory_xact_lock'):
                return SimpleNamespace(scalar=lambda:True)
            return execute(statement,*args,**kwargs)
        for options in [{'changed':True},{'corrupt':True}]:
            with patch('app.utils.sync_tasks.emit_sync_update'), patch('app.utils.nip_stock_trend_sync.BATCH_SIZE',1), \
                 patch.object(db.session,'execute',side_effect=execute_with_lock), \
                 patch('app.utils.sync_tasks.get_external_db_connection',return_value=self._nip_source(**options)):
                result=_sync_nip_stock_trend_attempt()
                self.assertEqual(result['status'],'error')
                self.assertTrue(result['retryable'])
                self.assertEqual(S.query.count(),4)
                self.assertEqual(S.query.filter_by(uid='4').one().gross_wt,Decimal(9999))

    def test_sync_retries_and_reports_only_final_failure(self):
        from app.utils.nip_stock_trend_sync import sync_nip_stock_trend_task
        failure={'status':'error','message':'connection lost','retryable':True}
        with patch('app.utils.nip_stock_trend_sync._sync_nip_stock_trend_attempt',
                   side_effect=[dict(failure),dict(failure),{'status':'success','count':5}]) as attempt, \
             patch('app.utils.nip_stock_trend_sync.time.sleep') as sleep, \
             patch('app.utils.sync_tasks.emit_sync_update') as emit:
            self.assertEqual(sync_nip_stock_trend_task(),{'status':'success','count':5})
            self.assertEqual(attempt.call_count,3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list],[5,10])
            self.assertTrue(all(call.args[0]=='processing' for call in emit.call_args_list))
        with patch('app.utils.nip_stock_trend_sync._sync_nip_stock_trend_attempt',
                   side_effect=[dict(failure) for _ in range(3)]) as attempt, \
             patch('app.utils.nip_stock_trend_sync.time.sleep'), \
             patch('app.utils.sync_tasks.emit_sync_update') as emit:
            result=sync_nip_stock_trend_task()
            self.assertEqual(result,{'status':'error','message':'connection lost'})
            self.assertEqual(attempt.call_count,3)
            self.assertEqual(emit.call_args.args[0],'error')
        with patch('app.utils.nip_stock_trend_sync._sync_nip_stock_trend_attempt',
                   return_value={'status':'error','message':'invalid source','retryable':False}) as attempt, \
             patch('app.utils.nip_stock_trend_sync.time.sleep') as sleep, \
             patch('app.utils.sync_tasks.emit_sync_update'):
            self.assertEqual(sync_nip_stock_trend_task()['status'],'error')
            self.assertEqual(attempt.call_count,1)
            sleep.assert_not_called()

    def test_ssl_disconnect_remains_retryable_when_rollback_fails(self):
        from psycopg2 import OperationalError
        from app.utils.nip_stock_trend_sync import _sync_nip_stock_trend_attempt
        ssl_error=OperationalError('SSL connection has been closed unexpectedly')
        with patch('app.utils.sync_tasks.emit_sync_update'), \
             patch.object(db.session,'execute',return_value=SimpleNamespace(scalar=lambda:True)), \
             patch('app.utils.sync_tasks.get_external_db_connection',side_effect=ssl_error), \
             patch.object(db.session,'rollback',side_effect=ssl_error), \
             patch.object(db.session(),'invalidate') as invalidate:
            result=_sync_nip_stock_trend_attempt()
            self.assertTrue(result['retryable'])
            self.assertEqual(result['message'],'SSL connection has been closed unexpectedly')
            invalidate.assert_called_once()


if __name__=='__main__':unittest.main()
