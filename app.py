import streamlit as st
import pandas as pd
from datetime import date
import io
import base64
import requests
from PIL import Image
import time
from components.functions import (
    atualizar_csv_github_df, 
    salvar_dados, 
    registrar_saida, 
    carregar_dados_github,  # <-- Esta linha já existe
    carregar_descricoes_personalizadas, 
    salvar_nova_descricao, 
    registrar_entrada, 
    registrar_transferencia
)
# Configuração da página
st.set_page_config(page_title="Santa Saúde - Movimentação de Caixa", layout="wide")

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
                st.image(image, 
                         width=400,
                         
                         )
           
        except:
            st.markdown("""
            <div class="login-container">
                <div class="login-header">
                    <h1>🏥 Santa Saúde</h1>
                    <p>Sistema de Movimentação de Caixa</p>
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

st.title("Movimentação de Caixa")

# === KPIS DE SALDO - SEMPRE VISÍVEIS ===
def calcular_saldos():
    # Saldos iniciais
    saldos_iniciais = {
        "DINHEIRO": 1255.40,
        "SANTANDER": 500.18,
        "BANESE": 212.47,
        "C6": 0.00,
        "CAIXA": 0.00,
        "BNB": 0.00,
        "MULVI": 0.00,
        "MERCADO PAGO": 0.00,
        "CONTA PIX": 0.65,
    }
    
    # Carrega movimentações
    df = carregar_dados_github("movimentacoes.csv")
    saldos_atuais = saldos_iniciais.copy()
    
    if not df.empty:
        for conta in saldos_iniciais.keys():
            # Entradas (conta_destino)
            entradas = df[df['conta_destino'] == conta]['valor'].sum()
            # Saídas (conta_origem) 
            saidas = df[df['conta_origem'] == conta]['valor'].sum()
            # Saldo atual = saldo inicial + entradas - saídas
            saldos_atuais[conta] = saldos_iniciais[conta] + entradas - saidas
    
    return saldos_atuais

# Header dos saldos com botão de atualização
col_saldo1, col_saldo2 = st.columns([3, 1])
with col_saldo1:
    st.subheader("💰 Saldos das Contas")
with col_saldo2:
    if st.button("🔄 Atualizar Saldos"):
        st.cache_data.clear()  # Limpa todo o cache
        st.rerun()  # Recarrega a página

# Calcula e exibe os saldos
saldos = calcular_saldos()

# Remove Conta Júlio e reorganiza em 4 colunas x 2 linhas
contas_exibir = ["DINHEIRO", "SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MULVI", "MERCADO PAGO"]

# CSS para estilizar as caixinhas
st.markdown("""
<style>
.saldo-box {
    border: 2px solid #1f4e79;
    background-color: #e6f2ff;
    border-radius: 8px;
    padding: 10px;
    text-align: center;
    margin: 5px 0;
}
.saldo-titulo {
    font-size: 14px;
    font-weight: bold;
    color: #1f4e79;
    margin-bottom: 2px;
}
.saldo-valor {
    font-size: 16px;
    font-weight: bold;
    color: #000;
}
.saldo-positivo {
    color: #008000;
}
.saldo-negativo {
    color: #cc0000;
}
</style>
""", unsafe_allow_html=True)

# Primeira linha - 4 colunas
cols1 = st.columns(4)
for j, conta in enumerate(contas_exibir[:4]):
    saldo = saldos[conta]
    cor_classe = "saldo-positivo" if saldo >= 0 else "saldo-negativo"
    icone = "🟢" if saldo >= 0 else "🔴"
    
    with cols1[j]:
        st.markdown(f"""
        <div class="saldo-box">
            <div class="saldo-titulo">{icone} {conta}</div>
            <div class="saldo-valor {cor_classe}">R$ {saldo:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

# Segunda linha - 4 colunas
cols2 = st.columns(4)
for j, conta in enumerate(contas_exibir[4:]):
    saldo = saldos[conta]
    cor_classe = "saldo-positivo" if saldo >= 0 else "saldo-negativo"
    icone = "🟢" if saldo >= 0 else "🔴"
    
    with cols2[j]:
        st.markdown(f"""
        <div class="saldo-box">
            <div class="saldo-titulo">{icone} {conta}</div>
            <div class="saldo-valor {cor_classe}">R$ {saldo:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()  # Linha separadora

hoje = date.today()
data_min_padrao = hoje.replace(day=1)
data_max_padrao = hoje

# Definições globais para uso em múltiplas abas
custos = [
    "Fixo", "Variável", "Laboratórios e Parceiros", "Recursos Humanos", "Impostos, Taxas e Conselhos",
    "Investimentos", "Comissões"
]

descricoes_dict = {
    "Fixo": sorted([
        "ALUGUEL", "ACESSO NET", "BRISA NET", "CONTABILIDADE", "ALLDOC", "TERMOCLAVE", "PONTO +",
        "MAYELLE", "MIDIA INDOOR", "MARKETING ACERTE", "COPYGRAF", "ASSINATURA FRETE",
        "WORKLAB (MENSALIDADES)", "SISTEMA IA WHATSAPP", "JURÍDICO", "CDL",
        "JOSELITO - COMISSÃO RT", "OUTROS CUSTOS FIXOS"
    ]),
    "Variável": sorted([
        "MANUTENÇÃO - PREDIO E EQUIPAMENTOS", "FARMAC", "CARTAO SANTANDER (8149)", "SULGIPE",
        "CARTÃO MERCADO PAGO", "CARTAO SANTANDER (0986)", "CARTAO PORTO SEGURO",
        "MATERIAL DE ESCRITÓRIO", "MATERIAL DE LIMPEZA E COPA", "CONSULTORIA (SETE ELOS)",
        "TECNICO DE SEGURANÇA DO TRABALHO", "SEGURO YLM", "TRAFEGO PAGO",
        "ALMOÇO E GASTOS DIVERSOS E MOTO TAXI", "SAAE", "OUTROS CUSTOS VARIÁVEIS"
    ]),
    "Laboratórios e Parceiros": sorted([
        "CLIMEDI", "ÁLVARO (LAUDOS)", "SOLIM", "SODRETOX (TOXICOLÓGICO)", "ÁLVARO 1", "ÁLVARO 2", "ÁLVARO 3", "ÁLVARO 4"
    ]),
    "Recursos Humanos": [
        "FOLHA DE PAGAMENTO", "IFOOD BENEFICIOS", "DÉCIMO TERCEIRO", "FERIAS", "VALE TRANSPORTE",
        "PLANO ODONTOLOGICO", "RESCISÃO"
    ],
    "Impostos, Taxas e Conselhos": [
        "SIMPLES (PARCELAMENTO)", "FGTS", "FGTS ATRASADO (funcionarios que saíram)", "INSS",
        "INSS PARCELAMENTO", "SIMPLES", "DAM", "IPTU", "TAXAS (JUROS DE CHEQUE ESPECIAL)",
        "TAXAS CARTÕES", "TAXA DE MANUTENCAO DE CONTA (SANTANDER)", "SOC BRAS DE ANALISE (PNCQ)",
        "CRM", "CRBM (PARCELAMETO)", "CRBM"
    ],
    "Investimentos": [
        "EMPRÉSTIMO BNB REFORMA","EMPRÉSTIMO BNB ULTRASSOM", "ROSE",
        "EMPRÉSTIMO SANTANDER", "EMRPÉSTIMO SANDRO 1",
        "FINANCIAMENTO PLACA SOLAR", "MENTORIA X5", "SISTEMA 2E DASHBOARD",
        "CARTÃO SANDRO", "CARTÃO JÚLIO", "ELETROCARDIOGRAMA"
    ],
    "Comissões": [
        "ESTORNO / TROCO", "COMISSÃO VIVIANE", "COMISSÃO JOANA", "COMISSÕES MÉDICAS"
    ]
}

centros_custo = ["Rateio", "Clínica", "Laboratório"]
formas_pagamento = ["Dinheiro", "Pix", "Débito", "Crédito", "Taxa Antecipação"]
bancos = ["SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MULVI", "MERCADO PAGO", "CONTA JÚLIO"]

# Carrega descrições personalizadas do GitHub (se existirem)
descricoes_extras = carregar_descricoes_personalizadas()
for custo, novas_desc in descricoes_extras.items():
    if custo in descricoes_dict:
        descricoes_dict[custo].extend(novas_desc)
        descricoes_dict[custo] = sorted(list(set(descricoes_dict[custo])))  # Remove duplicatas e ordena

aba = st.tabs(["Inserção", "Alteração Manual","Ver Tabela","Configurações"])

with aba[0]:
    tipos = ["Entrada", "Saída", "Transferência"]
    tipo = st.radio("Tipo", tipos, horizontal=True, key="tipo_input")

    # Inicializa o DataFrame temporário para cada tipo
    if 'linhas_temp' not in st.session_state or st.session_state.get('tipo_temp') != tipo:
        st.session_state['linhas_temp'] = []
        st.session_state['tipo_temp'] = tipo

    # --- ENTRADA ---
    if tipo == "Entrada":
        contas = ["Clinica", "Laboratorio", "Convenios"]
        bancos_convenio = {
            "SESI": "SANTANDER",
            "GEAP": "C6",
            "SUS": "C6",
            "IPES": "BANESE"
        }
        
        col1, col2, col3 = st.columns(3)
        with col1:
            conta = st.selectbox("Conta", contas, key="conta_input")
        
        if conta == "Convenios":
            detalhes = ["SUS", "SESI", "IPES", "GEAP"]
        else:
            detalhes = ["Dinheiro", "Pix", "Débito", "Crédito", "Taxa Antecipação"]
        
        with col2:
            detalhe = st.selectbox("Detalhe", detalhes, key="detalhe_input_entrada")
        
        with col3:
            if conta == "Convenios":
                banco = bancos_convenio.get(detalhe, "")
                st.selectbox("Banco", [banco], key="banco_input_entrada", disabled=True)
            elif detalhe == "Dinheiro":
                st.selectbox("Banco", ["DINHEIRO"], key="banco_input_entrada", disabled=True)
                banco = "DINHEIRO"
            else:
                bancos_disponiveis = ["SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MULVI", "MERCADO PAGO"]
                banco = st.selectbox("Banco", bancos_disponiveis, key="banco_input_entrada")
        
        col4, col5 = st.columns(2)
        with col4:
            data = st.date_input("Data", value=date.today(), key="data_input_entrada")
        with col5:
            valor = st.number_input("Valor", step=0.01, format="%.2f", key="valor_input_entrada")

        st.button("Registrar", on_click=registrar_entrada)

        if st.session_state['linhas_temp']:
            df_temp = pd.DataFrame(st.session_state['linhas_temp'])
            editado = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True, hide_index=True, key="inserir_editor_entrada")
            st.session_state['linhas_temp'] = editado.to_dict('records')
            if st.button("Salvar"):
                salvar_dados("Entrada")
        
    elif tipo == "Saída":
        
        if "data_saida" not in st.session_state:
            st.session_state["data_saida"] = date.today()
        if "custo_saida" not in st.session_state:
            st.session_state["custo_saida"] = "Fixo"
        if "descricao_saida" not in st.session_state:
            st.session_state["descricao_saida"] = ""
        if "detalhamento_saida" not in st.session_state:
            st.session_state["detalhamento_saida"] = ""
        if "centro_saida" not in st.session_state:
            st.session_state["centro_saida"] = "Rateio"
        if "forma_saida" not in st.session_state:
            st.session_state["forma_saida"] = "Dinheiro"
        if "banco_saida" not in st.session_state:
            st.session_state["banco_saida"] = "SANTANDER"
        if "valor_saida" not in st.session_state:
            st.session_state["valor_saida"] = 0.0

        col1, col2 = st.columns(2)
        with col1:
            custo = st.selectbox("Custo", custos, key="custo_saida")
        with col2:
            descricao = st.selectbox("Detalhe", descricoes_dict[custo], key="descricao_saida")
        detalhamento = st.text_input("Observação", key="detalhamento_saida")
        col3, col4 = st.columns(2)
        with col3:
            centro_custo = st.selectbox("Centro de Custo", centros_custo, key="centro_saida")
        with col4:
            forma_pagamento = st.selectbox("Forma de Pagamento", formas_pagamento, key="forma_saida")
        banco = st.selectbox("Banco", bancos, key="banco_saida")
        col5, col6 = st.columns(2)
        with col5:
            data = st.date_input("Data", key="data_saida")
        with col6:
            valor = st.number_input("Valor", step=0.01, format="%.2f", key="valor_saida")

        st.button("Registrar", on_click=registrar_saida)
            
        if st.session_state['linhas_temp']:
            df_temp = pd.DataFrame(st.session_state['linhas_temp'])
            editado = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True, hide_index=True, key="inserir_editor_saida")
            st.session_state['linhas_temp'] = editado.to_dict('records')
            if st.button("Salvar"):
                salvar_dados("Saída")
    elif tipo == "Transferência":
        # Lista de bancos/contas disponíveis
        bancos_contas = ["DINHEIRO", "SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MULVI", "MERCADO PAGO", "CONTA JÚLIO"]
        
        col1, col2 = st.columns(2)
        with col1:
            origem = st.selectbox("Origem", bancos_contas, key="origem_input")
        with col2:
            # Remove a origem das opções de destino para evitar transferência para a mesma conta
            destinos_disponiveis = [b for b in bancos_contas if b != origem]
            destino = st.selectbox("Destino", destinos_disponiveis, key="destino_input")
        
        col3, col4 = st.columns(2)
        with col3:
            data = st.date_input("Data", value=date.today(), key="data_input_transferencia")
        with col4:
            valor = st.number_input("Valor", step=0.01, format="%.2f", key="valor_input_transferencia")

        st.button("Registrar", on_click=registrar_transferencia)

        if st.session_state['linhas_temp']:
            df_temp = pd.DataFrame(st.session_state['linhas_temp'])
            editado = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True, hide_index=True, key="inserir_editor_transferencia")
            st.session_state['linhas_temp'] = editado.to_dict('records')
            if st.button("Salvar"):
                salvar_dados("Transferência")
                
with aba[1]:
    if st.session_state.get('force_refresh', False):
        st.session_state['force_refresh'] = False
        st.cache_data.clear()

    tipos = ["Entrada", "Saída", "Transferência"]
    tipo = st.radio("Tipo", tipos, horizontal=True, key="tipo_alteracao")

    # Agora sempre usa o arquivo único
    arquivo = "movimentacoes.csv"
    col_data = "data"

    df = carregar_dados_github(arquivo)
    if df.empty:
        st.warning("Arquivo ainda não existe ou está vazio.")

    if not df.empty:
        # Filtra apenas o tipo selecionado
        df_tipo = df[df['tipo'] == tipo].copy()
        
        if df_tipo.empty:
            st.info(f"Nenhuma movimentação do tipo {tipo} encontrada.")
        else:
            df_tipo[col_data] = pd.to_datetime(df_tipo[col_data]).dt.date
            data_min = df_tipo[col_data].min()
            data_max = date.today()
            
            hoje = date.today()
            data_min_padrao = hoje.replace(day=1)
            data_max_padrao = hoje
            
            value_ini = min(max(data_min, data_min_padrao), data_max)
            value_fim = max(min(data_max, data_max_padrao), data_min)
            
            col1, col2 = st.columns(2)
            with col1:
                data_ini = st.date_input(
                    "Data inicial",
                    value=value_ini,
                    min_value=data_min,
                    max_value=data_max,
                    key="alt_data_ini"
                )
            with col2:
                data_fim = st.date_input(
                    "Data final",
                    value=value_fim,
                    min_value=data_min,
                    max_value=data_max,
                    key="alt_data_fim"
                )

            mask = (df_tipo[col_data] >= data_ini) & (df_tipo[col_data] <= data_fim)
            df_periodo = df_tipo[mask].copy()

            editado = st.data_editor(
                df_periodo.reset_index(drop=True),
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key=f"alterar_editor_{tipo.lower()}"
            )

            if st.button("Salvar Alterações"):
                if "_deleted" in editado.columns:
                    editado = editado[~editado["_deleted"]].drop(columns=["_deleted"])
                
                # Remove as linhas do período selecionado do DataFrame original
                df_restante = df[~((df['tipo'] == tipo) & (df[col_data].isin(df_periodo[col_data])))]
                df_final = pd.concat([df_restante, editado], ignore_index=True)
                df_final = df_final.sort_values(by=col_data)
                
                atualizar_csv_github_df(
                    df_final,
                    token=st.secrets["github"]["github_token"],
                    repo="leoparipiranga/clinicasantasaude",
                    path="movimentacoes.csv",
                    mensagem="Atualiza movimentacoes.csv via Streamlit"
                )
                st.success("Alterações salvas com sucesso!")
    else:
        st.info("Nenhum dado disponível para alteração.")

with aba[2]:
    st.subheader("Visualização de Tabelas")
    
    tipos = ["Entrada", "Saída", "Transferência"]
    tipo_sel = st.radio("Tipo", tipos, horizontal=True, key="vis_tipo")
    
    arquivo = "movimentacoes.csv"
    df = carregar_dados_github(arquivo)
    
    if df.empty:
        st.warning("Arquivo ainda não existe ou está vazio.")
    else:
        # Filtra pelo tipo selecionado
        df_filtrado = df[df['tipo'] == tipo_sel].copy()
        
        if df_filtrado.empty:
            st.info(f"Nenhuma movimentação do tipo {tipo_sel} encontrada.")
        else:
            df_filtrado['data'] = pd.to_datetime(df_filtrado['data']).dt.date
            data_min = df_filtrado['data'].min()
            data_max = df_filtrado['data'].max()
            
            # Filtros de data
            col1, col2 = st.columns(2)
            with col1:
                data_ini = st.date_input("Data inicial", value=data_min, min_value=data_min, max_value=data_max, key="vis_data_ini")
            with col2:
                data_fim = st.date_input("Data final", value=data_max, min_value=data_min, max_value=data_max, key="vis_data_fim")

            # Aplica filtro de data
            mask = (df_filtrado['data'] >= data_ini) & (df_filtrado['data'] <= data_fim)
            df_filtrado = df_filtrado[mask].copy()

            # Filtros específicos por tipo
            if tipo_sel == "Entrada":
                categorias_disp = ["Todos"] + sorted(df_filtrado['categoria'].dropna().unique().tolist())
                categoria_filtro = st.selectbox("Categoria", categorias_disp, key="vis_categoria")
                if categoria_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['categoria'] == categoria_filtro]
                
                subcategorias_disp = ["Todos"] + sorted(df_filtrado['subcategoria'].dropna().unique().tolist())
                subcategoria_filtro = st.selectbox("Subcategoria", subcategorias_disp, key="vis_subcategoria")
                if subcategoria_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['subcategoria'] == subcategoria_filtro]
                
                contas_disp = ["Todos"] + sorted(df_filtrado['conta_destino'].dropna().unique().tolist())
                conta_filtro = st.selectbox("Conta Destino", contas_disp, key="vis_conta")
                if conta_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['conta_destino'] == conta_filtro]
                    
            elif tipo_sel == "Saída":
                categorias_disp = ["Todos"] + sorted(df_filtrado['categoria'].dropna().unique().tolist())
                categoria_filtro = st.selectbox("Categoria", categorias_disp, key="vis_categoria")
                if categoria_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['categoria'] == categoria_filtro]
                
                subcategorias_disp = ["Todos"] + sorted(df_filtrado['subcategoria'].dropna().unique().tolist())
                subcategoria_filtro = st.selectbox("Subcategoria", subcategorias_disp, key="vis_subcategoria")
                if subcategoria_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['subcategoria'] == subcategoria_filtro]
                
                contas_disp = ["Todos"] + sorted(df_filtrado['conta_origem'].dropna().unique().tolist())
                conta_filtro = st.selectbox("Conta Origem", contas_disp, key="vis_conta")
                if conta_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['conta_origem'] == conta_filtro]
                    
            elif tipo_sel == "Transferência":
                origens_disp = ["Todos"] + sorted(df_filtrado['conta_origem'].dropna().unique().tolist())
                origem_filtro = st.selectbox("Conta Origem", origens_disp, key="vis_origem")
                if origem_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['conta_origem'] == origem_filtro]
                
                destinos_disp = ["Todos"] + sorted(df_filtrado['conta_destino'].dropna().unique().tolist())
                destino_filtro = st.selectbox("Conta Destino", destinos_disp, key="vis_destino")
                if destino_filtro != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['conta_destino'] == destino_filtro]

            # Resumo e tabela
            num_linhas = len(df_filtrado)
            total = df_filtrado['valor'].sum()
            st.markdown(
                f"<div style='font-size:1.2em; font-weight:bold;'>{num_linhas} Linhas filtradas  -  Total: R$ {total:,.2f}</div>",
                unsafe_allow_html=True
            )

            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

with aba[3]:
    st.subheader("Configurações")
    
    config_opcao = st.radio("O que deseja configurar?", 
                           ["Descrições de Saída", "Outras Configurações"], 
                           horizontal=True)
    
    if config_opcao == "Descrições de Saída":
        st.subheader("Gerenciar Descrições de Saída")
        
        # Selectbox para escolher o tipo de custo
        custo_config = st.selectbox("Selecione o tipo de custo:", custos, key="custo_config")
        
        # Mostra as descrições atuais
        st.write(f"**Descrições atuais para {custo_config}:**")
        for desc in descricoes_dict[custo_config]:
            st.write(f"• {desc}")
        
        # Formulário para adicionar nova descrição
        with st.form("nova_descricao_form"):
            nova_desc = st.text_input("Nova descrição:")
            submitted = st.form_submit_button("Adicionar")
            
            if submitted and nova_desc:
                if nova_desc not in descricoes_dict[custo_config]:
                    # Salva a nova descrição em um arquivo
                    salvar_nova_descricao(custo_config, nova_desc)
                    st.success(f"Descrição '{nova_desc}' adicionada com sucesso!")
                    st.rerun()
                else:
                    st.warning("Esta descrição já existe!")