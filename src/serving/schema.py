
"""
SQLAlchemy Models for Local Paper Trading Simulation.
Persists portfolio state to PostgreSQL to bypass exchange demo limitations.
"""
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Enum as SqEnum
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import enum

Base = declarative_base()

class OrderSide(enum.Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(enum.Enum):
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"

class SimulationAccount(Base):
    __tablename__ = 'simulation_accounts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)  # e.g. "OKX_Paper"
    balance = Column(Float, default=10000.0) # Cash (USDT)
    equity = Column(Float, default=10000.0)  # Total Equity
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    positions = relationship("Position", back_populates="account", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="account")

class Position(Base):
    __tablename__ = 'positions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('simulation_accounts.id'), nullable=False)
    symbol = Column(String, nullable=False) # e.g. BTC/USDT
    
    amount = Column(Float, default=0.0)      # Quantity held
    entry_price = Column(Float, default=0.0) # Avg Entry Price
    current_price = Column(Float, default=0.0) # Last Mark Price
    unrealized_pnl = Column(Float, default=0.0)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    account = relationship("SimulationAccount", back_populates="positions")

class Order(Base):
    __tablename__ = 'orders'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('simulation_accounts.id'), nullable=False)
    
    symbol = Column(String, nullable=False)
    side = Column(SqEnum(OrderSide), nullable=False)
    type = Column(String, default="market")
    
    amount = Column(Float, nullable=False) # Executed amount
    price = Column(Float, nullable=False)  # Executed price
    fee = Column(Float, default=0.0)       # Fee paid
    
    status = Column(SqEnum(OrderStatus), default=OrderStatus.FILLED)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    account = relationship("SimulationAccount", back_populates="orders")
