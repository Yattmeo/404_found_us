import os
from flask import Flask, jsonify
from flask_cors import CORS  # noqa: F401

from config import config_by_name
from models import db
from routes import (
    transactions_bp, calculations_bp, merchants_bp, mccs_bp,
    register_error_handlers
)


def create_app(config_name='development'):
    """Application factory"""
    app = Flask(__name__)
    
    # Load configuration
    config_class = config_by_name.get(config_name.lower())
    if not config_class:
        raise ValueError(f'Unknown config: {config_name}')
    
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(transactions_bp)
    app.register_blueprint(calculations_bp)
    app.register_blueprint(merchants_bp)
    app.register_blueprint(mccs_bp)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Basic health endpoints
    @app.route('/')
    def hello_world():
        return jsonify({
            'message': 'Welcome to 404 Found ML Backend API',
            'status': 'success',
            'version': '1.0'
        })
    
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'service': 'ml-backend'
        })
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app


if __name__ == '__main__':
    config = os.getenv('FLASK_ENV', 'development')
    app = create_app(config)
    app.run(host='0.0.0.0', port=5000, debug=config == 'development')
