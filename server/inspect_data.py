
import sys
import os

# Add server directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_app
    from app.extensions import db
    from app.models import OwnerWiseOrderSummarySnapshot
    from sqlalchemy import func
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

def inspect_data():
    app = create_app()
    with app.app_context():
        print("Inspecting OwnerWiseOrderSummarySnapshot data...")
        
        # Check first 5 rows to see what's populated
        rows = OwnerWiseOrderSummarySnapshot.query.limit(5).all()
        for i, row in enumerate(rows):
            print(f"Row {i}: Supplier={row.supplier}")
            print(f"  Ordered: {row.ordered_pcs}, Accepted: {row.accepted_pcs}, Rejected: {row.rejected_pcs}")
            print(f"  Barcoded: {row.barcoded_pcs}, HM: {row.hm_passed_pcs}, QC: {row.qc_passed_pcs}")
            print(f"  Invoiced: {row.invoiced_pcs}, Delivered: {row.delivered_pcs}")
        
        # Check global sums again
        agg = db.session.query(
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('ordered'),
            func.sum(OwnerWiseOrderSummarySnapshot.accepted_pcs).label('accepted'),
            func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('delivered')
        ).first()
        print(f"Global Sums: Ordered={agg.ordered}, Accepted={agg.accepted}, Delivered={agg.delivered}")

if __name__ == "__main__":
    inspect_data()
