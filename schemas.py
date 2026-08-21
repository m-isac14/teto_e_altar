from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from models import TransactionType

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# User Schemas
class UserBase(BaseModel):
    nome: str
    email: EmailStr

class UserOut(UserBase):
    id: int
    class Config:
        from_attributes = True

# Category Schemas (Subcategoria no frontend)
class CategoryCreate(BaseModel):
    nome: str

class CategoryOut(BaseModel):
    id: int
    nome: str
    class Config:
        from_attributes = True


# Transaction Schemas
class TransactionCreate(BaseModel):
    valor: float
    tipo: TransactionType
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    category_id: Optional[int] = None

class TransactionOut(BaseModel):
    id: int
    valor: float
    tipo: TransactionType
    data: datetime
    descricao: Optional[str]
    user: UserOut
    categoria: Optional[str] = None
    category: Optional[CategoryOut] = None
    class Config:
        from_attributes = True

# Dashboard Schemas
class DashboardSummary(BaseModel):
    total_geral: float
    last_transactions: List[TransactionOut]
