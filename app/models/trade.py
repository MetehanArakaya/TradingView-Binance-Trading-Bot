from app import db
from datetime import datetime
from enum import Enum

class TradeStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    ERROR = "error"

class TradeType(Enum):
    LONG = "long"
    SHORT = "short"

class Trade(db.Model):
    __tablename__ = 'trades'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Trade identification
    signal_id = db.Column(db.Integer, db.ForeignKey('signals.id'), nullable=False)
    binance_order_id = db.Column(db.String(50), unique=True)
    
    # Trade details
    symbol = db.Column(db.String(20), nullable=False)
    trade_type = db.Column(db.Enum(TradeType), nullable=False)
    status = db.Column(db.Enum(TradeStatus), default=TradeStatus.PENDING)
    
    # Price and quantity
    entry_price = db.Column(db.Float)
    exit_price = db.Column(db.Float)
    quantity = db.Column(db.Float, nullable=False)
    leverage = db.Column(db.Integer, default=10)
    
    # Risk management
    stop_loss = db.Column(db.Float)
    take_profit = db.Column(db.Float)
    
    # Financial results
    pnl = db.Column(db.Float, default=0.0)  # Profit and Loss
    commission = db.Column(db.Float, default=0.0)
    net_pnl = db.Column(db.Float, default=0.0)  # PnL after commission
    pnl_percentage = db.Column(db.Float, default=0.0)  # PnL percentage
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    opened_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    
    # Error handling
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    
    # Relationships
    signal = db.relationship('Signal', backref=db.backref('trades', lazy=True))
    
    def __repr__(self):
        return f'<Trade {self.id}: {self.symbol} {self.trade_type.value} {self.status.value}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'trade_type': self.trade_type.value,
            'status': self.status.value,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'leverage': self.leverage,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'pnl': self.pnl,
            'commission': self.commission,
            'net_pnl': self.net_pnl,
            'pnl_percentage': self.pnl_percentage,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'error_message': self.error_message
        }
    
    def calculate_pnl(self):
        """Calculate PnL based on entry and exit prices"""
        if not self.entry_price or not self.exit_price:
            return 0.0
        
        if self.trade_type == TradeType.LONG:
            pnl = (self.exit_price - self.entry_price) * self.quantity
        else:  # SHORT
            pnl = (self.entry_price - self.exit_price) * self.quantity
        
        # Apply leverage to PnL
        pnl = pnl * self.leverage
        
        # Calculate commission (0.1% for futures trading)
        if not self.commission:
            notional_value = self.entry_price * self.quantity
            self.commission = notional_value * 0.001  # 0.1% commission
        
        self.pnl = pnl
        self.net_pnl = pnl - self.commission
        
        # Calculate PnL percentage
        if self.entry_price and self.entry_price > 0:
            initial_margin = (self.entry_price * self.quantity) / self.leverage
            if initial_margin > 0:
                self.pnl_percentage = (self.net_pnl / initial_margin) * 100
        
        return self.net_pnl
    
    def calculate_commission(self):
        """Calculate trading commission"""
        if self.entry_price and self.quantity:
            notional_value = self.entry_price * self.quantity
            self.commission = notional_value * 0.001  # 0.1% commission
            return self.commission
        return 0.0