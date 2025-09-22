import streamlit as st
import pandas as pd
from datetime import date, timedelta
import io
import base64
import requests
from PIL import Image
import time
import os
from components.functions import (
    atualizar_csv_github_df, 
    salvar_dados, 
    registrar_saida, 
    carregar_dados_github,
    carregar_dados_github_api,  
    carregar_descricoes_personalizadas, 
    salvar_nova_descricao, 
    registrar_entrada, 
    registrar_transferencia
)
from components.gestao_recebimentos import *
from components.importacao import *
from components.contas import *
from modules import (
    prestacao_servicos,
    recebimentos,
    pagamentos,
    pagamentos_medicos,
    transferencia,
    edicao,
    configuracoes)

inicializar_movimentacao_contas()

# Configuração da página
st.set_page_config(
    page_title="Santa Saúde - Sistema de Gestão", 
    layout="wide",
    initial_sidebar_state="expanded"
)

def login():
    """Tela de login do sistema"""
    
    # Container centralizado para o login
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Header com imagem
        try:
            image = Image.open("santasaude.png")
            st.markdown("""
            <div class="login-container">
                <div class="login-header">
            """, unsafe_allow_html=True)
            
            # Centraliza a imagem
            col_img1, col_img2, col_img3 = st.columns([1, 2, 1])
            with col_img2:
                st.image(image, width=400)
           
        except:
            st.markdown("""
            <div class="login-container">
                <div class="login-header">
                    <h1>🏥 Santa Saúde</h1>
                    <p>Sistema de Gestão</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Formulário de login
        with st.form("login_form"):
            st.markdown("### 🔐 Acesso ao Sistema")
            
            usuario = st.text_input(
                "👤 Usuário:",
                placeholder="Digite seu usuário",
                help="Use seu nome de usuário cadastrado"
            )
            
            senha = st.text_input(
                "🔑 Senha:",
                type="password",
                placeholder="Digite sua senha",
                help="Digite sua senha de acesso"
            )
            
            col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
            
            with col_btn2:
                submit_button = st.form_submit_button(
                    "🚀 Entrar no Sistema",
                    use_container_width=True,
                    type="primary"
                )
            
            if submit_button:
                if usuario and senha:
                    try:
                        usuarios = st.secrets["usuarios"]
                    except KeyError:
                        st.error("❌ Configuração de login não encontrada!")
                        st.stop()
                    
                    # Verifica se o usuário existe e a senha está correta
                    if usuario in usuarios and senha == usuarios[usuario]["senha"]:
                        # Login bem-sucedido
                        st.session_state['authenticated'] = True
                        st.session_state['usuario_logado'] = usuario
                        st.session_state['nome_completo'] = usuarios[usuario]["nome_completo"]
                        
                        st.success(f"✅ Bem-vindo, {usuarios[usuario]['nome_completo']}!")
                        st.rerun()
                        
                    else:
                        st.error("❌ Usuário ou senha incorretos!")
                        st.warning("💡 Verifique suas credenciais e tente novamente")
                        
                else:
                    st.warning("⚠️ Por favor, preencha usuário e senha")

def exibir_saldos():
    """Exibe os saldos das contas em formato de cards com estilo moderno."""
    
    # Header dos saldos com botão de atualização
    col_saldo1, col_saldo2 = st.columns([3, 1])
    with col_saldo1:
        st.subheader("💰 Saldos das Contas")
    with col_saldo2:
        if st.button("🔄 Atualizar Saldos"):
            st.cache_data.clear()
            st.rerun()

    # Calcula os saldos
    saldos = calcular_saldos()
    
    # Novo CSS para os cards com tons de cinza e efeito 3D
    st.markdown("""
    <style>
    .card-saldo {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
        text-align: center;
        height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .card-saldo:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    .card-titulo {
        font-size: 14px;
        font-weight: bold;
        color: #555555;
        margin-bottom: 8px;
    }
    .card-valor {
        font-size: 20px;
        font-weight: bold;
    }
    .saldo-positivo {
        color: #2e7d32; /* Verde mais sóbrio */
    }
    .saldo-negativo {
        color: #c62828; /* Vermelho mais sóbrio */
    }
    </style>
    """, unsafe_allow_html=True)

    # --- NOVO LAYOUT ---
    # Contas a serem exibidas
    contas_principais = ["DINHEIRO", "CONTA PIX"]
    outras_contas = ["SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MERCADO PAGO"]

    # Layout: 2 colunas principais para a nova organização
    col_main1, col_main2 = st.columns([1, 2])

    with col_main1:
        # Coluna para DINHEIRO e CONTA PIX
        for conta in contas_principais:
            saldo = saldos.get(conta, 0.0)
            cor_classe = "saldo-positivo" if saldo >= 0 else "saldo-negativo"
            nome_exibicao = "CAIXA FÍSICO" if conta == "DINHEIRO" else conta
            
            st.markdown(f"""
            <div class="card-saldo">
                <div class="card-titulo">{nome_exibicao}</div>
                <div class="card-valor {cor_classe}">R$ {saldo:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)

    with col_main2:
        # 3 colunas para as outras 6 contas
        cols_outras = st.columns(3)
        
        for i, conta in enumerate(outras_contas):
            col_idx = i % 3
            with cols_outras[col_idx]:
                saldo = saldos.get(conta, 0.0)
                cor_classe = "saldo-positivo" if saldo >= 0 else "saldo-negativo"
                nome_exibicao = "M. PAGO" if conta == "MERCADO PAGO" else conta

                st.markdown(f"""
                <div class="card-saldo">
                    <div class="card-titulo">{nome_exibicao}</div>
                    <div class="card-valor {cor_classe}">R$ {saldo:,.2f}</div>
                </div>
                """, unsafe_allow_html=True)

# Verifica se o usuário está autenticado
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    login()
    st.stop()

# Header com logout (só aparece se estiver autenticado)
col1, col2, col3 = st.columns([6, 1, 1])
with col2:
    nome = st.session_state.get('nome_completo', 'Usuário')
    st.write(f"**{nome}**")
with col3:
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.session_state["usuario_logado"] = ""
        st.session_state["nome_completo"] = ""
        st.rerun()

# CSS para estilizar o menu lateral
st.markdown("""
<style>
.sidebar-menu {
    padding: 20px 0;
}
.menu-item {
    display: block;
    padding: 15px 20px;
    margin: 10px 0;
    background-color: #f0f2f6;
    border-radius: 10px;
    text-decoration: none;
    color: #262730;
    border: 2px solid transparent;
    transition: all 0.3s ease;
}
.menu-item:hover {
    background-color: #e6f2ff;
    border-color: #1f4e79;
    transform: translateX(5px);
}
.menu-item.active {
    background-color: #1f4e79;
    color: white;
    border-color: #1f4e79;
}
.menu-icon {
    font-size: 24px;
    margin-right: 15px;
}
.menu-text {
    font-size: 16px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# Menu lateral
st.sidebar.markdown('<div class="sidebar-menu">', unsafe_allow_html=True)
st.sidebar.markdown("## 📋 Menu Principal")

# Inicializa a página selecionada se não existir
if 'page_selected' not in st.session_state:
    st.session_state.page_selected = 'prestacao_servicos'

# Botões do menu
if st.sidebar.button("🩺 Importações", use_container_width=True):
    st.session_state.page_selected = 'prestacao_servicos'
    st.rerun()

if st.sidebar.button("💰 Recebimentos", use_container_width=True):
    st.session_state.page_selected = 'recebimentos'
    st.rerun()

if st.sidebar.button("💳 Pagamentos", use_container_width=True):
    st.session_state.page_selected = 'pagamentos'
    st.rerun()

if st.sidebar.button("👨‍⚕️ Pagamentos Médicos", use_container_width=True):
    st.session_state.page_selected = 'pagamentos_medicos'
    st.rerun()

if st.sidebar.button("🔄 Transferências", use_container_width=True):
    st.session_state.page_selected = 'transferencia'
    st.rerun()
if st.sidebar.button("🛠️ Edição", use_container_width=True):
    st.session_state.page_selected = 'edicao'
    st.rerun()

# if st.sidebar.button("⚙️ Configurações", use_container_width=True):
#     st.session_state.page_selected = 'configuracoes'
#     st.rerun()

st.sidebar.markdown('</div>', unsafe_allow_html=True)

# Título principal
st.subheader("🏥 Santa Saúde - Sistema de Gestão")

# Carrega a página selecionada
page = st.session_state.page_selected

if page == 'prestacao_servicos':
    from modules import prestacao_servicos
    prestacao_servicos.show()
elif page == 'recebimentos':
    # Exibe saldos para páginas financeiras
    exibir_saldos()
    st.markdown("---")
    from modules import recebimentos
    recebimentos.show()
elif page == 'pagamentos':
    # Exibe saldos para páginas financeiras
    exibir_saldos()
    st.markdown("---")
    from modules import pagamentos
    pagamentos.show()
elif page == 'pagamentos_medicos':
    # Exibe saldos para páginas financeiras
    exibir_saldos()
    st.markdown("---")
    from modules import pagamentos_medicos
    pagamentos_medicos.show()
elif page == 'transferencia':
    # Exibe saldos para páginas financeiras
    exibir_saldos()
    st.markdown("---")
    from modules import transferencia
    transferencia.show()
elif page == "edicao":
    from modules.edicao import mostrar_edicao
    mostrar_edicao()
    
# elif page == 'configuracoes':
#     from modules import configuracoes
#     configuracoes.show()