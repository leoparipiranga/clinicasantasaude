import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- Funções de Cálculo Atualizadas ---
def calcular_taxa_bandeira(valor_bruto, bandeira, parcelas=1, modalidade=None):
    """Estima a taxa da operadora com base na bandeira e no número de parcelas.
    Se modalidade for 'debito' (opcional), aplica taxa de débito."""
    b = (bandeira or "").strip().lower()
    is_debito = modalidade and modalidade.strip().lower().startswith('deb')
    
    # Taxas por bandeira (valores em %)
    if is_debito:
        taxas_debito = {'visa': 1.10, 'mastercard': 1.12, 'elo': 1.85}
        taxa = taxas_debito.get(b, 1.10)
        return valor_bruto * (taxa / 100)
    
    if b == 'visa':
        if parcelas == 1:
            taxa = 2.09
        elif 2 <= parcelas <= 6:
            taxa = 1.98
        else:  # 7-12 e acima
            taxa = 2.20
    elif b in ('mastercard', 'master card', 'master-card'):
        if parcelas == 1:
            taxa = 1.85
        elif 2 <= parcelas <= 6:
            taxa = 2.04
        else:
            taxa = 2.20
    elif b == 'elo':
        if parcelas == 1:
            taxa = 2.55
        elif 2 <= parcelas <= 6:
            taxa = 2.78
        else:
            taxa = 2.94
    elif b in ('amex', 'american express', 'americanexpress'):
        if parcelas == 1:
            taxa = 3.30
        elif 2 <= parcelas <= 6:
            taxa = 3.46
        else:
            taxa = 3.70
    else:
        # Fallback genérico
        if parcelas == 1:
            taxa = 2.00
        elif 2 <= parcelas <= 6:
            taxa = 2.00
        else:
            taxa = 2.00
    
    return valor_bruto * (taxa / 100)

def calcular_antecipacao_banco(
    valores_parcelas: list[float],
    taxa_antecipacao_mes: float,
    data_venda: date,
    datas_vencimento: list[date] = None
) -> dict:
    """
    Calcula a antecipação exatamente como o banco faz,
    com a opção de fornecer datas específicas de vencimento.
    Regra aplicada: primeira parcela = data_venda + 31 dias;
    parcelas subsequentes = primeira parcela + n meses (mantém o dia da 1ª parcela,
    ajustando automaticamente para último dia do mês quando necessário).
    """
    numero_parcelas = len(valores_parcelas)
    valor_liquido_pos_taxa = sum(valores_parcelas)
    
    # Antecipação no dia seguinte
    data_antecipacao = data_venda + timedelta(days=1)
    
    # Taxa diária (usando 30 dias)
    taxa_antecipacao_dia = (taxa_antecipacao_mes / 100) / 30
    
    total_desconto_antecipacao = 0.0
    parcelas_detalhe = []
    
    primeira_venc = None
    for i, valor_parcela_atual in enumerate(valores_parcelas, 1):
        # Usa datas fornecidas se existirem
        if datas_vencimento and len(datas_vencimento) >= i:
            vencimento_parcela = datas_vencimento[i-1]
        else:
            # Regra 2: primeira = data_venda + 31 dias; subsequentes = primeira + (i-1) meses
            if i == 1:
                primeira_venc = data_venda + timedelta(days=31)
                vencimento_parcela = primeira_venc
            else:
                # garante que usamos a primeira_venc como referência
                if primeira_venc is None:
                    primeira_venc = data_venda + timedelta(days=31)
                vencimento_parcela = primeira_venc + relativedelta(months=(i-1))
        
        # Calcula dias para antecipação (INCLUINDO o dia da antecipação)
        dias_para_antecipar = (vencimento_parcela - data_antecipacao).days
        
        # Aplica a fórmula do banco
        desconto_parcela = 0.0
        if dias_para_antecipar > 0:
            desconto_parcela = valor_parcela_atual * taxa_antecipacao_dia * dias_para_antecipar
        
        total_desconto_antecipacao += desconto_parcela
        
        parcelas_detalhe.append({
            "parcela": i,
            "vencimento": vencimento_parcela.strftime('%d/%m/%Y'),
            "valor_liquido": round(valor_parcela_atual, 2),
            "dias_antecipacao": dias_para_antecipar,
            "desconto": round(desconto_parcela, 2)
        })
    
    valor_liquido_final = valor_liquido_pos_taxa - total_desconto_antecipacao
    
    return {
        "valor_liquido_pos_taxa": round(valor_liquido_pos_taxa, 2),
        "total_desconto_antecipacao": round(total_desconto_antecipacao, 2),
        "valor_liquido_recebido": round(valor_liquido_final, 2),
        "detalhe_parcelas": parcelas_detalhe,
        "prazo_medio": calcular_prazo_medio(parcelas_detalhe)
    }

def calcular_prazo_medio(parcelas_detalhe):
    """Calcula o prazo médio baseado nas parcelas."""
    if not parcelas_detalhe:
        return 0
    
    soma_dias_ponderados = sum(p["dias_antecipacao"] for p in parcelas_detalhe)
    return round(soma_dias_ponderados / len(parcelas_detalhe))

def encontrar_taxa_real(desconto_real, valores_parcelas, data_venda, datas_vencimento=None):
    """Encontra a taxa real que gera exatamente o desconto esperado."""
    taxa_inicial = 2.80  # Começamos próximo à taxa descoberta
    passo = 0.0001
    melhor_taxa = taxa_inicial
    menor_diferenca = float('inf')
    
    # Busca refinada em torno da taxa inicial
    for i in range(-100, 101):
        taxa_teste = taxa_inicial + (i * passo)
        resultado = calcular_antecipacao_banco(
            valores_parcelas=valores_parcelas,
            taxa_antecipacao_mes=taxa_teste,
            data_venda=data_venda,
            datas_vencimento=datas_vencimento
        )
        
        diferenca = abs(desconto_real - resultado["total_desconto_antecipacao"])
        
        if diferenca < menor_diferenca:
            menor_diferenca = diferenca
            melhor_taxa = taxa_teste
            
            if round(diferenca, 4) == 0:
                break
                
    return melhor_taxa

def calcular_antecipacao_agrupada(vendas_dia, data_venda, taxa_antecipacao_mes=2.81):
    """
    Calcula antecipação agrupando vendas por bandeira e data de vencimento,
    simulando exatamente como o banco faz.
    
    vendas_dia: lista de dicts com 'bandeira', 'valor_liquido', 'parcelas'
    """
    # Agrupa vendas por bandeira e data de vencimento
    grupos = {}
    
    for venda in vendas_dia:
        bandeira = venda['bandeira']
        valor_liquido = venda['valor_liquido']
        parcelas = venda['parcelas']
        
        # Calcula datas de vencimento para esta venda
        for i in range(parcelas):
            if i == 0:
                data_venc = data_venda + timedelta(days=31)
            else:
                primeira_venc = data_venda + timedelta(days=31)
                data_venc = primeira_venc + relativedelta(months=i)
            
            chave = f"{bandeira}_{data_venc.strftime('%Y%m%d')}"
            
            if chave not in grupos:
                grupos[chave] = {
                    'bandeira': bandeira,
                    'data_vencimento': data_venc,
                    'valor_total': 0.0,
                    'vendas': []
                }
            
            valor_parcela = valor_liquido / parcelas
            grupos[chave]['valor_total'] += valor_parcela
            grupos[chave]['vendas'].append({
                'valor_parcela': valor_parcela,
                'parcela': i + 1,
                'total_parcelas': parcelas
            })
    
    # Calcula antecipação para cada grupo
    data_antecipacao = data_venda + timedelta(days=1)
    taxa_diaria = (taxa_antecipacao_mes / 100) / 30
    
    total_desconto = 0.0
    detalhes_grupos = []
    
    for chave, grupo in grupos.items():
        dias_antecipacao = (grupo['data_vencimento'] - data_antecipacao).days
        desconto_grupo = grupo['valor_total'] * taxa_diaria * dias_antecipacao
        total_desconto += desconto_grupo
        
        detalhes_grupos.append({
            'bandeira': grupo['bandeira'],
            'data_vencimento': grupo['data_vencimento'].strftime('%d/%m/%Y'),
            'valor_grupo': round(grupo['valor_total'], 2),
            'dias_antecipacao': dias_antecipacao,
            'desconto': round(desconto_grupo, 2)
        })
    
    return {
        'total_desconto': round(total_desconto, 2),
        'detalhes_grupos': detalhes_grupos
    }

# --- Interface Streamlit ---
st.set_page_config(page_title="Calculadora de Antecipação v2", page_icon="💳", layout="wide")
st.title("💳 Calculadora de Antecipação de Cartão v2")
st.markdown("Simule ou valide descontos de antecipação de cartão com precisão.")

tab1, tab2 = st.tabs(["📊 Simulador", "🔍 Validador de Extrato"])

with tab1:
    st.subheader("Simulação de Nova Venda")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        data_venda = st.date_input("Data da Venda", value=date.today())
        valor_bruto = st.number_input("Valor Bruto (R$)", value=100.00, min_value=0.01, format="%.2f")
    
    with col2:
        bandeira = st.selectbox("Bandeira", ["Visa", "MasterCard", "Outra"])
        parcelas = st.number_input("Número de Parcelas", min_value=1, max_value=12, value=1)
    
    with col3:
        taxa_antecipacao = st.number_input("Taxa de Antecipação (%/mês)", value=2.80, format="%.4f")
        taxa_estimada = round(calcular_taxa_bandeira(valor_bruto, bandeira, parcelas), 2)
        st.metric("Taxa Estimada da Operadora", f"R$ {taxa_estimada:.2f}", help="Estimativa baseada nos dados analisados")

    if st.button("Simular Antecipação", type="primary", use_container_width=True):
        # Cálculos
        valor_liquido = valor_bruto - taxa_estimada
        valor_parcela = round(valor_liquido / parcelas, 2)
        
        # Ajuste para centavos
        valores_parcelas = [valor_parcela] * parcelas
        diferenca = round(valor_liquido - sum(valores_parcelas), 2)
        
        # Distribui a diferença de centavos
        for i in range(int(abs(diferenca) * 100)):
            valores_parcelas[i] += 0.01 if diferenca > 0 else -0.01
        
        # Calcula antecipação
        resultado = calcular_antecipacao_banco(
            valores_parcelas=valores_parcelas,
            taxa_antecipacao_mes=taxa_antecipacao,
            data_venda=data_venda
        )
        
        # Apresenta resultados
        st.success("Simulação concluída com sucesso!")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Valor Bruto", f"R$ {valor_bruto:.2f}")
            st.metric("Taxa da Operadora", f"R$ {taxa_estimada:.2f} ({(taxa_estimada/valor_bruto*100):.2f}%)")
            st.metric("Valor Líquido", f"R$ {valor_liquido:.2f}")
            
        with col2:
            st.metric("Desconto Antecipação", f"R$ {resultado['total_desconto_antecipacao']:.2f}")
            st.metric("Valor Após Antecipação", f"R$ {resultado['valor_liquido_recebido']:.2f}")
            st.metric("Prazo Médio", f"{resultado['prazo_medio']} dias")
            
        with col3:
            st.metric("Desconto Total", f"R$ {(taxa_estimada + resultado['total_desconto_antecipacao']):.2f}")
            st.metric("% sobre Valor Bruto", f"{((taxa_estimada + resultado['total_desconto_antecipacao'])/valor_bruto*100):.2f}%")
        
        st.markdown("### Detalhamento das Parcelas")
        df_parcelas = pd.DataFrame(resultado["detalhe_parcelas"])
        st.dataframe(df_parcelas, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Validação de Extrato")
    
    col1, col2 = st.columns(2)
    
    with col1:
        data_venda_val = st.date_input("Data da Venda", key="val_data", value=date.today() - timedelta(days=1))
        desconto_esperado = st.number_input("Desconto da Antecipação (R$)", key="val_desconto", format="%.2f")
        parcelas_val = st.number_input("Número de Parcelas", key="val_parcelas", min_value=1, max_value=12, value=1)
        
    with col2:
        usar_datas_especificas = st.checkbox("Usar Datas Específicas de Vencimento")
        taxa_sugerida = st.number_input("Taxa de Antecipação Sugerida (%/mês)", value=2.80, format="%.4f")
    
    # Seção dinâmica para parcelas
    st.markdown("### Valores das Parcelas")
    
    valores_parcelas_val = []
    datas_vencimento_val = []
    
    # Cria até 3 colunas para as parcelas
    max_cols = 3
    rows = (parcelas_val + max_cols - 1) // max_cols
    
    for row in range(rows):
        cols = st.columns(max_cols)
        for col_idx in range(max_cols):
            parcela_idx = row * max_cols + col_idx
            if parcela_idx < parcelas_val:
                with cols[col_idx]:
                    valor = st.number_input(f"Valor Parcela {parcela_idx+1} (R$)", key=f"val_p_{parcela_idx}", format="%.2f")
                    valores_parcelas_val.append(valor)
                    
                    if usar_datas_especificas:
                        data_venc = st.date_input(f"Vencimento Parcela {parcela_idx+1}", key=f"val_d_{parcela_idx}",
                                               value=data_venda_val + relativedelta(months=parcela_idx+1))
                        datas_vencimento_val.append(data_venc)
    
    if not usar_datas_especificas:
        datas_vencimento_val = None
        
    if st.button("Validar Desconto", type="primary", use_container_width=True):
        if all(p > 0 for p in valores_parcelas_val):
            with st.spinner("Calculando..."):
                # Calcula com a taxa sugerida
                resultado_sugerido = calcular_antecipacao_banco(
                    valores_parcelas=valores_parcelas_val, 
                    taxa_antecipacao_mes=taxa_sugerida,
                    data_venda=data_venda_val,
                    datas_vencimento=datas_vencimento_val
                )
                
                # Encontra a taxa real
                taxa_real = encontrar_taxa_real(
                    desconto_real=desconto_esperado,
                    valores_parcelas=valores_parcelas_val,
                    data_venda=data_venda_val,
                    datas_vencimento=datas_vencimento_val
                )
                
                # Calcula com a taxa real
                resultado_real = calcular_antecipacao_banco(
                    valores_parcelas=valores_parcelas_val,
                    taxa_antecipacao_mes=taxa_real,
                    data_venda=data_venda_val,
                    datas_vencimento=datas_vencimento_val
                )
                
                # Mostra resultados
                st.markdown("### Resultados da Validação")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Usando Taxa Sugerida (2,80%)**")
                    st.metric("Desconto Calculado", f"R$ {resultado_sugerido['total_desconto_antecipacao']:.2f}")
                    st.metric("Valor Líquido", f"R$ {resultado_sugerido['valor_liquido_recebido']:.2f}")
                    st.metric("Diferença", f"R$ {resultado_sugerido['total_desconto_antecipacao'] - desconto_esperado:.2f}")
                    
                with col2:
                    st.markdown("**Usando Taxa Real Encontrada**")
                    st.metric("Taxa Real", f"{taxa_real:.4f}%")
                    st.metric("Desconto Calculado", f"R$ {resultado_real['total_desconto_antecipacao']:.2f}")
                    st.metric("Valor Líquido", f"R$ {resultado_real['valor_liquido_recebido']:.2f}")
                
                if abs(resultado_real['total_desconto_antecipacao'] - desconto_esperado) < 0.01:
                    st.success("✅ Taxa real encontrada! Os valores batem perfeitamente.")
                else:
                    st.warning("⚠️ Não foi possível encontrar uma taxa que gere exatamente o desconto esperado.")
                
                st.markdown("### Detalhamento das Parcelas")
                df_parcelas = pd.DataFrame(resultado_real["detalhe_parcelas"])
                st.dataframe(df_parcelas, use_container_width=True, hide_index=True)
        else:
            st.error("Todas as parcelas precisam ter valores maiores que zero.")
    
    # Adicione esta seção no final da aba tab2 (Validador)
with st.expander("🔍 Análise de Vendas Agrupadas"):
    st.markdown("### Simulação de Múltiplas Vendas no Mesmo Dia")
    st.info("Simula como o banco agrupa vendas por bandeira e data de vencimento")
    
    data_vendas_grupo = st.date_input("Data das Vendas", key="grupo_data", value=date(2025, 9, 8))
    taxa_grupo = st.number_input("Taxa de Antecipação (%/mês)", key="grupo_taxa", value=2.81, format="%.2f")
    
    # Interface para adicionar vendas
    num_vendas = st.number_input("Número de Vendas", min_value=1, max_value=10, value=4, key="num_vendas")
    
    vendas = []
    for i in range(num_vendas):
        col1, col2, col3 = st.columns(3)
        with col1:
            bandeira = st.selectbox(f"Bandeira Venda {i+1}", ["Visa", "Mastercard"], key=f"bandeira_{i}")
        with col2:
            valor_liquido = st.number_input(f"Valor Líquido {i+1}", value=0.0, format="%.2f", key=f"valor_{i}")
        with col3:
            parcelas = st.number_input(f"Parcelas {i+1}", min_value=1, max_value=12, value=1, key=f"parcelas_{i}")
        
        if valor_liquido > 0:
            vendas.append({
                'bandeira': bandeira,
                'valor_liquido': valor_liquido,
                'parcelas': parcelas
            })
    
    if st.button("Calcular Antecipação Agrupada", key="calc_grupo"):
        if vendas:
            resultado = calcular_antecipacao_agrupada(vendas, data_vendas_grupo, taxa_grupo)
            
            st.success(f"Desconto Total Calculado: R$ {resultado['total_desconto']:.2f}")
            
            st.markdown("### Detalhamento por Grupo")
            df_grupos = pd.DataFrame(resultado['detalhes_grupos'])
            st.dataframe(df_grupos, use_container_width=True, hide_index=True)
            
            # Valores do seu exemplo
            st.markdown("### Comparação com seu exemplo:")
            st.write("Valor esperado: R$ 9,84")
            st.write(f"Valor calculado: R$ {resultado['total_desconto']:.2f}")
            st.write(f"Diferença: R$ {abs(9.84 - resultado['total_desconto']):.2f}")
        else:
            st.warning("Adicione pelo menos uma venda com valor maior que zero")