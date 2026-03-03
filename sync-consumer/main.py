import time
import json
import logging
from app import create_app
from app.extensions import redis_client
from app.utils.sync_tasks import (
    sync_owner_wise_data_task,
    sync_process_level_delay_data_task,
    sync_outstanding_purchase_order_data_task,
    sync_stage_level_delay_data_task,
    emit_sync_update
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SyncConsumer")

app = create_app()

def process_queue():
    logger.info("Sync Consumer started. Waiting for tasks...")
    
    while True:
        try:
            # Block until a task is available in 'sync_queue'
            # blpop returns (key, value)
            _, task_data_json = redis_client.blpop('sync_queue')
            
            task_data = json.loads(task_data_json)
            task_type = task_data.get('type')
            
            logger.info(f"Processing task: {task_type}")
            
            with app.app_context():
                if task_type == 'owner_wise':
                    sync_owner_wise_data_task()
                elif task_type == 'process_delay':
                    sync_process_level_delay_data_task()
                elif task_type == 'outstanding_po':
                    sync_outstanding_purchase_order_data_task()
                elif task_type == 'stage_delay':
                    sync_stage_level_delay_data_task()
                else:
                    logger.error(f"Unknown task type: {task_type}")
                    emit_sync_update('error', f'Unknown task type: {task_type}')
            
            logger.info(f"Task {task_type} completed.")
            
        except Exception as e:
            logger.error(f"Error in consumer loop: {str(e)}")
            time.sleep(5) # Avoid rapid-fire errors if Redis is down

if __name__ == "__main__":
    process_queue()
