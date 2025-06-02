import streamlit as st
import pandas as pd
from datetime import date
import io
import base64
import requests
from components.functions import atualizar_csv_github_df, limpar_form_saida, salvar_form_saida, registrar_saida

url_csv_reforco = "https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/reforco.csv"
df_reforco = pd.read_csv(url_csv_reforco)
url_csv_entrada = "https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/entrada.csv"
df_entrada = pd.read_csv(url_csv_entrada)
url_csv_saida = "https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/saida.csv"
df_saida = pd.read_csv(url_csv_saida)

hoje = date.today()
data_min_padrao = hoje.replace(day=1)
data_max_padrao = hoje

st.title("Movimentação de Caixa")

aba = st.tabs(["Inserção", "Alteração Manual","Ver Tabela"])

with aba[0]:
    tipos = ["Reforço", "Entrada", "Saída"]
    tipo = st.radio("Tipo", tipos, horizontal=True, key="tipo_input")

    # Inicializa o DataFrame temporário para cada tipo
    if 'linhas_temp' not in st.session_state or st.session_state.get('tipo_temp') != tipo:
        st.session_state['linhas_temp'] = []
        st.session_state['tipo_temp'] = tipo

    # --- REFORÇO ---
    if tipo == "Reforço":
        col1, col2 = st.columns(2)
        with col1:
            data = st.date_input("Data", value=date.today(), key="data_input_reforco")
        with col2:
            valor = st.number_input("Valor", step=0.01, format="%.2f", key="valor_input_reforco")

        if st.button("Registrar"):
            nova_linha = {
                "data": data,
                "valor": valor,
                "centro_custo": "Rateio",
                "forma_pagamento": "Dinheiro"
            }
            st.session_state['linhas_temp'].append(nova_linha)
            st.rerun()

        # Mostra linhas registradas e permite edição/exclusão
        if st.session_state['linhas_temp']:
            df_temp = pd.DataFrame(st.session_state['linhas_temp'])
            editado = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True, hide_index=True, key="editor_reforco")
            st.session_state['linhas_temp'] = editado.to_dict('records')
            if st.button("Salvar"):
                df_final = pd.concat([df_reforco, pd.DataFrame(st.session_state['linhas_temp'])], ignore_index=True)
                atualizar_csv_github_df(
                    df_final,
                    token=st.secrets["github_token"],
                    repo="leoparipiranga/clinicasantasaude",
                    path="reforco.csv",
                    mensagem="Atualiza reforco.csv via Streamlit"
                )
                st.session_state['linhas_temp'] = []
                st.rerun()

    # --- ENTRADA ---
    elif tipo == "Entrada":
        contas = ["Clinica", "Laboratorio", "Convenios"]
        bancos_convenio = {
            "SESI": "Santander",
            "GEAP": "C6",
            "SUS": "C6",
            "IPES": "Banese"
        }
        col1, col2, col3 = st.columns(3)
        with col1:
            conta = st.selectbox("Conta", contas, key="conta_input")
        if conta == "Convenios":
            detalhes = ["SUS", "SESI", "IPES", "GEAP"]
        else:
            # Pegue detalhes do DataFrame para Clinica/Laboratorio
            detalhes = df_entrada[df_entrada['conta'] == conta]['detalhe'].dropna().unique().tolist()
        with col2:
            detalhe = st.selectbox("Detalhe", detalhes, key="detalhe_input_entrada")
        with col3:
            if conta == "Convenios":
                banco = bancos_convenio.get(detalhe, "")
                st.selectbox("Banco", [banco], key="banco_input_entrada", disabled=True)
            else:
                bancos = df_entrada[(df_entrada['conta'] == conta) & (df_entrada['detalhe'] == detalhe)]['banco'].dropna().unique().tolist()
                if bancos:
                    banco = st.selectbox("Banco", bancos, key="banco_input_entrada")
                else:
                    banco = ""
        col4, col5 = st.columns(2)
        with col4:
            data = st.date_input("Data", value=date.today(), key="data_input_entrada")
        with col5:
            valor = st.number_input("Valor", step=0.01, format="%.2f", key="valor_input_entrada")

        if st.button("Registrar"):
            nova_linha = {
                "data": data,
                "conta": conta,
                "detalhe": detalhe,
                "banco": banco,
                "valor": valor
            }
            st.session_state['linhas_temp'].append(nova_linha)
            st.rerun()

        if st.session_state['linhas_temp']:
            df_temp = pd.DataFrame(st.session_state['linhas_temp'])
            editado = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True, hide_index=True, key="editor_entrada")
            st.session_state['linhas_temp'] = editado.to_dict('records')
            if st.button("Salvar"):
                df_final = pd.concat([df_entrada, pd.DataFrame(st.session_state['linhas_temp'])], ignore_index=True)
                atualizar_csv_github_df(
                    df_final,
                    token=st.secrets["github_token"],
                    repo="leoparipiranga/clinicasantasaude",
                    path="entrada.csv",
                    mensagem="Atualiza entrada.csv via Streamlit"
                )
                st.session_state['linhas_temp'] = []
                st.rerun()
        
    elif tipo == "Saída":
        # Opções de cada campo
        custos = [
            "Fixo", "Variável", "Laboratórios", "Recursos Humanos", "Tributos",
            "Empréstimos", "Investimentos", "Comissões"
        ]
        descricoes_dict = {
            "Fixo": sorted([
                "ALUGUEL", "ACESSO NET", "BRISA NET", "CONTABILIDADE", "ALLDOC", "TERMOCLAVE", "PONTO +",
                "MAYELLE", "MIDIA INDOOR", "MARKETING ACERTE", "COPYGRAF", "ASSINATURA FRETE",
                "WORKLAB (MENSALIDADES)", "SISTEMA IA WHATSAPP", "JURÍDICO", "CDL",
                "JOSELITO - COMISSÃO RT", "OUTROS CUSTOS FIXOS"
            ]),
            "Variável": sorted([
                "MANUTENÇÃO - PREDIO E EQUIPAMENTOS", "FARMAC", "CARTAO SANTANDER (8149)", "SULGIPE",
                "CARTÃO MERCADO PAGO", "CARTAO SANTANDER (0986)", "CARTAO PORTO SEGURO",
                "MATERIAL DE ESCRITÓRIO", "MATERIAL DE LIMPEZA E COPA", "CONSULTORIA (SETE ELOS)",
                "TECNICO DE SEGURANÇA DO TRABALHO", "SEGURO YLM", "TRAFEGO PAGO",
                "ALMOÇO E GASTOS DIVERSOS E MOTO TAXI", "SAAE", "OUTROS CUSTOS VARIÁVEIS"
            ]),
            "Laboratórios": sorted([
                "CLIMEDI", "ÁLVARO (LAUDOS)", "SOLIM", "SODRETOX", "ÁLVARO 1", "ÁLVARO 2", "ÁLVARO 3", "ÁLVARO 4"
            ]),
            "Recursos Humanos": [
                "FOLHA DE PAGAMENTO", "IFOOD BENEFICIOS", "DÉCIMO TERCEIRO", "FERIAS", "VALE TRANSPORTE",
                "PLANO ODONTOLOGICO", "RESCISÃO"
            ],
            "Tributos": [
                "SIMPLES (PARCELAMENTO)", "FGTS", "FGTS ATRASADO ( funcionarios que saíram)", "INSS",
                "INSS PARCELAMENTO", "SIMPLES", "DAM", "IPTU", "TAXAS (JUROS DE CHEQUE ESPECIAL)",
                "TAXAS CARTÕES", "TAXA DE MANUTENCAO DE CONTA (SANTANDER)", "SOC BRAS DE ANALISE (PNCQ)",
                "CRM", "CRBM (PARCELAMETO)", "CRBM"
            ],
            "Empréstimos": [
                "EMPRÉSTIMO BNB REFORMA", "EMPRÉSTIMO BNB ULTRASSOM"
            ],
            "Investimentos": [
                "CARTÃO SANDRO", "CARTÃO JULIO", "EMPRESTIMO SANDRO 1", "MENTORIA X5",
                "FINANCIAMENTO PLACA SOLAR", "ROSE", "EMPRESTIMO SANTANDER", "ESTORNO / TROCO", "ELETROCARDIOGRAMA"
            ],
            "Comissões": [
                "COMISSÃO VIVIANE", "COMISSÃO JOANA", "COMISSÕES MÉDICAS"
            ]
        }
        centros_custo = ["Rateio", "Clínica", "Laboratório"]
        formas_pagamento = ["Dinheiro", "Pix", "Débito", "Crédito"]
        bancos = ["SANTANDER", "BANESE", "C6", "CAIXA", "BNB", "MULVI", "MERCADO PAGO", "CONTA JÚLIO"]

        if "data_saida" not in st.session_state:
            st.session_state["data_saida"] = date.today()
        if "custo_saida" not in st.session_state:
            st.session_state["custo_saida"] = "Fixo"
        if "descricao_saida" not in st.session_state:
            st.session_state["descricao_saida"] = ""
        if "detalhamento_saida" not in st.session_state:
            st.session_state["detalhamento_saida"] = ""
        if "centro_saida" not in st.session_state:
            st.session_state["centro_saida"] = "Rateio"
        if "forma_saida" not in st.session_state:
            st.session_state["forma_saida"] = "Dinheiro"
        if "banco_saida" not in st.session_state:
            st.session_state["banco_saida"] = "SANTANDER"
        if "valor_saida" not in st.session_state:
            st.session_state["valor_saida"] = 0.0

        col1, col2 = st.columns(2)
        with col1:
            custo = st.selectbox("Custo", custos, key="custo_saida")
        with col2:
            descricao = st.selectbox("Descrição", descricoes_dict[custo], key="descricao_saida")
        detalhamento = st.text_input("Detalhamento", key="detalhamento_saida")
        col3, col4 = st.columns(2)
        with col3:
            centro_custo = st.selectbox("Centro de Custo", centros_custo, key="centro_saida")
        with col4:
            forma_pagamento = st.selectbox("Forma de Pagamento", formas_pagamento, key="forma_saida")
        banco = st.selectbox("Banco", bancos, key="banco_saida")
        col5, col6 = st.columns(2)
        with col5:
            data = st.date_input("Data", key="data_saida")
        with col6:
            valor = st.number_input("Valor", step=0.01, format="%.2f", key="valor_saida")

        st.button("Registrar", on_click=registrar_saida)
            
        if st.session_state['linhas_temp']:
            df_temp = pd.DataFrame(st.session_state['linhas_temp'])
            editado = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True, hide_index=True, key="editor_saida")
            st.session_state['linhas_temp'] = editado.to_dict('records')
            if st.button("Salvar", on_click=lambda: salvar_form_saida(descricoes_dict)):
                pass
                
with aba[1]:
    tipos = ["Reforço", "Entrada", "Saída"]
    tipo = st.radio("Tipo", tipos, horizontal=True, key="tipo_alteracao")

    # Escolhe o arquivo e as colunas conforme o tipo
    if tipo == "Reforço":
        url_csv = "https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/reforco.csv"
        col_data = "data"
    elif tipo == "Entrada":
        url_csv = "https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/entrada.csv"
        col_data = "data"
    else:
        url_csv = "https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/saida.csv"
        col_data = "data"

    try:
        df = pd.read_csv(url_csv)
    except Exception:
        st.warning("Arquivo ainda não existe ou está vazio.")
        df = pd.DataFrame()

    if not df.empty:
        df[col_data] = pd.to_datetime(df[col_data]).dt.date
        data_min = df[col_data].min()
        data_max = date.today()
        value_ini = max(data_min, data_min_padrao)
        value_fim = min(data_max, data_max_padrao)
        col1, col2 = st.columns(2)
        with col1:
            data_ini = st.date_input(
                "Data inicial",
                value=value_ini,
                min_value=data_min,
                max_value=data_max,
                key="alt_data_ini"
            )
        with col2:
            data_fim = st.date_input(
                "Data final",
                value=value_ini,
                min_value=data_min,
                max_value=data_max,
                key="alt_data_fim"
            )

        mask = (df[col_data] >= data_ini) & (df[col_data] <= data_fim)
        df_periodo = df[mask].copy()

        editado = st.data_editor(
            df_periodo.reset_index(drop=True),
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=f"editor_{tipo.lower()}"
        )

        if st.button("Salvar Alterações"):
            if "_deleted" in editado.columns:
                editado = editado[~editado["_deleted"]].drop(columns=["_deleted"])
            df_restante = df[~mask]
            df_final = pd.concat([df_restante, editado], ignore_index=True)
            df_final = df_final.sort_values(by=col_data)
            atualizar_csv_github_df(
                df_final,
                token=st.secrets["github_token"],
                repo="leoparipiranga/clinicasantasaude",
                path=f"{tipo.lower()}.csv",
                mensagem=f"Atualiza {tipo.lower()}.csv via Streamlit"
            )
            st.success("Alterações salvas com sucesso!")
    else:
        st.info("Nenhum dado disponível para alteração.")

with aba[2]:
    st.subheader("Visualização de Tabelas")
    tabelas = {
        "Reforço": {
            "url": "https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/reforco.csv",
            "colunas": ["data", "valor", "centro_custo", "forma_pagamento"]
        },
        "Entrada": {
            "url": "https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/entrada.csv",
            "colunas": ["data", "conta", "detalhe", "banco", "valor"]
        },
        "Saída": {
            "url": "https://raw.githubusercontent.com/leoparipiranga/clinicasantasaude/main/saida.csv",
            "colunas": ["data", "custo", "descricao", "detalhamento", "centro_custo", "forma_pagamento", "banco", "valor"]
        }
    }
    tabela_sel = st.radio("Tabela", list(tabelas.keys()), horizontal=True, key="vis_tabela")
    url_csv = tabelas[tabela_sel]["url"]
    colunas = tabelas[tabela_sel]["colunas"]

    try:
        df = pd.read_csv(url_csv)
    except Exception:
        st.warning("Arquivo ainda não existe ou está vazio.")
        df = pd.DataFrame(columns=colunas)

    if not df.empty:
        df['data'] = pd.to_datetime(df['data']).dt.date
        data_min = df['data'].min()
        data_max = df['data'].max()
    else:
        data_min = data_max = date.today()

    # Garante que os valores padrão estão dentro do intervalo permitido
    value_ini = min(max(data_min, data_min_padrao), data_max)
    value_fim = max(min(data_max, data_max_padrao), data_min)

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        data_ini = st.date_input(
            "Data inicial",
            value=value_ini,
            min_value=data_min,
            max_value=data_max,
            key="vis_data_ini"
        )
    with fcol2:
        data_fim = st.date_input(
            "Data final",
            value=value_fim,
            min_value=data_min,
            max_value=data_max,
            key="vis_data_fim"
        )

    mask = (df['data'] >= data_ini) & (df['data'] <= data_fim)
    df_filtro = df[mask].copy()

    # Filtros personalizados
    if tabela_sel == "Reforço":
        pass  # Só filtro de data
    elif tabela_sel == "Entrada":
        contas_disp = ["Todos"] + sorted(df_filtro['conta'].dropna().unique().tolist())
        conta_filtro = st.selectbox("Conta", contas_disp, key="vis_conta")
        if conta_filtro != "Todos":
            df_filtro = df_filtro[df_filtro['conta'] == conta_filtro]
        detalhes_disp = ["Todos"] + sorted(df_filtro['detalhe'].dropna().unique().tolist())
        detalhe_filtro = st.selectbox("Detalhe", detalhes_disp, key="vis_detalhe_entrada")
        if detalhe_filtro != "Todos":
            df_filtro = df_filtro[df_filtro['detalhe'] == detalhe_filtro]
        bancos_disp = ["Todos"] + sorted(df_filtro['banco'].dropna().unique().tolist())
        banco_filtro = st.selectbox("Banco", bancos_disp, key="vis_banco_entrada")
        if banco_filtro != "Todos":
            df_filtro = df_filtro[df_filtro['banco'] == banco_filtro]
    elif tabela_sel == "Saída":
        custos_disp = ["Todos"] + sorted(df_filtro['custo'].dropna().unique().tolist())
        custo_filtro = st.selectbox("Custo", custos_disp, key="vis_custo")
        if custo_filtro != "Todos":
            df_filtro = df_filtro[df_filtro['custo'] == custo_filtro]
        descricoes_disp = ["Todos"] + sorted(df_filtro['descricao'].dropna().unique().tolist())
        descricao_filtro = st.selectbox("Descrição", descricoes_disp, key="vis_descricao")
        if descricao_filtro != "Todos":
            df_filtro = df_filtro[df_filtro['descricao'] == descricao_filtro]
        centros_disp = ["Todos"] + sorted(df_filtro['centro_custo'].dropna().unique().tolist())
        centro_filtro = st.selectbox("Centro de Custo", centros_disp, key="vis_centro_saida")
        if centro_filtro != "Todos":
            df_filtro = df_filtro[df_filtro['centro_custo'] == centro_filtro]
        formas_disp = ["Todos"] + sorted(df_filtro['forma_pagamento'].dropna().unique().tolist())
        forma_filtro = st.selectbox("Forma de Pagamento", formas_disp, key="vis_forma")
        if forma_filtro != "Todos":
            df_filtro = df_filtro[df_filtro['forma_pagamento'] == forma_filtro]
        bancos_disp = ["Todos"] + sorted(df_filtro['banco'].dropna().unique().tolist())
        banco_filtro = st.selectbox("Banco", bancos_disp, key="vis_banco_saida")
        if banco_filtro != "Todos":
            df_filtro = df_filtro[df_filtro['banco'] == banco_filtro]

    # Resumo acima da tabela
    num_linhas = len(df_filtro)
    total = df_filtro['valor'].sum()
    st.markdown(
        f"<div style='font-size:1.2em; font-weight:bold;'>{num_linhas} Linhas filtradas  -  Total: R$ {total:,.2f}</div>",
        unsafe_allow_html=True
    )

    st.dataframe(df_filtro, use_container_width=True, hide_index=True)