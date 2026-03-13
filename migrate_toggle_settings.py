#!/usr/bin/env python3
"""
Migration script to add toggle settings for daily loss limit and max concurrent positions
"""

import sqlite3
import os

def migrate_toggle_settings():
    """Add toggle columns for daily loss limit and max concurrent positions"""
    
    db_path = os.path.join('instance', 'trading_bot.db')
    
    if not os.path.exists(db_path):
        print("Database file not found!")
        return False
    
    print("Starting toggle settings migration...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(bot_settings)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        columns_to_add = []
        
        # Check and add daily_loss_limit_enabled column
        if 'daily_loss_limit_enabled' not in existing_columns:
            columns_to_add.append(('daily_loss_limit_enabled', 'BOOLEAN DEFAULT 0'))
            print("+ daily_loss_limit_enabled column will be added")
        else:
            print("+ daily_loss_limit_enabled column already exists")
        
        # Check and add max_concurrent_positions_enabled column
        if 'max_concurrent_positions_enabled' not in existing_columns:
            columns_to_add.append(('max_concurrent_positions_enabled', 'BOOLEAN DEFAULT 1'))
            print("+ max_concurrent_positions_enabled column will be added")
        else:
            print("+ max_concurrent_positions_enabled column already exists")
        
        # Add missing columns
        for column_name, column_def in columns_to_add:
            sql = f"ALTER TABLE bot_settings ADD COLUMN {column_name} {column_def}"
            print(f"Executing: {sql}")
            cursor.execute(sql)
        
        conn.commit()
        conn.close()
        
        if columns_to_add:
            print(f"Successfully added {len(columns_to_add)} columns to bot_settings table")
        else:
            print("No new columns needed to be added")
        
        print("Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = migrate_toggle_settings()
    if success:
        print("You can now restart the application.")
    else:
        print("Migration failed. Please check the error messages above.")