#!/usr/bin/env python3
"""
Database migration script to add telegram_notifications_enabled column
"""

import sqlite3
import os

def migrate_database():
    """Add telegram_notifications_enabled column to bot_settings table"""
    db_path = 'instance/trading_bot.db'
    conn = None
    
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found!")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(bot_settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'telegram_notifications_enabled' in columns:
            print("Column 'telegram_notifications_enabled' already exists!")
            return True
        
        # Add the new column
        cursor.execute("""
            ALTER TABLE bot_settings
            ADD COLUMN telegram_notifications_enabled BOOLEAN DEFAULT 1
        """)
        
        # Update existing records to have notifications enabled by default
        cursor.execute("""
            UPDATE bot_settings
            SET telegram_notifications_enabled = 1
            WHERE telegram_notifications_enabled IS NULL
        """)
        
        conn.commit()
        print("Successfully added 'telegram_notifications_enabled' column to bot_settings table!")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(bot_settings)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Starting database migration...")
    success = migrate_database()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")