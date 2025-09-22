import streamlit as st
import pandas as pd
from datetime import date
from calculo_cartao import calcular_antecipacao, encontrar_taxa_real

# --- Configuração da Página ---
st.set_page_config(
    page_title="Calculadora de Antecipação",
    page_icon="🧮",
    layout="wide"
)

st.title("🧮 Calculadora e Verificadora de Antecipação de Cartão")
st.markdown("Use esta ferramenta para validar os descontos de antecipação do seu extrato de cartão.")

# --- Layout da Aplicação ---
col1, col2 = st.columns([1, 2])

with col1:
    st.header("📥 Dados da Venda")
    
    data_venda = st.date_input("Data da Venda", value=date.today())
    valor_bruto = st.number_input("Valor Bruto da Venda (R$)", min_value=0.0, format="%.2f")
    taxa_antecipacao_mes = st.number_input("Taxa de Antecipação ao Mês (%)", min_value=0.0, format="%.4f", help="A taxa informada pela operadora. Ex: 2.81")
    desconto_esperado = st.number_input("Desconto da Antecipação (do extrato em R$)", min_value=0.0, format="%.2f", help="O valor exato do desconto que consta no seu extrato.")
    
    st.markdown("---")
    
    num_parcelas = st.number_input("Nº de Parcelas", min_value=1, max_value=36, value=1)
    
    # Inputs dinâmicos para o valor de cada parcela
    valores_parcelas = []
    if num_parcelas > 0:
        st.markdown("**Valor Líquido de Cada Parcela (R$)**")
        for i in range(num_parcelas):
            valor = st.number_input(f"Parcela {i+1}", key=f"p_{i}", min_value=0.0, format="%.2f")
            valores_parcelas.append(valor)

# Botão para iniciar o cálculo
calcular = st.button("🔄 Calcular e Verificar", use_container_width=True, type="primary")

with col2:
    st.header("📊 Resultados do Cálculo")
    
    if calcular:
        # Validações
        if not all(p > 0 for p in valores_parcelas):
            st.error("Por favor, preencha o valor líquido de todas as parcelas.")
        elif desconto_esperado == 0:
            st.warning("O 'Desconto da Antecipação' está zerado. A engenharia reversa da taxa não será precisa.")
        else:
            with st.spinner("Calculando..."):
                # Monta os dados para as funções
                venda_dados = {
                    "valor_bruto": valor_bruto,
                    "valores_parcelas": valores_parcelas,
                    "taxa_antecipacao_mes": taxa_antecipacao_mes,
                    "data_venda": data_venda
                }

                # 1. Encontra a taxa real que gera o desconto esperado
                resultado_taxa = encontrar_taxa_real(desconto_esperado, **venda_dados)
                taxa_encontrada = resultado_taxa['taxa_real_encontrada']
                
                st.subheader("⚙️ Engenharia Reversa da Taxa")
                tax_col1, tax_col2 = st.columns(2)
                tax_col1.metric("Taxa Informada", f"{taxa_antecipacao_mes:.4f}%")
                tax_col2.metric("Taxa Real Calculada", f"{taxa_encontrada:.4f}%", help="Esta é a taxa que efetivamente gera o desconto informado no extrato.")

                # 2. Roda o cálculo final com a taxa precisa
                venda_dados["taxa_antecipacao_mes"] = taxa_encontrada
                resultado_final = calcular_antecipacao(**venda_dados)

                st.subheader("✅ Cálculo Final com Taxa Ajustada")
                
                # Mostra o resumo
                res_col1, res_col2, res_col3 = st.columns(3)
                res_col1.metric("Valor Líquido (Pós-Taxa)", f"R$ {resultado_final['valor_liquido_pos_taxa']:.2f}")
                res_col2.metric("Desconto Antecipação", f"R$ {resultado_final['total_desconto_antecipacao']:.2f}")
                res_col3.metric("Valor Líquido a Receber", f"R$ {resultado_final['valor_liquido_recebido']:.2f}")
                
                st.markdown("---")
                
                # Mostra o detalhamento das parcelas
                st.markdown("**Detalhamento das Parcelas**")
                df_detalhes = pd.DataFrame(resultado_final['detalhe_parcelas'])
                st.dataframe(df_detalhes, use_container_width=True, hide_index=True)

                # Verificação final
                st.subheader("🎯 Verificação Final")
                ver_col1, ver_col2 = st.columns(2)
                ver_col1.metric(
                    "Desconto Calculado vs. Extrato",
                    f"R$ {resultado_final['total_desconto_antecipacao']:.2f}",
                    f"R$ {desconto_esperado - resultado_final['total_desconto_antecipacao']:.2f} de diferença"
                )
                
                valor_liquido_esperado = resultado_final['valor_liquido_pos_taxa'] - desconto_esperado
                ver_col2.metric(
                    "Líquido Calculado vs. Esperado",
                    f"R$ {resultado_final['valor_liquido_recebido']:.2f}",
                    f"R$ {resultado_final['valor_liquido_recebido'] - valor_liquido_esperado:.2f} de diferença"
                )
                
                if abs(resultado_final['total_desconto_antecipacao'] - desconto_esperado) < 0.01:
                    st.success("✔️ Os valores batem perfeitamente!")
                else:
                    st.warning("⚠️ Os valores calculados estão próximos, mas há uma pequena diferença. Verifique os dados de entrada.")

    else:
        st.info("Preencha os dados da venda à esquerda e clique em 'Calcular e Verificar'.")