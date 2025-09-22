from pickle import FALSE
import streamlit as st
import pandas as pd
import os
from datetime import datetime

def mostrar_edicao():
    """Página principal de edição de dados."""
    st.subheader("✏️ Edição de Dados")
    st.markdown("---")
    
    # Seletor de abas
    aba_selecionada = st.selectbox(
        "Selecione a tabela para editar:",
        ["Movimentação das Contas"],
        key="aba_edicao"
    )
    
    if aba_selecionada == "Movimentação das Contas":
        mostrar_edicao_movimentacao_contas()

def mostrar_edicao_movimentacao_contas():
    """Edição da tabela movimentacao_contas.pkl."""
    st.markdown("### 💰 Edição - Movimentação das Contas")
    st.caption("Edite manualmente os registros de movimentação financeira")
    
    # Carrega dados
    caminho_arquivo = 'data/movimentacao_contas.pkl'
    
    if not os.path.exists(caminho_arquivo):
        st.error("Arquivo movimentacao_contas.pkl não encontrado!")
        return
    
    try:
        df_movimento = pd.read_pickle(caminho_arquivo)
    except Exception as e:
        st.error(f"Erro ao carregar arquivo: {e}")
        return
    
    if df_movimento.empty:
        st.warning("Nenhum dado encontrado no arquivo movimentacao_contas.pkl")
        return
    
    # Botões para selecionar tipo de movimentação
    st.markdown("#### 🔄 Tipo de Movimentação")
    col1, col2 = st.columns(2)
    
    with col1:
        btn_entrada = st.button("📈 Entrada", use_container_width=True, type="primary")
    with col2:
        btn_saida = st.button("📉 Saída", use_container_width=True, type="secondary")
    
    # Determina o tipo selecionado
    tipo_selecionado = None
    if btn_entrada:
        st.session_state.tipo_movimento_edicao = "entrada"
    elif btn_saida:
        st.session_state.tipo_movimento_edicao = "saida"
    
    # Recupera tipo do session_state ou usa padrão
    tipo_selecionado = st.session_state.get('tipo_movimento_edicao', 'entrada')
    
    # Exibe tipo atual
    st.info(f"💡 Exibindo movimentações de: **{tipo_selecionado.upper()}**")
    
    # Filtra dados por tipo
    if tipo_selecionado == "entrada":
        df_filtrado = df_movimento[df_movimento['tipo'] == 'ENTRADA'].copy()
        tipo_emoji = "📈"
    else:
        df_filtrado = df_movimento[df_movimento['tipo'] == 'SAIDA'].copy()
        tipo_emoji = "📉"
    
    if df_filtrado.empty:
        st.warning(f"Nenhuma movimentação de {tipo_selecionado} encontrada.")
        return
    
    # Prepara DataFrame para edição
    colunas_edicao = [
        'data_cadastro', 'categoria_pagamento', 'subcategoria_pagamento', 
        'pago', 'conta', 'descricao', 'observacoes', 'forma_pagamento', 
        'convenio', 'servicos', 'origem'
    ]
    
    # Verifica se todas as colunas existem
    colunas_existentes = [col for col in colunas_edicao if col in df_filtrado.columns]
    
    if not colunas_existentes:
        st.error("Colunas necessárias não encontradas no arquivo!")
        return
    
    df_edicao = df_filtrado[colunas_existentes].copy()
    
    # Converte data_cadastro para string para exibição
    if 'data_cadastro' in df_edicao.columns:
        df_edicao['data_cadastro'] = pd.to_datetime(df_edicao['data_cadastro']).dt.strftime('%d/%m/%Y')
    
    # Preenche valores NaN
    df_edicao = df_edicao.fillna('')
    
    st.markdown(f"#### {tipo_emoji} Dados de {tipo_selecionado.title()}")
    st.markdown(f"**Total de registros:** {len(df_edicao)}")
    
    # Editor de dados
    df_editado = st.data_editor(
        df_edicao,
        column_config={
            'data_cadastro': st.column_config.TextColumn(
                'Data',
                disabled=True,
                width='small',
                help="Data do cadastro (não editável)"
            ),
            'categoria_pagamento': st.column_config.TextColumn(
                'Categoria',
                width='small',
                help="Categoria do pagamento"
            ),
            'subcategoria_pagamento': st.column_config.TextColumn(
                'Subcategoria',
                width='small',
                help="Subcategoria do pagamento"
            ),
            'pago': st.column_config.NumberColumn(
                'Valor',
                format="%.2f",
                width='small',
                help="Valor pago"
            ),
            'conta': st.column_config.TextColumn(
                'Conta',
                width='medium',
                help="Conta de destino"
            ),
            'descricao': st.column_config.TextColumn(
                'Descrição',
                width='medium',
                help="Descrição da movimentação"
            ),
            'observacoes': st.column_config.TextColumn(
                'Observações',
                width='medium',
                help="Observações adicionais"
            ),
            'forma_pagamento': st.column_config.TextColumn(
                'Forma Pagamento',
                width='medium',
                help="Forma de pagamento utilizada"
            ),
            'convenio': st.column_config.TextColumn(
                'Convênio',
                width='small',
                help="Convênio relacionado"
            ),
            'servicos': st.column_config.TextColumn(
                'Serviços',
                width='medium',
                help="Serviços prestados"
            ),
            'origem': st.column_config.TextColumn(
                'Origem',
                width='small',
                help="Origem da movimentação"
            )
        },
        disabled=['data_cadastro'],
        hide_index=True,
        use_container_width=False,
        height=500,
        key=f"editor_movimento_{tipo_selecionado}"
    )
    
    # Botões de ação
    st.markdown("---")
    col_save, col_export, col_info = st.columns([1, 1, 2])
    
    with col_save:
        if st.button("💾 Salvar Alterações", type="primary", use_container_width=True):
            salvar_alteracoes_movimento(df_editado, df_movimento, df_filtrado, tipo_selecionado)
    
    with col_export:
        if st.button("📊 Exportar Excel", type="secondary", use_container_width=True):
            exportar_movimento_excel(df_editado, tipo_selecionado)
    
    with col_info:
        st.info("💡 As alterações só serão aplicadas após clicar em 'Salvar Alterações'")

def salvar_alteracoes_movimento(df_editado, df_original, df_filtrado_original, tipo_movimento):
    """Salva as alterações feitas na tabela de movimentação."""
    try:
        # Restaura a data_cadastro para formato datetime
        df_editado_copy = df_editado.copy()
        if 'data_cadastro' in df_editado_copy.columns:
            df_editado_copy['data_cadastro'] = pd.to_datetime(df_editado_copy['data_cadastro'], format='%d/%m/%Y')
        
        # Identifica registros alterados comparando com o original
        indices_originais = df_filtrado_original.index
        
        if len(df_editado_copy) != len(indices_originais):
            st.error("Erro: Número de linhas alterado durante a edição!")
            return
        
        # Atualiza o DataFrame original com as alterações
        df_atualizado = df_original.copy()
        
        for i, idx_original in enumerate(indices_originais):
            for coluna in df_editado_copy.columns:
                if coluna in df_atualizado.columns:
                    df_atualizado.loc[idx_original, coluna] = df_editado_copy.iloc[i][coluna]
        
        # Adiciona timestamp de edição
        df_atualizado.loc[indices_originais, 'data_ultima_edicao'] = datetime.now()
        
        # Salva arquivo
        os.makedirs('data', exist_ok=True)
        df_atualizado.to_pickle('data/movimentacao_contas.pkl')
        
        st.success(f"✅ {len(df_editado_copy)} registros de {tipo_movimento} salvos com sucesso!")
        
        # Força rerun para atualizar os dados
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erro ao salvar alterações: {str(e)}")

def exportar_movimento_excel(df_editado, tipo_movimento):
    """Exporta os dados editados para Excel."""
    try:
        from io import BytesIO
        
        # Prepara dados para Excel
        df_excel = df_editado.copy()
        
        # Converte valores numéricos
        if 'pago' in df_excel.columns:
            df_excel['pago'] = pd.to_numeric(df_excel['pago'], errors='coerce').fillna(0)
        
        # Cria buffer
        buffer = BytesIO()
        
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_excel.to_excel(
                writer, 
                sheet_name=f'Movimento_{tipo_movimento.title()}',
                index=False
            )
        
        # Gera nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"movimentacao_{tipo_movimento}_{timestamp}.xlsx"
        
        st.download_button(
            label="⬇️ Baixar Excel",
            data=buffer.getvalue(),
            file_name=nome_arquivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"❌ Erro ao exportar Excel: {str(e)}")

# Função principal para ser chamada no main.py
def main():
    mostrar_edicao()

if __name__ == "__main__":
    main()