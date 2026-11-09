import ast
from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.utils import stock_sync_chain as chain, sync_manager

WORKER = Path(__file__).resolve().parents[2] / 'sync-consumer/main.py'


class StopWorker(BaseException):
    pass


class StockSyncChainTests(unittest.TestCase):
    def test_followup_has_separate_log_and_initiator_on_success_and_failure(self):
        for outcome in [{'status': 'success', 'count': 42}, {'status': 'error', 'message': 'source failed'}, RuntimeError('raised')]:
            log = SimpleNamespace()
            session = MagicMock()
            with patch.object(chain, 'SyncLog', return_value=log) as create_log, patch.object(chain, 'db', SimpleNamespace(session=session)), patch.object(chain, 'sync_stock_drilldown_details') as run, patch.object(chain, 'emit_sync_update') as emit:
                if isinstance(outcome, Exception): run.side_effect = outcome
                else: run.return_value = outcome
                result = chain.run_stock_sync_followup({'type': 'provision_stock_status', 'user_id': '123'})
                self.assertEqual(create_log.call_args.kwargs['task_name'], 'stock_drilldown_details')
                self.assertEqual(create_log.call_args.kwargs['initiated_by'], '123')
                self.assertEqual(log.status, result['status'])
                self.assertGreaterEqual(log.duration, 0)
                self.assertEqual(session.commit.call_count, 2)
                run.assert_called_once()
                if isinstance(outcome, Exception): session.rollback.assert_called_once(); emit.assert_called_once()

    def test_unrelated_task_does_not_chain(self):
        with patch.object(chain, 'sync_stock_drilldown_details') as run:
            chain.run_stock_sync_followup({'type': 'stock_drilldown_details'})
            run.assert_not_called()

    def test_worker_chains_after_parent_on_all_exit_paths_before_batch_advance(self):
        tree = ast.parse(WORKER.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'process_sync_queue')
        for outcome in [{'status':'success'}, {'status':'error'}, RuntimeError('parent failed')]:
            events = []
            data = dict(type='provision_stock_status', user_id='THIRD_PARTY', scheduled_all_batch=True, batch_id='batch', batch_index=7)
            queue = MagicMock(); queue.blpop.side_effect = [('sync_queue', json.dumps(data)), StopWorker()]
            def parent():
                events.append('parent')
                if isinstance(outcome, Exception): raise outcome
                return outcome
            scope = dict(logger=MagicMock(), queue_redis_client=queue, json=json,
                         flask_app=SimpleNamespace(app_context=nullcontext),
                         time=SimpleNamespace(time=lambda:0,sleep=lambda _:None),
                         sync_provision_stock_status_data_task=parent,
                         enqueue_next_scheduled_all_task=lambda _:events.append('next'))
            exec(compile(ast.Module(body=[function], type_ignores=[]), str(WORKER), 'exec'), scope)
            with patch('app.models.core.SyncLog', return_value=SimpleNamespace()), patch('app.extensions.db', SimpleNamespace(session=MagicMock())), patch.object(chain, 'run_stock_sync_followup', side_effect=lambda _:events.append('details')) as followup:
                with self.assertRaises(StopWorker): scope['process_sync_queue']()
                self.assertEqual(events, ['parent','details','next'])
                followup.assert_called_once_with(data)

    def test_redundant_schedules_removed_and_manual_task_retained(self):
        self.assertIn('stock_drilldown_details', sync_manager.ALLOWED_SYNC_TASKS)
        self.assertNotIn('size_level_nip_barcode', sync_manager.SCHEDULED_ALL_SYNC_TASKS)
        self.assertNotIn('stock_drilldown_details', sync_manager.SCHEDULED_ALL_SYNC_TASKS)
        tree = ast.parse(WORKER.read_text())
        scheduled_args = [ast.literal_eval(kw.value) for call in ast.walk(tree) if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == 'add_job' for kw in call.keywords if kw.arg == 'args' and isinstance(kw.value, ast.List)]
        self.assertNotIn(['stock_drilldown_details'], scheduled_args)
        self.assertIn(['provision_stock_status'], scheduled_args)


if __name__ == '__main__': unittest.main()
