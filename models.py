from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import pytz
import enum

def get_br_time():
    return datetime.now(pytz.timezone('America/Sao_Paulo'))

class TransactionType(str, enum.Enum):
    receita = "receita"
    despesa = "despesa"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)

    transactions = relationship("Transaction", back_populates="user")


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(50), nullable=False) # Casamento ou Apartamento
    valor_objetivo = Column(Float, nullable=False)

    transactions = relationship("Transaction", back_populates="goal")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(50), nullable=False)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)

    transactions = relationship("Transaction", back_populates="category")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    valor = Column(Float, nullable=False)
    tipo = Column(Enum(TransactionType), nullable=False) # receita ou despesa
    data = Column(DateTime, default=get_br_time, nullable=False)
    descricao = Column(String(255), nullable=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)

    user = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    goal = relationship("Goal", back_populates="transactions")
