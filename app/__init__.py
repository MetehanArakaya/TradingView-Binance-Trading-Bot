from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config.settings import Config
import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

db = SQLAlchemy()

def create_app(config_class=Config):
    # Set template and static folders relative to project root
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')
    app.config.from_object(config_class)
    
    db.init_app(app)
    
    # Register blueprints
    from app.web import bp as web_bp
    app.register_blueprint(web_bp)
    
    from app.webhook import bp as webhook_bp
    app.register_blueprint(webhook_bp, url_prefix='/webhook')
    
    # Setup logging
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/trading_bot.log',
                                         maxBytes=10240000, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Trading Bot startup')
    
    return app