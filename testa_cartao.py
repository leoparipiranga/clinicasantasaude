import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# Colunas alvo (nomes canônicos esperados)
COLS_DETALHADO_ORIGINAIS = [
    'DATA DE VENCIMENTO','TIPO DE LANÇAMENTO','LANÇAMENTO','VALOR LÍQUIDO','VALOR LIQUIDADO',
    'DATA DA VENDA','HORA DA VENDA','VALOR DA VENDA','PARCELAS','VALOR DA PARCELA',
    'DESCONTOS','VALOR LIQUIDO DA PARCELA'
]
COLS_MONETARIAS = [
    'VALOR LÍQUIDO','VALOR LIQUIDADO','VALOR DA VENDA','VALOR DA PARCELA',
    'DESCONTOS','VALOR LIQUIDO DA PARCELA'
]

def _clean_text(v):
    return re.sub(r'\s+', ' ', str(v).strip()).upper()

def _converter_moeda_serie(s: pd.Series) -> pd.Series:
    """
    Converte valores monetários ignorando separadores e depois divide por 100
    para corrigir casos onde a vírgula decimal foi ignorada na leitura.
    Ex: '70,00' -> 7000 -> 7000/100 = 70.00
    """
    cleaned = (s.astype(str)
                 .str.replace(r'\s+', '', regex=True)
                 .str.replace('R$', '', regex=False)
                 .str.replace('.', '', regex=False)      # remove milhar
                 .str.replace(',', '', regex=False)      # remove vírgula (vai tratar via /100)
                 .str.replace('-', '', regex=False)
                 .str.replace('[^0-9]', '', regex=True)  # garante somente dígitos
                 .replace({'': np.nan, 'nan': np.nan}))
    nums = pd.to_numeric(cleaned, errors='coerce')
    return nums / 100.0   # ajuste final


def _detectar_linha_cabecalho(df_raw: pd.DataFrame, cols_alvo_upper:set):
    """
    Heurística: escolhe a linha que contém o MAIOR número de matches com os nomes alvo.
    """
    melhor_idx = None
    melhor_score = -1
    for i, row in df_raw.iterrows():
        valores = [_clean_text(x) for x in row.tolist()]
        score = sum(1 for v in valores if v in cols_alvo_upper)
        if score > melhor_score:
            melhor_score = score
            melhor_idx = i
    return melhor_idx, melhor_score

def processar_cartao_detalhado(arquivo, debug=False):
    """
    Processa arquivo (aba 'Detalhado') robustamente mesmo se a linha de cabeçalho variar.
    Regras:
      - Ignorar linhas acima do cabeçalho detectado
      - Remover linhas com 'Total Recebido' ou 'TOTAL' na primeira coluna (após cabeçalho)
      - Manter somente colunas esperadas
    """
    try:
        # 1. Lê tudo SEM cabeçalho para detectar
        df_raw = pd.read_excel(arquivo, sheet_name='Detalhado', header=None, dtype=str)
        if debug:
            print("Dimensão df_raw:", df_raw.shape)

        cols_alvo_upper = {_clean_text(c) for c in COLS_DETALHADO_ORIGINAIS}
        header_row_idx, score = _detectar_linha_cabecalho(df_raw, cols_alvo_upper)

        if header_row_idx is None or score == 0:
            return None, "Não foi possível detectar a linha de cabeçalho."

        # 2. Define cabeçalho
        header_values = df_raw.iloc[header_row_idx].tolist()
        header_clean = [_clean_text(c) for c in header_values]

        # 3. Dados = linhas abaixo do cabeçalho
        df = df_raw.iloc[header_row_idx+1:].copy()
        df.columns = header_clean

        # 4. Remove linhas totalmente vazias
        df = df.dropna(how='all')
        if df.empty:
            return None, "Sem dados após o cabeçalho."

        # 5. Filtra linhas 'Total Recebido' / 'TOTAL' na primeira coluna real
        primeira_col_real = df.columns[0]
        df = df[
            ~df[primeira_col_real].astype(str).str.upper().str.contains(r'(TOTAL RECEBIDO|^TOTAL$)', na=False)
        ]

        # 6. Mapeia colunas detectadas para nomes canônicos
        #    (permite pequenas diferenças de espaços / maiúsculas)
        col_map = {}
        df_cols_upper = list(df.columns)
        for alvo in COLS_DETALHADO_ORIGINAIS:
            alvo_norm = _clean_text(alvo)
            match = next((c for c in df_cols_upper if _clean_text(c) == alvo_norm), None)
            if match:
                col_map[match] = alvo  # renomeia para formato canônico

        df = df.rename(columns=col_map)

        # 7. Mantém só colunas desejadas que existem
        cols_existentes = [c for c in COLS_DETALHADO_ORIGINAIS if c in df.columns]
        df = df[cols_existentes].copy()

        # 8. Conversão de datas
        for c in ['DATA DE VENCIMENTO','DATA DA VENDA']:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], dayfirst=True, errors='coerce')

        # 9. Conversão de valores
        for c in COLS_MONETARIAS:
            if c in df.columns:
                df[c] = _converter_moeda_serie(df[c])

        # 10. Limpeza PARCELAS
        if 'PARCELAS' in df.columns:
            df['PARCELAS'] = df['PARCELAS'].astype(str).str.strip()

        # 11. Metadados
        df['origem'] = 'cartao_getnet'   # ajustado conforme solicitação
        df['data_importacao'] = datetime.now()
        df['status'] = 'pendente'

        msg_debug = ""
        if debug:
            msg_debug = (
                f"[DEBUG] Linha cabeçalho detectada: {header_row_idx} (score={score}) | "
                f"Colunas detectadas: {df.columns.tolist()}"
            )

        return df, f"Processado com sucesso: {len(df)} registros. {msg_debug}"
    except Exception as e:
        return None, f"Erro ao processar: {e}"

def show():
    st.header("🧪 Teste - Cartão (Detalhado)")
    st.caption("Importação robusta com detecção automática da linha de cabeçalho.")

    st.markdown("""
    Regras aplicadas:
    1. Detecta automaticamente a linha do cabeçalho (buscando maior número de colunas conhecidas)
    2. Remove linhas 'Total Recebido' ou 'TOTAL' na primeira coluna
    3. Mantém apenas colunas definidas
    4. Converte datas e valores
    """)

    debug = st.checkbox("Modo debug (mostra diagnósticos no topo)")
    arquivo = st.file_uploader("Arquivo XLSX (aba 'Detalhado')", type=['xlsx'])

    if not arquivo:
        st.info("Faça o upload do arquivo para iniciar.")
        return

    if debug:
        st.subheader("Pré-visualização bruta (primeiras 25 linhas)")
        try:
            raw_preview = pd.read_excel(arquivo, sheet_name='Detalhado', header=None, nrows=25, dtype=str)
            st.dataframe(raw_preview, use_container_width=True)
        except Exception as e:
            st.error(f"Erro leitura bruta: {e}")

    if st.button("Processar arquivo", use_container_width=True):
        with st.spinner("Processando..."):
            df, msg = processar_cartao_detalhado(arquivo, debug=debug)
        if df is None:
            st.error(msg)
            return

        st.success(msg)
        st.write("Colunas finais:", df.columns.tolist())
        st.metric("Registros", len(df))

        # Métricas de valores
        metric_cols = [c for c in ['VALOR LÍQUIDO','VALOR LIQUIDADO','VALOR DA VENDA'] if c in df.columns]
        cols = st.columns(len(metric_cols) if metric_cols else 1)
        for i, c in enumerate(metric_cols):
            with cols[i]:
                st.metric(c, f"R$ {df[c].sum():,.2f}")

        st.subheader("Dados Processados")
        st.dataframe(df, use_container_width=True, height=600)

        # Resumos
        if 'TIPO DE LANÇAMENTO' in df.columns:
            st.subheader("Resumo por Tipo de Lançamento")
            resumo = (df.groupby('TIPO DE LANÇAMENTO')
                        .agg(qtd=('LANÇAMENTO','count'))
                        .assign(total_valor_liquido=lambda d: df.groupby('TIPO DE LANÇAMENTO')['VALOR LÍQUIDO'].sum()
                                if 'VALOR LÍQUIDO' in df.columns else np.nan)
                        .reset_index())
            st.dataframe(resumo, use_container_width=True)

        if 'DATA DE VENCIMENTO' in df.columns and 'VALOR LÍQUIDO' in df.columns:
            st.subheader("Série Temporal (Valor Líquido por Data de Vencimento)")
            serie = (df.groupby('DATA DE VENCIMENTO')
                       .agg(total_liquido=('VALOR LÍQUIDO','sum'))
                       .reset_index()
                       .sort_values('DATA DE VENCIMENTO'))
            if not serie.empty:
                st.line_chart(serie.set_index('DATA DE VENCIMENTO'))

        st.download_button(
            "⬇️ Baixar CSV",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name="cartao_detalhado_processado.csv",
            mime="text/csv"
        )

        st.session_state.df_cartao_detalhado = df

    if 'df_cartao_detalhado' in st.session_state:
        df = st.session_state.df_cartao_detalhado
        with st.expander("Validações"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if 'DATA DE VENCIMENTO' in df:
                    st.write("Datas nulas:", df['DATA DE VENCIMENTO'].isna().sum())
            with col2:
                if 'VALOR LÍQUIDO' in df:
                    st.write("Valor Líq nulos:", df['VALOR LÍQUIDO'].isna().sum())
            with col3:
                st.write("Status:", df['status'].unique().tolist())
            with col4:
                st.write("Origem:", df['origem'].unique().tolist())

        if st.button("Limpar sessão"):
            st.session_state.pop('df_cartao_detalhado', None)
            st.rerun()

# Executa quando rodar diretamente
if __name__ == "__main__":
    show()