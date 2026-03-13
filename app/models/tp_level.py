from app import db
from datetime import datetime

class TPLevel(db.Model):
    """Take Profit Level model for managing multiple TP levels per position"""
    __tablename__ = 'tp_levels'
    
    id = db.Column(db.Integer, primary_key=True)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'), nullable=False)
    tp_level = db.Column(db.Integer, nullable=False)  # 1, 2, 3
    target_price = db.Column(db.Float, nullable=False)
    quantity_percent = db.Column(db.Float, nullable=False)  # Percentage of position to close
    status = db.Column(db.String(20), default='PENDING')  # PENDING, EXECUTED, CANCELLED
    order_id = db.Column(db.String(50))  # Binance order ID
    executed_at = db.Column(db.DateTime)
    executed_price = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    position = db.relationship('Position', backref='tp_levels')
    
    def __repr__(self):
        return f'<TPLevel {self.id}: TP{self.tp_level} @ {self.target_price} ({self.status})>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'position_id': self.position_id,
            'tp_level': self.tp_level,
            'target_price': self.target_price,
            'quantity_percent': self.quantity_percent,
            'status': self.status,
            'order_id': self.order_id,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'executed_price': self.executed_price,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def execute(self, executed_price, order_id=None):
        """Mark TP level as executed"""
        self.status = 'EXECUTED'
        self.executed_price = executed_price
        self.executed_at = datetime.utcnow()
        if order_id:
            self.order_id = order_id
        db.session.commit()
    
    def cancel(self):
        """Cancel TP level"""
        self.status = 'CANCELLED'
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    @classmethod
    def create_tp_levels(cls, position_id, tp_configs):
        """Create multiple TP levels for a position
        
        Args:
            position_id: Position ID
            tp_configs: List of dicts with 'level', 'price', 'quantity_percent'
        """
        tp_levels = []
        for config in tp_configs:
            tp_level = cls(
                position_id=position_id,
                tp_level=config['level'],
                target_price=config['price'],
                quantity_percent=config['quantity_percent']
            )
            db.session.add(tp_level)
            tp_levels.append(tp_level)
        
        db.session.commit()
        return tp_levels
    
    @classmethod
    def get_pending_for_position(cls, position_id):
        """Get all pending TP levels for a position"""
        return cls.query.filter_by(
            position_id=position_id,
            status='PENDING'
        ).order_by(cls.tp_level).all()
    
    @classmethod
    def get_executed_for_position(cls, position_id):
        """Get all executed TP levels for a position"""
        return cls.query.filter_by(
            position_id=position_id,
            status='EXECUTED'
        ).order_by(cls.tp_level).all()


class TPHistory(db.Model):
    """Take Profit History model for tracking TP actions"""
    __tablename__ = 'tp_history'
    
    id = db.Column(db.Integer, primary_key=True)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'), nullable=False)
    tp_level = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20), nullable=False)  # CREATED, EXECUTED, CANCELLED, MODIFIED
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    pnl = db.Column(db.Float)  # Profit/Loss from this TP
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    # Relationship
    position = db.relationship('Position', backref='tp_history')
    
    def __repr__(self):
        return f'<TPHistory {self.id}: TP{self.tp_level} {self.action} @ {self.price}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'position_id': self.position_id,
            'tp_level': self.tp_level,
            'action': self.action,
            'price': self.price,
            'quantity': self.quantity,
            'pnl': self.pnl,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'notes': self.notes
        }
    
    @classmethod
    def log_action(cls, position_id, tp_level, action, price, quantity, pnl=None, notes=None):
        """Log a TP action"""
        history = cls(
            position_id=position_id,
            tp_level=tp_level,
            action=action,
            price=price,
            quantity=quantity,
            pnl=pnl,
            notes=notes
        )
        db.session.add(history)
        db.session.commit()
        return history
    
    @classmethod
    def get_for_position(cls, position_id):
        """Get all TP history for a position"""
        return cls.query.filter_by(position_id=position_id).order_by(cls.timestamp.desc()).all()