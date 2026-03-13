#!/usr/bin/env python3
"""
Stop Loss System Migration Script
Adds new Stop Loss fields to bot_settings table
"""

import sqlite3
import os
from datetime import datetime

def migrate_stop_loss_system():
    """Add new Stop Loss system fields to bot_settings table"""
    
    db_path = os.path.join('instance', 'trading_bot.db')
    
    if not os.path.exists(db_path):
        print("❌ Veritabanı dosyası bulunamadı!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("Stop Loss sistemi migration baslatiliyor...")
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(bot_settings)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        # New Stop Loss fields to add
        new_fields = [
            # Percentage-based Stop Loss Settings
            ('percentage_sl_enabled', 'BOOLEAN DEFAULT 0'),
            ('percentage_sl_percent', 'REAL DEFAULT 3.0'),
            ('percentage_sl_portfolio_base', 'BOOLEAN DEFAULT 0'),
            
            # ATR-based Dynamic Stop Loss Settings
            ('atr_sl_enabled', 'BOOLEAN DEFAULT 0'),
            ('atr_sl_period', 'INTEGER DEFAULT 14'),
            ('atr_sl_multiplier', 'REAL DEFAULT 2.0'),
            ('atr_sl_dynamic', 'BOOLEAN DEFAULT 0'),
            
            # Breakeven Stop Loss Settings
            ('breakeven_sl_enabled', 'BOOLEAN DEFAULT 0'),
            ('breakeven_sl_activation_percent', 'REAL DEFAULT 2.0'),
            ('breakeven_sl_offset', 'REAL DEFAULT 0.1'),
            
            # Advanced Stop Loss Features
            ('sl_partial_close', 'BOOLEAN DEFAULT 0'),
            ('sl_partial_close_percent', 'REAL DEFAULT 50.0'),
            ('sl_time_based_exit', 'BOOLEAN DEFAULT 0'),
            ('sl_max_position_hours', 'INTEGER DEFAULT 24'),
        ]
        
        # Add missing columns
        added_count = 0
        for field_name, field_type in new_fields:
            if field_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE bot_settings ADD COLUMN {field_name} {field_type}")
                    print(f"[OK] {field_name} alani eklendi")
                    added_count += 1
                except sqlite3.Error as e:
                    print(f"[ERROR] {field_name} alani eklenirken hata: {e}")
            else:
                print(f"[WARNING] {field_name} alani zaten mevcut")
        
        conn.commit()
        
        if added_count > 0:
            print(f"\nMigration tamamlandi! {added_count} yeni alan eklendi.")
        else:
            print("\nTum alanlar zaten mevcut, migration gerekli degil.")
        
        # Verify the migration
        cursor.execute("PRAGMA table_info(bot_settings)")
        all_columns = [column[1] for column in cursor.fetchall()]
        
        print(f"\nToplam alan sayisi: {len(all_columns)}")
        
        # Check if all new fields are present
        missing_fields = []
        for field_name, _ in new_fields:
            if field_name not in all_columns:
                missing_fields.append(field_name)
        
        if missing_fields:
            print(f"[ERROR] Eksik alanlar: {', '.join(missing_fields)}")
            return False
        else:
            print("[OK] Tum Stop Loss alanlari basariyla eklendi!")
            return True
            
    except sqlite3.Error as e:
        print(f"[ERROR] Veritabani hatasi: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Beklenmeyen hata: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("STOP LOSS SYSTEM MIGRATION")
    print("=" * 60)
    print(f"Baslangic zamani: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = migrate_stop_loss_system()
    
    print()
    print("=" * 60)
    if success:
        print("Migration basariyla tamamlandi!")
        print("Uygulamayi yeniden baslatabilirsiniz.")
    else:
        print("Migration basarisiz!")
        print("Hata detaylarini kontrol edin.")
    print("=" * 60)