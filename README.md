# 💍🏠 Teto & Altar — Gestão Financeira Compartilhada

Sistema de gestão e planejamento financeiro conjunto para os projetos **Casamento (Altar)** e **Apartamento (Teto)**, desenvolvido em **Python + Streamlit** com suporte nativo a banco de dados relacional **PostgreSQL (Supabase)** e modo offline automático (JSON).

---

## 🚀 Arquitetura (Padrão Passei Concurso)

- **Frontend & App:** Python 3.11+ / Streamlit com Design System minimalista e gráficos dinâmicos via `Plotly`.
- **Banco de Dados Relacional:** **PostgreSQL (Supabase)** via `SQLAlchemy` e `psycopg2-binary`.
- **Inicialização Automática (`init_db`):** Criação automática de tabelas, índices e migração dos dados iniciais se o banco estiver vazio.
- **Fallback Gracioso Offline (`data/`):** Se a URL de banco não for configurada, o sistema opera 100% normalmente em arquivos JSON locais.
- **Segurança & Auditoria:** Autenticação com senhas protegidas por `bcrypt` e trilha de auditoria completa de todas as alterações.

---

## 📂 Estrutura de Diretórios

```
Teto_E_Altar/
├── .streamlit/
│   ├── config.toml           # Tema visual minimalista e paleta limpa
│   └── secrets.toml.example  # Modelo de credenciais do Supabase
├── data/                     # Persistência em arquivos JSON locais (modo offline)
│   ├── users.json
│   ├── categories.json
│   ├── transactions.json
│   └── audit_logs.json
├── legacy_fastapi/           # Código legado da v1.0 (FastAPI + Jinja2)
├── app.py                    # Aplicação principal Streamlit
├── database.py               # Camada de banco (Supabase PostgreSQL + JSON Fallback)
├── iniciar_teto_e_altar.bat  # Inicializador automático para Windows (1 clique)
├── requirements.txt          # Dependências do projeto
└── README.md
```

---

## ⚡ Como Executar Localmente no Windows

1. Dê um duplo clique no arquivo:
   ```cmd
   iniciar_teto_e_altar.bat
   ```
2. O sistema abrirá automaticamente no seu navegador padrão em:
   ```
   http://localhost:8501
   ```

---

## 🐘 Como Conectar ao Supabase (PostgreSQL)

1. Crie seu projeto gratuito no [Supabase](https://supabase.com);
2. Em **Project Settings > Database**, copie a **URI de Conexão** (*Transaction Pooler* ou *Direct*):
   ```
   postgresql://postgres.[SEU_PROJECT_REF]:[SUA_SENHA]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres
   ```
3. Crie o arquivo `.streamlit/secrets.toml` (ou configure em *App Settings > Secrets* no Streamlit Cloud):
   ```toml
   [connections.postgresql]
   url = "postgresql://postgres.[SEU_PROJECT_REF]:[SUA_SENHA]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
   ```
4. Ao iniciar, o sistema executa o `init_db()` automaticamente, gerando as tabelas e migrando os dados existentes!

---

## 👥 Usuários Padrão (Ambiente Inicial)

| Usuário | E-mail | Senha Padrão |
| :--- | :--- | :--- |
| **Isac** | `isac@teto.com` | `123456` |
| **Noiva** | `noiva@teto.com` | `123456` |
