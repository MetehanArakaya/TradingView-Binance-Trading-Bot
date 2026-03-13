#!/usr/bin/env python3
"""
Migration script to add pnl_percentage field to trades table
"""

import sqlite3
import os

def migrate_trade_fields():
    """Add pnl_percentage field to trades table"""
    db_path = 'instance/trading_bot.db'
    
    if not os.path.exists(db_path):
        print("Database file not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if pnl_percentage column exists
        cursor.execute("PRAGMA table_info(trades)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'pnl_percentage' not in columns:
            print("Adding pnl_percentage column to trades table...")
            cursor.execute("ALTER TABLE trades ADD COLUMN pnl_percentage REAL DEFAULT 0.0")
            print("SUCCESS: pnl_percentage column added successfully!")
        else:
            print("SUCCESS: pnl_percentage column already exists!")
        
        # Update existing trades to calculate missing values
        print("Updating existing trades with calculated values...")
        cursor.execute("""
            UPDATE trades
            SET commission = CASE
                WHEN commission = 0.0 AND entry_price IS NOT NULL AND quantity IS NOT NULL
                THEN (entry_price * quantity * 0.001)
                ELSE commission
            END,
            pnl_percentage = CASE
                WHEN entry_price IS NOT NULL AND exit_price IS NOT NULL AND entry_price > 0
                THEN (
                    CASE
                        WHEN trade_type = 'long'
                        THEN ((exit_price - entry_price) * quantity * leverage - (entry_price * quantity * 0.001)) / ((entry_price * quantity) / leverage) * 100
                        ELSE ((entry_price - exit_price) * quantity * leverage - (entry_price * quantity * 0.001)) / ((entry_price * quantity) / leverage) * 100
                    END
                )
                ELSE 0.0
            END
            WHERE entry_price IS NOT NULL AND quantity IS NOT NULL
        """)
        
        affected_rows = cursor.rowcount
        print(f"SUCCESS: Updated {affected_rows} trades with calculated values!")
        
        conn.commit()
        conn.close()
        
        print("SUCCESS: Trade fields migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        return False

if __name__ == "__main__":
    migrate_trade_fields()