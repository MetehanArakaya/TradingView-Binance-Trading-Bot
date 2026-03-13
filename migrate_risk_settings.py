"""
Database migration script for risk management settings
Adds missing columns: daily_loss_limit, max_risk_percent
"""

import sqlite3
import os

def migrate_risk_settings():
    """Add missing risk management columns to bot_settings table"""
    
    # Database path
    db_path = os.path.join('instance', 'trading_bot.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(bot_settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        migrations_needed = []
        
        # Check for daily_loss_limit column
        if 'daily_loss_limit' not in columns:
            migrations_needed.append(
                "ALTER TABLE bot_settings ADD COLUMN daily_loss_limit REAL DEFAULT 0.0"
            )
            print("+ daily_loss_limit column will be added")
        else:
            print("+ daily_loss_limit column already exists")
        
        # Check for max_risk_percent column
        if 'max_risk_percent' not in columns:
            migrations_needed.append(
                "ALTER TABLE bot_settings ADD COLUMN max_risk_percent REAL DEFAULT 20.0"
            )
            print("+ max_risk_percent column will be added")
        else:
            print("+ max_risk_percent column already exists")
        
        # Check for testnet_mode column
        if 'testnet_mode' not in columns:
            migrations_needed.append(
                "ALTER TABLE bot_settings ADD COLUMN testnet_mode BOOLEAN DEFAULT 1"
            )
            print("+ testnet_mode column will be added")
        else:
            print("+ testnet_mode column already exists")
        
        # Execute migrations
        if migrations_needed:
            for migration in migrations_needed:
                print(f"Executing: {migration}")
                cursor.execute(migration)
            
            # Commit changes
            conn.commit()
            print(f"Successfully added {len(migrations_needed)} columns to bot_settings table")
        else:
            print("All columns already exist, no migration needed")
        
        # Close connection
        conn.close()
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    print("Starting risk settings migration...")
    success = migrate_risk_settings()
    
    if success:
        print("Migration completed successfully!")
        print("You can now restart the application.")
    else:
        print("Migration failed!")