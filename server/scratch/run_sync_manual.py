from app import create_app
from app.utils.sync_tasks import sync_order_processing_pending_data_task

app = create_app()
with app.app_context():
    print("Starting sync task manually...")
    sync_order_processing_pending_data_task()
    print("Sync task completed!")
