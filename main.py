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

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Renderiza a página de logs (logs.html)."""
    return templates.TemplateResponse("logs.html", {"request": request})

# ==========================================
# Funções Utilitárias
# ==========================================
def create_log(db: Session, user_id: int, acao: str, entidade: str, detalhes: str = None):
    db_log = models.AuditLog(
        user_id=user_id,
        acao=acao,
        entidade=entidade,
        detalhes=detalhes
    )
    db.add(db_log)
    db.commit()

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
    
    # Registra o log
    create_log(
        db, current_user.id, "CRIAR", "Transação",
        f"Criou {transaction.tipo.value} no valor de R$ {transaction.valor:.2f}"
    )
    
    return db_transaction

@app.put("/transactions/{tx_id}", response_model=schemas.TransactionOut)
def update_transaction(tx_id: int, transaction_update: schemas.TransactionUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_transaction = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
        
    old_valor = db_transaction.valor
    old_descricao = db_transaction.descricao
    old_categoria = db_transaction.categoria
    old_category_id = db_transaction.category_id

    if transaction_update.valor is not None:
        db_transaction.valor = transaction_update.valor
    if transaction_update.descricao is not None:
        db_transaction.descricao = transaction_update.descricao
        
    if db_transaction.tipo == models.TransactionType.despesa:
        if transaction_update.categoria is not None:
            if transaction_update.categoria not in ["Casamento", "Apartamento"]:
                raise HTTPException(status_code=400, detail="Categoria Principal inválida")
            db_transaction.categoria = transaction_update.categoria
        if transaction_update.category_id is not None:
            cat = db.query(models.Category).filter(models.Category.id == transaction_update.category_id).first()
            if not cat:
                raise HTTPException(status_code=400, detail="Subcategoria não encontrada")
            db_transaction.category_id = transaction_update.category_id
            
    db.commit()
    db.refresh(db_transaction)
    
    # Montar log de alterações
    alteracoes = []
    if old_valor != db_transaction.valor: alteracoes.append(f"valor de R$ {old_valor:.2f} para R$ {db_transaction.valor:.2f}")
    if old_descricao != db_transaction.descricao: alteracoes.append(f"descrição de '{old_descricao}' para '{db_transaction.descricao}'")
    if old_categoria != db_transaction.categoria: alteracoes.append(f"projeto de '{old_categoria}' para '{db_transaction.categoria}'")
    if old_category_id != db_transaction.category_id: alteracoes.append(f"subcategoria ID de {old_category_id} para {db_transaction.category_id}")
    
    detalhes = f"Alterou {db_transaction.tipo.value}: " + ", ".join(alteracoes) if alteracoes else "Nenhuma alteração registrada."
    
    create_log(
        db, current_user.id, "EDITAR", "Transação",
        detalhes[:500]
    )
    
    return db_transaction

@app.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_transaction = db.query(models.Transaction).filter(models.Transaction.id == tx_id).first()
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
        
    tipo = db_transaction.tipo.value
    valor = db_transaction.valor
    descricao = db_transaction.descricao or "Sem descrição"
    
    db.delete(db_transaction)
    db.commit()
    
    create_log(
        db, current_user.id, "EXCLUIR", "Transação",
        f"Excluiu {tipo} no valor de R$ {valor:.2f} ({descricao})"
    )
    
    return {"ok": True}


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
    
    create_log(db, current_user.id, "CRIAR", "Subcategoria", f"Criou a subcategoria '{db_cat.nome}'")
    return db_cat

@app.put("/categories/{cat_id}", response_model=schemas.CategoryOut)
def update_category(cat_id: int, category: schemas.CategoryCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
    if not db_cat:
        raise HTTPException(status_code=404, detail="Subcategoria não encontrada")
    
    nome_antigo = db_cat.nome
    db_cat.nome = category.nome
    db.commit()
    db.refresh(db_cat)
    
    create_log(db, current_user.id, "EDITAR", "Subcategoria", f"Alterou subcategoria de '{nome_antigo}' para '{db_cat.nome}'")
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
        
    nome_apagado = db_cat.nome
    db.delete(db_cat)
    db.commit()
    
    create_log(db, current_user.id, "EXCLUIR", "Subcategoria", f"Apagou a subcategoria '{nome_apagado}'")
    return {"ok": True}

@app.get("/api/logs", response_model=List[schemas.AuditLogOut])
def get_audit_logs(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Retorna o histórico de logs de auditoria do sistema."""
    logs = db.query(models.AuditLog).order_by(models.AuditLog.data.desc()).all()
    return logs
