from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd

def calcular_antecipacao(
    valores_parcelas: list[float],
    taxa_antecipacao_mes: float,
    data_venda: date,
    valor_bruto: float = 0.0
) -> dict:
    """
    Calcula o valor líquido de uma venda após a aplicação da taxa de antecipação,
    usando os valores exatos de cada parcela.
    """
    numero_parcelas = len(valores_parcelas)
    valor_liquido_pos_taxa = sum(valores_parcelas)

    if numero_parcelas <= 1:
        return {"total_desconto_antecipacao": 0.0}

    data_antecipacao = data_venda + timedelta(days=1)
    taxa_antecipacao_dia = (taxa_antecipacao_mes / 100) / 30
    
    total_desconto_antecipacao = 0.0
    parcelas_detalhe = []

    for i, valor_parcela_atual in enumerate(valores_parcelas, 1):
        vencimento_parcela = data_venda + relativedelta(months=i)
        dias_para_antecipar = (vencimento_parcela - data_antecipacao).days
        desconto_parcela = valor_parcela_atual * taxa_antecipacao_dia * dias_para_antecipar if dias_para_antecipar > 0 else 0.0
        total_desconto_antecipacao += desconto_parcela
        
        parcelas_detalhe.append({
            "parcela_n": i,
            "vencimento": vencimento_parcela.strftime('%d/%m/%Y'),
            "valor_liquido_parcela": round(valor_parcela_atual, 2),
            "dias_antecipados": dias_para_antecipar,
            "desconto_antecipacao": round(desconto_parcela, 2)
        })

    valor_liquido_final = valor_liquido_pos_taxa - total_desconto_antecipacao

    return {
        "valor_bruto_venda": valor_bruto,
        "valor_liquido_pos_taxa": round(valor_liquido_pos_taxa, 2),
        "total_desconto_antecipacao": round(total_desconto_antecipacao, 2),
        "valor_liquido_recebido": round(valor_liquido_final, 2),
        "detalhe_parcelas": parcelas_detalhe
    }

def encontrar_taxa_real(desconto_real: float, **kwargs) -> dict:
    """
    Ajusta iterativamente a taxa mensal para encontrar a que corresponde ao desconto real.
    """
    taxa_teste = kwargs["taxa_antecipacao_mes"]
    melhor_taxa = taxa_teste
    menor_diferenca = float('inf')

    # Procura a melhor taxa em um intervalo próximo à taxa informada
    for i in range(-100, 101): # Testa 200 variações
        taxa_atual = taxa_teste + (i * 0.0001)
        kwargs_teste = kwargs.copy()
        kwargs_teste["taxa_antecipacao_mes"] = taxa_atual
        
        resultado_teste = calcular_antecipacao(**kwargs_teste)
        desconto_calculado = resultado_teste["total_desconto_antecipacao"]
        
        diferenca = abs(desconto_real - desconto_calculado)
        
        if diferenca < menor_diferenca:
            menor_diferenca = diferenca
            melhor_taxa = taxa_atual
            # Se encontrarmos a correspondência exata, podemos parar
            if menor_diferenca == 0:
                break
    
    return {"taxa_real_encontrada": melhor_taxa, "diferenca_minima": menor_diferenca}


# --- Exemplo de Uso com os seus dados ---
if __name__ == "__main__":
    venda_exemplo = {
        "valor_bruto": 290.00,
        "valores_parcelas": [56.80, 56.82, 56.82, 56.82, 56.82],
        "taxa_antecipacao_mes": 2.81,
        "data_venda": date(2025, 8, 6)
    }
    desconto_esperado = 24.08

    # 1. Encontra a taxa real que gera o desconto esperado
    resultado_taxa = encontrar_taxa_real(desconto_esperado, **venda_exemplo)
    taxa_encontrada = resultado_taxa['taxa_real_encontrada']
    
    print(f"--- ENGENHARIA REVERSA DA TAXA ---")
    print(f"Taxa informada: {venda_exemplo['taxa_antecipacao_mes']:.4f}%")
    print(f"Taxa real calculada para bater o valor: {taxa_encontrada:.4f}%\n")

    # 2. Roda o cálculo final com a taxa precisa
    venda_exemplo["taxa_antecipacao_mes"] = taxa_encontrada
    resultado_final = calcular_antecipacao(**venda_exemplo)

    print("--- CÁLCULO FINAL COM TAXA AJUSTADA ---")
    print(f"Valor Líquido (pós-taxa): R$ {resultado_final['valor_liquido_pos_taxa']:.2f}")
    print("-" * 60)
    df_detalhes = pd.DataFrame(resultado_final['detalhe_parcelas'])
    print(df_detalhes.to_string(index=False))
    print("-" * 60)
    print(f"TOTAL DESCONTO ANTECIPAÇÃO: R$ {resultado_final['total_desconto_antecipacao']:.2f}")
    print(f"VALOR LÍQUIDO A RECEBER: R$ {resultado_final['valor_liquido_recebido']:.2f}")

    print("\n--- Verificação Final ---")
    print(f"Desconto calculado: {resultado_final['total_desconto_antecipacao']:.2f} | Desconto esperado: {desconto_esperado:.2f}")
    print(f"Líquido calculado: {resultado_final['valor_liquido_recebido']:.2f} | Líquido esperado: 260.00")