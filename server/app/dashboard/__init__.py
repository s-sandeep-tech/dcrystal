from flask import Blueprint

dashboard_bp = Blueprint('dashboard', __name__)

from .routes import main, notification, order, short, provision, location_wise_order, branch_weight, branch_weight_v2

