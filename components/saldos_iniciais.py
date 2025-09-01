import pandas as pd
import os
from datetime import datetime

# --- CONFIGURE AQUI OS SALDOS INICIAIS ---
saldos_iniciais = {
    "SANTANDER": -3178.08,
    "BANESE": 0.33,
    "C6": 11.36,
    "CAIXA": 0,
    "BNB": 0.00,
    "MERCADO PAGO": 0,
    "CONTA PIX": -10091.82,
    "DINHEIRO": 260.86,
}
# -----------------------------------------

def definir_saldos():
    """
    Cria registros de 'SALDO INICIAL' no arquivo de movimentações.
    Grava valores negativos na coluna 'pago' para débitos.
    """
    caminho_arquivo = 'data/movimentacao_contas.pkl'
    data_saldo_inicial = datetime(2025, 1, 1)

    if os.path.exists(caminho_arquivo):
        df = pd.read_pickle(caminho_arquivo)
        if not df[df['descricao'] == 'SALDO INICIAL'].empty:
            print("❌ Erro: Saldos iniciais já parecem ter sido definidos. Abortando.")
            return
    else:
        df = pd.DataFrame()

    novas_entradas = []
    for conta, valor in saldos_iniciais.items():
        if valor == 0:
            continue

        # Define o tipo com base no sinal do valor
        tipo_mov = 'ENTRADA' if valor > 0 else 'SAIDA'
        
        # O valor a ser registrado é o próprio valor do saldo inicial
        valor_registro = float(valor)

        print(f"✔️ Preparando saldo inicial para {conta}: R$ {valor_registro:,.2f} (Tipo: {tipo_mov})")

        registro = {
            'data_cadastro': data_saldo_inicial,
            'tipo': tipo_mov,
            'categoria_pagamento': 'SALDO INICIAL',
            'subcategoria_pagamento': 'AJUSTE',
            'pago': valor_registro,  # Grava o valor com seu sinal original
            'conta': conta,
            'descricao': 'SALDO INICIAL',
            'observacoes': f'Definição de saldo inicial para a conta {conta}.',
            'id_transferencia': None,
            'paciente': None, 'medico': None, 'forma_pagamento': None, 
            'convenio': None, 'servicos': None, 'origem': 'SISTEMA'
        }
        novas_entradas.append(registro)

    if novas_entradas:
        df_novas = pd.DataFrame(novas_entradas)
        df_final = pd.concat([df, df_novas], ignore_index=True)
        
        # Apaga o arquivo antigo antes de salvar o novo para garantir a limpeza
        if os.path.exists(caminho_arquivo):
            os.remove(caminho_arquivo)
        df_final.to_pickle(caminho_arquivo)
        
        print("\n✅ Saldos iniciais registrados com sucesso!")
    else:
        print("⚠️ Nenhum saldo inicial para registrar.")

if __name__ == "__main__":
    confirmacao = input("Você tem certeza que deseja APAGAR os dados antigos e definir os saldos iniciais? (s/n): ")
    if confirmacao.lower() == 's':
        # Antes de rodar, apague o arquivo movimentacao_contas.pkl para garantir
        # que não haja saldos antigos.
        caminho_mov = 'data/movimentacao_contas.pkl'
        if os.path.exists(caminho_mov):
            print(f"Apagando arquivo antigo: {caminho_mov}")
            os.remove(caminho_mov)
        
        definir_saldos()
    else:
        print("Operação cancelada.")