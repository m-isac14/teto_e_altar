from __future__ import annotations
import sys
import os

# Garante que o diretório da aplicação tenha prioridade máxima no sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta

# Importa o módulo resiliente do banco / fallback
import database as db

# ==========================================
# Configurações Globais da Página
# ==========================================
st.set_page_config(
    page_title="Teto & Altar 💍🏠",
    page_icon="💍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# Design System & Estilos CSS Customizados
# ==========================================
st.markdown("""
<style>
    /* Estilo Geral e Tipografia */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.5rem;
    }
    
    /* Cartões Modernos de KPI */
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
        margin-bottom: 1rem;
        transition: transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
    }
    .kpi-title {
        color: #64748B;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.4rem;
    }
    .kpi-value {
        font-size: 1.65rem;
        font-weight: 700;
        color: #0F172A;
    }
    .kpi-value.positive {
        color: #059669;
    }
    .kpi-value.negative {
        color: #DC2626;
    }
    
    /* Badges de Projeto & Tipo */
    .badge-casamento {
        background-color: #EDE9FE;
        color: #6D28D9;
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-apartamento {
        background-color: #FEF3C7;
        color: #B45309;
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-receita {
        background-color: #D1FAE5;
        color: #047857;
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    
    /* Header Principal */
    .app-header {
        margin-bottom: 1.5rem;
    }
    .app-header h1 {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
        margin: 0;
    }
    .app-header p {
        color: #64748B;
        font-size: 0.95rem;
        margin: 0;
    }
    
    /* Box de Login */
    .login-container {
        max-width: 440px;
        margin: 4rem auto;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 2.2rem;
        box-shadow: 0 10px 25px rgba(15, 23, 42, 0.06);
    }
</style>
""", unsafe_allow_html=True)

# Tenta inicializar o banco relacional se ainda não tentou
if "db_initialized" not in st.session_state:
    ok, msg = db.init_db()
    st.session_state["db_initialized"] = True
    st.session_state["db_init_msg"] = msg

# ==========================================
# Controle de Autenticação (Opção A)
# ==========================================
if "user" not in st.session_state:
    st.session_state["user"] = None

def render_login():
    st.markdown("""
    <div class="login-container">
        <div style="text-align: center; margin-bottom: 1.5rem;">
            <span style="font-size: 3rem;">💍🏠</span>
            <h2 style="font-weight: 700; color: #0F172A; margin-top: 0.5rem; margin-bottom: 0.2rem;">Teto & Altar</h2>
            <p style="color: #64748B; font-size: 0.9rem;">Gestão Financeira Compartilhada — Casamento & Apartamento</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        tab_login, tab_quick = st.tabs(["🔑 Login com Senha", "⚡ Acesso Rápido"])
        
        with tab_login:
            users = db.db_get_users()
            user_options = {f"{u['nome']} ({u['email']})": u['email'] for u in users}
            
            with st.form("form_login"):
                selected_label = st.selectbox("Selecione seu Usuário", list(user_options.keys()))
                email_input = user_options[selected_label]
                password_input = st.text_input("Senha", type="password", placeholder="Digite sua senha")
                submitted = st.form_submit_button("Entrar no Sistema", use_container_width=True, type="primary")
                
                if submitted:
                    if not password_input:
                        st.error("Por favor, informe a senha.")
                    else:
                        user = db.db_authenticate(email_input, password_input)
                        if user:
                            st.session_state["user"] = user
                            st.success(f"Bem-vindo(a), {user['nome']}!")
                            st.rerun()
                        else:
                            st.error("Senha incorreta. Tente novamente.")
            st.caption("💡 *Senha inicial padrão dos usuários: `123456`*")

        with tab_quick:
            st.write("Entrar direto com a conta ativa:")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("👤 Entrar como Isac", use_container_width=True):
                    isac_user = next((u for u in db.db_get_users() if u["email"] == "isac@teto.com"), None)
                    if isac_user:
                        st.session_state["user"] = {"id": isac_user["id"], "nome": isac_user["nome"], "email": isac_user["email"]}
                        st.rerun()
            with col_b2:
                if st.button("👰 Entrar como Noiva", use_container_width=True):
                    noiva_user = next((u for u in db.db_get_users() if u["email"] == "noiva@teto.com"), None)
                    if noiva_user:
                        st.session_state["user"] = {"id": noiva_user["id"], "nome": noiva_user["nome"], "email": noiva_user["email"]}
                        st.rerun()

# Se não estiver logado, exibe apenas a tela de login
if not st.session_state["user"]:
    render_login()
    st.stop()

# ==========================================
# Usuário Autenticado - Barra Lateral
# ==========================================
current_user = st.session_state["user"]
summary_stats = db.db_get_summary_stats()

with st.sidebar:
    st.markdown(f"""
    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1rem; margin-bottom: 1rem;">
        <div style="font-weight: 700; font-size: 1.05rem; color: #0F172A;">👤 Olá, {current_user['nome']}!</div>
        <div style="font-size: 0.8rem; color: #64748B;">{current_user['email']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Botão Sair
    if st.button("🚪 Sair do Sistema", use_container_width=True):
        st.session_state["user"] = None
        st.rerun()
        
    st.divider()

    # Indicador de Conexão com Supabase / Local
    db_connected = db.is_db_connected()
    if db_connected:
        st.success("🟢 **Supabase Conectado**", icon="🐘")
    else:
        st.warning("🟡 **Modo Local (JSON)**", icon="💾")
        st.caption("Operando offline. Configure a URL do Supabase para persistência relacional na nuvem.")

    st.divider()
    
    # Caixa Geral no topo da Sidebar
    saldo = summary_stats["saldo_geral"]
    saldo_color = "positive" if saldo >= 0 else "negative"
    st.markdown(f"""
    <div class="kpi-card" style="margin-bottom: 1.5rem;">
        <div class="kpi-title">Caixa Único Geral</div>
        <div class="kpi-value {saldo_color}">R$ {saldo:,.2f}</div>
        <div style="font-size: 0.8rem; color: #64748B; margin-top: 0.3rem;">
            {summary_stats['count_transactions']} lançamentos registrados
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Navegação entre Módulos
    menu = st.radio(
        "Navegação",
        [
            "📊 Dashboard & Gráficos",
            "💸 Lançamentos",
            "🏷️ Subcategorias",
            "📋 Histórico & Auditoria",
            "⚙️ Configurações & Supabase"
        ],
        label_visibility="collapsed"
    )

# ==========================================
# 1. MÓDULO: DASHBOARD & GRÁFICOS
# ==========================================
if menu == "📊 Dashboard & Gráficos":
    st.markdown("""
    <div class="app-header">
        <h1>📊 Dashboard Financeiro — Teto & Altar</h1>
        <p>Visão consolidada do Caixa Único e distribuição de recursos entre Casamento e Apartamento.</p>
    </div>
    """, unsafe_allow_html=True)

    # 4 KPIs de Topo
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">💰 Saldo em Caixa</div>
            <div class="kpi-value {'positive' if summary_stats['saldo_geral'] >= 0 else 'negative'}">
                R$ {summary_stats['saldo_geral']:,.2f}
            </div>
            <div style="font-size: 0.78rem; color: #64748B; margin-top: 0.2rem;">Receitas − Todas as Despesas</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">📥 Total Receitas</div>
            <div class="kpi-value positive">
                R$ {summary_stats['total_receitas']:,.2f}
            </div>
            <div style="font-size: 0.78rem; color: #64748B; margin-top: 0.2rem;">Aportes e saldos iniciais</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">💒 Gastos Casamento</div>
            <div class="kpi-value" style="color: #6D28D9;">
                R$ {summary_stats['despesas_casamento']:,.2f}
            </div>
            <div style="font-size: 0.78rem; color: #64748B; margin-top: 0.2rem;">Altar & Cerimônia</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">🏢 Gastos Apartamento</div>
            <div class="kpi-value" style="color: #D97706;">
                R$ {summary_stats['despesas_apartamento']:,.2f}
            </div>
            <div style="font-size: 0.78rem; color: #64748B; margin-top: 0.2rem;">Teto, Reforma & Móveis</div>
        </div>
        """, unsafe_allow_html=True)

    # Filtro de Período para os Gráficos
    st.write("")
    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        period_choice = st.selectbox(
            "Filtrar período dos gráficos:",
            ["Todo o Período", "Últimos 30 dias", "Este Ano"],
            index=0
        )
    
    period_code = "all"
    if period_choice == "Últimos 30 dias":
        period_code = "30d"
    elif period_choice == "Este Ano":
        period_code = "year"

    reports_data = db.db_get_reports_data(period_code)

    # Gráfico 1: Evolução Patrimonial
    st.subheader("📈 Evolução do Saldo Geral ao Longo do Tempo")
    evo_points = reports_data["evolution"]
    if evo_points:
        df_evo = pd.DataFrame(evo_points)
        fig_evo = px.area(
            df_evo,
            x="data",
            y="saldo",
            title="Trajetória do Saldo Acumulado (R$)",
            labels={"saldo": "Saldo (R$)", "data": "Data"},
            color_discrete_sequence=["#4F46E5"]
        )
        fig_evo.update_traces(
            mode="lines+markers",
            line_shape="spline",
            line=dict(width=3, color="#4F46E5"),
            marker=dict(size=6, color="#4338CA"),
            fillcolor="rgba(79, 70, 229, 0.12)"
        )
        fig_evo.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20),
            hovermode="x unified",
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="#E2E8F0", tickprefix="R$ ")
        )
        st.plotly_chart(fig_evo, use_container_width=True)
    else:
        st.info("Nenhuma transação registrada no período selecionado.")

    # Gráficos 2 e 3 em Duas Colunas
    g_col1, g_col2 = st.columns(2)
    
    with g_col1:
        st.subheader("📊 Fluxo de Caixa Mensal (Entradas vs Saídas)")
        cashflow_dict = reports_data["cashflow"]
        if cashflow_dict:
            months = list(cashflow_dict.keys())
            entradas = [cashflow_dict[m]["entradas"] for m in months]
            saidas = [cashflow_dict[m]["saidas"] for m in months]

            fig_cf = go.Figure()
            fig_cf.add_trace(go.Bar(
                name="Entradas (Receitas)",
                x=months,
                y=entradas,
                marker_color="#059669"
            ))
            fig_cf.add_trace(go.Bar(
                name="Saídas (Despesas)",
                x=months,
                y=saidas,
                marker_color="#DC2626"
            ))
            fig_cf.update_layout(
                barmode="group",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=30, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                yaxis=dict(gridcolor="#E2E8F0", tickprefix="R$ ")
            )
            st.plotly_chart(fig_cf, use_container_width=True)
        else:
            st.info("Sem dados de fluxo mensal para exibir.")

    with g_col2:
        st.subheader("🍩 Distribuição de Gastos: Casamento vs Apartamento")
        dist = reports_data["distribution"]
        if dist:
            labels = list(dist.keys())
            values = [dist[k]["total"] for k in labels]
            fig_donut = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker=dict(colors=["#D97706", "#6D28D9", "#2563EB"])
            )])
            fig_donut.update_layout(
                margin=dict(l=20, r=20, t=30, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_donut, use_container_width=True)
            
            # Detalhamento por subcategorias
            with st.expander("🔍 Ver detalhamento por subcategoria"):
                for proj_name, proj_data in dist.items():
                    st.write(f"**{proj_name} (Total: R$ {proj_data['total']:,.2f}):**")
                    sub_items = sorted(proj_data["subcats"].items(), key=lambda x: x[1], reverse=True)
                    for sub_n, sub_v in sub_items:
                        pct = (sub_v / proj_data["total"] * 100) if proj_data["total"] > 0 else 0
                        st.write(f"- {sub_n}: R$ {sub_v:,.2f} ({pct:.1f}%)")
        else:
            st.info("Nenhuma despesa registrada para detalhar.")

# ==========================================
# 2. MÓDULO: LANÇAMENTOS (TRANSAÇÕES)
# ==========================================
elif menu == "💸 Lançamentos":
    st.markdown("""
    <div class="app-header">
        <h1>💸 Lançamentos de Receitas & Despesas</h1>
        <p>Adicione, visualize, filtre e gerencie todas as movimentações financeiras do casal.</p>
    </div>
    """, unsafe_allow_html=True)

    # Formulário de Novo Lançamento
    with st.expander("➕ **Novo Lançamento Financeiro**", expanded=True):
        with st.form("form_new_transaction"):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                tipo_input = st.radio("Tipo de Lançamento", ["Despesa", "Receita"], horizontal=True)
            with fc2:
                valor_input = st.number_input("Valor (R$)", min_value=0.01, step=10.0, format="%.2f")
            with fc3:
                data_input = st.date_input("Data do Lançamento", value=date.today())

            categoria_input = None
            category_id_input = None
            
            if tipo_input == "Despesa":
                fc4, fc5 = st.columns(2)
                with fc4:
                    categoria_input = st.selectbox("Projeto do Gasto", ["Apartamento", "Casamento"])
                with fc5:
                    available_cats = db.db_get_categories()
                    cat_map = {c["nome"]: c["id"] for c in available_cats}
                    if cat_map:
                        chosen_cat_name = st.selectbox("Subcategoria", list(cat_map.keys()))
                        category_id_input = cat_map[chosen_cat_name]
                    else:
                        st.warning("Nenhuma subcategoria cadastrada. Crie uma na aba Subcategorias primeiro.")

            descricao_input = st.text_input("Descrição ou Observações (opcional)", placeholder="Ex: Entrada Buffet, Pia da Cozinha, Saldo FGTS...")
            
            submit_tx = st.form_submit_button("💾 Salvar Lançamento", use_container_width=True, type="primary")
            if submit_tx:
                data_str = f"{data_input.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M:%S')}"
                ok, msg = db.db_create_transaction(
                    valor=valor_input,
                    tipo=tipo_input.lower(),
                    data_str=data_str,
                    descricao=descricao_input,
                    categoria=categoria_input,
                    category_id=category_id_input,
                    user_id=current_user["id"]
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    st.write("---")
    
    # Filtros e Tabela de Histórico
    st.subheader("📋 Histórico de Lançamentos")
    f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
    with f_col1:
        f_tipo = st.selectbox("Filtrar por Tipo:", ["Todos", "Receita", "Despesa"])
    with f_col2:
        f_proj = st.selectbox("Filtrar por Projeto:", ["Todas", "Casamento", "Apartamento"])
    with f_col3:
        search_term = st.text_input("Buscar por descrição ou subcategoria:")

    tx_list = db.db_get_transactions(
        tipo=None if f_tipo == "Todos" else f_tipo,
        categoria=None if f_proj == "Todas" else f_proj
    )

    if search_term.strip():
        term = search_term.strip().lower()
        tx_list = [
            t for t in tx_list
            if term in t["descricao"].lower() or term in t["category_nome"].lower() or term in t["user_nome"].lower()
        ]

    if tx_list:
        # Prepara DataFrame para visualização bonita
        display_data = []
        for t in tx_list:
            dt_label = t["data"][:10] if len(t["data"]) >= 10 else t["data"]
            proj_label = t["categoria"] if t["tipo"] == "despesa" else "— (Caixa Geral)"
            display_data.append({
                "ID": t["id"],
                "Data": dt_label,
                "Tipo": t["tipo"].capitalize(),
                "Projeto": proj_label,
                "Subcategoria": t["category_nome"] or "—",
                "Descrição": t["descricao"] or "—",
                "Quem Lançou": t["user_nome"],
                "Valor (R$)": f"R$ {t['valor']:,.2f}"
            })

        df_display = pd.DataFrame(display_data)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # Seção de Ações: Excluir ou Editar
        with st.expander("⚙️ **Editar ou Excluir Lançamento**"):
            tx_ids = [t["id"] for t in tx_list]
            selected_tx_id = st.selectbox("Selecione o ID do Lançamento:", tx_ids)
            selected_tx = next((t for t in tx_list if t["id"] == selected_tx_id), None)

            if selected_tx:
                col_ed1, col_ed2 = st.columns(2)
                with col_ed1:
                    new_val = st.number_input("Valor (R$)", value=float(selected_tx["valor"]), step=10.0, key="edit_val")
                    new_desc = st.text_input("Descrição", value=selected_tx["descricao"], key="edit_desc")
                with col_ed2:
                    new_proj = selected_tx["categoria"]
                    new_cat_id = selected_tx["category_id"]
                    if selected_tx["tipo"] == "despesa":
                        new_proj = st.selectbox("Projeto", ["Apartamento", "Casamento"], index=0 if selected_tx["categoria"] == "Apartamento" else 1, key="edit_proj")
                        available_cats = db.db_get_categories()
                        cat_map = {c["nome"]: c["id"] for c in available_cats}
                        curr_cat_name = selected_tx["category_nome"] if selected_tx["category_nome"] in cat_map else list(cat_map.keys())[0]
                        chosen_c = st.selectbox("Subcategoria", list(cat_map.keys()), index=list(cat_map.keys()).index(curr_cat_name), key="edit_cat")
                        new_cat_id = cat_map[chosen_c]

                col_btn1, col_btn2 = st.columns([1, 4])
                with col_btn1:
                    if st.button("💾 Salvar Alterações", type="primary"):
                        ok, msg = db.db_update_transaction(
                            tx_id=selected_tx_id,
                            valor=new_val,
                            data_str=selected_tx["data"],
                            descricao=new_desc,
                            categoria=new_proj,
                            category_id=new_cat_id,
                            user_id=current_user["id"]
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                with col_btn2:
                    if st.button("🗑️ Excluir Lançamento", type="secondary"):
                        ok, msg = db.db_delete_transaction(selected_tx_id, current_user["id"])
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
    else:
        st.info("Nenhuma transação encontrada com os filtros selecionados.")

# ==========================================
# 3. MÓDULO: SUBCATEGORIAS
# ==========================================
elif menu == "🏷️ Subcategorias":
    st.markdown("""
    <div class="app-header">
        <h1>🏷️ Gestão de Subcategorias</h1>
        <p>Cadastre e organize as subcategorias de gastos vinculadas aos projetos do Casamento e Apartamento.</p>
    </div>
    """, unsafe_allow_html=True)

    col_cat_form, col_cat_list = st.columns([1, 2])

    with col_cat_form:
        st.subheader("➕ Nova Subcategoria")
        with st.form("form_new_category"):
            new_cat_name = st.text_input("Nome da Subcategoria", placeholder="Ex: Fotografia, Iluminação, Pisos...")
            sub_cat = st.form_submit_button("Cadastrar Subcategoria", use_container_width=True, type="primary")
            if sub_cat:
                ok, msg = db.db_create_category(new_cat_name, current_user["id"])
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with col_cat_list:
        st.subheader("📑 Subcategorias Cadastradas")
        cats = db.db_get_categories()
        all_txs = db.db_get_transactions()

        if cats:
            cat_table = []
            for c in cats:
                count_usage = sum(1 for t in all_txs if t.get("category_id") == c["id"])
                total_spent = sum(t["valor"] for t in all_txs if t.get("category_id") == c["id"])
                cat_table.append({
                    "ID": c["id"],
                    "Nome": c["nome"],
                    "Gastos Vinculados": count_usage,
                    "Total Gasto (R$)": f"R$ {total_spent:,.2f}"
                })
            st.dataframe(pd.DataFrame(cat_table), use_container_width=True, hide_index=True)

            with st.expander("✏️ Editar ou Excluir Subcategoria"):
                cat_names_map = {c["nome"]: c["id"] for c in cats}
                selected_cat_to_edit = st.selectbox("Selecione a Subcategoria:", list(cat_names_map.keys()))
                sel_id = cat_names_map[selected_cat_to_edit]

                col_e1, col_e2 = st.columns([2, 1])
                with col_e1:
                    renamed = st.text_input("Novo Nome:", value=selected_cat_to_edit)
                with col_e2:
                    st.write("")
                    st.write("")
                    if st.button("Renomear"):
                        ok, msg = db.db_update_category(sel_id, renamed, current_user["id"])
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

                st.write("---")
                if st.button("🗑️ Excluir Subcategoria Selecionada", type="secondary"):
                    ok, msg = db.db_delete_category(sel_id, current_user["id"])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            st.info("Nenhuma subcategoria cadastrada.")

# ==========================================
# 4. MÓDULO: HISTÓRICO & AUDITORIA
# ==========================================
elif menu == "📋 Histórico & Auditoria":
    st.markdown("""
    <div class="app-header">
        <h1>📋 Trilha de Auditoria & Histórico de Modificações</h1>
        <p>Rastreamento de todas as ações de criação, edição e exclusão realizadas no sistema.</p>
    </div>
    """, unsafe_allow_html=True)

    logs = db.db_get_audit_logs(limit=200)
    if logs:
        df_logs = pd.DataFrame(logs)
        df_logs = df_logs[["data", "user_nome", "acao", "entidade", "detalhes"]]
        df_logs.columns = ["Data / Hora (Brasília)", "Usuário", "Ação", "Entidade", "Detalhes da Modificação"]
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum registro de auditoria disponível.")

# ==========================================
# 5. MÓDULO: CONFIGURAÇÕES & SUPABASE
# ==========================================
elif menu == "⚙️ Configurações & Supabase":
    st.markdown("""
    <div class="app-header">
        <h1>⚙️ Configurações do Sistema & Banco de Dados</h1>
        <p>Gerencie a integração com o Supabase (PostgreSQL) e o backup dos dados.</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("🐘 Status da Conexão com o Banco de Dados")
    connected = db.is_db_connected()
    if connected:
        st.success("✅ **O sistema está conectado ao PostgreSQL / Supabase com sucesso!**")
        st.info("Todos os dados são persistidos de forma segura e relacional na nuvem.")
    else:
        st.warning("⚠️ **Operando em Modo Fallback Local (Arquivos JSON)**")
        st.write("""
        Os dados estão sendo salvos localmente no diretório `data/`. Para conectar ao seu banco de dados na nuvem:
        1. Crie seu projeto no [Supabase](https://supabase.com);
        2. Copie a **URI de Conexão** (Transaction Pooler ou Direct Connection);
        3. Adicione no arquivo `.streamlit/secrets.toml` ou no Streamlit Cloud:
        ```toml
        [connections.postgresql]
        url = "postgresql://postgres.SEU_PROJETO:SUA_SENHA@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"
        ```
        """)

    # Botão para Rodar DDL / init_db()
    if st.button("🔄 Executar Inicialização & Sincronização do Banco (`init_db`)", type="primary"):
        with st.spinner("Sincronizando tabelas e migrando dados..."):
            ok, msg = db.init_db()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.write("---")
    st.subheader("💾 Backup e Download dos Dados")
    col_d1, col_d2, col_d3 = st.columns(3)
    
    with col_d1:
        tx_json = open(db.TRANSACTIONS_FILE, "r", encoding="utf-8").read() if os.path.exists(db.TRANSACTIONS_FILE) else "[]"
        st.download_button(
            "📥 Baixar Transações (`transactions.json`)",
            data=tx_json,
            file_name="transactions.json",
            mime="application/json"
        )
    with col_d2:
        cat_json = open(db.CATEGORIES_FILE, "r", encoding="utf-8").read() if os.path.exists(db.CATEGORIES_FILE) else "[]"
        st.download_button(
            "📥 Baixar Subcategorias (`categories.json`)",
            data=cat_json,
            file_name="categories.json",
            mime="application/json"
        )
    with col_d3:
        logs_json = open(db.AUDIT_LOGS_FILE, "r", encoding="utf-8").read() if os.path.exists(db.AUDIT_LOGS_FILE) else "[]"
        st.download_button(
            "📥 Baixar Logs (`audit_logs.json`)",
            data=logs_json,
            file_name="audit_logs.json",
            mime="application/json"
        )
