from app import db
from datetime import datetime
from enum import Enum

class PositionStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"

class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"

class Position(db.Model):
    __tablename__ = 'positions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Position identification
    symbol = db.Column(db.String(20), nullable=False)
    binance_position_id = db.Column(db.String(50))
    
    # Position details
    side = db.Column(db.Enum(PositionSide), nullable=False)
    status = db.Column(db.Enum(PositionStatus), default=PositionStatus.OPEN)
    
    # Size and leverage
    size = db.Column(db.Float, nullable=False)  # Position size in base currency
    notional = db.Column(db.Float, nullable=False)  # Position value in USDT
    leverage = db.Column(db.Integer, default=10)
    
    # Price information
    entry_price = db.Column(db.Float, nullable=False)
    mark_price = db.Column(db.Float)  # Current mark price
    liquidation_price = db.Column(db.Float)
    
    # Risk management
    stop_loss_price = db.Column(db.Float)
    take_profit_price = db.Column(db.Float)
    trailing_stop_price = db.Column(db.Float)
    
    # PnL tracking
    unrealized_pnl = db.Column(db.Float, default=0.0)
    realized_pnl = db.Column(db.Float, default=0.0)
    total_commission = db.Column(db.Float, default=0.0)
    
    # Margin information
    initial_margin = db.Column(db.Float)
    maintenance_margin = db.Column(db.Float)
    
    # Timestamps
    opened_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Related trades
    opening_trade_id = db.Column(db.Integer, db.ForeignKey('trades.id'))
    closing_trade_id = db.Column(db.Integer, db.ForeignKey('trades.id'))
    
    # Relationships
    opening_trade = db.relationship('Trade', foreign_keys=[opening_trade_id], backref='opened_position')
    closing_trade = db.relationship('Trade', foreign_keys=[closing_trade_id], backref='closed_position')
    
    def __repr__(self):
        return f'<Position {self.id}: {self.symbol} {self.side.value} {self.status.value}>'
    
    def calculate_unrealized_pnl(self, current_price=None):
        """Calculate unrealized PnL based on current price"""
        if not current_price:
            current_price = self.mark_price
        
        if not current_price or self.status != PositionStatus.OPEN:
            return 0.0
        
        if self.side == PositionSide.LONG:
            pnl = (current_price - self.entry_price) * self.size
        else:  # SHORT
            pnl = (self.entry_price - current_price) * self.size
        
        self.unrealized_pnl = pnl
        return pnl
    
    def calculate_pnl_percentage(self, current_price=None):
        """Calculate PnL as percentage of initial margin"""
        pnl = self.calculate_unrealized_pnl(current_price)
        if not self.initial_margin or self.initial_margin == 0:
            return 0.0
        return (pnl / self.initial_margin) * 100
    
    def update_mark_price(self, new_price):
        """Update mark price and recalculate PnL"""
        self.mark_price = new_price
        self.calculate_unrealized_pnl(new_price)
        self.updated_at = datetime.utcnow()
    
    def should_stop_loss(self, current_price=None):
        """Check if position should be closed due to stop loss"""
        if not self.stop_loss_price or self.status != PositionStatus.OPEN:
            return False
        
        if not current_price:
            current_price = self.mark_price
        
        if not current_price:
            return False
        
        if self.side == PositionSide.LONG:
            return current_price <= self.stop_loss_price
        else:  # SHORT
            return current_price >= self.stop_loss_price
    
    def should_take_profit(self, current_price=None):
        """Check if position should be closed due to take profit"""
        if not self.take_profit_price or self.status != PositionStatus.OPEN:
            return False
        
        if not current_price:
            current_price = self.mark_price
        
        if not current_price:
            return False
        
        if self.side == PositionSide.LONG:
            return current_price >= self.take_profit_price
        else:  # SHORT
            return current_price <= self.take_profit_price
    
    def update_trailing_stop(self, current_price, trailing_percent):
        """Update trailing stop price"""
        if self.status != PositionStatus.OPEN or not current_price:
            return
        
        if self.side == PositionSide.LONG:
            # For long positions, trailing stop moves up with price
            new_trailing_stop = current_price * (1 - trailing_percent / 100)
            if not self.trailing_stop_price or new_trailing_stop > self.trailing_stop_price:
                self.trailing_stop_price = new_trailing_stop
        else:  # SHORT
            # For short positions, trailing stop moves down with price
            new_trailing_stop = current_price * (1 + trailing_percent / 100)
            if not self.trailing_stop_price or new_trailing_stop < self.trailing_stop_price:
                self.trailing_stop_price = new_trailing_stop
    
    def should_trailing_stop(self, current_price=None):
        """Check if position should be closed due to trailing stop"""
        if not self.trailing_stop_price or self.status != PositionStatus.OPEN:
            return False
        
        if not current_price:
            current_price = self.mark_price
        
        if not current_price:
            return False
        
        if self.side == PositionSide.LONG:
            return current_price <= self.trailing_stop_price
        else:  # SHORT
            return current_price >= self.trailing_stop_price
    
    def close_position(self, closing_price, realized_pnl=None):
        """Close the position"""
        self.status = PositionStatus.CLOSED
        self.closed_at = datetime.utcnow()
        self.mark_price = closing_price
        
        if realized_pnl is not None:
            self.realized_pnl = realized_pnl
        else:
            self.realized_pnl = self.calculate_unrealized_pnl(closing_price)
        
        self.unrealized_pnl = 0.0
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side.value,
            'status': self.status.value,
            'size': self.size,
            'notional': self.notional,
            'leverage': self.leverage,
            'entry_price': self.entry_price,
            'mark_price': self.mark_price,
            'liquidation_price': self.liquidation_price,
            'stop_loss_price': self.stop_loss_price,
            'take_profit_price': self.take_profit_price,
            'trailing_stop_price': self.trailing_stop_price,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_commission': self.total_commission,
            'initial_margin': self.initial_margin,
            'maintenance_margin': self.maintenance_margin,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'pnl_percentage': self.calculate_pnl_percentage()
        }
    
    @classmethod
    def get_open_positions(cls):
        """Get all open positions"""
        return cls.query.filter_by(status=PositionStatus.OPEN).all()
    
    @classmethod
    def get_position_by_symbol(cls, symbol):
        """Get open position for a specific symbol"""
        return cls.query.filter_by(symbol=symbol, status=PositionStatus.OPEN).first()