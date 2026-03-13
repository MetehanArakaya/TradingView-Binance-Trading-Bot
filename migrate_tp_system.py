#!/usr/bin/env python3
"""
Migration script to add advanced Take Profit system
"""
import sqlite3
import os
from datetime import datetime

def migrate_tp_system():
    """Add advanced TP system fields to settings table"""
    
    db_path = os.path.join('instance', 'trading_bot.db')
    
    if not os.path.exists(db_path):
        print("Database file not found. Please run init_db.py first.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(bot_settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add new TP system columns
        new_columns = [
            ('multiple_tp_enabled', 'BOOLEAN DEFAULT 0'),
            ('tp1_percent', 'REAL DEFAULT 3.0'),
            ('tp2_percent', 'REAL DEFAULT 6.0'),
            ('tp3_percent', 'REAL DEFAULT 9.0'),
            ('tp1_quantity_percent', 'REAL DEFAULT 33.33'),
            ('tp2_quantity_percent', 'REAL DEFAULT 33.33'),
            ('tp3_quantity_percent', 'REAL DEFAULT 33.34'),
            ('trailing_tp_enabled', 'BOOLEAN DEFAULT 0'),
            ('trailing_tp_activation_percent', 'REAL DEFAULT 5.0'),
            ('trailing_tp_callback_percent', 'REAL DEFAULT 2.0'),
            ('auto_move_sl_to_breakeven', 'BOOLEAN DEFAULT 1'),
            ('breakeven_trigger_percent', 'REAL DEFAULT 2.0'),
            ('tp_management_enabled', 'BOOLEAN DEFAULT 1'),
            ('scale_out_enabled', 'BOOLEAN DEFAULT 1'),
            ('risk_free_after_tp1', 'BOOLEAN DEFAULT 1')
        ]
        
        for column_name, column_def in new_columns:
            if column_name not in columns:
                try:
                    cursor.execute(f'ALTER TABLE bot_settings ADD COLUMN {column_name} {column_def}')
                    print(f"[OK] Added column: {column_name}")
                except sqlite3.Error as e:
                    print(f"[ERROR] Error adding column {column_name}: {e}")
        
        # Add TP levels table for position-specific TP management
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tp_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                tp_level INTEGER NOT NULL,
                target_price REAL NOT NULL,
                quantity_percent REAL NOT NULL,
                status TEXT DEFAULT 'PENDING',
                order_id TEXT,
                executed_at DATETIME,
                executed_price REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (position_id) REFERENCES positions (id)
            )
        ''')
        print("[OK] Created tp_levels table")
        
        # Add TP history table for tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                tp_level INTEGER NOT NULL,
                action TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                pnl REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (position_id) REFERENCES positions (id)
            )
        ''')
        print("[OK] Created tp_history table")
        
        conn.commit()
        conn.close()
        
        print("\n[SUCCESS] Advanced TP system migration completed successfully!")
        print("\nNew features added:")
        print("- Multiple TP levels (TP1, TP2, TP3)")
        print("- Partial take profit with custom percentages")
        print("- Trailing take profit")
        print("- Auto move SL to breakeven")
        print("- TP management and scaling")
        print("- Risk-free mode after TP1")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return False

if __name__ == '__main__':
    migrate_tp_system()