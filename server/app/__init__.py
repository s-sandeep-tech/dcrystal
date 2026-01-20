from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app)

    # Register Blueprints
    from app.api.routes import api_bp
    from app.dashboard.routes import dashboard_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp)

    return app
