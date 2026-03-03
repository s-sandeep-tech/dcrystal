from flask import Blueprint

dashboard_bp = Blueprint('dashboard', __name__)

from .routes import main, notification, order, short, provision, location_wise_order, branch_weight, branch_weight_v2, branch_stock_provision, owner_wise_order, crystal_issues, admin_rbac_ui, process_level_delay, outstanding_purchase_order, stage_level_delay

