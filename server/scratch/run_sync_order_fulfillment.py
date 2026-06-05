from app import create_app
from app.utils.sync_tasks import sync_order_fulfillment_aging_matrix_task

app = create_app()
with app.app_context():
    print("Starting sync task manually...")
    result = sync_order_fulfillment_aging_matrix_task()
    print("Sync task completed!", result)
