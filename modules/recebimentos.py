import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from components.gestao_recebimentos import *
from components.importacao import atualizar_recebimentos_pendentes
import os

def _sanitize_valores_cols(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """
    Converte múltiplas colunas de valores para float.
    """
    if df is None or df.empty:
        return df
    for col in cols:
        if col not in df.columns:
            continue
        def _to_float(v):
            if pd.isna(v):
                return 0.0
            s = str(v).strip()
            if s in ('', '-', 'nan', 'None'):
                return 0.0
            s = (s.replace('R$', '')
                   .replace('r$', '')
                   .replace('\u00A0', '')
                   .replace(' ', ''))
            if '.' in s and ',' in s:
                s = s.replace('.', '').replace(',', '.')
            elif ',' in s and '.' not in s:
                s = s.replace(',', '.')
            try:
                return float(s)
            except:
                return 0.0
        df[col] = df[col].apply(_to_float)
    return df

def show():
    """Página principal de gestão de recebimentos."""
    st.header("💰 Gestão de Recebimentos")
    
    # Verifica se há dados de recebimentos
    df_todos = obter_recebimentos_pendentes()
    
    if df_todos.empty:
        st.info("📝 Nenhum recebimento pendente encontrado.")
        if st.button("🔄 Atualizar Recebimentos Pendentes", type="primary"):
            with st.spinner("Atualizando..."):
                sucesso, msg = atualizar_recebimentos_pendentes()
                if sucesso:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        return
    
    # Cria as 4 abas principais (adicionando Débito)
    tab_geral, tab_cartoes, tab_ipes = st.tabs([
        "📋 Geral (Convênios)", 
        "💳 Conciliação Cartões", 
        "🏥 Conciliação IPES"
    ])
    
    with tab_geral:
        mostrar_aba_geral()
    
    with tab_cartoes:
        mostrar_aba_cartoes()
        
    with tab_ipes:
        mostrar_aba_ipes()

def mostrar_aba_geral():
    """Aba para baixa manual de convênios (exceto IPES e cartões)."""
    st.caption("Aqui você pode dar baixa em convênios diversos (exceto IPES e cartões de crédito)")
    
    # Carrega apenas convênios outros
    df_convenios = obter_recebimentos_convenios_outros()
    df_convenios = _sanitize_valores_cols(df_convenios, ['valor_pendente'])
    
    if df_convenios.empty:
        st.info("Não há recebimentos de convênios pendentes.")
        return
    
    # Garante que só mostra pendentes (filtro adicional de segurança)
    if 'status' in df_convenios.columns:
        df_convenios = df_convenios[df_convenios['status'] == 'pendente']

    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        convenios_unicos = sorted(df_convenios['origem_recebimento'].unique())
        convenio_selecionado = st.selectbox(
            "Filtrar por Convênio:",
            options=['Todos'] + convenios_unicos,
            key="filtro_convenio_geral"
        )
    
    with col2:
        data_inicio = st.date_input(
            "Data Início:",
            value=df_convenios['data_operacao'].min(),
            key="data_inicio_geral"
        )
    
    with col3:
        data_fim = st.date_input(
            "Data Fim:",
            value=df_convenios['data_operacao'].max(),
            key="data_fim_geral"
        )
    
    # Aplica filtros
    df_filtrado = df_convenios.copy()
    
    if convenio_selecionado != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['origem_recebimento'] == convenio_selecionado]
    
    df_filtrado['data_operacao'] = pd.to_datetime(df_filtrado['data_operacao'])
    mask = (df_filtrado['data_operacao'].dt.date >= data_inicio) & (df_filtrado['data_operacao'].dt.date <= data_fim)
    df_filtrado = df_filtrado[mask]
    
    if df_filtrado.empty:
        st.warning("Nenhum recebimento encontrado com os filtros aplicados.")
        return
    
    # Métricas
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Total de Recebimentos", len(df_filtrado))
    with col_m2:
        st.metric("Valor Total", f"R$ {df_filtrado['valor_pendente'].sum():,.2f}")
    with col_m3:
        st.metric("Valor Médio", f"R$ {df_filtrado['valor_pendente'].mean():,.2f}")
    
    st.markdown("---")
    
    # NOVO: Seleção de conta ANTES da tabela para evitar reset
    contas = obter_contas_disponiveis()
    conta_destino = st.selectbox(
        "Conta de Destino:",
        options=contas,
        index=contas.index('DINHEIRO') if 'DINHEIRO' in contas else 0,
        key="conta_baixa_convenio"
    )
    
    # Tabela com checkbox
    st.markdown("### 📝 Selecione os recebimentos para baixa:")
    
    # Botão Selecionar Todos
    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        if st.button("✅ Selecionar Todos", key="sel_todos_convenios", use_container_width=True):
            st.session_state['selecionar_todos_convenios'] = True
    with col_btn2:
        if st.button("❌ Desmarcar Todos", key="desmarcar_todos_convenios", use_container_width=True):
            st.session_state['selecionar_todos_convenios'] = False
    
    # Adiciona coluna de seleção
    df_filtrado = df_filtrado.reset_index(drop=True)
    
    # NOVO: Preserva seleção da tabela no session_state
    if 'selecao_convenios' not in st.session_state:
        st.session_state.selecao_convenios = [False] * len(df_filtrado)
    
    # Define o estado inicial baseado no botão ou session_state
    if 'selecionar_todos_convenios' in st.session_state:
        df_filtrado['selecionar'] = st.session_state['selecionar_todos_convenios']
        st.session_state.selecao_convenios = df_filtrado['selecionar'].tolist()  # Atualiza session_state
    else:
        df_filtrado['selecionar'] = st.session_state.selecao_convenios[:len(df_filtrado)] + [False] * (len(df_filtrado) - len(st.session_state.selecao_convenios))
    
    # Prepara display
    df_display = df_filtrado.copy()
    df_display['data_operacao'] = df_display['data_operacao'].dt.strftime('%d/%m/%Y')
    
    # Editor com checkbox
    df_editado = st.data_editor(
        df_display[['selecionar', 'data_operacao', 'paciente', 'origem_recebimento', 'valor_pendente']],
        column_config={
            'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
            'data_operacao': 'Data',
            'paciente': 'Paciente',
            'origem_recebimento': 'Convênio',
            'valor_pendente': 'Valor'
        },
        disabled=['data_operacao', 'paciente', 'origem_recebimento', 'valor_pendente'],
        hide_index=True,
        use_container_width=True,
        key="editor_convenios"
    )
    
    # NOVO: Atualiza session_state com a seleção atual
    st.session_state.selecao_convenios = df_editado['selecionar'].tolist()
    
    # Limpa o estado após renderizar
    if 'selecionar_todos_convenios' in st.session_state:
        del st.session_state['selecionar_todos_convenios']
    
    # Área de confirmação
    if df_editado['selecionar'].any():
        selecionados = df_filtrado[df_editado['selecionar']]
        
        st.markdown("---")
        st.markdown("### ✅ Confirmar Baixa")
        
        valor_total = selecionados['valor_pendente'].sum()
        
        col_conf1, col_conf2 = st.columns(2)
        
        with col_conf1:
            st.info(f"**{len(selecionados)} recebimento(s) selecionado(s)**")
            st.info(f"**Valor total: R$ {valor_total:,.2f}**")
        
        with col_conf2:
            data_recebimento = st.date_input(
                "Data do Recebimento:",
                value=date.today(),
                key="data_baixa_convenio"
            )
            
            # NOVO: Campo editável para Valor Baixado
            valor_baixado = st.number_input(
                "Valor Baixado (opcional):",
                min_value=0.0,
                value=valor_total,  # Padrão = valor total
                step=0.01,
                format="%.2f",
                key="valor_baixado_convenio"
            )
        
        if st.button("💰 Confirmar Baixa", type="primary", use_container_width=True):
            ids_selecionados = selecionados['id_pendencia'].tolist()
            
            with st.spinner("Processando baixa..."):
                # NOVO: Passa valor_baixado para registrar na conta
                sucesso, msg = registrar_baixa_convenio(ids_selecionados, data_recebimento, conta_destino, valor_baixado=valor_baixado)
                
                if sucesso:
                    # NOVO: Salva diferença no pkl se valor_baixado != valor_total
                    if abs(valor_baixado - valor_total) > 0.01:  # Tolerância para arredondamento
                        salvar_diferenca_baixa(data_recebimento, valor_total, valor_baixado)
                    
                    st.success(msg)
                    st.balloons()
                    if 'selecao_convenios' in st.session_state:
                        del st.session_state.selecao_convenios
                    st.rerun()
                else:
                    st.error(msg)

def mostrar_aba_cartoes():
    """Aba para conciliação de cartões de crédito."""
    
    # Inicializa session_state se não existir
    if 'cartao_sel' not in st.session_state:
        st.session_state.cartao_sel = None
    
    # Botões para selecionar o cartão
    col1, col2 = st.columns(2)
    
    with col1:
        tipo_botao = "primary" if st.session_state.cartao_sel == 'MULVI' else "secondary"
        if st.button("💳 MULVI", use_container_width=True, type=tipo_botao, key="btn_mulvi"):
            st.session_state.cartao_sel = 'MULVI'
            st.rerun()
    
    with col2:
        tipo_botao = "primary" if st.session_state.cartao_sel == 'GETNET' else "secondary"
        if st.button("💳 GETNET", use_container_width=True, type=tipo_botao, key="btn_getnet"):
            st.session_state.cartao_sel = 'GETNET'
            st.rerun()
    
    # Mostra a conciliação do cartão selecionado
    cartao = st.session_state.get('cartao_sel')
    
    if not cartao:
        st.info("👆 Selecione um cartão para começar a conciliação")
        return
    
    st.markdown(f"---")
    st.markdown(f"### Conciliando: {cartao}")
    
    df_recebimentos = obter_recebimentos_cartao(cartao)
    df_recebimentos = _sanitize_valores_cols(df_recebimentos, ['valor_pendente'])
    
    df_transacoes = obter_dados_cartao(cartao)
    
    if df_recebimentos.empty:
        st.warning(f"Não há recebimentos pendentes de {cartao}")
        return
    
    if df_transacoes.empty:
        st.warning(f"Não há transações importadas de {cartao}")
        return

    df_transacoes.rename(columns={'Data_Transação': 'data_transacao'}, inplace=True)
    
    # Prepara dados para exibição - recebimentos
    df_recebimentos = df_recebimentos.reset_index(drop=True)
    df_recebimentos['selecionar'] = False
    
    # Prepara dados para exibição - transações (já tem indice_arquivo)
    df_transacoes = df_transacoes.reset_index(drop=True)
    df_transacoes['selecionar'] = False

    # --- Inputs de filtro de data (antes das tabelas) ---
    # determina intervalos padrão com base nos dados disponíveis
    min_candidates = []
    max_candidates = []
    if not df_recebimentos.empty and 'data_operacao' in df_recebimentos.columns:
        min_candidates.append(df_recebimentos['data_operacao'].min())
        max_candidates.append(df_recebimentos['data_operacao'].max())

    # para transações considere ambas as possíveis colunas: data_transacao (MULVI) ou data_venda (GETNET)
    if not df_transacoes.empty:
        if 'data_transacao' in df_transacoes.columns:
            dt = pd.to_datetime(df_transacoes['data_transacao'], errors='coerce')
            min_candidates.append(dt.min())
            max_candidates.append(dt.max())
        elif 'data_venda' in df_transacoes.columns:
            col = pd.to_datetime(df_transacoes['data_venda'], errors='coerce')
            min_candidates.append(col.min())
            max_candidates.append(col.max())

    min_default = min([d for d in min_candidates if pd.notna(d)], default=pd.to_datetime(date.today()))
    max_default = max([d for d in max_candidates if pd.notna(d)], default=pd.to_datetime(date.today()))

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filtro_inicio = st.date_input("Data Início:", value=min_default.date(), key="filtro_cartoes_inicio")
    with col_f2:
        filtro_fim = st.date_input("Data Fim:", value=max_default.date(), key="filtro_cartoes_fim")

    # aplica filtro a ambos os dataframes
    if not df_recebimentos.empty and 'data_operacao' in df_recebimentos.columns:
        mask_rec = (pd.to_datetime(df_recebimentos['data_operacao']).dt.date >= filtro_inicio) & (pd.to_datetime(df_recebimentos['data_operacao']).dt.date <= filtro_fim)
        df_recebimentos = df_recebimentos[mask_rec].reset_index(drop=True)

    if not df_transacoes.empty:
        # escolhe coluna de data apropriada e cria série datetime temporária para filtrar
        if 'data_transacao' in df_transacoes.columns:
            dt_series = pd.to_datetime(df_transacoes['data_transacao'], errors='coerce')
        elif 'data_venda' in df_transacoes.columns:
            col = df_transacoes['data_venda']
            if pd.api.types.is_datetime64_any_dtype(col):
                dt_series = col
            else:
                s = col.astype(str)
                try:
                    if s.str.contains('/').any():
                        dt_series = pd.to_datetime(s, dayfirst=True, errors='coerce')
                    else:
                        dt_series = pd.to_datetime(s, errors='coerce')
                except Exception:
                    dt_series = pd.to_datetime(s, errors='coerce')
        else:
            dt_series = None

        if dt_series is not None:
            mask_trans = (dt_series.dt.date >= filtro_inicio) & (dt_series.dt.date <= filtro_fim)
            df_transacoes = df_transacoes[mask_trans].reset_index(drop=True)


    # Duas colunas para as tabelas
    col_esq, col_dir = st.columns(2)
    
    with col_esq:
        st.markdown("#### 📋 Recebimentos Pendentes")
        
        df_rec_display = df_recebimentos.copy()
        df_rec_display['data_operacao'] = pd.to_datetime(df_rec_display['data_operacao']).dt.date
                
        st.markdown(f"<span style='color:blue; font-size:small;'>{len(df_recebimentos)} registros pendentes</span>", unsafe_allow_html=True)
        
        if 'baixa_parcial' not in df_rec_display.columns:
            df_rec_display['baixa_parcial'] = False
        if 'valor_residual' not in df_rec_display.columns:
            df_rec_display['valor_residual'] = df_rec_display['valor_pendente']
        if 'n_parcelas' not in df_rec_display.columns:
            df_rec_display['n_parcelas'] = 1
        
        colunas_exibir_rec = ['selecionar', 'baixa_parcial', 'data_operacao', 'paciente', 'valor_pendente', 'valor_residual', 'n_parcelas']
        
        column_config_rec = {
            'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
            'baixa_parcial': st.column_config.CheckboxColumn('Baixa Parcial', width='small'),
            'data_operacao': 'Data',
            'paciente': 'Paciente',
            'valor_pendente': 'Valor Total',
            'valor_residual': 'Valor Residual',
            'n_parcelas': st.column_config.NumberColumn('Nº Parcelas', format="%d")
        }
        
        df_rec_editado = st.data_editor(
            df_rec_display[colunas_exibir_rec],
            column_config=column_config_rec,
            disabled=['data_operacao', 'paciente', 'valor_pendente', 'valor_residual', 'n_parcelas'],
            hide_index=True,
            height=400,
            key=f"editor_rec_{cartao}"
        )
    
    with col_dir:
        st.markdown(f"#### 💳 Transações {cartao}")

        df_trans_display = df_transacoes.copy()
        if cartao == 'MULVI':
            # data principal e data da transação (adicionada)
            df_trans_display['data'] = pd.to_datetime(df_trans_display['Data_Lançamento'], dayfirst=True, errors='coerce').dt.date
            if 'data_transacao' in df_trans_display.columns:
                df_trans_display['data_transacao'] = pd.to_datetime(df_trans_display['data_transacao'], dayfirst=True, errors='coerce').dt.date
            else:
                df_trans_display['data_transacao'] = ''
            # n_parcelas e valores
            def get_n_parcelas(parcela):
                try:
                    return int(str(parcela).split('/')[-1])
                except:
                    return 1
            df_trans_display['n_parcelas'] = df_trans_display['Parcela'].apply(get_n_parcelas)
            df_trans_display['valor_total_venda'] = df_trans_display['ValorBruto'] * df_trans_display['n_parcelas']
            df_trans_display['info'] = df_trans_display['Bandeira']
            df_trans_display['parcela'] = df_trans_display['Parcela']
            # Colunas para exibir (inclui data_transacao)
            colunas_exibir = [
                'selecionar', 'data', 'data_transacao', 'valor_total_venda', 'ValorBruto', 'ValorLiquido', 'info', 'parcela'
            ]
            column_config = {
                'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
                'data': 'Data Lançamento',
                'data_transacao': 'Data Transação',
                'valor_total_venda': st.column_config.NumberColumn('Valor Total Venda', format="%.2f"),
                'ValorBruto': st.column_config.NumberColumn('Valor Bruto', format="%.2f"),
                'ValorLiquido': st.column_config.NumberColumn('Valor Líquido', format="%.2f"),
                'info': 'Tipo/Bandeira',
                'parcela': 'Parcela',
                'parcela_antiga': st.column_config.CheckboxColumn('Parcela Antiga', width='small')
            }
            # colunas que serão desabilitadas no editor
            disabled_cols = ['data', 'data_transacao', 'valor_total_venda', 'ValorBruto', 'ValorLiquido', 'info', 'parcela']
        else:  # GETNET 
            # Prepara as colunas para GETNET
            df_trans_display['cartoes'] = df_trans_display['cartoes']
            df_trans_display['data_venda'] = pd.to_datetime(df_trans_display['data_venda'], dayfirst=True, errors='coerce').dt.date
            df_trans_display['descricao'] = df_trans_display['descricao_lancamento']
            df_trans_display['n_parcelas'] = df_trans_display['n_parcelas']
            df_trans_display['valor_bruto'] = df_trans_display['valor_bruto']
            df_trans_display['valor_taxa'] = df_trans_display['valor_taxa']
            df_trans_display['valor_liquido'] = df_trans_display['valor_liquido']
            
            colunas_exibir = [
                'selecionar', 'cartoes', 'data_venda', 'descricao', 'n_parcelas', 'valor_bruto', 'valor_taxa', 'valor_liquido'
            ]
            column_config = {
                'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
                'cartoes': 'Cartões',
                'data_venda': 'Data Venda',
                'descricao': 'Descrição',
                'n_parcelas': st.column_config.NumberColumn('Total Parcelas', format="%d"),
                'valor_bruto': st.column_config.NumberColumn('Valor Bruto', format="%.2f"),
                'valor_taxa': st.column_config.NumberColumn('Valor Taxa', format="%.2f"),
                'valor_liquido': st.column_config.NumberColumn('Valor Líquido', format="%.2f"),
                'parcela_antiga': st.column_config.CheckboxColumn('Parcela Antiga', width='small')
            }
            disabled_cols = ['cartoes', 'data_venda', 'descricao', 'total_parcelas', 'valor_bruto', 'valor_taxa', 'valor_liquido']
        
        # Adiciona a coluna de seleção de parcela antiga
        df_trans_display['parcela_antiga'] = False
        colunas_exibir.append('parcela_antiga')

        st.markdown(f"<span style='color:blue; font-size:small;'>{len(df_trans_display)} registros pendentes</span>", unsafe_allow_html=True)

        df_trans_editado = st.data_editor(
            df_trans_display[colunas_exibir],
            column_config=column_config,
            disabled=disabled_cols,
            hide_index=True,
            height=400,
            key=f"editor_trans_{cartao}"
        )
    
    # Área de confirmação
    rec_selecionados = df_recebimentos[df_rec_editado['selecionar']]
    trans_selecionadas = df_transacoes[df_trans_editado['selecionar']]

    baixa_parcial_selecionada = df_rec_editado['baixa_parcial'].any()
    parcela_antiga_selecionada = df_trans_editado['parcela_antiga'].any()

    # Permite conciliação se houver transações selecionadas E (recebimentos selecionados OU parcela antiga marcada)
    if not trans_selecionadas.empty and (not rec_selecionados.empty or parcela_antiga_selecionada):
        st.markdown("---")
        st.markdown("### ✅ Escolha a Operação")
        
        # NOVO: Para GETNET, mostra dois botões
        if cartao == 'GETNET':
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                btn_conciliacao = st.button(
                    "💰 Confirmar Conciliação GETNET", 
                    type="secondary", 
                    use_container_width=True,
                    key="btn_conciliacao_getnet"
                )
            
            with col_btn2:
                btn_antecipacao = st.button(
                    "⚡ Registrar Antecipação", 
                    type="primary", 
                    use_container_width=True,
                    key="btn_antecipacao_getnet"
                )
            
            # Inicializa session_state se não existir
            if 'operacao_selecionada_getnet' not in st.session_state:
                st.session_state.operacao_selecionada_getnet = None
            
            # Define qual operação foi selecionada
            if btn_conciliacao:
                st.session_state.operacao_selecionada_getnet = 'conciliacao'
            elif btn_antecipacao:
                st.session_state.operacao_selecionada_getnet = 'antecipacao'
            
            # Mostra formulário baseado na operação selecionada
            if st.session_state.operacao_selecionada_getnet == 'conciliacao':
                st.markdown("### 💰 Conciliação GETNET")
                
                # Calcula valores para conciliação
                if baixa_parcial_selecionada:
                    valor_bruto = trans_selecionadas['valor_bruto'].sum()
                else:
                    if not rec_selecionados.empty:
                        valor_bruto = rec_selecionados['valor_pendente'].sum()
                    else:
                        valor_bruto = trans_selecionadas['valor_bruto'].sum()
                
                valor_liquido = trans_selecionadas['valor_liquido'].sum()
                taxa = valor_bruto - valor_liquido
                
                col_info1, col_info2, col_info3 = st.columns(3)
                
                with col_info1:
                    st.metric("Valor Bruto", f"R$ {valor_bruto:,.2f}")
                with col_info2:
                    st.metric("Valor Líquido", f"R$ {valor_liquido:,.2f}")
                with col_info3:
                    st.metric("Taxa", f"R$ {taxa:,.2f}", delta_color="inverse")
                
                # Seleção de conta
                contas = obter_contas_disponiveis()
                conta_destino = st.selectbox(
                    "Conta de Destino:",
                    options=contas,
                    index=contas.index('BANESE') if 'BANESE' in contas else 0,
                    key="conta_conciliacao_getnet"
                )
                
                if st.button("✅ Executar Conciliação", type="primary", use_container_width=True):
                    # Define ids_rec baseado em parcela antiga
                    if parcela_antiga_selecionada:
                        ids_rec = []
                    else:
                        ids_rec = rec_selecionados['id_pendencia'].tolist()
                    
                    indices_trans_arquivo = _extract_indices_trans(trans_selecionadas)
                    
                    # Para baixa parcial, use o valor_bruto da transação como valor_parcial
                    if baixa_parcial_selecionada:
                        valores_parciais = [valor_bruto] * len(ids_rec)
                    else:
                        valores_parciais = []
                    
                    with st.spinner("Processando conciliação..."):
                        sucesso, msg = registrar_conciliacao_cartao(
                            ids_rec, 
                            indices_trans_arquivo, 
                            cartao, 
                            conta_destino,
                            baixa_parcial=baixa_parcial_selecionada,
                            valores_parciais=valores_parciais,
                            parcela_antiga=parcela_antiga_selecionada
                        )
                        
                        if sucesso:
                            st.success(msg)
                            st.balloons()
                            st.session_state.operacao_selecionada_getnet = None
                            st.rerun()
                        else:
                            st.error(msg)
            
            elif st.session_state.operacao_selecionada_getnet == 'antecipacao':
                st.markdown("### ⚡ Registro de Antecipação")
                
                # NOVA VALIDAÇÃO: Verificar se há apenas uma linha selecionada em cada tabela
                num_rec_selecionados = len(rec_selecionados)
                num_trans_selecionadas = len(trans_selecionadas)
                
                if num_rec_selecionados != 1 or num_trans_selecionadas != 1:
                    st.error("⚠️ Selecione apenas um lançamento em cada tabela para registrar a antecipação")
                    return
                
                # Extrai dados das linhas selecionadas
                rec_linha = rec_selecionados.iloc[0]
                trans_linha = trans_selecionadas.iloc[0]
                
                # Determina a bandeira baseada na coluna 'Cartões'
                cartoes_texto = str(trans_linha.get('cartoes', '')).upper()
                if 'VISA' in cartoes_texto:
                    bandeira_auto = "Visa"
                elif 'MASTER' in cartoes_texto:
                    bandeira_auto = "MasterCard"
                elif 'ELO' in cartoes_texto:
                    bandeira_auto = "Elo"
                elif 'AMEX' in cartoes_texto:
                    bandeira_auto = "American Express"
                else:
                    bandeira_auto = "Visa"  # Default
                
                # Data da venda do recebimento
                data_venda_auto = pd.to_datetime(rec_linha['data_operacao']).date()
                
                # Número de parcelas do recebimento
                n_parcelas_auto = int(rec_linha.get('n_parcelas', 1))
                
                # Valor bruto do recebimento
                valor_bruto_auto = float(rec_linha['valor_pendente'])
                
                # Formulário de antecipação com valores preenchidos
                col1, col2 = st.columns(2)
                
                with col1:
                    data_venda = st.date_input(
                        "Data da Venda:",
                        value=data_venda_auto,
                        key="data_venda_antecipacao"
                    )
                    
                    bandeira = st.selectbox(
                        "Bandeira:",
                        options=["Visa", "MasterCard", "Elo", "American Express"],
                        index=["Visa", "MasterCard", "Elo", "American Express"].index(bandeira_auto),
                        key="bandeira_antecipacao"
                    )
                    
                    valor_bruto_input = st.number_input(
                        "Valor Bruto (R$):",
                        value=valor_bruto_auto,
                        format="%.2f",
                        key="valor_bruto_antecipacao"
                    )
                
                with col2:
                    parcelas = st.number_input(
                        "Número de Parcelas:",
                        min_value=1,
                        max_value=12,
                        value=n_parcelas_auto,
                        key="parcelas_antecipacao"
                    )
                    
                    taxa_antecipacao = st.number_input(
                        "Taxa de Antecipação (%/mês):",
                        value=2.80,
                        format="%.4f",
                        key="taxa_antecipacao"
                    )
                    
                    # Seleção de conta com Santander como padrão
                    contas = obter_contas_disponiveis()
                    conta_destino = st.selectbox(
                        "Conta de Destino:",
                        options=contas,
                        index=contas.index('SANTANDER') if 'SANTANDER' in contas else 0,
                        key="conta_antecipacao_getnet"
                    )
                
                if st.button("📊 Calcular Antecipação", use_container_width=True):
                    # Calcula taxa da operadora
                    taxa_operadora = calcular_taxa_bandeira(valor_bruto_input, bandeira, parcelas)
                    valor_liquido_pos_taxa = valor_bruto_input - taxa_operadora
                    valor_parcela = round(valor_liquido_pos_taxa / parcelas, 2)
                    
                    # Ajuste para centavos
                    valores_parcelas = [valor_parcela] * parcelas
                    diferenca = round(valor_liquido_pos_taxa - sum(valores_parcelas), 2)
                    
                    # Distribui a diferença de centavos
                    for i in range(int(abs(diferenca) * 100)):
                        if i < len(valores_parcelas):
                            valores_parcelas[i] += 0.01 if diferenca > 0 else -0.01
                    
                    # Calcula antecipação
                    resultado = calcular_antecipacao_banco(
                        valores_parcelas=valores_parcelas,
                        taxa_antecipacao_mes=taxa_antecipacao,
                        data_venda=data_venda
                    )
                    
                    # Armazena resultados no session_state
                    st.session_state.resultado_antecipacao = {
                        'valor_bruto': valor_bruto_input,
                        'taxa_operadora': taxa_operadora,
                        'taxa_antecipacao': resultado['total_desconto_antecipacao'],
                        'valor_liquido_final': resultado['valor_liquido_recebido'],
                        'detalhe_parcelas': resultado['detalhe_parcelas'],
                        'prazo_medio': resultado['prazo_medio']
                    }
                    
                    st.rerun()
                
                # Mostra resultados se calculados
                if 'resultado_antecipacao' in st.session_state:
                    resultado = st.session_state.resultado_antecipacao
                    
                    st.markdown("#### 📈 Resultados da Simulação")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Valor Bruto", f"R$ {resultado['valor_bruto']:,.2f}")
                    with col2:
                        st.metric("Taxa Operadora", f"R$ {resultado['taxa_operadora']:,.2f}")
                    with col3:
                        st.metric("Taxa Antecipação", f"R$ {resultado['taxa_antecipacao']:,.2f}")
                    with col4:
                        st.metric("Valor Líquido Final", f"R$ {resultado['valor_liquido_final']:,.2f}")
                    
                    st.markdown("#### 📋 Detalhamento das Parcelas")
                    df_parcelas = pd.DataFrame(resultado["detalhe_parcelas"])
                    st.dataframe(df_parcelas, use_container_width=True, hide_index=True)
                    
                    if st.button("✅ Confirmar Antecipação", type="primary", use_container_width=True):
                        # Define ids_rec baseado em parcela antiga
                        if parcela_antiga_selecionada:
                            ids_rec = []
                        else:
                            ids_rec = rec_selecionados['id_pendencia'].tolist()

                        indices_trans_arquivo = _extract_indices_trans(trans_selecionadas)

                        # Para baixa parcial
                        if baixa_parcial_selecionada:
                            valores_parciais = [resultado['valor_bruto']] * len(ids_rec)
                        else:
                            valores_parciais = []
                        
                        with st.spinner("Processando antecipação..."):
                            sucesso, msg = registrar_antecipacao_cartao(
                                ids_rec,
                                indices_trans_arquivo,
                                cartao,
                                conta_destino,
                                resultado['valor_bruto'],
                                resultado['taxa_operadora'],
                                resultado['taxa_antecipacao'],
                                resultado['valor_liquido_final'],
                                baixa_parcial=baixa_parcial_selecionada,
                                valores_parciais=valores_parciais,
                                parcela_antiga=parcela_antiga_selecionada
                            )
                            
                            if sucesso:
                                st.success(msg)
                                st.balloons()
                                st.session_state.operacao_selecionada_getnet = None
                                if 'resultado_antecipacao' in st.session_state:
                                    del st.session_state.resultado_antecipacao
                                st.rerun()
                            else:
                                st.error(msg)
        
        else:  # MULVI - mantém comportamento original
            st.markdown("### ✅ Confirmar Conciliação")
            
            # Calcula valores
            if baixa_parcial_selecionada:
                valor_bruto = trans_selecionadas['ValorBruto'].sum()
            else:
                if not rec_selecionados.empty:
                    valor_bruto = rec_selecionados['valor_pendente'].sum()
                else:
                    valor_bruto = trans_selecionadas['ValorBruto'].sum()
            
            valor_liquido = trans_selecionadas['ValorLiquido'].sum()
            taxa = valor_bruto - valor_liquido
            
            col_info1, col_info2, col_info3 = st.columns(3)
            
            with col_info1:
                st.metric("Valor Bruto", f"R$ {valor_bruto:,.2f}")
            with col_info2:
                st.metric("Valor Líquido", f"R$ {valor_liquido:,.2f}")
            with col_info3:
                st.metric("Taxa", f"R$ {taxa:,.2f}", delta_color="inverse")
            
            # Seleção de conta
            contas = obter_contas_disponiveis()
            conta_destino = st.selectbox(
                "Conta de Destino:",
                options=contas,
                index=contas.index('BANESE') if 'BANESE' in contas else 0,
                key="conta_mulvi"
            )
            
            if st.button(f"✅ Confirmar Conciliação {cartao}", type="primary", use_container_width=True):
                # Define ids_rec baseado em parcela antiga
                if parcela_antiga_selecionada:
                    ids_rec = []
                else:
                    ids_rec = rec_selecionados['id_pendencia'].tolist()

                indices_trans_arquivo = _extract_indices_trans(trans_selecionadas)

                # Para baixa parcial, use o valor_bruto da transação como valor_parcial
                if baixa_parcial_selecionada:
                    valores_parciais = [valor_bruto] * len(ids_rec)
                else:
                    valores_parciais = []
                
                with st.spinner("Processando conciliação..."):
                    sucesso, msg = registrar_conciliacao_cartao(
                        ids_rec, 
                        indices_trans_arquivo, 
                        cartao, 
                        conta_destino,
                        baixa_parcial=baixa_parcial_selecionada,
                        valores_parciais=valores_parciais,
                        parcela_antiga=parcela_antiga_selecionada
                    )
                    
                    if sucesso:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)

    # Ajusta mensagens de aviso
    elif not trans_selecionadas.empty and parcela_antiga_selecionada:
        st.info("ℹ️ Parcela antiga selecionada. Confirme para registrar apenas a entrada na conta.")
    elif not trans_selecionadas.empty and rec_selecionados.empty:
        st.warning("⚠️ Selecione pelo menos um recebimento pendente OU marque 'Parcela Antiga'")
    elif trans_selecionadas.empty:
        st.warning("⚠️ Selecione pelo menos uma transação")

def mostrar_aba_ipes():
    """Aba para conciliação de convênio IPES."""
    
    # Carrega dados consolidados do IPES
    df_recebimentos = obter_recebimentos_ipes()
    df_recebimentos = _sanitize_valores_cols(df_recebimentos, ['valor'])

    # Filtra apenas pendentes
    df_recebimentos = df_recebimentos[df_recebimentos['status_conciliacao'] == 'pendente']

    # Agrupa por data/paciente mantendo listas de id_pendencia para baixa
    if not df_recebimentos.empty:
        df_recebimentos_agrupado = (
            df_recebimentos
            .groupby(['data_cadastro', 'paciente'])
            .agg(
                valor=('valor', 'sum'),
                id_pendencia=('id_pendencia', lambda s: list(s))
            )
            .reset_index()
        )
    else:
        df_recebimentos_agrupado = pd.DataFrame(columns=['data_cadastro', 'paciente', 'valor', 'id_pendencia'])

    # ETAPA 1: Cria coluna indice_paciente para recebimentos IPES
    if not df_recebimentos_agrupado.empty:
        df_recebimentos_agrupado['data_cadastro'] = pd.to_datetime(df_recebimentos_agrupado['data_cadastro'])
        df_recebimentos_agrupado['indice_paciente'] = (
            df_recebimentos_agrupado['data_cadastro'].dt.strftime('%Y-%m-%d') + '_' + 
            df_recebimentos_agrupado['paciente'].astype(str)
        )
    
    df_pagamentos = obter_dados_ipes()

    # Etapa 2: Cria coluna indice_paciente para pagamentos IPES
    if not df_pagamentos.empty:
        df_pagamentos['data_cadastro'] = pd.to_datetime(df_pagamentos['data_cadastro'], errors='coerce')
        df_pagamentos['indice_paciente'] = (
            df_pagamentos['data_cadastro'].dt.strftime('%Y-%m-%d') + '_' + 
            df_pagamentos['paciente'].astype(str)
        )
    
    if df_recebimentos_agrupado.empty:
        st.info("Não há recebimentos pendentes do convênio IPES")
        return
    
    if df_pagamentos.empty:
        st.warning("Não há pagamentos IPES importados. Importe o relatório IPES primeiro.")
        return

    modo_selecionado = st.pills("Selecione o modo de visualização:", ["Individual", "Agrupado"], key="modo_ipes")

    if modo_selecionado == "Individual":
        mostrar_conciliacao_individual_ipes(df_recebimentos_agrupado, df_pagamentos)
    else:
        mostrar_conciliacao_automatizada_ipes()

def mostrar_conciliacao_individual_ipes(df_recebimentos, df_pagamentos):

    # --- SEÇÃO DE FILTROS ---
    st.markdown("#### 🔎 Filtros")
    
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])

    with col_f1:
        filtro_paciente = st.text_input("Filtrar por nome do paciente:", key="filtro_paciente_ipes")
    
    # Define datas padrão para os filtros de data
    data_min_rec = df_recebimentos['data_cadastro'].min().date() if not df_recebimentos.empty else date.today()
    data_max_rec = df_recebimentos['data_cadastro'].max().date() if not df_recebimentos.empty else date.today()

    with col_f2:
        filtro_data_inicio = st.date_input("Data Início:", value=data_min_rec, key="data_inicio_ipes")
    with col_f3:
        filtro_data_fim = st.date_input("Data Fim:", value=data_max_rec, key="data_fim_ipes")

    # Aplica filtros
    if filtro_paciente:
        df_recebimentos = df_recebimentos[df_recebimentos['paciente'].str.contains(filtro_paciente, case=False, na=False)]
        df_pagamentos = df_pagamentos[df_pagamentos['paciente'].str.contains(filtro_paciente, case=False, na=False)]

    # Filtro de data para recebimentos
    if not df_recebimentos.empty:
        df_recebimentos['data_cadastro'] = pd.to_datetime(df_recebimentos['data_cadastro'])
        mask_rec = (df_recebimentos['data_cadastro'].dt.date >= filtro_data_inicio) & (df_recebimentos['data_cadastro'].dt.date <= filtro_data_fim)
        df_recebimentos = df_recebimentos[mask_rec]

    # Filtro de data para pagamentos
    if not df_pagamentos.empty:
        df_pagamentos['data_cadastro'] = pd.to_datetime(df_pagamentos['data_cadastro'])
        mask_pag = (df_pagamentos['data_cadastro'].dt.date >= filtro_data_inicio) & (df_pagamentos['data_cadastro'].dt.date <= filtro_data_fim)
        df_pagamentos = df_pagamentos[mask_pag]

    if df_recebimentos.empty:
        st.warning("Nenhum recebimento pendente encontrado com os filtros aplicados.")
    
    if df_pagamentos.empty:
        st.warning("Nenhum pagamento IPES encontrado com os filtros aplicados.")


    # Prepara dados
    df_recebimentos = df_recebimentos.reset_index(drop=True)
    df_recebimentos['selecionar'] = False
    
    df_pagamentos = df_pagamentos.reset_index(drop=True)
    df_pagamentos['selecionar'] = False
    
    # Duas colunas para as tabelas
    col_esq, col_dir = st.columns(2)
    
    with col_esq:
        st.markdown("#### 📋 Recebimentos Pendentes")
        
        df_rec_display = df_recebimentos.copy()
        df_rec_display['data_cadastro'] = pd.to_datetime(df_rec_display['data_cadastro']).dt.strftime('%d/%m/%Y')
                
        st.markdown(f"<span style='color:blue; font-size:small;'>{len(df_recebimentos)} registros pendentes</span>", unsafe_allow_html=True)
        
        colunas_exibir_rec = ['selecionar', 'data_cadastro', 'paciente', 'valor']
        
        column_config_rec = {
            'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
            'data_cadastro': 'Data',
            'paciente': 'Paciente',
            'valor': 'Valor Total',
        }
        
        df_rec_editado = st.data_editor(
            df_rec_display[colunas_exibir_rec],
            column_config=column_config_rec,
            disabled=['data_cadastro', 'paciente', 'valor'],
            hide_index=True,
            height=400,
            key="editor_rec_IPES"
        )
    
    with col_dir:
        st.markdown("#### 💵 Pagamentos IPES Agrupados")

        # DataFrame para armazenar a seleção do editor agrupado
        pag_selecionados_agrupados = pd.DataFrame()

        if not df_pagamentos.empty:
            # Agrupa os pagamentos por data e paciente, coletando os índices originais
            df_agrupado = df_pagamentos.groupby(['paciente', 'data_cadastro']).agg(
                valor_total=('valor_exec', 'sum'),
                indices_originais=('indice_arquivo', list)
            ).reset_index()

            # Prepara o DataFrame para exibição no data_editor
            df_agrupado['selecionar'] = False
            df_agrupado['data_fmt'] = pd.to_datetime(df_agrupado['data_cadastro']).dt.strftime('%d/%m/%Y')
                        
            colunas_exibir_agrupado = ['selecionar', 'data_fmt', 'paciente', 'valor_total']

            st.markdown(f"<span style='color:blue; font-size:small;'>{len(df_agrupado)} registros agrupados</span>", unsafe_allow_html=True)

            df_pag_editado_agrupado = st.data_editor(
                df_agrupado[colunas_exibir_agrupado],
                column_config={
                    'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
                    'data_fmt': 'Data',
                    'paciente': 'Paciente',
                    'valor_total': st.column_config.NumberColumn('Valor Total', format="%.2f")
                },
                disabled=['data_fmt', 'paciente', 'valor_total'],
                hide_index=True,
                height=400,
                key="editor_pag_ipes_agrupado"
            )
            
            # Captura as linhas agrupadas que foram selecionadas
            pag_selecionados_agrupados = df_agrupado[df_pag_editado_agrupado['selecionar']]
        else:
            st.info("Nenhum pagamento IPES pendente.")

    # Área de confirmação
    rec_selecionados = df_recebimentos[df_rec_editado['selecionar']]
    
    # A condição agora usa a seleção do DataFrame agrupado
    if not rec_selecionados.empty and not pag_selecionados_agrupados.empty:
        # ETAPA 4: Botão para detalhar convênios
        st.markdown("---")
        col_detalhar, col_spacer = st.columns([1, 3])
        with col_detalhar:
            if st.button("🔍 Detalhar Convênios", use_container_width=True, key="btn_detalhar_convenios"):
                st.session_state.mostrar_detalhamento = True
                st.rerun()
        
        # ETAPA 4: Mostra detalhamento se solicitado
        if st.session_state.get('mostrar_detalhamento', False):
            mostrar_detalhamento_convenios(rec_selecionados, pag_selecionados_agrupados)

        st.markdown("---")
        st.markdown("### ✅ Confirmar Conciliação IPES")
                
        valor_pendente = rec_selecionados['valor'].sum()
        valor_pago = pag_selecionados_agrupados['valor_total'].sum()
        
        col_info1, col_info2 = st.columns(2)
        
        with col_info1:
            st.metric("Total Pendente", f"R$ {valor_pendente:,.2f}")
        with col_info2:
            st.metric("Total a Receber", f"R$ {valor_pago:,.2f}")
        
        # Seleção de conta
        contas = obter_contas_disponiveis()
        conta_destino = st.selectbox(
            "Conta de Destino:",
            options=contas,
            key="conta_ipes"
        )
        
        if st.button("✅ Confirmar Conciliação IPES", type="primary", use_container_width=True):
            # rec_selecionados['id_pendencia'] pode conter listas de ids — achata para lista única
            nested = rec_selecionados['id_pendencia'].tolist()
            ids_rec = []
            for e in nested:
                if isinstance(e, (list, tuple, pd.Series)):
                    ids_rec.extend(list(e))
                elif pd.isna(e):
                    continue
                else:
                    ids_rec.append(e)
            indices_pag_arquivo = [idx for sublist in pag_selecionados_agrupados['indices_originais'] for idx in sublist]
            valor_pendente = rec_selecionados['valor'].sum()
            valor_pago = pag_selecionados_agrupados['valor_total'].sum()
            with st.spinner("Processando conciliação IPES..."):
                sucesso, msg = registrar_conciliacao_ipes(
                    ids_rec,
                    indices_pag_arquivo,
                    conta_destino,
                    valor_pago=valor_pago  # Passe o valor pago para a função
                )
                if sucesso:
                    # Salva diferença se houver
                    if abs(valor_pago - valor_pendente) > 0.01:
                        salvar_diferenca_baixa_ipes(date.today(), valor_pendente, valor_pago)
                    st.success(msg)
                    st.balloons()
                    # Limpa o detalhamento ao confirmar
                    if 'mostrar_detalhamento' in st.session_state:
                        del st.session_state.mostrar_detalhamento
                    st.rerun()
                else:
                    st.error(msg)
    
    elif not rec_selecionados.empty and pag_selecionados_agrupados.empty:
        st.warning("⚠️ Selecione pelo menos um pagamento IPES")
    elif rec_selecionados.empty and not pag_selecionados_agrupados.empty:
        st.warning("⚠️ Selecione pelo menos um recebimento pendente IPES")
    else:
        st.warning("⚠️ Selecione pelo menos um pagamento IPES")

def mostrar_conciliacao_automatizada_ipes():
    """
    Conciliação automatizada de IPES - compara tabelas lado a lado.
    Usa dados consolidados que incluem clínica + laboratório vs relatórios IPES.
    """
    
    st.markdown("### 🤖 Conciliação Automatizada de Convênios IPES")
    st.caption("Compara automaticamente todos os exames entre o sistema (clínica + laboratório) e relatórios IPES")
        
    # Carrega dados detalhados
    try:
        # Usa dados consolidados ao invés de convenio_detalhado.pkl
        df_sistema = obter_recebimentos_ipes()  # Dados consolidados pendentes
        
        if not os.path.exists('data/convenio_ipes.pkl'):
            st.warning("Arquivo convenio_ipes.pkl não encontrado. Importe relatório IPES primeiro.")
            return
        import pandas as pd
        df_ipes = pd.read_pickle('data/convenio_ipes.pkl')
        
    except Exception as e:
        st.error(f"Erro ao carregar arquivos: {e}")
        return
    
    if df_sistema.empty:
        st.warning("Nenhum dado consolidado do sistema encontrado. Execute a consolidação primeiro.")
        return
    
    if df_ipes.empty:
        st.warning("Nenhum dado do IPES encontrado.")
        return
    
    # Adiciona filtro de status_conciliacao para o IPES
    if 'status_conciliacao' in df_ipes.columns:
        df_ipes = df_ipes[df_ipes['status_conciliacao'] == 'pendente']
    
    # Inicializa estado de linhas removidas (após registrar inconsistência)
    if 'removidos_automatizada' not in st.session_state:
        st.session_state.removidos_automatizada = {'sistema': set(), 'ipes': set()}
    removidos = st.session_state.removidos_automatizada
    
    # Prepara DataFrames para exibição
    if not df_sistema.empty:
        df_sis = df_sistema[['data_cadastro', 'paciente', 'codigo_exame', 'descricao', 'valor']].copy()
        df_sis.columns = ['data_cadastro', 'paciente', 'codigo_exame', 'descricao', 'valor_sistema']
        # Cria indice_paciente para comparação
        df_sis['data_cadastro'] = pd.to_datetime(df_sis['data_cadastro'])
        df_sis['indice_paciente'] = (
            df_sis['data_cadastro'].dt.strftime('%Y-%m-%d') + '_' + 
            df_sis['paciente'].astype(str)
        )
        # uid para manter marcação no session_state (não exibido)
        df_sis['uid'] = df_sis.apply(lambda r: f"s_{r['indice_paciente']}_{int(r['codigo_exame'])}_{float(r['valor_sistema']):.2f}", axis=1)
        df_sis['selecionar'] = False
    else:
        df_sis = pd.DataFrame(columns=['data_cadastro', 'paciente', 'codigo_exame', 'descricao', 'valor_sistema', 'indice_paciente', 'uid', 'selecionar'])
    
    if not df_ipes.empty:
        # Mapeia colunas do IPES
        colunas_ipes = ['data_cadastro', 'paciente', 'procedimento_codigo', 'valor_exec','descricao']
        if 'beneficiario_nome' in df_ipes.columns and 'paciente' not in df_ipes.columns:
            colunas_ipes[1] = 'beneficiario_nome'
        
        df_ips = df_ipes[colunas_ipes].copy()
        df_ips.columns = ['data_cadastro', 'paciente', 'codigo_exame', 'valor_ipes', 'descricao']
                
        # Cria indice_paciente para comparação
        df_ips['data_cadastro'] = pd.to_datetime(df_ips['data_cadastro'])
        df_ips['indice_paciente'] = (
            df_ips['data_cadastro'].dt.strftime('%Y-%m-%d') + '_' + 
            df_ips['paciente'].astype(str)
        )
        df_ips['uid'] = df_ips.apply(lambda r: f"i_{r['indice_paciente']}_{int(r['codigo_exame'])}_{float(r['valor_ipes']):.2f}", axis=1)
        df_ips['selecionar'] = False
    else:
        df_ips = pd.DataFrame(columns=['data_cadastro', 'paciente', 'codigo_exame', 'valor_ipes', 'descricao', 'indice_paciente', 'uid', 'selecionar'])
    
    # Calcula coluna OK baseada na existência de correspondência por indice_paciente + código + valor (~0.01)
    def calcular_ok_para_sistema(row):
        matches = df_ips[
            (df_ips['indice_paciente'] == row['indice_paciente']) &
            (df_ips['codigo_exame'].astype(str) == str(int(row['codigo_exame'])))
        ]
        if not matches.empty:
            return any(abs(float(row['valor_sistema']) - float(v)) < 0.01 for v in matches['valor_ipes'])
        return False

    def calcular_ok_para_ipes(row):
        matches = df_sis[
            (df_sis['indice_paciente'] == row['indice_paciente']) &
            (df_sis['codigo_exame'].astype(str) == str(int(row['codigo_exame'])))
        ]
        if not matches.empty:
            return any(abs(float(row['valor_ipes']) - float(v)) < 0.01 for v in matches['valor_sistema'])
        return False

    df_sis['ok'] = df_sis.apply(calcular_ok_para_sistema, axis=1)
    df_ips['ok'] = df_ips.apply(calcular_ok_para_ipes, axis=1)
    
    # Inicializa session_state para marcações persistentes
    if 'ok_automatizada' not in st.session_state:
        st.session_state.ok_automatizada = {'sistema': set(), 'ipes': set()}
    
    # Reaplica marcações manuais previamente feitas
    df_sis['ok_manual'] = df_sis['uid'].apply(lambda u: u in st.session_state.ok_automatizada['sistema'])
    df_ips['ok_manual'] = df_ips['uid'].apply(lambda u: u in st.session_state.ok_automatizada['ipes'])
    
    # Valor final para exibir: ok_display = ok OR ok_manual
    df_sis['ok_display'] = df_sis['ok'] | df_sis['ok_manual']
    df_ips['ok_display'] = df_ips['ok'] | df_ips['ok_manual']

    # --- CONTROLES ---
    st.markdown("#### 🛠️ Controles")
    
    col_ctrl1, col_ctrl2, col_ctrl3, col_ctrl4 = st.columns(4)
    
    with col_ctrl1:
        if st.button("✅ Selecionar Todos", use_container_width=True, key="selecionar_todos_automatizada"):
            df_sis['selecionar'] = True
            df_ips['selecionar'] = True
    
    with col_ctrl2:
        if st.button("❌ Desmarcar Todos", use_container_width=True, key="desmarcar_todos_automatizada"):
            df_sis['selecionar'] = False
            df_ips['selecionar'] = False
    
    with col_ctrl3:
        # Checkbox para ocultar valores coincidentes
        ocultar_coincidentes = st.checkbox(
            "🔍 Ocultar valores coincidentes",
            value=False,
            key="ocultar_coincidentes_automatizada"
        )
    
    with col_ctrl4:
        # Filtro por paciente
        pacientes_unicos = sorted(set(df_sis['paciente'].tolist() + df_ips['paciente'].tolist()))
        filtro_paciente = st.selectbox(
            "Filtrar por paciente:",
            options=['Todos'] + pacientes_unicos,
            key="filtro_paciente_automatizada"
        )
    
    # Aplica filtros
    if filtro_paciente != 'Todos':
        df_sis = df_sis[df_sis['paciente'] == filtro_paciente]
        df_ips = df_ips[df_ips['paciente'] == filtro_paciente]
    
    # Filtra visualmente conforme checkbox
    display_sis = df_sis[~df_sis['ok_display']] if ocultar_coincidentes else df_sis.copy()
    display_ips = df_ips[~df_ips['ok_display']] if ocultar_coincidentes else df_ips.copy()
    
    # Exclui uids já removidos por registros anteriores
    display_sis = display_sis[~display_sis['uid'].isin(removidos['sistema'])]
    display_ips = display_ips[~display_ips['uid'].isin(removidos['ipes'])]
    
    # --- TABELAS LADO A LADO ---
    col_esq, col_dir = st.columns(2)
    
    with col_esq:
        st.markdown("#### 🏥 Sistema (clínica + laboratório)")
        st.markdown(f"<span style='color:blue; font-size:small;'>{len(display_sis)} registros</span>", unsafe_allow_html=True)
        
        # Prepara DataFrame para exibição (sem uid)
        df_sis_for_display = display_sis[['selecionar', 'data_cadastro', 'paciente', 'codigo_exame', 'descricao', 'valor_sistema', 'ok_display']].copy()
        df_sis_for_display['data_cadastro'] = df_sis_for_display['data_cadastro'].dt.strftime('%d/%m/%Y')
        
        df_sis_edit = st.data_editor(
            df_sis_for_display,
            column_config={
                'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
                'data_cadastro': st.column_config.TextColumn('Data', width='small'),
                'paciente': st.column_config.TextColumn('Paciente', width='medium'),
                'codigo_exame': st.column_config.NumberColumn('Código', format="%d", width='small'),
                'descricao': st.column_config.TextColumn('Descrição', width='medium'),
                'valor_sistema': st.column_config.NumberColumn('Valor', format="%.2f", width='small'),
                'ok_display': st.column_config.CheckboxColumn('OK', width='small')
            },
            disabled=['data_cadastro', 'paciente', 'codigo_exame', 'descricao', 'valor_sistema', 'ok_display'],
            hide_index=True,
            height=500,
            use_container_width=False,
            key="editor_sis_automatizada"
        )
    
    with col_dir:
        st.markdown("#### 🧾 IPES (relatório)")
        st.markdown(f"<span style='color:blue; font-size:small;'>{len(display_ips)} registros</span>", unsafe_allow_html=True)
        
        # Prepara DataFrame para exibição (sem uid)
        df_ips_for_display = display_ips[['selecionar', 'data_cadastro', 'paciente', 'codigo_exame', 'descricao', 'valor_ipes', 'ok_display']].copy()
        df_ips_for_display['data_cadastro'] = df_ips_for_display['data_cadastro'].dt.strftime('%d/%m/%Y')
        
        df_ips_edit = st.data_editor(
            df_ips_for_display,
            column_config={
                'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
                'data_cadastro': st.column_config.TextColumn('Data', width='small'),
                'paciente': st.column_config.TextColumn('Paciente', width='medium'),
                'codigo_exame': st.column_config.NumberColumn('Código', format="%d", width='small'),
                'descricao': st.column_config.TextColumn('Descrição', width='medium'),
                'valor_ipes': st.column_config.NumberColumn('Valor', format="%.2f", width='small'),
                'ok_display': st.column_config.CheckboxColumn('OK', width='small')
            },
            disabled=['data_cadastro', 'paciente', 'codigo_exame', 'descricao', 'valor_ipes', 'ok_display'],
            hide_index=True,
            height=500,
            use_container_width=False,
            key="editor_ips_automatizada"
        )
    
    # Mapeia seleções por posição para obter os uids/linhas originais
    selected_pos_sis = [i for i, v in enumerate(df_sis_edit['selecionar'].tolist()) if v] if df_sis_edit is not None else []
    selected_pos_ips = [i for i, v in enumerate(df_ips_edit['selecionar'].tolist()) if v] if df_ips_edit is not None else []
    
    sel_sis = display_sis.iloc[selected_pos_sis].copy() if len(selected_pos_sis) else pd.DataFrame(columns=display_sis.columns)
    sel_ips = display_ips.iloc[selected_pos_ips].copy() if len(selected_pos_ips) else pd.DataFrame(columns=display_ips.columns)
    
    # --- MÉTRICAS ---
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_sistema = len(df_sis)
        st.metric("Total Sistema", total_sistema)
    
    with col2:
        total_ipes = len(df_ips)
        st.metric("Total IPES", total_ipes)
    
    with col3:
        coincidentes_sis = len(df_sis[df_sis['ok_display']])
        coincidentes_ips = len(df_ips[df_ips['ok_display']])
        st.metric("Coincidências", f"S:{coincidentes_sis} / I:{coincidentes_ips}")
    
    with col4:
        selecionados_count = len(sel_sis) + len(sel_ips)
        st.metric("Selecionados", selecionados_count)
    
    # --- AÇÕES ---
    if not sel_sis.empty or not sel_ips.empty:
        st.markdown("---")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            if st.button("⚠️ Registrar Inconsistências", type="primary", use_container_width=True):
                if not sel_sis.empty and not sel_ips.empty:
                    sucesso, msg = salvar_inconsistencias_automatizada_v2(
                        {'sistema': sel_sis, 'ipes': sel_ips}
                    )
                    
                    if sucesso:
                        # Marca uids como removidos da view
                        for uid in sel_sis['uid'].tolist():
                            st.session_state.removidos_automatizada['sistema'].add(uid)
                        for uid in sel_ips['uid'].tolist():
                            st.session_state.removidos_automatizada['ipes'].add(uid)
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Selecione linhas em ambas as tabelas para registrar inconsistências")
        
        with col_btn2:
            if st.button("✅ Marcar como OK", type="secondary", use_container_width=True):
                # Adiciona uids selecionados ao session_state
                for uid in sel_sis['uid'].tolist():
                    st.session_state.ok_automatizada['sistema'].add(uid)
                for uid in sel_ips['uid'].tolist():
                    st.session_state.ok_automatizada['ipes'].add(uid)
                st.success("Linhas marcadas como OK")
                st.rerun()
        
        with col_btn3:
            if st.button("📊 Exportar Excel", type="secondary", use_container_width=True):
                # Exporta dados selecionados para Excel
                try:
                    from io import BytesIO
                    import pandas as pd
                    
                    buffer = BytesIO()
                    
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        # Prepara dados para Excel
                        if not sel_sis.empty:
                            excel_sis = sel_sis[['data_cadastro', 'paciente', 'codigo_exame', 'descricao', 'valor_sistema']].copy()
                            excel_sis['data_cadastro'] = excel_sis['data_cadastro'].dt.strftime('%d/%m/%Y')
                            # Renomeia colunas para clareza
                            excel_sis.columns = ['Data', 'Paciente', 'Código Exame', 'Descrição', 'Valor Sistema']
                            excel_sis.to_excel(writer, sheet_name='Sistema', index=False)
                        
                        if not sel_ips.empty:
                            # CORREÇÃO: Agora inclui a coluna 'descricao' também para IPES
                            excel_ips = sel_ips[['data_cadastro', 'paciente', 'codigo_exame', 'descricao', 'valor_ipes']].copy()
                            excel_ips['data_cadastro'] = excel_ips['data_cadastro'].dt.strftime('%d/%m/%Y')
                            # Renomeia colunas para clareza
                            excel_ips.columns = ['Data', 'Paciente', 'Código Exame', 'Descrição', 'Valor IPES']
                            excel_ips.to_excel(writer, sheet_name='IPES', index=False)
                    
                    # Gera nome do arquivo com timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nome_arquivo = f"conciliacao_automatizada_ipes_{timestamp}.xlsx"
                    
                    st.download_button(
                        label="⬇️ Baixar Excel",
                        data=buffer.getvalue(),
                        file_name=nome_arquivo,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"Erro ao gerar Excel: {e}")
    else:
        st.info("Selecione linhas em uma ou ambas as tabelas para habilitar ações")
def mostrar_detalhamento_convenios(rec_selecionados, pag_selecionados_agrupados):
    """
    ETAPA 4: Mostra detalhamento dos convênios selecionados.
    Agora exibe DUAS tabelas separadas (Sistema / IPES) com coluna 'OK' e seleção.
    Registra inconsistências removendo as linhas selecionadas das visualizações.
    """
    
    st.markdown("---")
    st.markdown("### 🔍 Detalhamento dos Convênios")
    st.caption("Dados consolidados: clínica + laboratório vs IPES (visualização lado a lado)")
    
    # Fecha o detalhamento
    if st.button("❌ Fechar Detalhamento", key="fechar_detalhamento"):
        if 'mostrar_detalhamento' in st.session_state:
            del st.session_state.mostrar_detalhamento
        st.rerun()
        return

    # inicializa estado de linhas removidas (após registrar inconsistência)
    if 'removidos_detalhado' not in st.session_state:
        st.session_state.removidos_detalhado = {'sistema': set(), 'ipes': set()}
    removidos = st.session_state.removidos_detalhado

    # Coleta os índices de paciente selecionados
    indices_paciente_rec = rec_selecionados['indice_paciente'].tolist()
    indices_paciente_pag = []
    
    # Para pagamentos, precisa reconstruir indice_paciente do agrupado
    for _, linha in pag_selecionados_agrupados.iterrows():
        data_str = pd.to_datetime(linha['data_cadastro']).strftime('%Y-%m-%d')
        paciente = linha['paciente']
        indice = f"{data_str}_{paciente}"
        indices_paciente_pag.append(indice)
    
    # Carrega dados detalhados do sistema (dados consolidados)
    try:
        from components.importacao import obter_dados_ipes_consolidado
        df_sistema = obter_dados_ipes_consolidado()
        
        if not df_sistema.empty and 'indice_paciente' in df_sistema.columns:
            df_sistema_filtrado = df_sistema[df_sistema['indice_paciente'].isin(indices_paciente_rec)].copy()
        else:
            df_sistema_filtrado = pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar dados consolidados do sistema: {e}")
        df_sistema_filtrado = pd.DataFrame()
    
    # Carrega dados detalhados do IPES (convenio_ipes.pkl)
    try:
        if os.path.exists('data/convenio_ipes.pkl'):
            df_ipes = pd.read_pickle('data/convenio_ipes.pkl')
            if 'indice_paciente' in df_ipes.columns:
                df_ipes_filtrado = df_ipes[df_ipes['indice_paciente'].isin(indices_paciente_pag)].copy()
            else:
                df_ipes_filtrado = pd.DataFrame()
        else:
            df_ipes_filtrado = pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar dados do IPES: {e}")
        df_ipes_filtrado = pd.DataFrame()
    
    # Verifica dados
    if df_sistema_filtrado.empty and df_ipes_filtrado.empty:
        st.warning("Nenhum dado detalhado encontrado para os pacientes selecionados")
        return
    
    # Prepara DataFrames para exibição: colunas básicas (checkbox, codigo, descricao, valor)
    if not df_sistema_filtrado.empty:
        df_sis = df_sistema_filtrado[['codigo_exame', 'descricao', 'valor']].copy()
        df_sis.columns = ['codigo_exame', 'descricao', 'valor_sistema']
        # uid para manter marcação no session_state (não exibido)
        df_sis['uid'] = df_sis.apply(lambda r: f"s_{int(r['codigo_exame'])}_{float(r['valor_sistema']):.2f}_{str(r['descricao'])[:60]}", axis=1)
        df_sis['selecionar'] = False
    else:
        df_sis = pd.DataFrame(columns=['codigo_exame', 'descricao', 'valor_sistema', 'uid', 'selecionar'])
    
    if not df_ipes_filtrado.empty:
        df_ips = df_ipes_filtrado[['procedimento_codigo', 'valor_exec', 'descricao']].copy() if 'descricao' in df_ipes_filtrado.columns else df_ipes_filtrado[['procedimento_codigo', 'valor_exec']].copy()
        df_ips.rename(columns={'procedimento_codigo': 'codigo_exame', 'valor_exec': 'valor_ipes', 'descricao': 'descricao'}, inplace=True)
        df_ips['descricao'] = df_ips.get('descricao', '').fillna('')
        df_ips['uid'] = df_ips.apply(lambda r: f"i_{int(r['codigo_exame'])}_{float(r['valor_ipes']):.2f}_{str(r.get('descricao',''))[:60]}", axis=1)
        df_ips['selecionar'] = False
    else:
        df_ips = pd.DataFrame(columns=['codigo_exame', 'descricao', 'valor_ipes', 'uid', 'selecionar'])
    
    # Calcula coluna OK baseada na existência de correspondência por código e valor (~ igualdade 0.01)
    def calcular_ok_para_sistema(row):
        matches = df_ips[df_ips['codigo_exame'].astype(str) == str(int(row['codigo_exame']))]
        if not matches.empty:
            return any(abs(float(row['valor_sistema']) - float(v)) < 0.01 for v in matches['valor_ipes'])
        return False

    def calcular_ok_para_ipes(row):
        matches = df_sis[df_sis['codigo_exame'].astype(str) == str(int(row['codigo_exame']))]
        if not matches.empty:
            return any(abs(float(row['valor_ipes']) - float(v)) < 0.01 for v in matches['valor_sistema'])
        return False

    df_sis['ok'] = df_sis.apply(calcular_ok_para_sistema, axis=1)
    df_ips['ok'] = df_ips.apply(calcular_ok_para_ipes, axis=1)
    
    # Inicializa session_state para marcações persistentes
    if 'ok_detalhado' not in st.session_state:
        st.session_state.ok_detalhado = {'sistema': set(), 'ipes': set()}
    
    # Reaplica marcações manuais previamente feitas
    df_sis['ok_manual'] = df_sis['uid'].apply(lambda u: u in st.session_state.ok_detalhado['sistema'])
    df_ips['ok_manual'] = df_ips['uid'].apply(lambda u: u in st.session_state.ok_detalhado['ipes'])
    
    # Valor final para exibir: ok_display = ok OR ok_manual
    df_sis['ok_display'] = df_sis['ok'] | df_sis['ok_manual']
    df_ips['ok_display'] = df_ips['ok'] | df_ips['ok_manual']
    
    # Opção para ocultar coincidências
    ocultar_coincidentes = st.checkbox("🔍 Ocultar valores coincidentes (remover linhas OK)", value=False, key="ocultar_coinc_detalhado")
    
    # Filtra visualmente conforme checkbox
    display_sis = df_sis[~df_sis['ok_display']] if ocultar_coincidentes else df_sis.copy()
    display_ips = df_ips[~df_ips['ok_display']] if ocultar_coincidentes else df_ips.copy()
    
    # Exclui uids já removidos por registros anteriores
    display_sis = display_sis[~display_sis['uid'].isin(removidos['sistema'])]
    display_ips = display_ips[~display_ips['uid'].isin(removidos['ipes'])]
    
    # Guardar listas de uid na mesma ordem para mapear seleção por posição (uid NÃO será exibido)
    uid_list_sis = display_sis['uid'].tolist()
    uid_list_ips = display_ips['uid'].tolist()
    
    # Colunas para exibição (sem uid)
    col_esq, col_dir = st.columns(2)
    with col_esq:
        st.markdown("#### 🏥 Sistema (clínica + laboratório)")
        st.markdown(f"<span style='color:blue; font-size:small;'>{len(display_sis)} registros</span>", unsafe_allow_html=True)
        # monta DataFrame exibido sem uid
        df_sis_for_display = display_sis[['selecionar', 'codigo_exame', 'descricao', 'valor_sistema', 'ok_display']].copy()
        df_sis_edit = st.data_editor(
            df_sis_for_display,
            column_config={
                'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
                'codigo_exame': st.column_config.NumberColumn('Código', format="%d", width='small'),
                'descricao': st.column_config.TextColumn('Descrição', width='large'),
                'valor_sistema': st.column_config.NumberColumn('Valor', format="%.2f", width='small'),
                'ok_display': st.column_config.TextColumn('OK', width='small')
            },
            disabled=['codigo_exame', 'descricao', 'valor_sistema', 'ok_display'],
            hide_index=True,
            use_container_width=True,
            key="editor_sis_detalhado"
        )
    
    with col_dir:
        st.markdown("#### 🧾 IPES (relatório)")
        st.markdown(f"<span style='color:blue; font-size:small;'>{len(display_ips)} registros</span>", unsafe_allow_html=True)
        df_ips_for_display = display_ips[['selecionar', 'codigo_exame', 'descricao', 'valor_ipes', 'ok_display']].copy()
        df_ips_edit = st.data_editor(
            df_ips_for_display,
            column_config={
                'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
                'codigo_exame': st.column_config.NumberColumn('Código', format="%d", width='small'),
                'descricao': st.column_config.TextColumn('Descrição', width='large'),
                'valor_ipes': st.column_config.NumberColumn('Valor', format="%.2f", width='small'),
                'ok_display': st.column_config.TextColumn('OK', width='small')
            },
            disabled=['codigo_exame', 'descricao', 'valor_ipes', 'ok_display'],
            hide_index=True,
            use_container_width=True,
            key="editor_ips_detalhado"
        )
    
    # A partir dos data_edit retornados, mapeia seleções por posição para obter os uids/linhas originais
    selected_pos_sis = [i for i, v in enumerate(df_sis_edit['selecionar'].tolist()) if v] if df_sis_edit is not None else []
    selected_pos_ips = [i for i, v in enumerate(df_ips_edit['selecionar'].tolist()) if v] if df_ips_edit is not None else []
    
    sel_sis = display_sis.iloc[selected_pos_sis].copy() if len(selected_pos_sis) else pd.DataFrame(columns=display_sis.columns)
    sel_ips = display_ips.iloc[selected_pos_ips].copy() if len(selected_pos_ips) else pd.DataFrame(columns=display_ips.columns)
    
    # Ações habilitadas somente se há seleção em ambas as tabelas
    if not sel_sis.empty and not sel_ips.empty:
        st.markdown("---")
        col_btn1, col_btn2 = st.columns([1,1])
        with col_btn1:
            if st.button("⚠️ Registrar Inconsistências", type="primary", use_container_width=True):
                # chama função que salva comparativamente codigo_sistema x codigo_ipes
                sucesso, msg = salvar_inconsistencias_ipes_exportar({'sistema': sel_sis, 'ipes': sel_ips}, rec_selecionados)
                if sucesso:
                    # marca uids como removidos da view e rerun para atualizar contagem (diminui 1:1)
                    for uid in sel_sis['uid'].tolist():
                        st.session_state.removidos_detalhado['sistema'].add(uid)
                    for uid in sel_ips['uid'].tolist():
                        st.session_state.removidos_detalhado['ipes'].add(uid)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        with col_btn2:
            if st.button("✅ Marcar como ok", type="secondary", use_container_width=True):
                # Adiciona uids selecionados ao session_state para ambas as tabelas (marca OK)
                for uid in sel_sis['uid'].tolist():
                    st.session_state.ok_detalhado['sistema'].add(uid)
                for uid in sel_ips['uid'].tolist():
                    st.session_state.ok_detalhado['ipes'].add(uid)
                st.success("Linhas marcadas como OK")
                st.rerun()
    else:
        st.info("Selecione ao menos uma linha em cada tabela para habilitar ações")

def salvar_inconsistencias_ipes_exportar(selecionados, rec_selecionados):
    """
    Registra inconsistências selecionadas no arquivo inconsistencias_ipes.pkl.
    Agora grava registros comparativos entre sistema e IPES.
    Versão atualizada compatível com o novo formato de dados consolidados.
    Param selecionados: dict com chaves 'sistema' e 'ipes' contendo DataFrames selecionados.
    Estrutura gravada: data, paciente, codigo_sistema, descricao_sistema, valor_sistema,
                       codigo_ipes, descricao_ipes, valor_ipes, data_exportacao, origem
    """
    try:
        df_sis = selecionados.get('sistema', pd.DataFrame())
        df_ips = selecionados.get('ipes', pd.DataFrame())
        
        if df_sis.empty and df_ips.empty:
            return False, "Nenhuma seleção para salvar."
        
        dados_para_salvar = []
        
        # Se ambos têm linhas, grava combinações cruzadas (cada par sistema x ipes)
        if (not df_sis.empty) and (not df_ips.empty):
            for _, s in df_sis.iterrows():
                for _, i in df_ips.iterrows():
                    # Extrai data do campo data_cadastro de cada linha
                    data_s = pd.to_datetime(s.get('data_cadastro')).date() if pd.notna(s.get('data_cadastro')) else datetime.now().date()
                    data_i = pd.to_datetime(i.get('data_cadastro')).date() if pd.notna(i.get('data_cadastro')) else datetime.now().date()
                    
                    # Usa a data do sistema como referência, paciente do sistema
                    dados_para_salvar.append({
                        'data': data_s,
                        'paciente': s.get('paciente', ''),
                        'codigo_sistema': int(s.get('codigo_exame', 0)),
                        'descricao_sistema': s.get('descricao', '') or '',
                        'valor_sistema': float(s.get('valor_sistema', 0.0) or 0.0),
                        'codigo_ipes': int(i.get('codigo_exame', 0)),
                        'descricao_ipes': i.get('descricao', '') or '',
                        'valor_ipes': float(i.get('valor_ipes', 0.0) or 0.0),
                        'data_exportacao': datetime.now(),
                        'origem': 'inconsistencia_individual'
                    })
        else:
            # Se há apenas um dos lados, cria registros com o outro lado vazio/zero
            if not df_sis.empty:
                for _, s in df_sis.iterrows():
                    data_s = pd.to_datetime(s.get('data_cadastro')).date() if pd.notna(s.get('data_cadastro')) else datetime.now().date()
                    
                    dados_para_salvar.append({
                        'data': data_s,
                        'paciente': s.get('paciente', ''),
                        'codigo_sistema': int(s.get('codigo_exame', 0)),
                        'descricao_sistema': s.get('descricao', '') or '',
                        'valor_sistema': float(s.get('valor_sistema', 0.0) or 0.0),
                        'codigo_ipes': None,
                        'descricao_ipes': '',
                        'valor_ipes': 0.0,
                        'data_exportacao': datetime.now(),
                        'origem': 'inconsistencia_individual'
                    })
            
            if not df_ips.empty:
                for _, i in df_ips.iterrows():
                    data_i = pd.to_datetime(i.get('data_cadastro')).date() if pd.notna(i.get('data_cadastro')) else datetime.now().date()
                    
                    dados_para_salvar.append({
                        'data': data_i,
                        'paciente': i.get('paciente', ''),
                        'codigo_sistema': None,
                        'descricao_sistema': '',
                        'valor_sistema': 0.0,
                        'codigo_ipes': int(i.get('codigo_exame', 0)),
                        'descricao_ipes': i.get('descricao', '') or '',
                        'valor_ipes': float(i.get('valor_ipes', 0.0) or 0.0),
                        'data_exportacao': datetime.now(),
                        'origem': 'inconsistencia_individual'
                    })
        
        df_novos = pd.DataFrame(dados_para_salvar)
        
        # Carrega arquivo existente ou cria novo
        caminho_arquivo = 'data/inconsistencias_ipes.pkl'
        
        if os.path.exists(caminho_arquivo):
            try:
                df_existente = pd.read_pickle(caminho_arquivo)
                df_final = pd.concat([df_existente, df_novos], ignore_index=True)
            except Exception:
                df_final = df_novos
        else:
            df_final = df_novos
        
        os.makedirs('data', exist_ok=True)
        df_final.to_pickle(caminho_arquivo)
        
        return True, f"{len(df_novos)} inconsistência(s) registradas em inconsistencias_ipes.pkl"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Erro ao registrar inconsistências: {str(e)}"


# Função auxiliar para extrair índices do arquivo de forma robusta
def _extract_indices_trans(df):
    """
    Retorna lista de índices originais ('indice_arquivo') a partir do DataFrame selecionado.
    Se a coluna não existir, usa o índice do DataFrame. Garante lista de ints.
    """
    if df is None or df.empty:
        return []
    if 'indice_arquivo' in df.columns:
        col = df['indice_arquivo']
        # caso por algum motivo a seleção retorne DataFrame em vez de Series
        if isinstance(col, pd.DataFrame):
            col = col.iloc[:, 0]
        return col.dropna().astype(int).tolist()
    # fallback: índices do DataFrame resultante (posições)
    return [int(x) for x in df.index.tolist()]

def salvar_inconsistencias_automatizada(selecionados):
    """
    Salva inconsistências da conciliação automatizada no arquivo inconsistencias_ipes.pkl.
    """
    try:
        # Prepara dados para salvar
        dados_para_salvar = []
        
        for _, exame in selecionados.iterrows():
            dados_para_salvar.append({
                'data': exame['data'],
                'paciente': exame['paciente'],
                'descricao': exame['descricao'],
                'codigo': exame['codigo_exame'],
                'valor_sistema': exame['valor_sistema'],
                'valor_ipes': exame['valor_ipes'],
                'data_exportacao': datetime.now(),
                'origem': 'conciliacao_automatizada_consolidado'  # MODIFICADO: indica uso de dados consolidados
            })
        
        df_novos = pd.DataFrame(dados_para_salvar)
        
        # Carrega arquivo existente ou cria novo
        caminho_arquivo = 'data/inconsistencias_ipes.pkl'
        
        if os.path.exists(caminho_arquivo):
            try:
                df_existente = pd.read_pickle(caminho_arquivo)
                # Concatena dados novos com existentes
                df_final = pd.concat([df_existente, df_novos], ignore_index=True)
            except Exception:
                # Se houver erro ao ler o arquivo existente, cria novo
                df_final = df_novos
        else:
            df_final = df_novos
        
        # Salva o arquivo
        os.makedirs('data', exist_ok=True)
        df_final.to_pickle(caminho_arquivo)
        
        return True, f"{len(selecionados)} inconsistências registradas automaticamente (dados consolidados)"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Erro ao registrar inconsistências: {str(e)}"

def salvar_inconsistencias_automatizada_v2(selecionados):
    """
    Salva inconsistências da conciliação automatizada no arquivo inconsistencias_ipes.pkl.
    Versão atualizada compatível com o novo formato de dados consolidados.
    """
    try:
        df_sis = selecionados.get('sistema', pd.DataFrame())
        df_ips = selecionados.get('ipes', pd.DataFrame())
        
        if df_sis.empty and df_ips.empty:
            return False, "Nenhuma seleção para salvar."
        
        dados_para_salvar = []
        
        # Se ambos têm linhas, grava combinações cruzadas (cada par sistema x ipes)
        if (not df_sis.empty) and (not df_ips.empty):
            for _, s in df_sis.iterrows():
                for _, i in df_ips.iterrows():
                    # Extrai data do campo data_cadastro (que está em formato datetime)
                    data_s = pd.to_datetime(s.get('data_cadastro')).date() if pd.notna(s.get('data_cadastro')) else datetime.now().date()
                    data_i = pd.to_datetime(i.get('data_cadastro')).date() if pd.notna(i.get('data_cadastro')) else datetime.now().date()
                    
                    dados_para_salvar.append({
                        'data': data_s,  # Usa data do sistema como referência
                        'paciente': s.get('paciente', ''),
                        'codigo_sistema': int(s.get('codigo_exame', 0)),
                        'descricao_sistema': s.get('descricao', '') or '',
                        'valor_sistema': float(s.get('valor_sistema', 0.0) or 0.0),
                        'codigo_ipes': int(i.get('codigo_exame', 0)),
                        'descricao_ipes': i.get('descricao', '') or '',
                        'valor_ipes': float(i.get('valor_ipes', 0.0) or 0.0),
                        'data_exportacao': datetime.now(),
                        'origem': 'conciliacao_automatizada'
                    })
        else:
            # Se há apenas um dos lados, cria registros com o outro lado vazio/zero
            if not df_sis.empty:
                for _, s in df_sis.iterrows():
                    data_s = pd.to_datetime(s.get('data_cadastro')).date() if pd.notna(s.get('data_cadastro')) else datetime.now().date()
                    
                    dados_para_salvar.append({
                        'data': data_s,
                        'paciente': s.get('paciente', ''),
                        'codigo_sistema': int(s.get('codigo_exame', 0)),
                        'descricao_sistema': s.get('descricao', '') or '',
                        'valor_sistema': float(s.get('valor_sistema', 0.0) or 0.0),
                        'codigo_ipes': None,
                        'descricao_ipes': '',
                        'valor_ipes': 0.0,
                        'data_exportacao': datetime.now(),
                        'origem': 'conciliacao_automatizada'
                    })
            
            if not df_ips.empty:
                for _, i in df_ips.iterrows():
                    data_i = pd.to_datetime(i.get('data_cadastro')).date() if pd.notna(i.get('data_cadastro')) else datetime.now().date()
                    
                    dados_para_salvar.append({
                        'data': data_i,
                        'paciente': i.get('paciente', ''),
                        'codigo_sistema': None,
                        'descricao_sistema': '',
                        'valor_sistema': 0.0,
                        'codigo_ipes': int(i.get('codigo_exame', 0)),
                        'descricao_ipes': i.get('descricao', '') or '',
                        'valor_ipes': float(i.get('valor_ipes', 0.0) or 0.0),
                        'data_exportacao': datetime.now(),
                        'origem': 'conciliacao_automatizada'
                    })
        
        df_novos = pd.DataFrame(dados_para_salvar)
        
        # Carrega arquivo existente ou cria novo
        caminho_arquivo = 'data/inconsistencias_ipes.pkl'
        
        if os.path.exists(caminho_arquivo):
            try:
                df_existente = pd.read_pickle(caminho_arquivo)
                df_final = pd.concat([df_existente, df_novos], ignore_index=True)
            except Exception:
                df_final = df_novos
        else:
            df_final = df_novos
        
        os.makedirs('data', exist_ok=True)
        df_final.to_pickle(caminho_arquivo)
        
        return True, f"{len(df_novos)} inconsistência(s) registradas em inconsistencias_ipes.pkl"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Erro ao registrar inconsistências: {str(e)}"