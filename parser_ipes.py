import re
import pdfplumber
import pandas as pd
import streamlit as st
from datetime import datetime
import os
import tempfile

st.set_page_config(
    page_title="Debug Parser IPES",
    page_icon="🔍",
    layout="wide"
)

def normalize_line(s: str) -> str:
    """Normaliza linha removendo espaços extras"""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()

# Regex para identificar linhas de procedimento (aceita 8 ou 9 dígitos; garante que não esteja dentro de número maior)
RX_PROCEDIMENTO = re.compile(
    r'^\s*\d+\s+\d{2}\s+(?<!\d)(\d{8,9})(?!\d)\s*-\s*(.+?)(?:\s+\d+\s+\d+\s+\d+|\s+R\$|\s+\$)',
    re.I
)

def extrair_procedimento_da_linha(linha: str):
    """
    Extrai código e descrição do procedimento de uma linha.
    Formato esperado: seq tabela CODIGO - DESCRICAO - Categoria qtde...
    """
    linha_norm = normalize_line(linha)
    
    def extrair_descricao_por_caixa(descricao_bruta: str) -> str:
        # procura primeiro caractere alfabético minúsculo
        idx_lower = None
        for i, ch in enumerate(descricao_bruta):
            if ch.isalpha() and ch.islower():
                idx_lower = i
                break
        if idx_lower is not None:
            # recua até o último " - " antes do primeiro lowercase
            pos_sep = descricao_bruta.rfind(' - ', 0, idx_lower)
            if pos_sep != -1:
                desc = descricao_bruta[:pos_sep].strip()
            else:
                # fallback: pega a parte antes do primeiro " - " se existir
                desc = descricao_bruta.split(' - ')[0].strip()
        else:
            # sem minúsculas: pega a parte até o primeiro " - " ou toda a string
            desc = descricao_bruta.split(' - ')[0].strip()
        # remove espaços redundantes e trims finais de pontuação indesejada
        desc = re.sub(r'\s+', ' ', desc).strip()
        desc = re.sub(r'[\s\-\–_:]+$', '', desc).strip()
        return desc

    # Tenta match com regex principal
    match = RX_PROCEDIMENTO.match(linha_norm)
    if match:
        codigo = match.group(1)
        descricao_bruta = match.group(2).strip()
        
        descricao_limpa = extrair_descricao_por_caixa(descricao_bruta)
        
        return {
            'codigo_procedimento': codigo,
            'descricao_procedimento': descricao_limpa,
            'linha_original': linha_norm
        }
    
    # Tentativa alternativa para linhas quebradas ou mal formatadas
    # Match alternativo exige que os 8/9 dígitos não façam parte de um número maior
    match_alt = re.search(r'(?<!\d)(\d{8,9})(?!\d)\s*-\s*([^-]+)', linha_norm)
    if match_alt:
        codigo = match_alt.group(1)
        descricao_bruta = match_alt.group(2).strip()
        
        descricao_limpa = extrair_descricao_por_caixa(descricao_bruta)
        
        return {
            'codigo_procedimento': codigo,
            'descricao_procedimento': descricao_limpa,
            'linha_original': linha_norm
        }
    
    return None

def extrair_procedimentos_pdf(pdf_path: str):
    """
    Extrai apenas códigos e descrições de procedimentos do PDF IPES
    """
    procedimentos = []
    linhas_falha = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for pidx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            buffer = ""
            
            for raw_line in text.splitlines():
                linha = normalize_line(raw_line)
                
                # Se linha começa com número (possível início de procedimento)
                if re.match(r'^\s*\d+\s+\d{2}\s+\d+', linha):
                    # Processa buffer anterior se existir
                    if buffer.strip():
                        resultado = extrair_procedimento_da_linha(buffer)
                        if resultado:
                            resultado['pagina'] = pidx
                            procedimentos.append(resultado)
                        else:
                            linhas_falha.append({'pagina': pidx, 'linha': buffer})
                    
                    # Inicia novo buffer
                    buffer = linha
                
                # Se tem buffer ativo, continua acumulando
                elif buffer:
                    buffer = buffer + " " + linha
                    
                    # Se linha parece terminar (tem R$ ou $), processa
                    if re.search(r'R\$|(?<!\w)\$', linha):
                        resultado = extrair_procedimento_da_linha(buffer)
                        if resultado:
                            resultado['pagina'] = pidx
                            procedimentos.append(resultado)
                        else:
                            linhas_falha.append({'pagina': pidx, 'linha': buffer})
                        buffer = ""
                
                # Linha independente com código de procedimento
                elif re.search(r'\d{8}\s*-', linha):
                    resultado = extrair_procedimento_da_linha(linha)
                    if resultado:
                        resultado['pagina'] = pidx
                        procedimentos.append(resultado)
                    else:
                        linhas_falha.append({'pagina': pidx, 'linha': linha})
            
            # Processa buffer final da página
            if buffer.strip():
                resultado = extrair_procedimento_da_linha(buffer)
                if resultado:
                    resultado['pagina'] = pidx
                    procedimentos.append(resultado)
                else:
                    linhas_falha.append({'pagina': pidx, 'linha': buffer})
    
    df_procedimentos = pd.DataFrame(procedimentos)
    df_falhas = pd.DataFrame(linhas_falha)
    
    # Remove duplicatas baseado no código
    if not df_procedimentos.empty:
        df_procedimentos = df_procedimentos.drop_duplicates(subset=['codigo_procedimento'], keep='first')
        df_procedimentos = df_procedimentos.sort_values('codigo_procedimento').reset_index(drop=True)
    
    return df_procedimentos, df_falhas

def mostrar_debug_parser_ipes():
    """
    Interface Streamlit para debug do parser de procedimentos IPES
    """
    st.title("🔍 Debug Parser IPES - Códigos e Descrições")
    st.caption("Ferramenta para extrair e validar códigos de procedimentos dos relatórios IPES")
    
    # Upload do arquivo
    uploaded_file = st.file_uploader(
        "Selecione o arquivo PDF do relatório IPES:",
        type=['pdf'],
        help="Faça upload do relatório IPES em formato PDF"
    )
    
    if uploaded_file is not None:
        # Salva arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        try:
            # Botão para processar
            if st.button("🚀 Extrair Procedimentos", type="primary"):
                with st.spinner("Processando PDF..."):
                    df_procedimentos, df_falhas = extrair_procedimentos_pdf(tmp_path)
                
                # Resultados
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("✅ Procedimentos Extraídos", len(df_procedimentos))
                
                with col2:
                    st.metric("❌ Linhas com Falha", len(df_falhas))
                
                # Mostra procedimentos extraídos
                if not df_procedimentos.empty:
                    st.success(f"🎉 Extraídos {len(df_procedimentos)} procedimentos únicos!")
                    
                    # Filtro de busca
                    st.markdown("---")
                    col_busca, col_export = st.columns([3, 1])
                    
                    with col_busca:
                        filtro = st.text_input(
                            "🔍 Filtrar por código ou descrição:",
                            placeholder="Digite para filtrar..."
                        )
                    
                    # Aplica filtro
                    df_display = df_procedimentos.copy()
                    if filtro:
                        mask = (
                            df_display['codigo_procedimento'].str.contains(filtro, case=False, na=False) |
                            df_display['descricao_procedimento'].str.contains(filtro, case=False, na=False)
                        )
                        df_display = df_display[mask]
                    
                    # Tabela principal
                    st.dataframe(
                        df_display[['codigo_procedimento', 'descricao_procedimento', 'pagina']],
                        column_config={
                            'codigo_procedimento': st.column_config.TextColumn('Código', width='small'),
                            'descricao_procedimento': st.column_config.TextColumn('Descrição', width='large'),
                            'pagina': st.column_config.NumberColumn('Página', width='small')
                        },
                        hide_index=True,
                        use_container_width=True,
                        height=400
                    )
                    
                    # Botão de export
                    with col_export:
                        # Prepara CSV para download
                        csv = df_procedimentos.to_csv(index=False, encoding='utf-8-sig')
                        st.download_button(
                            label="📥 Baixar CSV",
                            data=csv,
                            file_name=f"procedimentos_ipes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    
                    # Seção de estatísticas
                    st.markdown("---")
                    st.markdown("#### 📊 Estatísticas")
                    
                    col_stats1, col_stats2, col_stats3 = st.columns(3)
                    
                    with col_stats1:
                        codigos_unicos = df_procedimentos['codigo_procedimento'].nunique()
                        st.metric("Códigos Únicos", codigos_unicos)
                    
                    with col_stats2:
                        desc_mais_longa = df_procedimentos['descricao_procedimento'].str.len().max()
                        st.metric("Maior Descrição", f"{desc_mais_longa} chars")
                    
                    with col_stats3:
                        paginas_processadas = df_procedimentos['pagina'].nunique()
                        st.metric("Páginas Processadas", paginas_processadas)
                    
                    # Procedimentos mais comuns
                    if len(df_procedimentos) > 0:
                        st.markdown("#### 🔝 Procedimentos por Página")
                        proc_por_pagina = df_procedimentos.groupby('pagina').size().reset_index(name='quantidade')
                        st.bar_chart(proc_por_pagina.set_index('pagina'))
                
                # Mostra falhas se houver
                if not df_falhas.empty:
                    st.markdown("---")
                    st.warning(f"⚠️ {len(df_falhas)} linhas não puderam ser processadas")
                    
                    with st.expander("🔍 Ver Linhas com Falha", expanded=False):
                        st.dataframe(
                            df_falhas,
                            column_config={
                                'pagina': st.column_config.NumberColumn('Página', width='small'),
                                'linha': st.column_config.TextColumn('Linha Original', width='large')
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                
                # Seção de debugging
                st.markdown("---")
                st.markdown("#### 🛠️ Debug - Linhas Originais")
                
                if not df_procedimentos.empty:
                    with st.expander("🔍 Ver Linhas Originais Processadas", expanded=False):
                        debug_df = df_procedimentos[['codigo_procedimento', 'descricao_procedimento', 'linha_original', 'pagina']].copy()
                        st.dataframe(
                            debug_df,
                            column_config={
                                'codigo_procedimento': st.column_config.TextColumn('Código', width='small'),
                                'descricao_procedimento': st.column_config.TextColumn('Descrição', width='medium'),
                                'linha_original': st.column_config.TextColumn('Linha Original', width='large'),
                                'pagina': st.column_config.NumberColumn('Pág', width='tiny')
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                
                # Teste de regex em tempo real
                st.markdown("---")
                st.markdown("#### 🧪 Teste de Regex")
                
                linha_teste = st.text_input(
                    "Digite uma linha para testar o parser:",
                    placeholder="Ex: 4 00 40301630 - CREATININA - Exames de Patologia Clínica 1 1 1 01/08/2025 R$ 4,35"
                )
                
                if linha_teste:
                    resultado_teste = extrair_procedimento_da_linha(linha_teste)
                    if resultado_teste:
                        st.success("✅ Linha processada com sucesso!")
                        col_cod, col_desc = st.columns(2)
                        with col_cod:
                            st.code(f"Código: {resultado_teste['codigo_procedimento']}")
                        with col_desc:
                            st.code(f"Descrição: {resultado_teste['descricao_procedimento']}")
                    else:
                        st.error("❌ Não foi possível extrair dados desta linha")
                        
                        # Mostra patterns encontrados para debug
                        st.markdown("**Debug da linha:**")
                        if re.search(r'\d{8}', linha_teste):
                            st.info(f"✅ Código de 8 dígitos encontrado: {re.search(r'(\d{8})', linha_teste).group(1)}")
                        else:
                            st.warning("❌ Código de 8 dígitos não encontrado")
                        
                        if '-' in linha_teste:
                            st.info("✅ Hífen encontrado")
                        else:
                            st.warning("❌ Hífen não encontrado")
        
        finally:
            # Remove arquivo temporário
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    else:
        st.info("📤 Faça upload de um arquivo PDF para começar a extração")

# Função para usar em outros módulos
def obter_procedimentos_ipes_pdf(uploaded_file):
    """
    Função utilitária para extrair procedimentos de um PDF uploadado
    Retorna DataFrame com códigos e descrições
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        df_procedimentos, df_falhas = extrair_procedimentos_pdf(tmp_path)
        
        os.unlink(tmp_path)
        
        return df_procedimentos, df_falhas, None
        
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

# Chama a função principal do debug
mostrar_debug_parser_ipes()
