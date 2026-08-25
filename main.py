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

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    """Renderiza a página de relatórios (reports.html)."""
    return templates.TemplateResponse("reports.html", {"request": request})

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

@app.get("/api/reports")
def get_reports(period: str = "30d", db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Retorna os dados agregados para os gráficos do Dashboard Financeiro."""
    import pytz
    from datetime import datetime, timedelta
    
    br_tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(br_tz)
    
    if period == '30d':
        start_date = now - timedelta(days=30)
        date_format = '%d/%m'
    elif period == 'year':
        start_date = datetime(now.year, 1, 1, tzinfo=br_tz)
        date_format = '%m/%Y'
    else: # all
        start_date = datetime(2000, 1, 1, tzinfo=br_tz)
        date_format = '%m/%Y'

    # Remove timezone for DB comparison if the DB stores naive datetimes
    start_date_naive = start_date.replace(tzinfo=None)

    all_txs = db.query(models.Transaction).order_by(models.Transaction.data.asc()).all()

    initial_balance = 0.0
    evolution_dict = {}
    cashflow_dict = {}
    distribution_dict = {}

    for tx in all_txs:
        # Check if transaction is before the period to compute starting balance
        if tx.data < start_date_naive:
            if tx.tipo == models.TransactionType.receita:
                initial_balance += tx.valor
            else:
                initial_balance -= tx.valor
            continue
        
        # Determine the label for evolution based on period
        label = tx.data.strftime(date_format)
        month_label = tx.data.strftime('%m/%Y')
        
        # 1. Evolution (Saldo Geral)
        # We will track the balance on each transaction date
        if label not in evolution_dict:
            evolution_dict[label] = 0.0

        if tx.tipo == models.TransactionType.receita:
            initial_balance += tx.valor
        else:
            initial_balance -= tx.valor
            
        # At this point, the initial_balance acts as the running total
        evolution_dict[label] = initial_balance

        # 2. Cashflow (Fluxo de Caixa)
        if month_label not in cashflow_dict:
            cashflow_dict[month_label] = {'entradas': 0.0, 'saidas': 0.0}
        
        if tx.tipo == models.TransactionType.receita:
            cashflow_dict[month_label]['entradas'] += tx.valor
        else:
            cashflow_dict[month_label]['saidas'] += tx.valor

        # 3. Distribution (Distribuição de Gastos)
        if tx.tipo == models.TransactionType.despesa and tx.categoria:
            main_cat = tx.categoria
            sub_cat = tx.category.nome if tx.category else 'Outros'
            
            if main_cat not in distribution_dict:
                distribution_dict[main_cat] = {'total': 0.0, 'subcategories': {}}
            
            distribution_dict[main_cat]['total'] += tx.valor
            
            if sub_cat not in distribution_dict[main_cat]['subcategories']:
                distribution_dict[main_cat]['subcategories'][sub_cat] = 0.0
            
            distribution_dict[main_cat]['subcategories'][sub_cat] += tx.valor

    # Formatting responses for frontend
    # Evolution: We want a list of labels and a list of data
    evolution_labels = list(evolution_dict.keys())
    evolution_data = list(evolution_dict.values())
    
    # If there were no transactions in the period, add one point with the initial balance
    if not evolution_labels:
        evolution_labels.append(now.strftime(date_format))
        evolution_data.append(initial_balance)

    # Cashflow
    cashflow_labels = list(cashflow_dict.keys())
    cashflow_entradas = [cashflow_dict[k]['entradas'] for k in cashflow_labels]
    cashflow_saidas = [cashflow_dict[k]['saidas'] for k in cashflow_labels]
    
    # Distribution
    dist_labels = list(distribution_dict.keys())
    dist_data = [distribution_dict[k]['total'] for k in dist_labels]
    
    # Format subcategories as a clean dict for easy mapping in JS
    dist_sub = {
        k: [{"nome": sub_k, "valor": sub_v} for sub_k, sub_v in distribution_dict[k]['subcategories'].items()]
        for k in dist_labels
    }

    return {
        "evolution": {
            "labels": evolution_labels,
            "data": evolution_data
        },
        "cashflow": {
            "labels": cashflow_labels,
            "entradas": cashflow_entradas,
            "saidas": cashflow_saidas
        },
        "distribution": {
            "labels": dist_labels,
            "data": dist_data,
            "subcategories": dist_sub
        }
    }
