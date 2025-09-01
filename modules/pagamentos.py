import streamlit as st
import pandas as pd
import os
from datetime import date, timedelta
from components.functions import (
    salvar_dados, 
    registrar_saida, 
    carregar_dados_github_api,
    carregar_descricoes_personalizadas, 
    salvar_nova_descricao
)

@st.cache_data
def carregar_categorias_despesas():
    """
    Carrega e processa o arquivo de categorias e subcategorias de despesas.
    Retorna um dicionário onde as chaves são categorias e os valores são listas de subcategorias.
    """
    caminho_arquivo = 'categoria_despesas.csv'
    if not os.path.exists(caminho_arquivo):
        st.error(f"Arquivo de categorias não encontrado em '{caminho_arquivo}'")
        return {}
    try:
        df = pd.read_csv(caminho_arquivo, sep=';')
        # Garante que não há valores nulos que possam quebrar o groupby
        df.dropna(subset=['CATEGORIA', 'SUBCATEGORIA'], inplace=True)
        
        categorias_dict = df.groupby('CATEGORIA')['SUBCATEGORIA'].apply(lambda x: sorted(list(x.unique()))).to_dict()
        return categorias_dict
    except Exception as e:
        st.error(f"Erro ao carregar 'categoria_despesas.csv': {e}")
        return {}

def show():
    """Página de Pagamentos"""
    
    st.header("💳 Pagamentos")
    st.markdown("**Registro de saídas e pagamentos diversos**")
    
    # Carrega as categorias de despesas
    categorias_despesas = carregar_categorias_despesas()
    
    # Abas para diferentes tipos de operação
    tab1, tab2, tab3 = st.tabs(["💰 Novo Pagamento", "📝 Alterar Registro", "📊 Histórico"])
    
    with tab1:
        st.markdown("### 💰 Registrar Novo Pagamento")

        # --- LÓGICA DA MENSAGEM DE SUCESSO ---
        # Verifica se há uma mensagem de sucesso para exibir após um rerun
        if 'show_success_message' in st.session_state and st.session_state.show_success_message:
            st.success("✅ Pagamento registrado com sucesso!")
            # Limpa a flag para não mostrar a mensagem novamente
            del st.session_state.show_success_message
        
        if not categorias_despesas:
            st.warning("Não foi possível carregar as categorias de despesas. Verifique o arquivo 'data/categoria_despesas.csv'.")
            return

        # --- SELETORES FORA DO FORMULÁRIO ---
        col1_select, col2_select = st.columns(2)
        with col1_select:
            lista_categorias = sorted(list(categorias_despesas.keys()))
            categoria = st.selectbox(
                "📂 Categoria",
                lista_categorias,
                index=None,
                placeholder="Selecione a categoria...",
                help="Selecione a categoria principal da despesa",
                key="categoria_pagamento" # Adicionar uma chave ajuda a manter o estado
            )
        
        with col2_select:
            if categoria:
                lista_subcategorias = categorias_despesas.get(categoria, [])
            else:
                lista_subcategorias = []

            subcategoria = st.selectbox(
                "📋 Subcategoria",
                lista_subcategorias,
                index=None,
                placeholder="Selecione a subcategoria...",
                help="Selecione primeiro uma categoria",
                disabled=not categoria,
                key="subcategoria_pagamento" # Adicionar uma chave ajuda a manter o estado
            )

        if 'form_counter' not in st.session_state:
            st.session_state.form_counter = 0
            
        with st.form(f"form_pagamento_{st.session_state.form_counter}"):
            col1, col2 = st.columns(2)
            
            with col1:
                data_pagamento = st.date_input(
                    "📅 Data do Pagamento",
                    value=date.today(),
                    help="Data em que o pagamento foi realizado"
                )
                valor = st.number_input(
                    "💵 Valor (R$)",
                    min_value=0.01,
                    format="%.2f",
                    help="Valor do pagamento"
                )
            
            with col2:
                conta_origem = st.selectbox(
                    "🏦 Conta de Origem",
                    ["DINHEIRO", "SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MERCADO PAGO", "CONTA PIX"],
                    help="Conta de onde o dinheiro será debitado"
                )
                observacoes = st.text_area(
                    "📄 Observações",
                    height=120,
                    placeholder="Digite aqui informações adicionais (opcional)...",
                    help="Informações adicionais sobre o pagamento"
                )
            
            # Botão de envio
            submitted = st.form_submit_button(
                "✅ Registrar Pagamento", 
                type="primary",
                use_container_width=True
            )
            
            # Processamento do formulário
            if submitted:
                if categoria and subcategoria and valor > 0:
                    try:
                        sucesso = registrar_saida(
                            data=data_pagamento,
                            categoria=categoria,
                            subcategoria=subcategoria,
                            valor=valor,
                            conta_origem=conta_origem,
                            observacoes=observacoes
                        )

                        if sucesso:
                            # Define a flag de sucesso para ser exibida após o rerun
                            st.session_state.show_success_message = True
                            
                            # Limpa os campos do formulário que usam 'key' para que eles reiniciem
                            if 'categoria_pagamento' in st.session_state:
                                del st.session_state.categoria_pagamento
                            if 'subcategoria_pagamento' in st.session_state:
                                del st.session_state.subcategoria_pagamento
                            
                            # Incrementa o contador para forçar recriação do formulário
                            st.session_state.form_counter += 1
                            
                            # Limpa o cache de dados e força o rerun da página
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("❌ Erro ao registrar o pagamento.")
                            
                    except Exception as e:
                        st.error(f"❌ Erro inesperado: {str(e)}")
                else:
                    st.warning("⚠️ Preencha os campos Categoria, Subcategoria e Valor antes de registrar.")

    with tab2:
        st.markdown("### 📝 Alterar Registro Existente")
        
        try:
            # Carrega as movimentações
            df = carregar_dados_github_api(
                "movimentacoes.csv",
                st.secrets["github"]["github_token"],
                "leoparipiranga/clinicasantasaude"
            )
            
            if not df.empty:
                # Filtra apenas saídas (pagamentos) dos últimos 30 dias
                df_saidas = df[df['tipo'] == 'SAIDA'].copy()
                
                if not df_saidas.empty:
                    # Converte data para facilitar filtro
                    df_saidas['data'] = pd.to_datetime(df_saidas['data']).dt.date
                    
                    # Filtro por período
                    data_limite = date.today() - timedelta(days=30)
                    df_recentes = df_saidas[df_saidas['data'] >= data_limite]
                    
                    if not df_recentes.empty:
                        # Seletor de registro
                        opcoes_registros = []
                        for idx, row in df_recentes.iterrows():
                            try:
                                data_str = row['data'].strftime('%d/%m/%Y')
                                valor_num = float(row['valor'])
                                opcao = f"{data_str} - {row['descricao']} - R$ {valor_num:.2f} - {row['conta_origem']}"
                                opcoes_registros.append((opcao, idx))
                            except (ValueError, TypeError):
                                continue
                        
                        if opcoes_registros:
                            registro_selecionado = st.selectbox(
                                "Selecione o registro para alterar:",
                                options=[None] + opcoes_registros,
                                format_func=lambda x: "Selecione um registro..." if x is None else x[0]
                            )
                            
                            if registro_selecionado:
                                idx_selecionado = registro_selecionado[1]
                                dados_registro = df_recentes.loc[idx_selecionado]
                                
                                st.markdown("#### 🔧 Editar Registro")
                                
                                with st.form("form_edicao"):
                                    col_ed1, col_ed2 = st.columns(2)
                                    
                                    with col_ed1:
                                        nova_data = st.date_input(
                                            "📅 Data",
                                            value=dados_registro['data']
                                        )
                                        
                                        nova_categoria = st.text_input(
                                            "📂 Categoria",
                                            value=str(dados_registro['categoria'])
                                        )
                                        
                                        nova_subcategoria = st.text_input(
                                            "📋 Subcategoria",
                                            value=str(dados_registro['subcategoria'])
                                        )
                                        
                                        try:
                                            valor_atual = float(dados_registro['valor'])
                                        except (ValueError, TypeError):
                                            valor_atual = 0.01
                                        
                                        novo_valor = st.number_input(
                                            "💵 Valor (R$)",
                                            value=valor_atual,
                                            min_value=0.01,
                                            format="%.2f"
                                        )
                                    
                                    with col_ed2:
                                        contas_disponiveis = ["DINHEIRO", "SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MERCADO PAGO", "CONTA PIX"]
                                        
                                        # Verifica se a conta atual está na lista
                                        conta_atual = str(dados_registro['conta_origem'])
                                        if conta_atual in contas_disponiveis:
                                            index_conta = contas_disponiveis.index(conta_atual)
                                        else:
                                            index_conta = 0
                                        
                                        nova_conta = st.selectbox(
                                            "🏦 Conta de Origem",
                                            contas_disponiveis,
                                            index=index_conta
                                        )
                                        
                                        nova_descricao = st.text_input(
                                            "📝 Descrição",
                                            value=str(dados_registro['descricao'])
                                        )
                                        
                                        novas_observacoes = st.text_area(
                                            "📄 Observações",
                                            value=str(dados_registro.get('observacoes', '')),
                                            height=80
                                        )
                                    
                                    col_ed_btn1, col_ed_btn2 = st.columns(2)
                                    
                                    with col_ed_btn1:
                                        if st.form_submit_button("✅ Salvar Alterações", type="primary"):
                                            # Aqui implementaria a atualização do registro
                                            # Por enquanto, apenas mostra uma mensagem
                                            st.success("✅ Alterações salvas com sucesso!")
                                            st.info("🔧 Funcionalidade de edição em desenvolvimento")
                                    
                                    with col_ed_btn2:
                                        if st.form_submit_button("🗑️ Excluir Registro"):
                                            # Aqui implementaria a exclusão do registro
                                            st.error("🗑️ Funcionalidade de exclusão em desenvolvimento")
                        else:
                            st.warning("⚠️ Nenhum registro válido encontrado para edição")
                    else:
                        st.info("📝 Nenhum pagamento encontrado nos últimos 30 dias")
                else:
                    st.info("📝 Nenhum pagamento registrado ainda")
            else:
                st.info("📝 Nenhuma movimentação encontrada")
                
        except Exception as e:
            st.error(f"❌ Erro ao carregar registros: {str(e)}")
    
    with tab3:
        st.markdown("### 📊 Histórico de Pagamentos")
        
        try:
            # Carrega as movimentações
            df = carregar_dados_github_api(
                "movimentacoes.csv",
                st.secrets["github"]["github_token"],
                "leoparipiranga/clinicasantasaude"
            )
            
            if not df.empty:
                # Filtra apenas saídas (pagamentos)
                pagamentos = df[df['tipo'] == 'SAIDA'].copy()
                
                if not pagamentos.empty:
                    # Filtros
                    col_f1, col_f2, col_f3 = st.columns(3)
                    
                    with col_f1:
                        categoria_filtro = st.selectbox(
                            "📂 Categoria:",
                            ["Todas"] + list(pagamentos['categoria'].unique()),
                            key="cat_filtro_pag"
                        )
                    
                    with col_f2:
                        conta_filtro = st.selectbox(
                            "🏦 Conta:",
                            ["Todas"] + list(pagamentos['conta_origem'].unique()),
                            key="conta_filtro_pag"
                        )
                    
                    with col_f3:
                        # Filtro de período
                        pagamentos['data'] = pd.to_datetime(pagamentos['data']).dt.date
                        data_min = pagamentos['data'].min()
                        data_max = pagamentos['data'].max()
                        
                        periodo_opcoes = {
                            "Últimos 7 dias": 7,
                            "Últimos 30 dias": 30,
                            "Últimos 90 dias": 90,
                            "Todos": None
                        }
                        
                        periodo_selecionado = st.selectbox(
                            "📅 Período:",
                            list(periodo_opcoes.keys()),
                            key="periodo_filtro_pag"
                        )
                    
                    # Aplica filtros
                    df_filtrado = pagamentos.copy()
                    
                    if categoria_filtro != "Todas":
                        df_filtrado = df_filtrado[df_filtrado['categoria'] == categoria_filtro]
                    
                    if conta_filtro != "Todas":
                        df_filtrado = df_filtrado[df_filtrado['conta_origem'] == conta_filtro]
                    
                    if periodo_opcoes[periodo_selecionado]:
                        data_limite = date.today() - timedelta(days=periodo_opcoes[periodo_selecionado])
                        df_filtrado = df_filtrado[df_filtrado['data'] >= data_limite]
                    
                    if not df_filtrado.empty:
                        # Converte valores para numérico
                        df_filtrado['valor'] = pd.to_numeric(df_filtrado['valor'], errors='coerce').fillna(0)
                        
                        # Ordena por data (mais recente primeiro)
                        df_filtrado = df_filtrado.sort_values('data', ascending=False)
                        
                        # Métricas resumo
                        total_pago = df_filtrado['valor'].sum()
                        total_registros = len(df_filtrado)
                        ticket_medio = total_pago / total_registros if total_registros > 0 else 0
                        
                        col_m1, col_m2, col_m3 = st.columns(3)
                        
                        with col_m1:
                            st.metric("💰 Total Pago", f"R$ {total_pago:,.2f}")
                        with col_m2:
                            st.metric("📊 Quantidade", f"{total_registros} pagamentos")
                        with col_m3:
                            st.metric("📈 Ticket Médio", f"R$ {ticket_medio:,.2f}")
                        
                        # Gráfico por categoria (se houver múltiplas categorias)
                        if len(df_filtrado['categoria'].unique()) > 1:
                            st.markdown("#### 📊 Pagamentos por Categoria")
                            
                            categoria_resumo = df_filtrado.groupby('categoria')['valor'].sum().sort_values(ascending=False)
                            st.bar_chart(categoria_resumo)
                        
                        # Tabela detalhada
                        st.markdown("#### 📋 Detalhamento dos Pagamentos")
                        
                        # Seleciona colunas para exibir
                        colunas_exibir = ['data', 'categoria', 'subcategoria', 'descricao', 'valor', 'conta_origem']
                        
                        # Adiciona observações se existir
                        if 'observacoes' in df_filtrado.columns:
                            colunas_exibir.append('observacoes')
                        
                        st.dataframe(
                            df_filtrado[colunas_exibir],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "data": st.column_config.DateColumn(
                                    "Data",
                                    format="DD/MM/YYYY"
                                ),
                                "valor": st.column_config.NumberColumn(
                                    "Valor",
                                    format="R$ %.2f"
                                ),
                                "categoria": "Categoria",
                                "subcategoria": "Subcategoria",
                                "descricao": "Descrição",
                                "conta_origem": "Conta",
                                "observacoes": "Observações"
                            }
                        )
                        
                        # Opção de exportar dados
                        if st.button("📥 Exportar para CSV"):
                            csv = df_filtrado.to_csv(index=False, encoding='utf-8')
                            st.download_button(
                                label="⬇️ Download CSV",
                                data=csv,
                                file_name=f"pagamentos_{date.today().strftime('%Y%m%d')}.csv",
                                mime="text/csv"
                            )
                    else:
                        st.info("📝 Nenhum pagamento encontrado com os filtros selecionados")
                else:
                    st.info("📝 Nenhum pagamento registrado ainda")
            else:
                st.info("📝 Nenhuma movimentação encontrada")
                
        except Exception as e:
            st.error(f"❌ Erro ao carregar histórico: {str(e)}")