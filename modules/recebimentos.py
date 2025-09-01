import streamlit as st
import pandas as pd
from datetime import date, datetime
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
    
    # Cria as 3 abas principais
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
    
    # Carrega dados
    df_recebimentos = obter_recebimentos_cartao(cartao)
    df_recebimentos = _sanitize_valores_cols(df_recebimentos, ['valor_pendente'])
    
    df_transacoes = obter_dados_cartao(cartao)
    
    if df_recebimentos.empty:
        st.warning(f"Não há recebimentos pendentes de {cartao}")
        return
    
    if df_transacoes.empty:
        st.warning(f"Não há transações importadas de {cartao}")
        return
    
    # Prepara dados para exibição - recebimentos
    df_recebimentos = df_recebimentos.reset_index(drop=True)
    df_recebimentos['selecionar'] = False
    
    # Prepara dados para exibição - transações (já tem indice_arquivo)
    df_transacoes = df_transacoes.reset_index(drop=True)
    df_transacoes['selecionar'] = False
        
    # Duas colunas para as tabelas
    col_esq, col_dir = st.columns(2)
    
    with col_esq:
        st.markdown("#### 📋 Recebimentos Pendentes")
        
        df_rec_display = df_recebimentos.copy()
        df_rec_display['data_operacao'] = pd.to_datetime(df_rec_display['data_operacao']).dt.strftime('%d/%m/%Y')
                
        st.markdown(f"<span style='color:blue; font-size:small;'>{len(df_recebimentos)} registros pendentes</span>", unsafe_allow_html=True)
        
        if 'baixa_parcial' not in df_rec_display.columns:
            df_rec_display['baixa_parcial'] = False
        if 'valor_residual' not in df_rec_display.columns:
            df_rec_display['valor_residual'] = df_rec_display['valor_pendente']
        
        colunas_exibir_rec = ['selecionar', 'baixa_parcial', 'data_operacao', 'paciente', 'valor_pendente', 'valor_residual']
        
        column_config_rec = {
            'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
            'baixa_parcial': st.column_config.CheckboxColumn('Baixa Parcial', width='small'),
            'data_operacao': 'Data',
            'paciente': 'Paciente',
            'valor_pendente': 'Valor Total',
            'valor_residual': 'Valor Residual'
        }
        
        df_rec_editado = st.data_editor(
            df_rec_display[colunas_exibir_rec],
            column_config=column_config_rec,
            disabled=['data_operacao', 'paciente', 'valor_pendente', 'valor_residual'],
            hide_index=True,
            height=400,
            key=f"editor_rec_{cartao}"
        )
    
    with col_dir:
        st.markdown(f"#### 💳 Transações {cartao}")

        df_trans_display = df_transacoes.copy()
        if cartao == 'MULVI':
            df_trans_display['data'] = pd.to_datetime(df_trans_display['Data_Lançamento']).dt.strftime('%d/%m/%Y')
            def get_n_parcelas(parcela):
                try:
                    return int(str(parcela).split('/')[-1])
                except:
                    return 1
            df_trans_display['n_parcelas'] = df_trans_display['Parcela'].apply(get_n_parcelas)
            df_trans_display['valor_total_venda'] = df_trans_display['ValorBruto'] * df_trans_display['n_parcelas']
            df_trans_display['info'] = df_trans_display['Bandeira']
            df_trans_display['parcela'] = df_trans_display['Parcela']
            # Use os nomes reais das colunas do DataFrame!
            colunas_exibir = [
                'selecionar', 'data', 'valor_total_venda', 'ValorBruto', 'ValorLiquido', 'info', 'parcela'
            ]
            column_config = {
                'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
                'data': 'Data',
                'valor_total_venda': st.column_config.NumberColumn('Valor Total Venda', format="%.2f"),
                'ValorBruto': st.column_config.NumberColumn('Valor Bruto', format="%.2f"),
                'ValorLiquido': st.column_config.NumberColumn('Valor Líquido', format="%.2f"),
                'info': 'Tipo/Bandeira',
                'parcela': 'Parcela',
                'parcela_antiga': st.column_config.CheckboxColumn('Parcela Antiga', width='small')
            }
        else:  # GETNET
            df_trans_display['data'] = pd.to_datetime(df_trans_display['DATA DE VENCIMENTO']).dt.strftime('%d/%m/%Y')
            df_trans_display['valor_total_venda'] = df_trans_display['VALOR DA VENDA']
            df_trans_display['info'] = df_trans_display['TIPO DE LANÇAMENTO']
            df_trans_display['parcela'] = df_trans_display['PARCELAS']
            colunas_exibir = [
                'selecionar', 'data', 'valor_total_venda', 'VALOR DA PARCELA', 'VALOR LÍQUIDO', 'info', 'parcela'
            ]
            column_config = {
                'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
                'data': 'Data',
                'valor_total_venda': st.column_config.NumberColumn('Valor Total Venda', format="%.2f"),
                'VALOR DA PARCELA': st.column_config.NumberColumn('Valor Bruto', format="%.2f"),
                'VALOR LÍQUIDO': st.column_config.NumberColumn('Valor Líquido', format="%.2f"),
                'info': 'Tipo/Bandeira',
                'parcela': 'Parcela',
                'parcela_antiga': st.column_config.CheckboxColumn('Parcela Antiga', width='small')
            }
        # Adiciona a coluna de seleção de parcela antiga
        df_trans_display['parcela_antiga'] = False
        colunas_exibir.append('parcela_antiga')

        st.markdown(f"<span style='color:blue; font-size:small;'>{len(df_trans_display)} registros pendentes</span>", unsafe_allow_html=True)

        df_trans_editado = st.data_editor(
            df_trans_display[colunas_exibir],
            column_config=column_config,
            disabled=['data', 'valor_total_venda', colunas_exibir[3], colunas_exibir[4], 'info', 'parcela'],
            hide_index=True,
            height=400,
            key=f"editor_trans_{cartao}"
        )
    
    # Área de confirmação
    rec_selecionados = df_recebimentos[df_rec_editado['selecionar']]
    trans_selecionadas = df_transacoes[df_trans_editado['selecionar']]

    baixa_parcial_selecionada = df_rec_editado['baixa_parcial'].any()
    parcela_antiga_selecionada = df_trans_editado['parcela_antiga'].any()  # NOVO: Verifica se parcela antiga foi marcada
    
    # NOVO: Permite conciliação se houver transações selecionadas E (recebimentos selecionados OU parcela antiga marcada)
    if not trans_selecionadas.empty and (not rec_selecionados.empty or parcela_antiga_selecionada):
        st.markdown("---")
        st.markdown("### ✅ Confirmar Conciliação")
                
        # Calcula valores
        if baixa_parcial_selecionada:
            if cartao == 'MULVI':
                valor_bruto = trans_selecionadas['ValorBruto'].sum()
            else:  # GETNET
                valor_bruto = trans_selecionadas['VALOR DA PARCELA'].sum()
        else:
            # Lógica original: usa o valor total do recebimento pendente (se houver)
            if not rec_selecionados.empty:
                valor_bruto = rec_selecionados['valor_pendente'].sum()
            else:
                # NOVO: Para parcela antiga, usa o valor bruto da transação
                if cartao == 'MULVI':
                    valor_bruto = trans_selecionadas['ValorBruto'].sum()
                else:
                    valor_bruto = trans_selecionadas['VALOR DA PARCELA'].sum()
        
        if cartao == 'MULVI':
            valor_liquido = trans_selecionadas['ValorLiquido'].sum()
        else:
            valor_liquido = trans_selecionadas['VALOR LÍQUIDO'].sum()
        
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
            key=f"conta_{cartao}"
        )
        
        if st.button(f"✅ Confirmar Conciliação {cartao}", type="primary", use_container_width=True):
            # NOVO: Define ids_rec baseado em parcela antiga
            if parcela_antiga_selecionada:
                ids_rec = []  # Nenhum recebimento pendente para parcelas antigas
            else:
                ids_rec = rec_selecionados['id_pendencia'].tolist()
            
            indices_trans_arquivo = trans_selecionadas['indice_arquivo'].tolist()
            
            # NOVO: Para baixa parcial, use o valor_bruto da transação como valor_parcial
            if baixa_parcial_selecionada:
                valores_parciais = [valor_bruto] * len(ids_rec)  # Mesmo valor para todos os selecionados
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
                    parcela_antiga=parcela_antiga_selecionada  # NOVO: Passa flag de parcela antiga
                )
                
                if sucesso:
                    st.success(msg)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)
    
    # NOVO: Ajusta mensagens de aviso
    elif not trans_selecionadas.empty and parcela_antiga_selecionada:
        st.info("ℹ️ Parcela antiga selecionada. Confirme para registrar apenas a entrada na conta.")
    elif not trans_selecionadas.empty and rec_selecionados.empty:
        st.warning("⚠️ Selecione pelo menos um recebimento pendente OU marque 'Parcela Antiga'")
    elif trans_selecionadas.empty:
        st.warning("⚠️ Selecione pelo menos uma transação")

def mostrar_aba_ipes():
    """Aba para conciliação de convênio IPES."""
    
    # Carrega dados
    df_recebimentos = obter_recebimentos_ipes()
    df_recebimentos = _sanitize_valores_cols(df_recebimentos, ['valor_pendente'])
    
    df_pagamentos = obter_dados_ipes()
    
    if df_recebimentos.empty:
        st.info("Não há recebimentos pendentes do convênio IPES")
        return
    
    if df_pagamentos.empty:
        st.warning("Não há pagamentos IPES importados. Importe o relatório IPES primeiro.")
        return
    
    # --- SEÇÃO DE FILTROS ---
    st.markdown("---")
    st.markdown("#### 🔎 Filtros")
    
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])

    with col_f1:
        filtro_paciente = st.text_input("Filtrar por nome do paciente:", key="filtro_paciente_ipes")
    
    # Define datas padrão para os filtros de data
    data_min_rec = df_recebimentos['data_operacao'].min() if not df_recebimentos.empty else date.today()
    data_max_rec = df_recebimentos['data_operacao'].max() if not df_recebimentos.empty else date.today()

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
        df_recebimentos['data_operacao'] = pd.to_datetime(df_recebimentos['data_operacao'])
        mask_rec = (df_recebimentos['data_operacao'].dt.date >= filtro_data_inicio) & (df_recebimentos['data_operacao'].dt.date <= filtro_data_fim)
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
        st.markdown("#### 📋 Recebimentos Pendentes IPES")
        
        df_rec_display = df_recebimentos.copy()
        df_rec_display['data_operacao'] = pd.to_datetime(df_rec_display['data_operacao']).dt.strftime('%d/%m/%Y')
        
        st.markdown(f"<span style='color:blue; font-size:small;'>{len(df_rec_display)} registros pendentes</span>", unsafe_allow_html=True)

        df_rec_editado = st.data_editor(
            df_rec_display[['selecionar', 'data_operacao', 'paciente', 'valor_pendente']],
            column_config={
                'selecionar': st.column_config.CheckboxColumn('✓', width='small'),
                'data_operacao': 'Data',
                'paciente': 'Paciente',
                'valor_pendente': 'Valor'
            },
            disabled=['data_operacao', 'paciente', 'valor_pendente'],
            hide_index=True,
            height=400,
            key="editor_rec_ipes"
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
        st.markdown("---")
        st.markdown("### ✅ Confirmar Conciliação IPES")
                
        valor_pendente = rec_selecionados['valor_pendente'].sum()
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
            ids_rec = rec_selecionados['id_pendencia'].tolist()
            indices_pag_arquivo = [idx for sublist in pag_selecionados_agrupados['indices_originais'] for idx in sublist]
            valor_pendente = rec_selecionados['valor_pendente'].sum()
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
                    st.rerun()
                else:
                    st.error(msg)
    
    elif not rec_selecionados.empty and pag_selecionados_agrupados.empty:
        st.warning("⚠️ Selecione pelo menos um pagamento IPES")
    elif rec_selecionados.empty and not pag_selecionados_agrupados.empty:
        st.warning("⚠️ Selecione pelo menos um recebimento pendente IPES")
    else:
        st.warning("⚠️ Selecione pelo menos um pagamento IPES")