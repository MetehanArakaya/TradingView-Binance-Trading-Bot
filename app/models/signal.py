from app import db
from datetime import datetime
from enum import Enum

class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"

class SignalStatus(Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    PROCESSED = "processed"
    REJECTED = "rejected"
    ERROR = "error"

class Signal(db.Model):
    __tablename__ = 'signals'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Signal identification
    external_id = db.Column(db.String(100))  # TradingView alert ID if available
    
    # Signal details
    symbol = db.Column(db.String(20), nullable=False)
    signal_type = db.Column(db.Enum(SignalType), nullable=False)
    status = db.Column(db.Enum(SignalStatus), default=SignalStatus.RECEIVED)
    
    # Price information
    price = db.Column(db.Float)
    stop_loss = db.Column(db.Float)
    take_profit = db.Column(db.Float)
    
    # Raw webhook data
    raw_data = db.Column(db.Text)  # Store original JSON
    
    # Processing information
    processed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Source information
    source_ip = db.Column(db.String(45))  # IPv6 support
    user_agent = db.Column(db.String(255))
    
    def __repr__(self):
        return f'<Signal {self.id}: {self.symbol} {self.signal_type.value} {self.status.value}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'external_id': self.external_id,
            'symbol': self.symbol,
            'signal_type': self.signal_type.value,
            'status': self.status.value,
            'price': self.price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'error_message': self.error_message,
            'source_ip': self.source_ip
        }
    
    def is_valid(self):
        """Basic validation of signal data"""
        if not self.symbol or not self.signal_type:
            return False
        
        # Symbol should be valid format (e.g., BTCUSDT, BTCUSDT.P)
        # Remove .P suffix for validation if present
        symbol_clean = self.symbol.replace('.P', '') if self.symbol.endswith('.P') else self.symbol
        if len(symbol_clean) < 6 or not symbol_clean.isalnum():
            return False
        
        # Price validation for BUY/SELL signals (CLOSE signals don't need price)
        if self.signal_type in [SignalType.BUY, SignalType.SELL]:
            # Price is optional - if not provided, current market price will be used
            if self.price is not None and self.price <= 0:
                return False
        
        # Stop loss should be reasonable if provided
        if self.stop_loss and self.price:
            if self.signal_type == SignalType.BUY and self.stop_loss >= self.price:
                return False
            if self.signal_type == SignalType.SELL and self.stop_loss <= self.price:
                return False
        
        # Take profit should be reasonable if provided
        if self.take_profit and self.price:
            if self.signal_type == SignalType.BUY and self.take_profit <= self.price:
                return False
            if self.signal_type == SignalType.SELL and self.take_profit >= self.price:
                return False
        
        return True
    
    def mark_processed(self):
        """Mark signal as processed"""
        self.status = SignalStatus.PROCESSED
        self.processed_at = datetime.utcnow()
    
    def mark_rejected(self, reason):
        """Mark signal as rejected with reason"""
        self.status = SignalStatus.REJECTED
        self.error_message = reason
        self.processed_at = datetime.utcnow()
    
    def mark_error(self, error_message):
        """Mark signal as error with message"""
        self.status = SignalStatus.ERROR
        self.error_message = error_message
        self.processed_at = datetime.utcnow()