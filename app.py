import streamlit as st
import pandas as pd
from datetime import date, timedelta
import requests
import base64

def atualizar_csv_github(token, repo, path, mensagem, branch="main"):
    # Lê o arquivo atualizado
    with open(path, "rb") as f:
        content = f.read()
        content_b64 = base64.b64encode(content).decode()

    # Pega o SHA do arquivo atual
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error(f"Erro ao obter SHA do arquivo: {r.text}")
        return False
    sha = r.json()["sha"]

    # Faz o commit
    data = {
        "message": mensagem,
        "content": content_b64,
        "sha": sha,
        "branch": branch
    }
    r = requests.put(url, headers=headers, json=data)
    if r.status_code in [200, 201]:
        st.success("Arquivo atualizado no GitHub!")
        return True
    else:
        st.error(f"Erro ao atualizar: {r.text}")
        return False

hoje = date.today()
data_min_padrao = hoje - timedelta(days=7)
data_max_padrao = hoje

df = pd.read_csv('base_caixa.csv')

st.title("Movimentação de Caixa")

aba = st.tabs(["Inserção", "Alteração Manual","Ver Tabela"])

with aba[0]:
    if 'novas_linhas' not in st.session_state:
        st.session_state['novas_linhas'] = []

    tipos = ["Reforço", "Entrada", "Saída"]
    tipo = st.radio("Tipo", tipos, horizontal=True, key="tipo_input")

    centros = df[df['Tipo'] == tipo]['CentroCusto'].dropna().unique().tolist()
    if centros:
        centro_padrao = centros[0]
    else:
        centro_padrao = ""

    detalhes = df[(df['Tipo'] == tipo) & (df['CentroCusto'] == centro_padrao)]['Detalhe'].dropna().unique().tolist()

    # Centro de Custo e Detalhe na mesma linha
    col1, col2 = st.columns(2)
    with col1:
        centro_custo = st.selectbox("Centro de Custo", centros, key="centro_input")
    with col2:
        detalhes = df[(df['Tipo'] == tipo) & (df['CentroCusto'] == centro_custo)]['Detalhe'].dropna().unique().tolist()
        detalhe = st.selectbox("Detalhe", detalhes, key="detalhe_input")

    # Banco depende do detalhe
    if detalhe != "Dinheiro":
        bancos = df[
            (df['Tipo'] == tipo) &
            (df['CentroCusto'] == centro_custo) &
            (df['Detalhe'] == detalhe)
        ]['Banco'].dropna().unique().tolist()
        banco = st.selectbox("Banco", bancos, key="banco_input")
    else:
        banco = ""

    # Data e Valor na mesma linha
    col3, col4 = st.columns(2)
    with col3:
        data = st.date_input("Data", value=date.today(), key="data_input")
    with col4:
        valor = st.number_input("Valor", step=0.01, format="%.2f", key="valor_input")

    def registrar_callback():
        nova_linha = {
            "Data": st.session_state["data_input"],
            "Tipo": st.session_state["tipo_input"],
            "CentroCusto": st.session_state["centro_input"],
            "Detalhe": st.session_state["detalhe_input"],
            "Banco": st.session_state["banco_input"] if "banco_input" in st.session_state else "",
            "Valor": st.session_state["valor_input"]
        }
        st.session_state['novas_linhas'].append(nova_linha)
        st.session_state["data_input"] = date.today()
        st.session_state["valor_input"] = 0.0
        st.session_state["tipo_input"] = tipos[0]
        st.session_state["centro_input"] = centros[0] if centros else ""
        st.session_state["detalhe_input"] = detalhes[0] if detalhes else ""
        if "banco_input" in st.session_state and bancos:
            st.session_state["banco_input"] = bancos[0]

    def limpar_callback():
        st.session_state['novas_linhas'] = []
        st.session_state["data_input"] = date.today()
        st.session_state["valor_input"] = 0.0
        st.session_state["tipo_input"] = tipos[0]
        st.session_state["centro_input"] = centros[0] if centros else ""
        st.session_state["detalhe_input"] = detalhes[0] if detalhes else ""
        if "banco_input" in st.session_state and bancos:
            st.session_state["banco_input"] = bancos[0]

    def salvar_callback():
        if st.session_state['novas_linhas']:
            novas_df = pd.DataFrame(st.session_state['novas_linhas'])
            df_final = pd.concat([df, novas_df], ignore_index=True)
            df_final.to_csv('base_caixa.csv', index=False)
            qtd = len(st.session_state['novas_linhas'])
            st.session_state['novas_linhas'] = []
            st.success(f"{qtd} novas linhas inseridas.")

            # Atualiza o arquivo no GitHub
            atualizar_csv_github(
            token=st.secrets["github_token"],
            repo="leoparipiranga/clinicasantasaude",
            path="base_caixa.csv",
            mensagem="Atualiza base_caixa.csv via Streamlit"
            )

    # Botões juntos na mesma linha
    colb1, colb2, colb3 = st.columns([1,1,1])
    with colb1:
        st.button("Registrar", on_click=registrar_callback)
    with colb2:
        st.button("Salvar", on_click=salvar_callback, disabled=len(st.session_state['novas_linhas']) == 0)
    with colb3:
        st.button("Limpar Edição", on_click=limpar_callback, disabled=len(st.session_state['novas_linhas']) == 0)

    # Mostrar linhas registradas
    if st.session_state['novas_linhas']:
        st.subheader("Linhas a serem inseridas:")
        st.dataframe(pd.DataFrame(st.session_state['novas_linhas']), use_container_width=True, hide_index=True)
    pass

with aba[1]:
    col1, col2 = st.columns(2)
    with col1:
        data_ini = st.date_input(
            "Data inicial",
            value=data_min_padrao,
            min_value=pd.to_datetime(df['Data']).min().date(),
            max_value=pd.to_datetime(df['Data']).max().date()
        )
    with col2:
        data_fim = st.date_input(
            "Data final",
            value=data_max_padrao,
            min_value=pd.to_datetime(df['Data']).min().date(),
            max_value=pd.to_datetime(df['Data']).max().date()
        )

    # Filtrar DataFrame pelo período
    df['Data'] = pd.to_datetime(df['Data']).dt.date
    mask = (df['Data'] >= data_ini) & (df['Data'] <= data_fim)
    df_periodo = df[mask].copy()

    # Após editar:
    editado = st.data_editor(
        df_periodo.reset_index(drop=True),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor"
    )

    if st.button("Salvar Alterações"):
        # Se existir a coluna _deleted, filtra as linhas não excluídas
        if "_deleted" in editado.columns:
            editado = editado[~editado["_deleted"]].drop(columns=["_deleted"])
        # Remove as linhas do período selecionado do DataFrame original
        df_restante = df[~mask]
        # Junta as linhas editadas de volta
        df_final = pd.concat([df_restante, editado], ignore_index=True)
        # Ordena por data, se desejar
        df_final = df_final.sort_values(by="Data")
        df_final.to_csv('base_caixa.csv', index=False)
        st.success("Alterações salvas com sucesso!")
        # Atualiza o arquivo no GitHub
        atualizar_csv_github(
            token=st.secrets["github_token"],
            repo="leoparipiranga/clinicasantasaude",
            path="base_caixa.csv",
            mensagem="Atualiza base_caixa.csv via Streamlit"
        )

with aba[2]:

    df['Data'] = pd.to_datetime(df['Data']).dt.date

    # Filtros de data
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        data_ini = st.date_input("Data inicial", value=st.session_state.get('vis_data_ini', data_min_padrao), key="vis_data_ini")
    with fcol2:
        data_fim = st.date_input("Data final", value=st.session_state.get('vis_data_fim', data_max_padrao), key="vis_data_fim")

    # Filtros dinâmicos em cascata
    tipos_disp = sorted(df[(df['Data'] >= data_ini) & (df['Data'] <= data_fim)]['Tipo'].dropna().unique().tolist())
   
    # Linha 1: Tipo e Centro de Custo
    col1, col2 = st.columns(2)
    with col1:
        tipo_filtro = st.selectbox("Tipo", ["Todos"] + tipos_disp, key="vis_tipo2")
    with col2:
        if tipo_filtro != "Todos":
            df_tipo = df[(df['Data'] >= data_ini) & (df['Data'] <= data_fim) & (df['Tipo'] == tipo_filtro)]
        else:
            df_tipo = df[(df['Data'] >= data_ini) & (df['Data'] <= data_fim)]
        centros_disp = sorted(df_tipo['CentroCusto'].dropna().unique().tolist())
        centro_filtro = st.selectbox("Centro de Custo", ["Todos"] + centros_disp, key="vis_centro")

    # Atualizar df_tipo se tipo_filtro mudou na linha 1
    if tipo_filtro != "Todos":
        df_tipo = df[(df['Data'] >= data_ini) & (df['Data'] <= data_fim) & (df['Tipo'] == tipo_filtro)]
    else:
        df_tipo = df[(df['Data'] >= data_ini) & (df['Data'] <= data_fim)]

    if centro_filtro != "Todos":
        df_centro = df_tipo[df_tipo['CentroCusto'] == centro_filtro]
    else:
        df_centro = df_tipo
    detalhes_disp = sorted(df_centro['Detalhe'].dropna().unique().tolist())

    # Linha 2: Detalhe e Banco
    col3, col4 = st.columns(2)
    with col3:
        detalhe_filtro = st.selectbox("Detalhe", ["Todos"] + detalhes_disp, key="vis_detalhe")
    with col4:
        if detalhe_filtro != "Todos":
            df_detalhe = df_centro[df_centro['Detalhe'] == detalhe_filtro]
        else:
            df_detalhe = df_centro
        bancos_disp = sorted(df_detalhe['Banco'].dropna().unique().tolist())
        banco_filtro = st.selectbox("Banco", ["Todos"] + bancos_disp, key="vis_banco")

    # Botão para limpar filtros
    if st.button("Limpar Filtros"):
        for k in ["vis_data_ini", "vis_data_fim", "vis_tipo2", "vis_centro", "vis_detalhe", "vis_banco"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    # Aplicar filtros finais
    df_filtrado = df[
        (df['Data'] >= data_ini) & (df['Data'] <= data_fim)
        & ((df['Tipo'] == tipo_filtro) if tipo_filtro != "Todos" else True)
        & ((df['CentroCusto'] == centro_filtro) if centro_filtro != "Todos" else True)
        & ((df['Detalhe'] == detalhe_filtro) if detalhe_filtro != "Todos" else True)
        & ((df['Banco'] == banco_filtro) if banco_filtro != "Todos" else True)
    ].copy()

    df_filtrado = df_filtrado[df_filtrado['Valor'] > 0]

    # Resumo acima da tabela
    num_linhas = len(df_filtrado)
    total = df_filtrado['Valor'].sum()
    st.markdown(
        f"<div style='font-size:1.2em; font-weight:bold;'>{num_linhas} Linhas filtradas  -  Total: R$ {total:,.2f}</div>",
        unsafe_allow_html=True
    )

    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)