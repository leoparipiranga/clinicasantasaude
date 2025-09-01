# components/functions.py

import io
import os
import base64
import requests
import streamlit as st
import pandas as pd
from datetime import date, datetime

def atualizar_csv_github_df(df, token, repo, path, mensagem, branch="main"):
    import time
    from datetime import datetime
    
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    content_b64 = base64.b64encode(csv_buffer.getvalue().encode()).decode()
    
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}"}
    
    # Adiciona timestamp à mensagem para forçar commit único
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mensagem_timestamped = f"{mensagem} - {timestamp}"
    
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json()["sha"]
    elif r.status_code == 404:
        sha = None
    else:
        st.error(f"Erro ao obter SHA do arquivo: {r.text}")
        return False
    
    data = {
        "message": mensagem_timestamped,
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

def carregar_dados_github_api(arquivo, token, repo):
    """Carrega dados diretamente via API do GitHub (sem cache)"""
    url = f"https://api.github.com/repos/{repo}/contents/{arquivo}"
    headers = {"Authorization": f"token {token}"}
    
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        content = r.json()["content"]
        decoded_content = base64.b64decode(content).decode('utf-8')
        from io import StringIO
        return pd.read_csv(StringIO(decoded_content))
    elif r.status_code == 404:
        # Arquivo não existe, retorna DataFrame vazio
        return pd.DataFrame(columns=["data", "tipo", "conta_origem", "conta_destino", "valor", "categoria", "subcategoria", "detalhamento"])
    else:
        st.error(f"Erro ao carregar arquivo: {r.text}")
        return pd.DataFrame()
    
def salvar_dados(tipo):
    arquivo = "movimentacoes.csv"
    
    # Lê dados diretamente via API (sem cache)
    df_existente = carregar_dados_github_api(
        arquivo, 
        st.secrets["github"]["github_token"], 
        "leoparipiranga/clinicasantasaude"
    )
    
    
    # Transforma os dados temporários no formato unificado
    linhas_unificadas = []
    for linha in st.session_state['linhas_temp']:
        if tipo == "Entrada":
            nova_linha = {
                "data": linha["data"],
                "tipo": "Entrada",
                "conta_origem": "",
                "conta_destino": linha["banco"].upper() if linha["banco"] else "",  # Força maiúscula
                "valor": linha["valor"],
                "categoria": linha["conta"],
                "subcategoria": linha["detalhe"],
                "detalhamento": ""
            }
        elif tipo == "Saída":
            nova_linha = {
                "data": linha["data"],
                "tipo": "Saída", 
                "conta_origem": linha["banco"].upper() if linha["banco"] else "",  # Força maiúscula
                "conta_destino": "",
                "valor": linha["valor"],
                "categoria": linha["custo"],
                "subcategoria": linha["descricao"],
                "detalhamento": linha["detalhamento"]
            }
        elif tipo == "Transferência":
            nova_linha = {
                "data": linha["data"],
                "tipo": "Transferência",
                "conta_origem": linha["origem"].upper() if linha["origem"] else "",  # Força maiúscula
                "conta_destino": linha["destino"].upper() if linha["destino"] else "",  # Força maiúscula
                "valor": linha["valor"],
                "categoria": "",
                "subcategoria": "",
                "detalhamento": ""
            }
        linhas_unificadas.append(nova_linha)
    
    # Concatena com os dados existentes
    df_final = pd.concat([df_existente, pd.DataFrame(linhas_unificadas)], ignore_index=True)
    
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
        # Força limpeza total do cache
        st.cache_data.clear()
        # Adiciona um pequeno delay para garantir sincronização
        import time
        time.sleep(2)
    
    return sucesso

# @st.cache_data(ttl=180)
def carregar_dados_github(arquivo):
    """Carrega dados diretamente da API do GitHub"""
    try:
        url = f"https://api.github.com/repos/leoparipiranga/clinicasantasaude/contents/{arquivo}"
        headers = {"Authorization": f"token {st.secrets['github']['github_token']}"}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            content = base64.b64decode(response.json()['content']).decode('utf-8')
            return pd.read_csv(io.StringIO(content))
        else:
            return pd.DataFrame()
    except:
        return pd.DataFrame()
    
def registrar_entrada():
    nova_linha = {
        "data": st.session_state["data_input_entrada"],
        "conta": st.session_state["conta_input"],
        "detalhe": st.session_state["detalhe_input_entrada"],
        "banco": st.session_state["banco_input_entrada"],
        "valor": st.session_state["valor_input_entrada"]
    }
    st.session_state['linhas_temp'].append(nova_linha)
    # Limpa o formulário
    st.session_state["data_input_entrada"] = date.today()
    st.session_state["conta_input"] = "Clinica"
    st.session_state["detalhe_input_entrada"] = ""
    st.session_state["banco_input_entrada"] = ""
    st.session_state["valor_input_entrada"] = 0.0

def limpar_form_entrada():
    st.session_state["data_input_entrada"] = date.today()
    st.session_state["conta_input"] = "Clinica"
    st.session_state["detalhe_input_entrada"] = ""
    st.session_state["banco_input_entrada"] = ""
    st.session_state["valor_input_entrada"] = 0.0

def carregar_movimentacao_contas():
    """
    Carrega o DataFrame de movimentação de contas a partir do arquivo pickle.
    Retorna um DataFrame vazio se o arquivo não existir ou se ocorrer um erro.
    """
    caminho_arquivo = 'data/movimentacao_contas.pkl'
    try:
        if os.path.exists(caminho_arquivo):
            df = pd.read_pickle(caminho_arquivo)
            # Garante que a coluna de data está no formato correto para ordenação
            if 'data_cadastro' in df.columns:
                df['data_cadastro'] = pd.to_datetime(df['data_cadastro'], errors='coerce')
            return df
        else:
            # Retorna um DataFrame vazio com as colunas esperadas para evitar erros
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo movimentacao_contas.pkl: {e}")
        return pd.DataFrame()

def calcular_saldos_contas():
    """
    Calcula os saldos de todas as contas baseado no arquivo movimentacao_contas.pkl
    Considera ENTRADA como positivo e SAIDA como negativo
    """
    df = carregar_movimentacao_contas()
    
    if df.empty or 'conta' not in df.columns:
        return {}
    
    saldos = {}
    
    # Agrupa por conta e calcula o saldo
    for conta in df['conta'].dropna().unique():
        df_conta = df[df['conta'] == conta]
        
        saldo_total = 0
        for _, row in df_conta.iterrows():
            valor = float(row.get('pago', 0))
            tipo = row.get('tipo', '')
            
            # CORREÇÃO: Se tem coluna 'tipo', usa ela para determinar se soma ou subtrai
            if 'tipo' in df.columns and pd.notna(row.get('tipo')):
                if tipo == 'ENTRADA':
                    saldo_total += valor
                elif tipo == 'SAIDA':
                    saldo_total -= valor
            else:
                # Fallback: se não tem coluna tipo, assume que valores positivos são entrada
                saldo_total += valor
        
        saldos[conta] = saldo_total
    
    return saldos

def limpar_form_transferencia():
    """Limpa os campos do formulário de transferência"""
    if "data_input_transferencia" in st.session_state:
        st.session_state["data_input_transferencia"] = date.today()
    if "origem_input" in st.session_state:
        st.session_state["origem_input"] = "DINHEIRO"
    if "destino_input" in st.session_state:
        st.session_state["destino_input"] = "SANTANDER"
    if "valor_input_transferencia" in st.session_state:
        st.session_state["valor_input_transferencia"] = 0.0
    if "observacoes_input_transferencia" in st.session_state:
        st.session_state["observacoes_input_transferencia"] = ""
        
def registrar_transferencia(data, conta_origem, conta_destino, valor, motivo, descricao, observacoes, taxa=0.0):
    """
    Registra uma transferência entre contas, criando duas entradas no
    movimentacao_contas.pkl. A saída é registrada com valor negativo.
    """
    try:
        caminho_arquivo = 'data/movimentacao_contas.pkl'
        
        if os.path.exists(caminho_arquivo):
            df = pd.read_pickle(caminho_arquivo)
        else:
            df = pd.DataFrame(columns=[
                'data_cadastro', 'tipo', 'categoria_pagamento', 'subcategoria_pagamento', 
                'pago', 'conta', 'descricao', 'observacoes', 'id_transferencia',
                'paciente', 'medico', 'forma_pagamento', 'convenio', 'servicos', 'origem'
            ])

        id_transferencia = f"transf_{int(datetime.now().timestamp())}"

        colunas_nulas = {
            'paciente': None, 'medico': None, 'forma_pagamento': None, 
            'convenio': None, 'servicos': None, 'origem': 'TRANSFERENCIA'
        }

        # Registro de SAÍDA da conta de origem (com valor NEGATIVO)
        saida = {
            'data_cadastro': pd.to_datetime(data),
            'tipo': 'SAIDA',
            'categoria_pagamento': 'TRANSFERENCIA',
            'subcategoria_pagamento': motivo,
            'pago': -abs(float(valor)),  # CORREÇÃO: Valor negativo para a saída
            'conta': conta_origem,
            'descricao': f"Transferência para {conta_destino}",
            'observacoes': observacoes,
            'id_transferencia': id_transferencia,
            **colunas_nulas
        }

        # Registro de ENTRADA na conta de destino (com valor POSITIVO)
        valor_liquido = float(valor) - float(taxa)
        entrada = {
            'data_cadastro': pd.to_datetime(data),
            'tipo': 'ENTRADA',
            'categoria_pagamento': 'TRANSFERENCIA',
            'subcategoria_pagamento': motivo,
            'pago': abs(valor_liquido), # Garante que o valor de entrada é positivo
            'conta': conta_destino,
            'descricao': f"Transferência de {conta_origem}",
            'observacoes': observacoes,
            'id_transferencia': id_transferencia,
            **colunas_nulas
        }
        
        registros_a_adicionar = [saida, entrada]

        if taxa > 0:
            taxa_registro = {
                'data_cadastro': pd.to_datetime(data),
                'tipo': 'SAIDA',
                'categoria_pagamento': 'DESPESAS OPERACIONAIS',
                'subcategoria_pagamento': 'TAXAS BANCÁRIAS',
                'pago': -abs(float(taxa)), # CORREÇÃO: Taxa também é uma saída negativa
                'conta': conta_origem,
                'descricao': f"Taxa de transferência de {conta_origem} para {conta_destino}",
                'observacoes': observacoes,
                'id_transferencia': id_transferencia,
                **colunas_nulas
            }
            registros_a_adicionar.append(taxa_registro)

        novos_registros = pd.DataFrame(registros_a_adicionar)
        df_atualizado = pd.concat([df, novos_registros], ignore_index=True)
        df_atualizado.to_pickle(caminho_arquivo)
        
        return True

    except Exception as e:
        st.error(f"Erro ao registrar transferência na função: {e}")
        return False

def limpar_form_transferencia():
    st.session_state["data_input_transferencia"] = date.today()
    st.session_state["origem_input"] = "DINHEIRO"
    st.session_state["destino_input"] = "SANTANDER"
    st.session_state["valor_input_transferencia"] = 0.0

def limpar_form_saida():
    st.session_state["data_saida"] = date.today()
    st.session_state["custo_saida"] = "Fixo"
    st.session_state["descricao_saida"] = ""
    st.session_state["detalhamento_saida"] = ""
    st.session_state["centro_saida"] = "Rateio"
    st.session_state["forma_saida"] = "Dinheiro"
    st.session_state["banco_saida"] = "SANTANDER"
    st.session_state["valor_saida"] = 0.0

def registrar_saida(data, categoria, subcategoria, valor, conta_origem, observacoes):
    """
    Registra uma nova transação de saída (pagamento) no arquivo movimentacao_contas.pkl.

    Args:
        data (datetime.date): Data da transação.
        categoria (str): Categoria do pagamento.
        subcategoria (str): Subcategoria do pagamento.
        valor (float): Valor do pagamento (deve ser positivo).
        conta_origem (str): Nome da conta de onde o dinheiro saiu.
        observacoes (str): Observações adicionais.

    Returns:
        bool: True se a operação foi bem-sucedida, False caso contrário.
    """
    caminho_arquivo = 'data/movimentacao_contas.pkl'

    try:
        # --- 1. Carregar o DataFrame de movimentações ---
        if os.path.exists(caminho_arquivo):
            df_movimentacao = pd.read_pickle(caminho_arquivo)
        else:
            # Se o arquivo não existe, a operação não pode continuar, pois não há contas para debitar.
            # A função inicializar_movimentacao_contas() deve ser chamada em outro lugar.
            print(f"ERRO: Arquivo '{caminho_arquivo}' não encontrado. Execute a inicialização primeiro.")
            return False

        # --- 2. Preparar o novo registro de pagamento ---
        # O valor é registrado como negativo, pois é uma SAÍDA.
        valor_saida = -abs(float(valor))

        novo_pagamento = {
            'data_cadastro': pd.to_datetime(data),
            'paciente': 'PAGAMENTO',  # Identificador para transações de pagamento
            'medico': '',
            'forma_pagamento': 'DÉBITO', # Identifica como uma saída
            'convenio': '',
            'servicos': subcategoria, # Usa a subcategoria para descrever o serviço/produto pago
            'origem': 'SISTEMA',
            'pago': valor_saida,
            'conta': conta_origem,
            'categoria_pagamento': categoria,
            'subcategoria_pagamento': subcategoria,
            'observacoes': observacoes
        }
        
        df_novo_pagamento = pd.DataFrame([novo_pagamento])

        # --- 3. Garantir que todas as colunas existam no DataFrame principal ---
        for col in df_novo_pagamento.columns:
            if col not in df_movimentacao.columns:
                df_movimentacao[col] = pd.NA # Adiciona a coluna com valores nulos se não existir

        # --- 4. Adicionar o pagamento ao histórico e salvar ---
        df_atualizado = pd.concat([df_movimentacao, df_novo_pagamento], ignore_index=True)
        
        # Salva o arquivo atualizado
        df_atualizado.to_pickle(caminho_arquivo)
        
        print(f"Pagamento de R${valor:.2f} registrado com sucesso na conta '{conta_origem}'.")
        return True

    except Exception as e:
        print(f"ERRO ao registrar saída: {e}")
        return False


def salvar_nova_descricao(custo, descricao):
    """Salva nova descrição no GitHub"""
    try:
        # Carrega arquivo de configurações existente
        try:
            df_config = carregar_dados_github("configuracoes.csv")
        except:
            df_config = pd.DataFrame(columns=["custo", "descricao"])
        
        # Adiciona nova linha
        nova_linha = pd.DataFrame({"custo": [custo], "descricao": [descricao]})
        df_final = pd.concat([df_config, nova_linha], ignore_index=True)
        
        # Salva no GitHub
        atualizar_csv_github_df(
            df_final,
            token=st.secrets["github"]["github_token"],
            repo="leoparipiranga/clinicasantasaude",
            path="configuracoes.csv",
            mensagem="Adiciona nova descrição"
        )
        return True
    except:
        return False

def carregar_descricoes_personalizadas():
    """Carrega descrições personalizadas do GitHub"""
    try:
        df_config = carregar_dados_github("configuracoes.csv")
        descricoes_extras = {}
        for _, row in df_config.iterrows():
            custo = row['custo']
            descricao = row['descricao']
            if custo not in descricoes_extras:
                descricoes_extras[custo] = []
            descricoes_extras[custo].append(descricao)
        return descricoes_extras
    except:
        return {}