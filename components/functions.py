# components/functions.py

import io
import base64
import requests
import streamlit as st
import pandas as pd
from datetime import date

def atualizar_csv_github_df(df, token, repo, path, mensagem, branch="main"):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    content_b64 = base64.b64encode(csv_buffer.getvalue().encode()).decode()
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json()["sha"]
    elif r.status_code == 404:
        sha = None
    else:
        st.error(f"Erro ao obter SHA do arquivo: {r.text}")
        return False
    data = {
        "message": mensagem,
        "content": content_b64,
        "branch": branch
    }
    if sha:
        data["sha"] = sha
    r = requests.put(url, headers=headers, json=data)
    if r.status_code in [200, 201]:
        st.success("Arquivo atualizado no GitHub!")
        return True
    else:
        st.error(f"Erro ao atualizar: {r.text}")
        return False

def salvar_dados(tipo):
    """Função genérica para salvar dados de qualquer tipo (Reforço, Entrada, Saída)"""
    if tipo == "Reforço":
        arquivo = "reforco.csv"
        colunas = ["data", "valor", "centro_custo", "forma_pagamento"]
    elif tipo == "Entrada":
        arquivo = "entrada.csv"
        colunas = ["data", "conta", "detalhe", "banco", "valor"]
    elif tipo == "Saída":
        arquivo = "saida.csv"
        colunas = ["data", "custo", "descricao", "detalhamento", "centro_custo", "forma_pagamento", "banco", "valor"]
    else:
        st.error("Tipo inválido!")
        return False

    # Lê ou cria o arquivo
    url_csv = f"https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/{arquivo}"
    try:
        df_existente = pd.read_csv(url_csv)
    except Exception:
        df_existente = pd.DataFrame(columns=colunas)
    
    # Concatena com os dados temporários
    df_final = pd.concat([df_existente, pd.DataFrame(st.session_state['linhas_temp'])], ignore_index=True)
    
    # Remove linhas com valor zero
    df_final = df_final[df_final['valor'] != 0]
    
    # Salva no GitHub
    sucesso = atualizar_csv_github_df(
        df_final,
        token=st.secrets["github"]["github_token"],
        repo="leoparipiranga/clinicasantasaude",
        path=arquivo,
        mensagem=f"Atualiza {arquivo} via Streamlit"
    )
    
    if sucesso:
        st.session_state['linhas_temp'] = []
    
    return sucesso

def limpar_form_saida():
    st.session_state["data_saida"] = date.today()
    st.session_state["custo_saida"] = "Fixo"
    st.session_state["descricao_saida"] = ""
    st.session_state["detalhamento_saida"] = ""
    st.session_state["centro_saida"] = "Rateio"
    st.session_state["forma_saida"] = "Dinheiro"
    st.session_state["banco_saida"] = "SANTANDER"
    st.session_state["valor_saida"] = 0.0

def registrar_saida():
    nova_linha = {
        "data": st.session_state["data_saida"],
        "custo": st.session_state["custo_saida"],
        "descricao": st.session_state["descricao_saida"],
        "detalhamento": st.session_state["detalhamento_saida"],
        "centro_custo": st.session_state["centro_saida"],
        "forma_pagamento": st.session_state["forma_saida"],
        "banco": st.session_state["banco_saida"],
        "valor": st.session_state["valor_saida"]
    }
    st.session_state['linhas_temp'].append(nova_linha)
    limpar_form_saida()