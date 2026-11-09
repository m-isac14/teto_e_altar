from __future__ import annotations
import os
import sys
import json
import logging
from datetime import datetime, date
import pytz
import bcrypt
import streamlit as st

# Tentativa de carregar SQLAlchemy
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    HAS_SQLALCHEMY = True
except Exception:
    create_engine = None
    text = None
    Engine = object
    HAS_SQLALCHEMY = False

logger = logging.getLogger("teto_altar_db")

# Timezone de Brasília
BR_TZ = pytz.timezone("America/Sao_Paulo")

def get_br_now() -> datetime:
    return datetime.now(BR_TZ)

# Diretório e arquivos locais (para modo fallback / offline)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CATEGORIES_FILE = os.path.join(DATA_DIR, "categories.json")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.json")
AUDIT_LOGS_FILE = os.path.join(DATA_DIR, "audit_logs.json")

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)

def _read_json(filepath: str, default=None):
    ensure_data_dir()
    if not os.path.exists(filepath):
        return default if default is not None else []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao ler {filepath}: {e}")
        return default if default is not None else []

def _write_json(filepath: str, data):
    ensure_data_dir()
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Erro ao gravar {filepath}: {e}")
        return False

# ==========================================
# Conexão com Supabase / PostgreSQL
# ==========================================
def get_database_url() -> str | None:
    """Recupera a URL de conexão do PostgreSQL de st.secrets ou variável de ambiente."""
    # 0. Tenta carregar diretamente do arquivo local .streamlit/secrets.toml
    secrets_file = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if os.path.exists(secrets_file):
        try:
            import tomllib
            with open(secrets_file, "rb") as f:
                sec_data = tomllib.load(f)
                if "connections" in sec_data and "postgresql" in sec_data["connections"]:
                    cfg = sec_data["connections"]["postgresql"]
                    if isinstance(cfg, dict) and "url" in cfg:
                        return cfg["url"]
                    if isinstance(cfg, str):
                        return cfg
                if "DATABASE_URL" in sec_data:
                    return sec_data["DATABASE_URL"]
        except Exception:
            pass

    # 1. Tenta conexões nomeadas do Streamlit ([connections.postgresql])
    try:
        if "connections" in st.secrets and "postgresql" in st.secrets["connections"]:
            cfg = st.secrets["connections"]["postgresql"]
            if isinstance(cfg, dict) and "url" in cfg:
                return cfg["url"]
            if isinstance(cfg, str):
                return cfg
    except Exception:
        pass

    # 2. Tenta DATABASE_URL em st.secrets
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass

    # 3. Tenta variável de ambiente
    if os.environ.get("DATABASE_URL"):
        return os.environ.get("DATABASE_URL")

    # 4. Tenta session_state
    if st.session_state.get("custom_db_url"):
        return st.session_state["custom_db_url"]

    return None

@st.cache_resource(show_spinner=False)
def _build_engine(db_url: str):
    """Cria e mantém o Engine do SQLAlchemy em cache."""
    if not HAS_SQLALCHEMY or create_engine is None:
        return None
    
    if db_url.startswith("postgres://"):
        norm_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
        norm_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        norm_url = db_url

    connect_args = {"connect_timeout": 8}
    if "localhost" not in norm_url and "127.0.0.1" not in norm_url:
        connect_args["sslmode"] = "require"

    engine = create_engine(
        norm_url,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        pool_pre_ping=True,
        connect_args=connect_args
    )
    with engine.connect() as conn:
        conn.execute(text("SELECT 1;"))
    return engine

def get_engine() -> Engine | None:
    db_url = get_database_url()
    if not db_url:
        return None
    try:
        return _build_engine(db_url)
    except Exception as e:
        logger.error(f"Erro ao conectar ao PostgreSQL: {e}")
        try:
            st.session_state["db_last_error"] = str(e)
        except Exception:
            pass
        return None

def is_db_connected() -> bool:
    engine = get_engine()
    return engine is not None

# ==========================================
# Inicialização DDL & Migração Automática
# ==========================================
def init_db() -> tuple[bool, str]:
    """Cria as tabelas no PostgreSQL/Supabase e migra dados locais de JSON se as tabelas estiverem vazias."""
    engine = get_engine()
    if not engine:
        return False, "Banco de dados não configurado (operando em modo local JSON)."

    ddl_users = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        email VARCHAR(150) UNIQUE NOT NULL,
        senha_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    """

    ddl_categories = """
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) UNIQUE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """

    ddl_transactions = """
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        valor NUMERIC(12,2) NOT NULL,
        tipo VARCHAR(20) NOT NULL,
        data TIMESTAMP NOT NULL,
        descricao VARCHAR(255),
        categoria VARCHAR(50),
        user_id INTEGER REFERENCES users(id) ON DELETE RESTRICT,
        category_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_transactions_data ON transactions(data);
    CREATE INDEX IF NOT EXISTS idx_transactions_tipo ON transactions(tipo);
    CREATE INDEX IF NOT EXISTS idx_transactions_categoria ON transactions(categoria);
    CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
    CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id);
    """

    ddl_audit_logs = """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        data TIMESTAMP NOT NULL,
        user_id INTEGER,
        acao VARCHAR(50) NOT NULL,
        entidade VARCHAR(50) NOT NULL,
        detalhes TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_audit_logs_data ON audit_logs(data);
    """

    try:
        with engine.begin() as conn:
            conn.execute(text(ddl_users))
            conn.execute(text(ddl_categories))
            conn.execute(text(ddl_transactions))
            conn.execute(text(ddl_audit_logs))

            # Se users estiver vazio, migra do JSON
            count_users = conn.execute(text("SELECT COUNT(*) FROM users;")).scalar()
            if count_users == 0:
                local_users = _read_json(USERS_FILE, [])
                for u in local_users:
                    conn.execute(
                        text("INSERT INTO users (id, nome, email, senha_hash) VALUES (:id, :nome, :email, :senha_hash) ON CONFLICT (id) DO NOTHING;"),
                        {"id": u["id"], "nome": u["nome"], "email": u["email"], "senha_hash": u["senha_hash"]}
                    )
                # Atualiza sequence do PostgreSQL
                conn.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE(MAX(id), 1)) FROM users;"))

            # Se categories estiver vazio, migra do JSON
            count_cat = conn.execute(text("SELECT COUNT(*) FROM categories;")).scalar()
            if count_cat == 0:
                local_cats = _read_json(CATEGORIES_FILE, [])
                for c in local_cats:
                    conn.execute(
                        text("INSERT INTO categories (id, nome) VALUES (:id, :nome) ON CONFLICT (id) DO NOTHING;"),
                        {"id": c["id"], "nome": c["nome"]}
                    )
                conn.execute(text("SELECT setval(pg_get_serial_sequence('categories', 'id'), COALESCE(MAX(id), 1)) FROM categories;"))

            # Se transactions estiver vazio, migra do JSON
            count_tx = conn.execute(text("SELECT COUNT(*) FROM transactions;")).scalar()
            if count_tx == 0:
                local_txs = _read_json(TRANSACTIONS_FILE, [])
                for t in local_txs:
                    conn.execute(
                        text("""
                        INSERT INTO transactions (id, valor, tipo, data, descricao, categoria, user_id, category_id)
                        VALUES (:id, :valor, :tipo, :data, :descricao, :categoria, :user_id, :category_id)
                        ON CONFLICT (id) DO NOTHING;
                        """),
                        {
                            "id": t["id"],
                            "valor": float(t["valor"]),
                            "tipo": t["tipo"],
                            "data": t["data"],
                            "descricao": t.get("descricao"),
                            "categoria": t.get("categoria"),
                            "user_id": t["user_id"],
                            "category_id": t.get("category_id")
                        }
                    )
                conn.execute(text("SELECT setval(pg_get_serial_sequence('transactions', 'id'), COALESCE(MAX(id), 1)) FROM transactions;"))

            # Se audit_logs estiver vazio, migra do JSON
            count_logs = conn.execute(text("SELECT COUNT(*) FROM audit_logs;")).scalar()
            if count_logs == 0:
                local_logs = _read_json(AUDIT_LOGS_FILE, [])
                for l in local_logs:
                    conn.execute(
                        text("""
                        INSERT INTO audit_logs (id, data, user_id, acao, entidade, detalhes)
                        VALUES (:id, :data, :user_id, :acao, :entidade, :detalhes)
                        ON CONFLICT (id) DO NOTHING;
                        """),
                        {
                            "id": l["id"],
                            "data": l["data"],
                            "user_id": l["user_id"],
                            "acao": l["acao"],
                            "entidade": l["entidade"],
                            "detalhes": l.get("detalhes")
                        }
                    )
                conn.execute(text("SELECT setval(pg_get_serial_sequence('audit_logs', 'id'), COALESCE(MAX(id), 1)) FROM audit_logs;"))

        return True, "Banco de dados relacional Supabase sincronizado com sucesso!"
    except Exception as e:
        logger.error(f"Erro em init_db: {e}")
        return False, f"Falha na inicialização do banco: {e}"

# ==========================================
# Segurança & Autenticação de Usuários
# ==========================================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def db_get_users() -> list[dict]:
    engine = get_engine()
    if engine:
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT id, nome, email, senha_hash FROM users ORDER BY id ASC;"))
                return [{"id": r[0], "nome": r[1], "email": r[2], "senha_hash": r[3]} for r in res.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao buscar usuários do DB: {e}")
    return _read_json(USERS_FILE, [])

def db_authenticate(email: str, password: str) -> dict | None:
    users = db_get_users()
    for u in users:
        if u["email"].lower() == email.strip().lower():
            if verify_password(password, u["senha_hash"]):
                return {"id": u["id"], "nome": u["nome"], "email": u["email"]}
    return None

# ==========================================
# Auditoria (Audit Logs)
# ==========================================
def db_create_log(user_id: int, acao: str, entidade: str, detalhes: str = None):
    now_str = get_br_now().strftime("%Y-%m-%d %H:%M:%S")
    engine = get_engine()
    if engine:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO audit_logs (data, user_id, acao, entidade, detalhes) VALUES (:data, :user_id, :acao, :entidade, :detalhes);"),
                    {"data": now_str, "user_id": user_id, "acao": acao, "entidade": entidade, "detalhes": detalhes}
                )
            return True
        except Exception as e:
            logger.error(f"Erro ao criar log no PostgreSQL: {e}")

    # Fallback local
    logs = _read_json(AUDIT_LOGS_FILE, [])
    new_id = max([l["id"] for l in logs], default=0) + 1
    logs.insert(0, {
        "id": new_id,
        "data": now_str,
        "user_id": user_id,
        "acao": acao,
        "entidade": entidade,
        "detalhes": detalhes
    })
    _write_json(AUDIT_LOGS_FILE, logs)
    return True

def db_get_audit_logs(limit: int = 150) -> list[dict]:
    engine = get_engine()
    if engine:
        try:
            with engine.connect() as conn:
                query = """
                SELECT l.id, l.data, l.user_id, COALESCE(u.nome, 'Sistema') AS user_nome, l.acao, l.entidade, l.detalhes
                FROM audit_logs l
                LEFT JOIN users u ON l.user_id = u.id
                ORDER BY l.data DESC
                LIMIT :limit;
                """
                res = conn.execute(text(query), {"limit": limit})
                return [
                    {
                        "id": r[0],
                        "data": str(r[1]),
                        "user_id": r[2],
                        "user_nome": r[3],
                        "acao": r[4],
                        "entidade": r[5],
                        "detalhes": r[6]
                    }
                    for r in res.fetchall()
                ]
        except Exception as e:
            logger.error(f"Erro ao buscar logs do DB: {e}")

    # Fallback local
    logs = _read_json(AUDIT_LOGS_FILE, [])
    users_map = {u["id"]: u["nome"] for u in _read_json(USERS_FILE, [])}
    formatted = []
    for l in sorted(logs, key=lambda x: str(x["data"]), reverse=True)[:limit]:
        formatted.append({
            "id": l["id"],
            "data": str(l["data"]),
            "user_id": l["user_id"],
            "user_nome": users_map.get(l["user_id"], "Usuário"),
            "acao": l["acao"],
            "entidade": l["entidade"],
            "detalhes": l.get("detalhes", "")
        })
    return formatted

# ==========================================
# Gestão de Subcategorias
# ==========================================
def db_get_categories() -> list[dict]:
    engine = get_engine()
    if engine:
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT id, nome FROM categories ORDER BY nome ASC;"))
                return [{"id": r[0], "nome": r[1]} for r in res.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao buscar categorias do DB: {e}")
    cats = _read_json(CATEGORIES_FILE, [])
    return sorted(cats, key=lambda x: x["nome"])

def db_create_category(nome: str, user_id: int) -> tuple[bool, str]:
    nome_clean = nome.strip()
    if not nome_clean:
        return False, "O nome da subcategoria não pode ser vazio."

    engine = get_engine()
    if engine:
        try:
            with engine.begin() as conn:
                res = conn.execute(text("SELECT id FROM categories WHERE LOWER(nome) = LOWER(:nome);"), {"nome": nome_clean}).first()
                if res:
                    return False, f"A subcategoria '{nome_clean}' já existe."
                conn.execute(text("INSERT INTO categories (nome) VALUES (:nome);"), {"nome": nome_clean})
            db_create_log(user_id, "CRIAR", "Subcategoria", f"Criou a subcategoria '{nome_clean}'")
            return True, f"Subcategoria '{nome_clean}' criada com sucesso!"
        except Exception as e:
            logger.error(f"Erro ao criar categoria no DB: {e}")
            return False, f"Erro: {e}"

    # Fallback local
    cats = _read_json(CATEGORIES_FILE, [])
    if any(c["nome"].lower() == nome_clean.lower() for c in cats):
        return False, f"A subcategoria '{nome_clean}' já existe."
    new_id = max([c["id"] for c in cats], default=0) + 1
    cats.append({"id": new_id, "nome": nome_clean})
    _write_json(CATEGORIES_FILE, cats)
    db_create_log(user_id, "CRIAR", "Subcategoria", f"Criou a subcategoria '{nome_clean}'")
    return True, f"Subcategoria '{nome_clean}' criada com sucesso!"

def db_update_category(cat_id: int, new_nome: str, user_id: int) -> tuple[bool, str]:
    nome_clean = new_nome.strip()
    if not nome_clean:
        return False, "O novo nome não pode ser vazio."

    engine = get_engine()
    if engine:
        try:
            with engine.begin() as conn:
                old = conn.execute(text("SELECT nome FROM categories WHERE id = :id;"), {"id": cat_id}).scalar()
                if not old:
                    return False, "Subcategoria não encontrada."
                conn.execute(text("UPDATE categories SET nome = :nome WHERE id = :id;"), {"nome": nome_clean, "id": cat_id})
            db_create_log(user_id, "EDITAR", "Subcategoria", f"Alterou subcategoria de '{old}' para '{nome_clean}'")
            return True, "Subcategoria atualizada com sucesso!"
        except Exception as e:
            return False, f"Erro ao atualizar: {e}"

    cats = _read_json(CATEGORIES_FILE, [])
    for c in cats:
        if c["id"] == cat_id:
            old_nome = c["nome"]
            c["nome"] = nome_clean
            _write_json(CATEGORIES_FILE, cats)
            db_create_log(user_id, "EDITAR", "Subcategoria", f"Alterou subcategoria de '{old_nome}' para '{nome_clean}'")
            return True, "Subcategoria atualizada com sucesso!"
    return False, "Subcategoria não encontrada."

def db_delete_category(cat_id: int, user_id: int) -> tuple[bool, str]:
    engine = get_engine()
    if engine:
        try:
            with engine.begin() as conn:
                tx_count = conn.execute(text("SELECT COUNT(*) FROM transactions WHERE category_id = :id;"), {"id": cat_id}).scalar()
                if tx_count > 0:
                    return False, f"Esta subcategoria não pode ser apagada pois possui {tx_count} lançamento(s) vinculado(s)."
                old_nome = conn.execute(text("SELECT nome FROM categories WHERE id = :id;"), {"id": cat_id}).scalar()
                conn.execute(text("DELETE FROM categories WHERE id = :id;"), {"id": cat_id})
            db_create_log(user_id, "EXCLUIR", "Subcategoria", f"Apagou a subcategoria '{old_nome}'")
            return True, "Subcategoria excluída com sucesso!"
        except Exception as e:
            return False, f"Erro ao excluir: {e}"

    txs = _read_json(TRANSACTIONS_FILE, [])
    tx_count = sum(1 for t in txs if t.get("category_id") == cat_id)
    if tx_count > 0:
        return False, f"Esta subcategoria não pode ser apagada pois possui {tx_count} lançamento(s) vinculado(s)."

    cats = _read_json(CATEGORIES_FILE, [])
    cat_to_del = next((c for c in cats if c["id"] == cat_id), None)
    if not cat_to_del:
        return False, "Subcategoria não encontrada."
    cats = [c for c in cats if c["id"] != cat_id]
    _write_json(CATEGORIES_FILE, cats)
    db_create_log(user_id, "EXCLUIR", "Subcategoria", f"Apagou a subcategoria '{cat_to_del['nome']}'")
    return True, "Subcategoria excluída com sucesso!"

# ==========================================
# Gestão de Transações (Receitas & Despesas)
# ==========================================
def db_get_transactions(tipo: str = None, categoria: str = None) -> list[dict]:
    engine = get_engine()
    if engine:
        try:
            with engine.connect() as conn:
                query = """
                SELECT t.id, t.valor, t.tipo, t.data, t.descricao, t.categoria, t.user_id, COALESCE(u.nome, 'Usuário') AS user_nome,
                       t.category_id, COALESCE(c.nome, '') AS category_nome
                FROM transactions t
                LEFT JOIN users u ON t.user_id = u.id
                LEFT JOIN categories c ON t.category_id = c.id
                WHERE 1=1
                """
                params = {}
                if tipo and tipo != "Todos":
                    query += " AND t.tipo = :tipo"
                    params["tipo"] = tipo.lower()
                if categoria and categoria != "Todas":
                    query += " AND t.categoria = :categoria"
                    params["categoria"] = categoria
                query += " ORDER BY t.data DESC;"
                res = conn.execute(text(query), params)
                return [
                    {
                        "id": r[0],
                        "valor": float(r[1]),
                        "tipo": r[2],
                        "data": str(r[3]),
                        "descricao": r[4] or "",
                        "categoria": r[5] or "",
                        "user_id": r[6],
                        "user_nome": r[7],
                        "category_id": r[8],
                        "category_nome": r[9]
                    }
                    for r in res.fetchall()
                ]
        except Exception as e:
            logger.error(f"Erro ao buscar transações do DB: {e}")

    # Fallback local
    txs = _read_json(TRANSACTIONS_FILE, [])
    users_map = {u["id"]: u["nome"] for u in _read_json(USERS_FILE, [])}
    cats_map = {c["id"]: c["nome"] for c in _read_json(CATEGORIES_FILE, [])}
    formatted = []
    for t in sorted(txs, key=lambda x: str(x["data"]), reverse=True):
        if tipo and tipo != "Todos" and t["tipo"].lower() != tipo.lower():
            continue
        if categoria and categoria != "Todas" and t.get("categoria") != categoria:
            continue
        formatted.append({
            "id": t["id"],
            "valor": float(t["valor"]),
            "tipo": t["tipo"],
            "data": str(t["data"]),
            "descricao": t.get("descricao") or "",
            "categoria": t.get("categoria") or "",
            "user_id": t["user_id"],
            "user_nome": users_map.get(t["user_id"], "Usuário"),
            "category_id": t.get("category_id"),
            "category_nome": cats_map.get(t.get("category_id"), "")
        })
    return formatted

def db_create_transaction(
    valor: float,
    tipo: str,
    data_str: str,
    descricao: str,
    categoria: str | None,
    category_id: int | None,
    user_id: int
) -> tuple[bool, str]:
    if valor <= 0:
        return False, "O valor deve ser maior que zero."

    tipo_clean = tipo.lower()
    if tipo_clean == "despesa":
        if not categoria or categoria not in ["Casamento", "Apartamento"]:
            return False, "Selecione o Projeto do gasto (Casamento ou Apartamento)."
        if not category_id:
            return False, "Selecione uma Subcategoria válida para a despesa."
    else:
        categoria = None
        category_id = None

    engine = get_engine()
    if engine:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                    INSERT INTO transactions (valor, tipo, data, descricao, categoria, category_id, user_id)
                    VALUES (:valor, :tipo, :data, :descricao, :categoria, :category_id, :user_id);
                    """),
                    {
                        "valor": valor,
                        "tipo": tipo_clean,
                        "data": data_str,
                        "descricao": descricao.strip() if descricao else None,
                        "categoria": categoria,
                        "category_id": category_id,
                        "user_id": user_id
                    }
                )
            desc_log = f"({descricao.strip()})" if descricao else ""
            db_create_log(user_id, "CRIAR", "Transação", f"Criou {tipo_clean} no valor de R$ {valor:.2f} {desc_log}".strip())
            return True, f"{tipo.capitalize()} de R$ {valor:,.2f} registrada com sucesso!"
        except Exception as e:
            logger.error(f"Erro ao inserir transação: {e}")
            return False, f"Erro: {e}"

    # Fallback local
    txs = _read_json(TRANSACTIONS_FILE, [])
    new_id = max([t["id"] for t in txs], default=0) + 1
    txs.append({
        "id": new_id,
        "valor": valor,
        "tipo": tipo_clean,
        "data": data_str,
        "descricao": descricao.strip() if descricao else None,
        "categoria": categoria,
        "category_id": category_id,
        "user_id": user_id
    })
    _write_json(TRANSACTIONS_FILE, txs)
    desc_log = f"({descricao.strip()})" if descricao else ""
    db_create_log(user_id, "CRIAR", "Transação", f"Criou {tipo_clean} no valor de R$ {valor:.2f} {desc_log}".strip())
    return True, f"{tipo.capitalize()} de R$ {valor:,.2f} registrada com sucesso!"

def db_update_transaction(
    tx_id: int,
    valor: float,
    data_str: str,
    descricao: str,
    categoria: str | None,
    category_id: int | None,
    user_id: int
) -> tuple[bool, str]:
    if valor <= 0:
        return False, "O valor deve ser maior que zero."

    engine = get_engine()
    if engine:
        try:
            with engine.begin() as conn:
                old = conn.execute(text("SELECT valor, tipo, descricao, categoria, category_id FROM transactions WHERE id = :id;"), {"id": tx_id}).first()
                if not old:
                    return False, "Transação não encontrada."
                
                tipo_current = old[1]
                if tipo_current == "despesa":
                    if categoria not in ["Casamento", "Apartamento"]:
                        return False, "Projeto inválido."
                    if not category_id:
                        return False, "Subcategoria obrigatória."
                else:
                    categoria = None
                    category_id = None

                conn.execute(
                    text("""
                    UPDATE transactions
                    SET valor = :valor, data = :data, descricao = :descricao, categoria = :categoria, category_id = :category_id
                    WHERE id = :id;
                    """),
                    {
                        "id": tx_id,
                        "valor": valor,
                        "data": data_str,
                        "descricao": descricao.strip() if descricao else None,
                        "categoria": categoria,
                        "category_id": category_id
                    }
                )
            db_create_log(user_id, "EDITAR", "Transação", f"Editou lançamento #{tx_id} para R$ {valor:.2f}")
            return True, "Transação atualizada com sucesso!"
        except Exception as e:
            return False, f"Erro: {e}"

    txs = _read_json(TRANSACTIONS_FILE, [])
    for t in txs:
        if t["id"] == tx_id:
            t["valor"] = valor
            t["data"] = data_str
            t["descricao"] = descricao.strip() if descricao else None
            if t["tipo"] == "despesa":
                t["categoria"] = categoria
                t["category_id"] = category_id
            _write_json(TRANSACTIONS_FILE, txs)
            db_create_log(user_id, "EDITAR", "Transação", f"Editou lançamento #{tx_id} para R$ {valor:.2f}")
            return True, "Transação atualizada com sucesso!"
    return False, "Transação não encontrada."

def db_delete_transaction(tx_id: int, user_id: int) -> tuple[bool, str]:
    engine = get_engine()
    if engine:
        try:
            with engine.begin() as conn:
                old = conn.execute(text("SELECT valor, tipo, descricao FROM transactions WHERE id = :id;"), {"id": tx_id}).first()
                if not old:
                    return False, "Transação não encontrada."
                conn.execute(text("DELETE FROM transactions WHERE id = :id;"), {"id": tx_id})
            db_create_log(user_id, "EXCLUIR", "Transação", f"Excluiu {old[1]} no valor de R$ {float(old[0]):.2f} ({old[2] or 'Sem descrição'})")
            return True, "Transação excluída com sucesso!"
        except Exception as e:
            return False, f"Erro: {e}"

    txs = _read_json(TRANSACTIONS_FILE, [])
    tx_to_del = next((t for t in txs if t["id"] == tx_id), None)
    if not tx_to_del:
        return False, "Transação não encontrada."
    txs = [t for t in txs if t["id"] != tx_id]
    _write_json(TRANSACTIONS_FILE, txs)
    db_create_log(user_id, "EXCLUIR", "Transação", f"Excluiu {tx_to_del['tipo']} no valor de R$ {float(tx_to_del['valor']):.2f} ({tx_to_del.get('descricao') or 'Sem descrição'})")
    return True, "Transação excluída com sucesso!"

# ==========================================
# Agregações Financeiras & Relatórios
# ==========================================
def db_get_summary_stats() -> dict:
    txs = db_get_transactions()
    total_receitas = 0.0
    total_despesas = 0.0
    despesas_casamento = 0.0
    despesas_apartamento = 0.0

    for t in txs:
        val = t["valor"]
        if t["tipo"] == "receita":
            total_receitas += val
        else:
            total_despesas += val
            if t.get("categoria") == "Casamento":
                despesas_casamento += val
            elif t.get("categoria") == "Apartamento":
                despesas_apartamento += val

    saldo_geral = total_receitas - total_despesas
    return {
        "saldo_geral": saldo_geral,
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "despesas_casamento": despesas_casamento,
        "despesas_apartamento": despesas_apartamento,
        "count_transactions": len(txs)
    }

def db_get_reports_data(period: str = "all") -> dict:
    all_txs = sorted(db_get_transactions(), key=lambda x: str(x["data"]))
    now = get_br_now()

    if period == "30d":
        start_date = now - timedelta(days=30)
    elif period == "year":
        start_date = datetime(now.year, 1, 1, tzinfo=BR_TZ)
    else:
        start_date = datetime(2000, 1, 1, tzinfo=BR_TZ)

    initial_balance = 0.0
    evolution_points = []
    cashflow_dict = {}
    dist_dict = {}

    running_balance = 0.0

    for t in all_txs:
        # Tenta converter data da transação
        raw_dt = str(t["data"])
        try:
            if "T" in raw_dt:
                dt = datetime.fromisoformat(raw_dt)
            else:
                dt = datetime.strptime(raw_dt[:19], "%Y-%m-%d %H:%M:%S")
            if dt.tzinfo is None:
                dt = BR_TZ.localize(dt)
        except Exception:
            dt = now

        val = float(t["valor"])
        is_rec = (t["tipo"] == "receita")

        if is_rec:
            running_balance += val
        else:
            running_balance -= val

        if dt < start_date:
            continue

        # 1. Ponto de Evolução
        evolution_points.append({
            "data": dt.strftime("%d/%m/%Y"),
            "data_dt": dt,
            "saldo": running_balance,
            "descricao": t.get("descricao") or t["tipo"].capitalize()
        })

        # 2. Fluxo de Caixa Mensal
        month_key = dt.strftime("%m/%Y")
        if month_key not in cashflow_dict:
            cashflow_dict[month_key] = {"entradas": 0.0, "saidas": 0.0}
        if is_rec:
            cashflow_dict[month_key]["entradas"] += val
        else:
            cashflow_dict[month_key]["saidas"] += val

        # 3. Distribuição de Gastos
        if not is_rec and t.get("categoria"):
            proj = t["categoria"]
            subcat = t.get("category_nome") or "Outros"
            if proj not in dist_dict:
                dist_dict[proj] = {"total": 0.0, "subcats": {}}
            dist_dict[proj]["total"] += val
            dist_dict[proj]["subcats"][subcat] = dist_dict[proj]["subcats"].get(subcat, 0.0) + val

    return {
        "evolution": evolution_points,
        "cashflow": cashflow_dict,
        "distribution": dist_dict,
        "current_balance": running_balance
    }
