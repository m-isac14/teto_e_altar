from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import timedelta
import os

import models
import schemas
import auth
from database import engine, get_db

# Cria todas as tabelas no banco de dados, caso elas ainda não existam.
models.Base.metadata.create_all(bind=engine)

# Instancia a aplicação FastAPI, definindo o título da API.
app = FastAPI(title="Teto & Altar API")

# Configura o diretório onde os templates HTML (Jinja2) estão armazenados.
templates = Jinja2Templates(directory="templates")

# ==========================================
# Rotas Web (Frontend)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """Renderiza a página inicial de login (login.html)."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/app", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Renderiza a página principal do dashboard (dashboard.html) após o login."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/subcategorias", response_class=HTMLResponse)
async def subcategories_page(request: Request):
    """Renderiza a página de gestão de subcategorias (categories.html)."""
    return templates.TemplateResponse("categories.html", {"request": request})

# ==========================================
# Rotas da API (Backend)
# ==========================================

@app.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Recebe e-mail e senha, verifica no banco de dados e retorna um token de acesso JWT se válido."""
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    # Verifica se o usuário existe e se a senha está correta
    if not user or not auth.verify_password(form_data.password, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Gera o tempo de expiração e cria o token de acesso
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/transactions", response_model=schemas.TransactionOut)
def create_transaction(
    transaction: schemas.TransactionCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    """Cria uma nova transação (receita ou despesa) associada ao usuário autenticado."""
    # Se for despesa, é obrigatório ter Categoria Principal e Subcategoria
    if transaction.tipo == models.TransactionType.despesa:
        if not transaction.category_id or not transaction.categoria:
            raise HTTPException(status_code=400, detail="Categoria e Subcategoria são obrigatórias para despesas.")
        
        cat = db.query(models.Category).filter(models.Category.id == transaction.category_id).first()
        if not cat:
            raise HTTPException(status_code=400, detail="Subcategoria não encontrada")
            
        if transaction.categoria not in ["Casamento", "Apartamento"]:
            raise HTTPException(status_code=400, detail="Categoria Principal inválida")
    else:
        # Se for receita, forçamos null nestes campos
        transaction.categoria = None
        transaction.category_id = None
    
    # Prepara o modelo da transação e o salva no banco
    db_transaction = models.Transaction(
        valor=transaction.valor,
        tipo=transaction.tipo,
        descricao=transaction.descricao,
        user_id=current_user.id,
        category_id=transaction.category_id,
        categoria=transaction.categoria
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@app.get("/dashboard", response_model=schemas.DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Obtém um resumo do dashboard: saldo do Caixa Geral e as últimas transações realizadas."""
    
    # Calcula o saldo geral do Caixa Único
    receitas = db.query(func.sum(models.Transaction.valor)).filter(
        models.Transaction.tipo == models.TransactionType.receita
    ).scalar() or 0.0
    
    despesas = db.query(func.sum(models.Transaction.valor)).filter(
        models.Transaction.tipo == models.TransactionType.despesa
    ).scalar() or 0.0
    
    total_geral = receitas - despesas

    # Últimas 10 transações conjuntas
    last_transactions = db.query(models.Transaction).order_by(models.Transaction.data.desc()).limit(10).all()

    return schemas.DashboardSummary(
        total_geral=total_geral,
        last_transactions=last_transactions
    )

@app.get("/categories", response_model=List[schemas.CategoryOut])
def get_categories(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Retorna todas as subcategorias disponíveis no banco de dados para os selects e CRUD."""
    return db.query(models.Category).all()

@app.post("/categories", response_model=schemas.CategoryOut)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_cat = models.Category(nome=category.nome)
    db.add(db_cat)
    db.commit()
    db.refresh(db_cat)
    return db_cat

@app.put("/categories/{cat_id}", response_model=schemas.CategoryOut)
def update_category(cat_id: int, category: schemas.CategoryCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
    if not db_cat:
        raise HTTPException(status_code=404, detail="Subcategoria não encontrada")
    
    db_cat.nome = category.nome
    db.commit()
    db.refresh(db_cat)
    return db_cat

@app.delete("/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
    if not db_cat:
        raise HTTPException(status_code=404, detail="Subcategoria não encontrada")
        
    # Block deletion if transactions are linked
    tx_count = db.query(models.Transaction).filter(models.Transaction.category_id == cat_id).count()
    if tx_count > 0:
        raise HTTPException(status_code=400, detail=f"Esta subcategoria não pode ser apagada pois possui {tx_count} gastos.")
        
    db.delete(db_cat)
    db.commit()
    return {"ok": True}
