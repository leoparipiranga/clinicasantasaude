# components/functions.py

import io
import base64
import requests
import streamlit as st
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

def limpar_form_saida():
    st.session_state["data_saida"] = date.today()
    st.session_state["custo_saida"] = "Fixo"
    st.session_state["descricao_saida"] = ""
    st.session_state["detalhamento_saida"] = ""
    st.session_state["centro_saida"] = "Rateio"
    st.session_state["forma_saida"] = "Dinheiro"
    st.session_state["banco_saida"] = "SANTANDER"
    st.session_state["valor_saida"] = 0.0

def salvar_form_saida(descricoes_dict):
    import pandas as pd
    from datetime import date
    import streamlit as st

    url_csv = "https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/saida.csv"
    try:
        df_saida = pd.read_csv(url_csv)
    except Exception:
        df_saida = pd.DataFrame(columns=[
            "data", "custo", "descricao", "detalhamento", "centro_custo",
            "forma_pagamento", "banco", "valor"
        ])
    df_final = pd.concat([df_saida, pd.DataFrame(st.session_state['linhas_temp'])], ignore_index=True)
    from components.functions import atualizar_csv_github_df  # Importa aqui para evitar import circular
    atualizar_csv_github_df(
        df_final,
        token=st.secrets["github_token"],
        repo="leoparipiranga/clinicasantasaude",
        path="saida.csv",
        mensagem="Atualiza saida.csv via Streamlit"
    )
    st.session_state['linhas_temp'] = []
    # Limpa os campos do formulário
    st.session_state["data_saida"] = date.today()
    st.session_state["custo_saida"] = "Fixo"
    st.session_state["descricao_saida"] = ""  # ou a primeira opção de descricoes_dict["Fixo"]
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
    # Limpa o formulário
    st.session_state["data_saida"] = date.today()
    st.session_state["custo_saida"] = "Fixo"
    st.session_state["descricao_saida"] = ""
    st.session_state["detalhamento_saida"] = ""
    st.session_state["centro_saida"] = "Rateio"
    st.session_state["forma_saida"] = "Dinheiro"
    st.session_state["banco_saida"] = "SANTANDER"
    st.session_state["valor_saida"] = 0.0