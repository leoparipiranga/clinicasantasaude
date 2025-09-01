import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import math
from streamlit_modal import Modal
from components.functions import registrar_saida

def inicializar_status_repasses():
    """
    Adiciona a coluna 'status' ao arquivo movimento_clinica.pkl se ela não existir.
    Todos os registros sem status recebem 'a_pagar' como padrão.
    """
    try:
        caminho_arquivo = 'data/movimento_clinica.pkl'
        df = pd.read_pickle(caminho_arquivo)
        
        # Verifica se a coluna status já existe
        if 'status_repasse' not in df.columns:
            # Adiciona a coluna com valor padrão 'a_pagar' para todos os registros
            df['status_repasse'] = 'a_pagar'
            
            # Salva o arquivo atualizado
            df.to_pickle(caminho_arquivo)
            st.info("✅ Coluna 'status_repasse' adicionada ao arquivo de movimentos da clínica.")
        
        return df
    except Exception as e:
        st.error(f"Erro ao inicializar status dos repasses: {e}")
        return pd.DataFrame()

def carregar_movimentos_clinica():
    """Carrega os dados do arquivo movimento_clinica.pkl."""
    try:
        # Inicializa a coluna de status se necessário
        df = inicializar_status_repasses()
        
        if df.empty:
            return pd.DataFrame()
        
        # Garante que a coluna de data seja datetime
        if 'data_cadastro' in df.columns:
            df['data_cadastro'] = pd.to_datetime(df['data_cadastro'])
        
        # Filtra apenas registros com repasse médico > 0 E status 'a_pagar'
        if 'repasse_medico' in df.columns and 'status_repasse' in df.columns:
            df = df[
                (df['repasse_medico'] > 0) & 
                (df['status_repasse'] == 'a_pagar')
            ]
        
        return df
    except FileNotFoundError:
        st.error("Arquivo 'movimento_clinica.pkl' não encontrado.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def atualizar_status_repasses(indices_pagos):
    """
    Atualiza o status dos repasses médicos para 'pago' no arquivo movimento_clinica.pkl.
    
    Args:
        indices_pagos (list): Lista de índices dos registros que foram pagos
    
    Returns:
        bool: True se a atualização foi bem-sucedida, False caso contrário
    """
    try:
        caminho_arquivo = 'data/movimento_clinica.pkl'
        df = pd.read_pickle(caminho_arquivo)
        
        # Atualiza o status dos registros pagos
        df.loc[indices_pagos, 'status_repasse'] = 'pago'
        df.loc[indices_pagos, 'data_pagamento'] = datetime.now()
        
        # Salva o arquivo atualizado
        df.to_pickle(caminho_arquivo)
        return True
        
    except Exception as e:
        st.error(f"Erro ao atualizar status dos repasses: {e}")
        return False

def processar_pagamento_medicos(registros_selecionados, data_pagamento, conta_origem, observacoes):
    """
    Processa o pagamento dos repasses médicos selecionados.
    """
    try:
        total_pago = 0
        pagamentos_realizados = []
        indices_processados = []
        
        for idx, registro in registros_selecionados.iterrows():
            # Monta a descrição do pagamento
            descricao = f"Repasse médico - Dr. {registro['medico']} - {registro['paciente']}"
            
            # Registra cada pagamento individualmente no movimentacao_contas.pkl
            sucesso = registrar_saida(
                data=data_pagamento,
                categoria="COMISSÕES",
                subcategoria="COMISSÕES MÉDICAS",
                valor=float(registro['repasse_medico']),
                conta_origem=conta_origem,
                observacoes=f"{observacoes} | {descricao}"
            )
            
            if sucesso:
                total_pago += registro['repasse_medico']
                indices_processados.append(idx)  # Salva o índice para atualizar o status
                pagamentos_realizados.append({
                    'medico': registro['medico'],
                    'paciente': registro['paciente'],
                    'valor': registro['repasse_medico']
                })
            else:
                st.error(f"Erro ao processar pagamento para Dr. {registro['medico']}")
                return False, 0, []
        
        # Se todos os pagamentos foram bem-sucedidos, atualiza o status no arquivo
        if indices_processados:
            sucesso_status = atualizar_status_repasses(indices_processados)
            if not sucesso_status:
                st.warning("⚠️ Pagamentos registrados, mas houve erro ao atualizar status dos repasses.")
        
        return True, total_pago, pagamentos_realizados
        
    except Exception as e:
        st.error(f"Erro ao processar pagamentos: {e}")
        return False, 0, []

def carregar_historico_completo():
    """
    Carrega todos os repasses médicos (pagos e pendentes) para relatórios.
    """
    try:
        df = pd.read_pickle('data/movimento_clinica.pkl')
        if df.empty:
            return pd.DataFrame()
        
        # Garante que a coluna de data seja datetime
        if 'data_cadastro' in df.columns:
            df['data_cadastro'] = pd.to_datetime(df['data_cadastro'])
        
        # Filtra apenas registros com repasse médico > 0 (independente do status)
        if 'repasse_medico' in df.columns:
            df = df[df['repasse_medico'] > 0]
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return pd.DataFrame()

def show():
    """Página de Pagamentos Médicos."""
    st.header("👨‍⚕️ Pagamentos Médicos")
    st.markdown("**Gestão de repasses médicos pendentes.**")

    # Inicializa o estado da página se não existir
    if 'current_page_medicos' not in st.session_state:
        st.session_state.current_page_medicos = 1

    # --- LÓGICA DA MENSAGEM DE SUCESSO ---
    if 'show_success_message_medicos' in st.session_state and st.session_state.show_success_message_medicos:
        st.success("✅ Pagamentos médicos registrados com sucesso!")
        del st.session_state.show_success_message_medicos

    # --- MODAL DE PAGAMENTO (FORA DAS ABAS) ---
    modal = Modal("Pagamento de Repasses Médicos", key="modal_pagamento_medicos")

    # --- CONTEÚDO DO MODAL (FORA DAS ABAS) ---
    if modal.is_open():
        with modal.container():
            
            if 'registros_para_pagamento' not in st.session_state or st.session_state.registros_para_pagamento.empty:
                st.error("❌ Erro: Nenhum registro selecionado encontrado!")
                if st.button("❌ Fechar"):
                    modal.close()
                    st.rerun()
                return
            
            # Usa os registros salvos no session_state
            registros_modal = st.session_state.registros_para_pagamento
            
            # Verifica se a coluna repasse_medico existe
            if 'repasse_medico' not in registros_modal.columns:
                st.error("❌ Erro: Coluna 'repasse_medico' não encontrada nos dados selecionados!")
                st.write("**Colunas disponíveis:**", list(registros_modal.columns))
                if st.button("❌ Fechar"):
                    modal.close()
                    st.rerun()
                return
            
            total_pagamento = registros_modal['repasse_medico'].sum()
            quantidade_repasses = len(registros_modal)

            col_resumo1, col_resumo2 = st.columns(2)
            with col_resumo1:
                st.metric("Quantidade de Repasses", quantidade_repasses)
                st.metric("Valor Total", f"R$ {total_pagamento:,.2f}")
            with col_resumo2:
                # Lista dos médicos e valores
                st.markdown("**Detalhamento:**")
                for _, row in registros_modal.iterrows():
                    st.write(f"• Dr. {row['medico']} - {row['paciente']} - R$ {row['repasse_medico']:,.2f}")
            
            # Formulário de pagamento
            with st.form("form_pagamento_medicos"):
                col1, col2 = st.columns(2)
                
                with col1:
                    data_pagamento = st.date_input(
                        "📅 Data do Pagamento",
                        value=date.today(),
                        help="Data em que o pagamento foi realizado"
                    )
                    
                    # Exibe as categorias fixas
                    st.text_input(
                        "📂 Categoria",
                        value="COMISSÕES",
                        disabled=True,
                        help="Categoria fixa para repasses médicos"
                    )
                
                with col2:
                    conta_origem = st.selectbox(
                        "🏦 Conta de Origem",
                        ["DINHEIRO", "SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MERCADO PAGO", "CONTA PIX"],
                        help="Conta de onde o dinheiro será debitado"
                    )
                    
                    st.text_input(
                        "📋 Subcategoria",
                        value="COMISSÕES MÉDICAS",
                        disabled=True,
                        help="Subcategoria fixa para repasses médicos"
                    )
                
                observacoes = st.text_area(
                    "📄 Observações",
                    height=100,
                    placeholder="Digite observações sobre este pagamento (opcional)...",
                    help="Informações adicionais sobre o pagamento"
                )
                
                # Botões do modal
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.form_submit_button("✅ Confirmar Pagamento", type="primary", use_container_width=True):
                        if data_pagamento and conta_origem:
                            sucesso, total_pago, detalhes = processar_pagamento_medicos(
                                registros_modal, data_pagamento, conta_origem, observacoes
                            )
                            
                            if sucesso:
                                # Limpa as seleções usando os índices salvos
                                if 'indices_selecionados' in st.session_state:
                                    for idx in st.session_state.indices_selecionados:
                                        if f"select_medico_{idx}" in st.session_state:
                                            del st.session_state[f"select_medico_{idx}"]
                                
                                # Limpa os dados temporários do modal
                                if 'registros_para_pagamento' in st.session_state:
                                    del st.session_state.registros_para_pagamento
                                if 'indices_selecionados' in st.session_state:
                                    del st.session_state.indices_selecionados
                                
                                # Define flag de sucesso e fecha modal
                                st.session_state.show_success_message_medicos = True
                                modal.close()
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("❌ Erro ao processar os pagamentos.")
                        else:
                            st.warning("⚠️ Preencha todos os campos obrigatórios.")
                
                with col_btn2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        # Limpa os dados temporários do modal
                        if 'registros_para_pagamento' in st.session_state:
                            del st.session_state.registros_para_pagamento
                        if 'indices_selecionados' in st.session_state:
                            del st.session_state.indices_selecionados
                        modal.close()
                        st.rerun()

    # --- ABAS PARA PENDENTES E HISTÓRICO ---
    tab_pendentes, tab_historico = st.tabs(["💰 Repasses Pendentes", "📊 Histórico Completo"])
    
    with tab_pendentes:
        df_movimentos = carregar_movimentos_clinica()

        if df_movimentos.empty:
            st.info("✅ Nenhum repasse médico pendente encontrado.")
            return

        # --- Filtros ---
        st.markdown("##### 🔍 Filtros")
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            # Filtro de período
            data_min = df_movimentos['data_cadastro'].min().date()
            data_max = df_movimentos['data_cadastro'].max().date()
            
            data_inicio = st.date_input(
                "Data Início:",
                value=data_min,
                min_value=data_min,
                max_value=data_max,
                key="data_inicio_medicos"
            )
            
            data_fim = st.date_input(
                "Data Fim:",
                value=data_max,
                min_value=data_min,
                max_value=data_max,
                key="data_fim_medicos"
            )
        
        with col_f2:
            # Filtro de paciente
            pacientes_disponiveis = ["Todos"] + sorted(list(df_movimentos['paciente'].unique()))
            paciente_filtro = st.selectbox("Filtrar por Paciente:", pacientes_disponiveis, key="paciente_medicos")
            
            # Filtro de médico
            medicos_disponiveis = ["Todos"] + sorted(list(df_movimentos['medico'].unique()))
            medico_filtro = st.selectbox("Filtrar por Médico:", medicos_disponiveis, key="medico_medicos")
        
        with col_f3:
            # Filtro de convênio
            convenios_disponiveis = ["Todos"] + sorted(list(df_movimentos['convenio'].unique()))
            convenio_filtro = st.selectbox("Filtrar por Convênio:", convenios_disponiveis, key="convenio_medicos")
            
            # Filtro de serviços
            servicos_disponiveis = ["Todos"] + sorted(list(df_movimentos['servicos'].unique()))
            servico_filtro = st.selectbox("Filtrar por Serviços:", servicos_disponiveis, key="servico_medicos")

        # --- Aplicar filtros ---
        df_filtrado = df_movimentos.copy()
        
        # Filtro de período
        df_filtrado = df_filtrado[
            (df_filtrado['data_cadastro'].dt.date >= data_inicio) &
            (df_filtrado['data_cadastro'].dt.date <= data_fim)
        ]
        
        # Filtro de paciente
        if paciente_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado['paciente'] == paciente_filtro]
        
        # Filtro de médico
        if medico_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado['medico'] == medico_filtro]
        
        # Filtro de convênio
        if convenio_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado['convenio'] == convenio_filtro]
        
        # Filtro de serviços
        if servico_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado['servicos'] == servico_filtro]

        if df_filtrado.empty:
            st.warning("🔍 Nenhum registro encontrado com os filtros aplicados.")
            return

        # --- Paginação ---
        registros_por_pagina = 10
        total_registros = len(df_filtrado)
        total_paginas = math.ceil(total_registros / registros_por_pagina)

        # Garante que a página atual não exceda o total
        if st.session_state.current_page_medicos > total_paginas:
            st.session_state.current_page_medicos = 1

        # Calcula os índices para a página atual
        inicio = (st.session_state.current_page_medicos - 1) * registros_por_pagina
        fim = inicio + registros_por_pagina
        df_pagina = df_filtrado.iloc[inicio:fim].copy()

        # Informações de paginação
        st.markdown(f"""
        <p style='color: #1f77b4; font-size: 14px; margin-bottom: 10px;'>
        📊 {total_registros} registros encontrados / Exibindo página {st.session_state.current_page_medicos} de {total_paginas}
        </p>
        """, unsafe_allow_html=True)

        # --- Verificar seleções ---
        registros_selecionados_indices = [
            idx for idx in df_pagina.index
            if st.session_state.get(f"select_medico_{idx}", False)
        ]
        
        registros_selecionados = df_pagina.loc[registros_selecionados_indices] if registros_selecionados_indices else pd.DataFrame()
        selected_count = len(registros_selecionados)

        # --- Botão de Registrar Pagamento (ACIMA DA TABELA) ---
        col_btn_pagamento, col_select = st.columns([2, 2])
        
        with col_btn_pagamento:
            if selected_count > 0:
                total_selecionado = registros_selecionados['repasse_medico'].sum()
                if st.button(f"💰 Registrar Pagamento ({selected_count} selecionados - R$ {total_selecionado:,.2f})", type="primary"):
                    # Salva os registros selecionados no session_state antes de abrir o modal
                    st.session_state.registros_para_pagamento = registros_selecionados.copy()
                    st.session_state.indices_selecionados = registros_selecionados_indices.copy()
                    modal.open()
            else:
                st.button("💰 Registrar Pagamento", disabled=True, help="Selecione pelo menos um repasse para registrar o pagamento")

        with col_select:
            if st.button("📋 Selecionar Todos da Página", key="select_all_medicos"):
                for idx in df_pagina.index:
                    st.session_state[f"select_medico_{idx}"] = True
                st.rerun()

        # --- Tabela de repasses médicos ---
        st.markdown("##### 💰 Repasses Médicos Pendentes")
        
        for idx, row in df_pagina.iterrows():
            with st.container():
                col_checkbox, col_data = st.columns([0.5, 9.5])
                
                with col_checkbox:
                    selected = st.checkbox(
                        "",
                        key=f"select_medico_{idx}",
                        value=st.session_state.get(f"select_medico_{idx}", False)
                    )
                
                with col_data:
                    # Formata a data
                    data_formatada = row['data_cadastro'].strftime('%d/%m/%Y')
                    
                    # Cria o card com as informações
                    st.markdown(f"""
                    <div style='border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px; margin-bottom: 8px; background-color: #f9f9f9;'>
                        <div style='display: flex; justify-content: space-between; align-items: center;'>
                            <div>
                                <strong>📅 {data_formatada}</strong> | 
                                <strong>🧑‍⚕️ {row['medico']}</strong> | 
                                <strong>👤 {row['paciente']}</strong>
                            </div>
                            <div style='text-align: right;'>
                                <span style='color: #28a745; font-weight: bold; font-size: 16px;'>
                                    R$ {row['repasse_medico']:,.2f}
                                </span>
                            </div>
                        </div>
                        <div style='margin-top: 8px; color: #666;'>
                            <strong>Convênio:</strong> {row['convenio']} | 
                            <strong>Serviços:</strong> {row['servicos']} | 
                            <strong>Total Procedimento:</strong> R$ {row['total']:,.2f}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # --- Botões de navegação ---
        st.markdown("---")
        col_nav1, col_nav2, col_nav3, col_nav4, col_nav5 = st.columns([1, 1, 2, 1, 1])
        
        with col_nav1:
            if st.button("⏮️ Primeira", disabled=st.session_state.current_page_medicos == 1):
                st.session_state.current_page_medicos = 1
                st.rerun()
        
        with col_nav2:
            if st.button("⬅️ Anterior", disabled=st.session_state.current_page_medicos == 1):
                st.session_state.current_page_medicos -= 1
                st.rerun()
        
        with col_nav3:
            st.markdown(f"<p style='text-align: center; margin-top: 8px;'>Página {st.session_state.current_page_medicos} de {total_paginas}</p>", unsafe_allow_html=True)
        
        with col_nav4:
            if st.button("➡️ Próxima", disabled=st.session_state.current_page_medicos == total_paginas):
                st.session_state.current_page_medicos += 1
                st.rerun()
        
        with col_nav5:
            if st.button("⏭️ Última", disabled=st.session_state.current_page_medicos == total_paginas):
                st.session_state.current_page_medicos = total_paginas
                st.rerun()

        # --- Resumo geral ---
        st.markdown("---")
        st.markdown("##### 📊 Resumo Geral")
        
        col_resumo1, col_resumo2, col_resumo3 = st.columns(3)
        
        with col_resumo1:
            total_repasses = df_filtrado['repasse_medico'].sum()
            st.metric("💰 Total de Repasses", f"R$ {total_repasses:,.2f}")
        
        with col_resumo2:
            total_procedimentos = df_filtrado['total'].sum()
            st.metric("🏥 Total de Procedimentos", f"R$ {total_procedimentos:,.2f}")
        
        with col_resumo3:
            media_repasse = df_filtrado['repasse_medico'].mean()
            st.metric("📈 Repasse Médio", f"R$ {media_repasse:,.2f}")
    
    with tab_historico:
        st.markdown("### 📊 Histórico Completo de Repasses Médicos")
        
        df_historico = carregar_historico_completo()
        
        if df_historico.empty:
            st.info("📄 Nenhum registro de repasse médico encontrado.")
            return
        
        # Filtro por status
        col_status, col_info = st.columns([1, 3])
        with col_status:
            status_filtro = st.selectbox(
                "Status:",
                ["Todos", "A Pagar", "Pago"],
                key="status_historico"
            )
        
        # Aplica filtro de status
        if status_filtro == "A Pagar":
            df_historico_filtrado = df_historico[df_historico['status_repasse'] == 'a_pagar']
        elif status_filtro == "Pago":
            df_historico_filtrado = df_historico[df_historico['status_repasse'] == 'pago']
        else:
            df_historico_filtrado = df_historico
        
        # Exibe a tabela completa
        if not df_historico_filtrado.empty:
            colunas_historico = [
                'data_cadastro', 'paciente', 'medico', 'convenio', 
                'servicos', 'total', 'repasse_medico', 'status_repasse'
            ]
            
            # Adiciona coluna de data de pagamento se existir
            if 'data_pagamento' in df_historico_filtrado.columns:
                colunas_historico.append('data_pagamento')
            
            st.dataframe(
                df_historico_filtrado[colunas_historico],
                use_container_width=True,
                hide_index=True
            )
            
            # Resumo do histórico
            st.markdown("---")
            col_res1, col_res2, col_res3 = st.columns(3)
            
            with col_res1:
                total_repasses = df_historico_filtrado['repasse_medico'].sum()
                st.metric("💰 Total de Repasses", f"R$ {total_repasses:,.2f}")
            
            with col_res2:
                repasses_pagos = df_historico_filtrado[df_historico_filtrado['status_repasse'] == 'pago']['repasse_medico'].sum()
                st.metric("✅ Repasses Pagos", f"R$ {repasses_pagos:,.2f}")
            
            with col_res3:
                repasses_pendentes = df_historico_filtrado[df_historico_filtrado['status_repasse'] == 'a_pagar']['repasse_medico'].sum()
                st.metric("⏳ Repasses Pendentes", f"R$ {repasses_pendentes:,.2f}")
        else:
            st.info("📄 Nenhum registro encontrado com o filtro aplicado.")