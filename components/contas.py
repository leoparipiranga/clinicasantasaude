"""
Módulo centralizado para gestão de contas bancárias e saldos.
"""
import pandas as pd
import os

# Lista oficial de contas do sistema
CONTAS_SISTEMA = [
    "DINHEIRO", 
    "SANTANDER", 
    "BANESE", 
    "C6",
    "CAIXA", 
    "BNB", 
    "MERCADO PAGO", 
    "CONTA PIX"
]

def obter_lista_contas():
    """Retorna a lista oficial de contas do sistema."""
    return CONTAS_SISTEMA.copy()

def calcular_saldos():
    """Calcula os saldos atuais a partir do arquivo de movimentação já tratado."""
    
    try:
        df = pd.read_pickle('data/movimentacao_contas.pkl')
    except FileNotFoundError:
        return {conta: 0 for conta in CONTAS_SISTEMA}
    
    # Agrupa diretamente pela coluna 'conta'
    saldos_atuais = df.groupby('conta')['pago'].sum().to_dict()
    
    # Garante que todas as contas existam no dicionário
    for conta in CONTAS_SISTEMA:
        if conta not in saldos_atuais:
            saldos_atuais[conta] = 0
    
    return saldos_atuais

def obter_saldo_conta(nome_conta):
    """Retorna o saldo de uma conta específica."""
    saldos = calcular_saldos()
    return saldos.get(nome_conta, 0)

def validar_conta(nome_conta):
    """Verifica se o nome da conta é válido."""
    return nome_conta in CONTAS_SISTEMA