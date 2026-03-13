#!/usr/bin/env python3
"""
Close all open positions in database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.position import Position, PositionStatus
from datetime import datetime

def close_all_positions():
    app = create_app()
    
    with app.app_context():
        print("=== TÜM AÇIK POZİSYONLARI KAPATMA ===")
        
        # Get all open positions
        open_positions = Position.get_open_positions()
        print(f"Kapatılacak açık pozisyon sayısı: {len(open_positions)}")
        
        if not open_positions:
            print("Kapatılacak açık pozisyon bulunamadı.")
            return
        
        # Confirm action
        confirm = input(f"\n{len(open_positions)} açık pozisyonu kapatmak istediğinizden emin misiniz? (y/N): ")
        if confirm.lower() != 'y':
            print("İşlem iptal edildi.")
            return
        
        closed_count = 0
        
        for pos in open_positions:
            try:
                print(f"Kapatılıyor: {pos.symbol} (ID: {pos.id})")
                
                # Close position manually in database
                pos.status = PositionStatus.CLOSED
                pos.closed_at = datetime.utcnow()
                pos.mark_price = pos.entry_price  # Use entry price as closing price
                
                # Calculate realized PnL as 0 (manual close)
                pos.realized_pnl = 0.0
                pos.unrealized_pnl = 0.0
                
                closed_count += 1
                
            except Exception as e:
                print(f"Hata - {pos.symbol} kapatılamadı: {e}")
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\n✅ Başarıyla {closed_count} pozisyon kapatıldı!")
            
            # Verify
            remaining_open = Position.get_open_positions()
            print(f"Kalan açık pozisyon sayısı: {len(remaining_open)}")
            
        except Exception as e:
            print(f"❌ Veritabanı hatası: {e}")
            db.session.rollback()

if __name__ == "__main__":
    close_all_positions()