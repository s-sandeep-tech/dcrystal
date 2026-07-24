from flask import Blueprint

dashboard_bp = Blueprint('dashboard', __name__)

from .routes import main, notification, order, short, provision, location_wise_order, branch_weight, branch_weight_v2, branch_stock_provision, owner_wise_order, crystal_issues, admin_rbac_ui, process_level_delay, outstanding_purchase_order, stage_level_delay, order_pending_rejection, order_delay_tracking, pending_acceptance, rejected_weight, provision_allocation, showroom_wise_order_summary, bh_showroom_wise_order_summary, provision_stock_status, location_physical_stock_status, transaction_performance, order_processing_pending, qc_delay_management, hm_delay_management, party_delay_management, order_fulfillment_value_aging_matrix, pending_order_details, active_order_details, collection_wise_average_delivery_days


