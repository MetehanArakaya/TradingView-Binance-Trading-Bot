#!/usr/bin/env python3

from app import create_app, db
from app.models.trade import Trade
from app.models.position import Position

def check_trades_data():
    app = create_app()
    with app.app_context():
        # Get total count
        total_trades = Trade.query.count()
        print(f'Total trades: {total_trades}')
        
        # Get recent trades
        trades = Trade.query.order_by(Trade.created_at.desc()).limit(10).all()
        print(f'\nRecent 10 trades:')
        for trade in trades:
            print(f'Trade {trade.id}: {trade.symbol} {trade.status.value}')
            print(f'  Entry: {trade.entry_price}, Exit: {trade.exit_price}')
            print(f'  PnL: {trade.net_pnl}, Commission: {trade.commission}')
            print(f'  PnL %: {trade.pnl_percentage}')
            print(f'  Opened: {trade.opened_at}')
            print(f'  Closed: {trade.closed_at}')
            print()
        
        # Check for trades that need PnL calculation
        trades_needing_update = Trade.query.filter(
            Trade.entry_price.isnot(None),
            Trade.exit_price.isnot(None),
            Trade.net_pnl == 0.0
        ).all()
        
        print(f'\nTrades needing PnL update: {len(trades_needing_update)}')
        
        if trades_needing_update:
            print('Updating PnL for trades...')
            updated_count = 0
            for trade in trades_needing_update:
                try:
                    trade.calculate_pnl()
                    updated_count += 1
                    print(f'Updated trade {trade.id}: PnL = {trade.net_pnl}, Commission = {trade.commission}')
                except Exception as e:
                    print(f'Error updating trade {trade.id}: {e}')
            
            if updated_count > 0:
                try:
                    db.session.commit()
                    print(f'\nSuccessfully updated {updated_count} trades')
                except Exception as e:
                    print(f'Error committing changes: {e}')
                    db.session.rollback()

if __name__ == '__main__':
    check_trades_data()