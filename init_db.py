#!/usr/bin/env python3
"""
Database initialization script
"""

import os
from app import create_app, db

def init_database():
    """Initialize the database with all tables"""
    # Remove existing database if it exists
    if os.path.exists('trading_bot.db'):
        os.remove('trading_bot.db')
        print("Removed existing database file")
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")
        
        # Import models to ensure they're registered
        from app.models.settings import BotSettings
        from app.models.signal import Signal
        from app.models.position import Position
        from app.models.trade import Trade
        
        # Create default settings
        default_settings = BotSettings()
        db.session.add(default_settings)
        db.session.commit()
        print("Default settings created!")
        
        print("Database initialization completed successfully!")

if __name__ == "__main__":
    init_database()