#!/usr/bin/env python3
"""
Check current positions in database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.position import Position, PositionStatus
from app.models.settings import BotSettings

def check_positions():
    app = create_app()
    
    with app.app_context():
        print("=== POZISYON DURUMU ===")
        
        # Get settings
        settings = BotSettings.get_settings()
        print(f"Maksimum eş zamanlı pozisyon limiti: {settings.max_concurrent_positions}")
        
        # Get all positions
        all_positions = Position.query.all()
        print(f"\nToplam pozisyon sayısı: {len(all_positions)}")
        
        # Get open positions
        open_positions = Position.get_open_positions()
        print(f"Açık pozisyon sayısı: {len(open_positions)}")
        
        if open_positions:
            print("\n=== AÇIK POZİSYONLAR ===")
            for pos in open_positions:
                print(f"ID: {pos.id}, Symbol: {pos.symbol}, Side: {pos.side.value}, Status: {pos.status.value}")
                print(f"  Açılış: {pos.opened_at}, Kapanış: {pos.closed_at}")
                print(f"  Entry Price: {pos.entry_price}, Size: {pos.size}")
                print("---")
        
        # Get closed positions
        closed_positions = Position.query.filter_by(status=PositionStatus.CLOSED).all()
        print(f"\nKapalı pozisyon sayısı: {len(closed_positions)}")
        
        if closed_positions:
            print("\n=== KAPALI POZİSYONLAR (Son 5) ===")
            for pos in closed_positions[-5:]:
                print(f"ID: {pos.id}, Symbol: {pos.symbol}, Side: {pos.side.value}, Status: {pos.status.value}")
                print(f"  Açılış: {pos.opened_at}, Kapanış: {pos.closed_at}")
                print(f"  Entry Price: {pos.entry_price}, Size: {pos.size}")
                print("---")

if __name__ == "__main__":
    check_positions()