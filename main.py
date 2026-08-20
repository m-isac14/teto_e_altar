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
    # Verifica se a categoria e a meta (goal) existem
    cat = db.query(models.Category).filter(models.Category.id == transaction.category_id).first()
    goal = db.query(models.Goal).filter(models.Goal.id == transaction.goal_id).first()
    
    if not cat:
        raise HTTPException(status_code=400, detail="Categoria não encontrada")
    if not goal:
        raise HTTPException(status_code=400, detail="Meta (Goal) não encontrada")
    
    # Prepara o modelo da transação e o salva no banco
    db_transaction = models.Transaction(
        valor=transaction.valor,
        tipo=transaction.tipo,
        descricao=transaction.descricao,
        user_id=current_user.id,
        category_id=transaction.category_id,
        goal_id=transaction.goal_id
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@app.get("/dashboard", response_model=schemas.DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Obtém um resumo do dashboard: saldo das metas principais e as últimas transações realizadas."""
    # Pega Metas principais (Casamento e Apartamento)
    casamento_goal = db.query(models.Goal).filter(models.Goal.nome == "Casamento").first()
    apartamento_goal = db.query(models.Goal).filter(models.Goal.nome == "Apartamento").first()

    # Função auxiliar para calcular saldo de uma meta (Receitas - Despesas)
    def calcular_saldo(goal_id):
        if not goal_id: return 0.0
        
        receitas = db.query(func.sum(models.Transaction.valor)).filter(
            models.Transaction.goal_id == goal_id,
            models.Transaction.tipo == models.TransactionType.receita
        ).scalar() or 0.0
        
        despesas = db.query(func.sum(models.Transaction.valor)).filter(
            models.Transaction.goal_id == goal_id,
            models.Transaction.tipo == models.TransactionType.despesa
        ).scalar() or 0.0
        
        return receitas - despesas

    # Calcula os totais das metas principais
    total_casamento = calcular_saldo(casamento_goal.id if casamento_goal else None)
    total_apartamento = calcular_saldo(apartamento_goal.id if apartamento_goal else None)

    # Últimas 10 transações conjuntas (independentemente de quem lançou, são todas do casal)
    last_transactions = db.query(models.Transaction).order_by(models.Transaction.data.desc()).limit(10).all()

    return schemas.DashboardSummary(
        total_casamento=total_casamento,
        total_apartamento=total_apartamento,
        last_transactions=last_transactions
    )

@app.get("/categories", response_model=List[schemas.CategoryOut])
def get_categories(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Retorna todas as categorias disponíveis no banco de dados para os selects."""
    return db.query(models.Category).all()

@app.get("/goals", response_model=List[schemas.GoalOut])
def get_goals(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Retorna todas as metas (projetos) disponíveis no banco de dados."""
    return db.query(models.Goal).all()
