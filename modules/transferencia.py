import streamlit as st
import pandas as pd
from datetime import date, timedelta
from components.functions import *

def show():
    """Página de Transferências"""
    st.header("🔄 Transferências")
    st.markdown("**Transferências entre contas**")

    # Abas para diferentes funcionalidades
    tab1, tab2 = st.tabs(["💸 Nova Transferência", "📊 Histórico de Transferências"])
    
    with tab1:
        st.markdown("### 💸 Registrar Nova Transferência")
        
        # --- Mensagem de sucesso fora do form para não ser perdida ---
        if 'transferencia_sucesso' in st.session_state and st.session_state.transferencia_sucesso:
            st.success(f"✅ {st.session_state.transferencia_sucesso}")
            del st.session_state.transferencia_sucesso
        
        # Formulário de transferência simplificado
        with st.form("form_transferencia"):
            
            # --- Layout Visual para Origem → Destino ---
            st.markdown("##### 🔄 Transferência")
            col_origem, col_seta, col_destino = st.columns([3, 1, 3])
            
            # Mapeamento de ícones para as contas
            icones_contas = {
                "SANTANDER": "🏦",
                "BANESE": "🏛️", 
                "C6": "💳",
                "CAIXA": "🏦",
                "BNB": "🏛️",
                "MERCADO PAGO": "💰",
                "CONTA PIX": "📱",
                "DINHEIRO": "💵"
            }
            
            with col_origem:
                st.markdown("**DE:**")
                conta_origem = st.selectbox(
                    "Conta de Origem",
                    ["SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MERCADO PAGO", "CONTA PIX", "DINHEIRO"],
                    key="origem_input",
                    label_visibility="collapsed"
                )
                
                # Exibe ícone e nome da conta origem
                icone_origem = icones_contas.get(conta_origem, "🏦")
                st.markdown(f"<div style='text-align: center; font-size: 20px; margin-top: 10px;'>{icone_origem}<br><strong>{conta_origem}</strong></div>", unsafe_allow_html=True)
            
            with col_seta:
                st.markdown("<div style='text-align: center; font-size: 40px; margin-top: 50px;'>➡️</div>", unsafe_allow_html=True)
            
            with col_destino:
                st.markdown("**PARA:**")
                conta_destino = st.selectbox(
                    "Conta de Destino",
                    ["DINHEIRO", "SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MERCADO PAGO", "CONTA PIX"],
                    key="destino_input",  # CORRIGIDO: key que coincide com a função limpar
                    label_visibility="collapsed"
                )
                
                # Exibe ícone e nome da conta destino
                icone_destino = icones_contas.get(conta_destino, "🏦")
                st.markdown(f"<div style='text-align: center; font-size: 20px; margin-top: 10px;'>{icone_destino}<br><strong>{conta_destino}</strong></div>", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- Outros campos do formulário ---
            col1, col2 = st.columns(2)
            
            with col1:
                data_transferencia = st.date_input(
                    "📅 Data da Transferência",
                    value=date.today(),
                    key="data_input_transferencia"  # CORRIGIDO: key que coincide com a função limpar
                )
                
                valor = st.number_input(
                    "💵 Valor da Transferência (R$)",
                    min_value=0.01,
                    format="%.2f",
                    key="valor_input_transferencia"  # CORRIGIDO: key que coincide com a função limpar
                )
            
            with col2:
                observacoes = st.text_area(
                    "📄 Observações",
                    height=100,
                    placeholder="Motivo ou informações sobre a transferência...",
                    key="observacoes_input_transferencia"  # Adicionado key para poder limpar
                )
            
            # Validação simples
            if conta_origem == conta_destino:
                st.error("❌ A conta de origem deve ser diferente da conta de destino!")
            
            # Botão de submissão
            submitted = st.form_submit_button(
                "✅ Realizar Transferência",
                type="primary",
                use_container_width=True,
                disabled=(conta_origem == conta_destino or valor <= 0)
            )
            
            # Processamento do formulário
            if submitted:
                if valor > 0 and conta_origem != conta_destino:
                    try:
                        # Registra a transferência
                        sucesso = registrar_transferencia(
                            data=data_transferencia,
                            conta_origem=conta_origem,
                            conta_destino=conta_destino,
                            valor=valor,
                            motivo="TRANSFERENCIA",
                            descricao=f"Transferência de {conta_origem} para {conta_destino}",
                            observacoes=observacoes,
                            taxa=0
                        )
                        
                        if sucesso:
                            # Define mensagem de sucesso detalhada para ser exibida após o rerun
                            st.session_state.transferencia_sucesso = f"Transferência de R$ {valor:.2f} de {conta_origem} para {conta_destino} realizada com sucesso!"
                            
                            # Limpa o cache para atualizar saldos
                            st.cache_data.clear()
                            
                            # CORREÇÃO: Remove a chamada para limpar_form_transferencia().
                            # Em vez disso, deleta as chaves do session_state para resetar o formulário no rerun.
                            keys_to_clear = [
                                "origem_input", 
                                "destino_input", 
                                "data_input_transferencia", 
                                "valor_input_transferencia", 
                                "observacoes_input_transferencia"
                            ]
                            for key in keys_to_clear:
                                if key in st.session_state:
                                    del st.session_state[key]
                            
                            # Força a atualização da página
                            st.rerun()
                        else:
                            st.error("❌ Erro ao registrar a transferência. Tente novamente.")
                            
                    except Exception as e:
                        st.error(f"❌ Erro ao registrar transferência: {str(e)}")
                else:
                    st.warning("⚠️ Preencha todos os campos obrigatórios!")

    
    with tab2:
        st.markdown("### 📊 Histórico de Transferências")
        
        df_movimentacoes = carregar_movimentacao_contas()
        
        if df_movimentacoes.empty or 'categoria_pagamento' not in df_movimentacoes.columns:
            st.info("📝 Nenhuma movimentação encontrada.")
            return

        transferencias = df_movimentacoes[df_movimentacoes['categoria_pagamento'] == 'TRANSFERENCIA'].copy()
        
        if transferencias.empty:
            st.info("📝 Nenhuma transferência registrada ainda.")
            return

        # Garante que a coluna id_transferencia existe para o join
        if 'id_transferencia' not in transferencias.columns:
            st.error("A coluna 'id_transferencia' é necessária para exibir o histórico. Por favor, atualize seus dados.")
            return

        # Agrupa as saídas e entradas pelo id_transferencia para reconstruir a visão de transferência
        saidas = transferencias[transferencias['tipo'] == 'SAIDA'].set_index('id_transferencia')
        entradas = transferencias[transferencias['tipo'] == 'ENTRADA'].set_index('id_transferencia')
        
        # Junta os pares de transferência
        df_hist = saidas.join(entradas, lsuffix='_saida', rsuffix='_entrada')
        df_hist.dropna(subset=['pago_entrada'], inplace=True) # Garante que temos o par completo
        
        # Limpa e renomeia colunas para exibição
        df_hist = df_hist.reset_index()
        df_hist.rename(columns={
            'data_cadastro_saida': 'data',
            'conta_saida': 'origem',
            'conta_entrada': 'destino',
            'pago_saida': 'valor_transferido',
            'pago_entrada': 'valor_recebido',
            'observacoes_saida': 'observacoes'
        }, inplace=True)
        
        colunas_finais = ['data', 'origem', 'destino', 'valor_transferido', 'valor_recebido', 'observacoes']
        df_hist = df_hist[colunas_finais]

        # --- Filtros ---
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            contas_disponiveis = sorted(list(set(df_hist['origem'].unique()) | set(df_hist['destino'].unique())))
            conta_filtro = st.selectbox("Filtrar por Conta (Origem ou Destino):", ["Todas"] + contas_disponiveis)
        with col_f2:
            # Filtro por período
            periodo_filtro = st.selectbox(
                "Filtrar por Período:",
                ["Todos", "Últimos 7 dias", "Últimos 30 dias", "Últimos 90 dias"]
            )

        # Aplica filtros
        df_filtrado = df_hist.copy()
        
        if conta_filtro != "Todas":
            df_filtrado = df_filtrado[(df_filtrado['origem'] == conta_filtro) | (df_filtrado['destino'] == conta_filtro)]
        
        if periodo_filtro != "Todos":
            dias_map = {
                "Últimos 7 dias": 7,
                "Últimos 30 dias": 30,
                "Últimos 90 dias": 90
            }
            data_limite = date.today() - timedelta(days=dias_map[periodo_filtro])
            df_filtrado = df_filtrado[pd.to_datetime(df_filtrado['data']).dt.date >= data_limite]

        if not df_filtrado.empty:
            # Exibe histórico com cards visuais
            for idx, row in df_filtrado.iterrows():
                icone_origem = icones_contas.get(row['origem'], "🏦")
                icone_destino = icones_contas.get(row['destino'], "🏦")
                data_formatada = pd.to_datetime(row['data']).strftime('%d/%m/%Y')
                
                st.markdown(f"""
                <div style='border: 1px solid #e0e0e0; border-radius: 8px; padding: 15px; margin-bottom: 10px; background-color: #f9f9f9;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <div style='display: flex; align-items: center; gap: 15px;'>
                            <span style='font-size: 20px;'>{icone_origem}</span>
                            <strong>{row['origem']}</strong>
                            <span style='font-size: 20px;'>➡️</span>
                            <span style='font-size: 20px;'>{icone_destino}</span>
                            <strong>{row['destino']}</strong>
                        </div>
                        <div style='text-align: right;'>
                            <span style='color: #28a745; font-weight: bold; font-size: 18px;'>
                                R$ {row['valor_transferido']:,.2f}
                            </span>
                        </div>
                    </div>
                    <div style='margin-top: 8px; color: #666; font-size: 14px;'>
                        <strong>Data:</strong> {data_formatada} | 
                        <strong>Observações:</strong> {row['observacoes'] if pd.notna(row['observacoes']) else 'Nenhuma'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Resumo simples
            st.markdown("---")
            col_res1, col_res2 = st.columns(2)
            
            with col_res1:
                total_transferido = df_filtrado['valor_transferido'].sum()
                st.metric("💸 Total Transferido", f"R$ {total_transferido:,.2f}")
            
            with col_res2:
                quantidade_transferencias = len(df_filtrado)
                st.metric("🔢 Quantidade de Transferências", quantidade_transferencias)
        else:
            st.info("📝 Nenhuma transferência encontrada com os filtros selecionados")