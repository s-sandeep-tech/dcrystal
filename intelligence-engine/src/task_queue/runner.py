"""Coordinate durable database results with at-least-once stream delivery."""
import hashlib
from sqlalchemy import text
from ..db.connection import task_transaction
from ..db.models import IntelligenceTaskResult
from ..db.writer import DatabaseWriter
from ..utils.logger import logger
from .protocol import TaskRequest, TaskResult, TaskStatus


class TaskBusy(Exception):
    pass


def lock_task(session, task_id):
    # Transaction-scoped lock also fences a worker whose Redis lease expired.
    key = int.from_bytes(hashlib.sha256(task_id.encode()).digest()[:8], 'big', signed=True)
    if not session.execute(text('SELECT pg_try_advisory_xact_lock(:key)'), {'key': key}).scalar():
        raise TaskBusy(task_id)


class TaskRunner:
    def __init__(self, redis_manager, execute):
        self.queue = redis_manager
        self.execute = execute

    def process(self, delivery):
        try:
            task = TaskRequest.model_validate_json(delivery.raw)
            if not task.task_id or len(task.task_id) > 100:
                raise ValueError('task_id must contain 1-100 characters')
        except ValueError as error:
            self.queue.acknowledge(delivery, error=f'Invalid task payload: {error}')
            return

        with self.queue.heartbeat(delivery) as check_lease:
            try:
                with task_transaction() as session:
                    lock_task(session, task.task_id)
                    saved = session.get(IntelligenceTaskResult, task.task_id)
                    if saved:
                        result = TaskResult.model_validate(saved.result_json)
                    else:
                        if delivery.attempts > self.queue.max_attempts:
                            raise RuntimeError('Retry limit reached after interrupted execution')
                        self.queue.update_task_status(task.task_id, TaskStatus.PROCESSING)
                        DatabaseWriter.log_task_start(task.task_id, task.task_type.value, task.payload)
                        result = self.execute(task)
                        if result.status != TaskStatus.COMPLETED:
                            raise RuntimeError(result.error or 'Task execution failed')
                        DatabaseWriter.log_task_finish(task.task_id, result.status.value)
                        session.add(IntelligenceTaskResult(
                            task_id=task.task_id, result_json=result.model_dump(mode='json')))
                    check_lease()
            except TaskBusy:
                return  # Existing transaction still owns this task; leave pending.
            except Exception as error:
                logger.exception('Task %s failed on attempt %s', task.task_id, delivery.attempts)
                check_lease()
                terminal = delivery.attempts >= self.queue.max_attempts
                result = TaskResult(
                    task_id=task.task_id, task_type=task.task_type,
                    status=TaskStatus.FAILED if terminal else TaskStatus.RETRYING,
                    error=str(error)
                )
                # Separate transaction: execution output has already rolled back.
                # Check for a receipt again, including an uncertain commit outcome.
                try:
                    with task_transaction() as session:
                        lock_task(session, task.task_id)
                        saved = session.get(IntelligenceTaskResult, task.task_id)
                        if saved:
                            result = TaskResult.model_validate(saved.result_json)
                        else:
                            DatabaseWriter.log_task_start(task.task_id, task.task_type.value, task.payload)
                            DatabaseWriter.log_task_finish(task.task_id, result.status.value, result.error)
                            if terminal:
                                session.add(IntelligenceTaskResult(
                                    task_id=task.task_id, result_json=result.model_dump(mode='json')))
                        check_lease()
                except TaskBusy:
                    return
                except Exception:
                    # Cannot persist even failure status: retain the delivery, and
                    # expose the outage without claiming durable completion/failure.
                    result.status = TaskStatus.RETRYING
                    self.queue.save_task_result(result)
                    raise

            # A Redis failure here leaves the message pending. Recovery replays the
            # committed receipt, never the database writes or external computation.
            self.queue.save_task_result(result)
            if result.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                self.queue.acknowledge(delivery, error=result.error if result.status == TaskStatus.FAILED else None)
            logger.info('[%s] Task status: %s (attempt %s)', task.task_id, result.status.value, delivery.attempts)
