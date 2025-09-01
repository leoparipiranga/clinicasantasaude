import pandas as pd
import pickle
import os
from datetime import datetime
import re
from components.pdf_parser import *
import streamlit as st
import random
import string

def gerar_id_aleatorio(tamanho=3):
    """Gera uma string alfanumérica aleatória."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=tamanho))


def processar_movimento_clinica(arquivo):
    """Processa o novo formato de arquivo de movimento da clínica."""
    try:
        # Lê o arquivo Excel, considerando o cabeçalho na linha 8 (índice 7)
        df = pd.read_excel(arquivo, header=7)

        # Substitui '-' por NaN para evitar erros de conversão e exclusão de linhas
        df.replace('-', pd.NA, inplace=True)
        
        # Remove linhas de rodapé que são totalmente vazias ou contêm totais
        df = df.dropna(how='all')
        df = df[~df['Código'].astype(str).str.contains('Total', na=False)]

        # Mapeamento de colunas para o novo formato
        colunas_mapeamento = {
            'Data Pagamento': 'data',
            'Descrição': 'descricao',
            'Forma Pagamento': 'forma_pagamento',
            'Valor Pago': 'pago',
            'Código': 'codigo',
            'Data Cad.': 'data_cadastro',
            'Nome': 'paciente',
            'Médico': 'medico',
            'Unidade': 'unidade',
            'Convênio': 'convenio',
            'Serviços': 'servicos',
            'Total Serviços': 'subtotal',
            'Total Pago': 'total',
            'Repassse Médico': 'repasse_medico',
            'A Pagar': 'a_pagar'
        }
        
        # Renomeia colunas
        colunas_existentes = {k: v for k, v in colunas_mapeamento.items() if k in df.columns}
        df = df.rename(columns=colunas_existentes)
        
        # Função para converter valores monetários em string para float
        def converter_valor(valor):
            if pd.isna(valor) or valor == '':
                return 0.0
            # Se o valor já for numérico, retorna como float
            if isinstance(valor, (int, float)):
                return float(valor)
            
            # Converte para string, remove 'R$', espaços, separador de milhar '.' e troca vírgula ',' por ponto '.'
            valor_str = str(valor).replace('R$', '').strip().replace('.', '').replace(',', '.')
            try:
                return float(valor_str)
            except (ValueError, TypeError):
                return 0.0

        # Lista de colunas monetárias a serem convertidas
        colunas_monetarias = ['pago', 'subtotal', 'total', 'repasse_medico', 'a_pagar']
        
        for col in colunas_monetarias:
            if col in df.columns:
                df[col] = df[col].apply(converter_valor)

        # Converte as colunas de data para o formato datetime
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'], dayfirst=True, errors='coerce')
        if 'data_cadastro' in df.columns:
            df['data_cadastro'] = pd.to_datetime(df['data_cadastro'], dayfirst=True, errors='coerce')
                
        # Adiciona identificadores
        df['origem'] = 'clinica'
        df['data_importacao'] = datetime.now()

        # GERAÇÃO DE ID ÚNICO
        df['id_unico'] = (
            pd.to_datetime(df['data_cadastro']).dt.strftime('%Y%m%d') + '_' +
            df['codigo'].astype(str) + '_' +
            df['subtotal'].astype(str) + '_' +
            df['origem']
        ).apply(lambda x: x + '_' + gerar_id_aleatorio())
              
        return df
        
    except Exception as e:
        raise Exception(f"Erro ao processar movimento clínica: {str(e)}")


def processar_movimento_laboratorio(arquivo):
    """Processa arquivo de movimento do laboratório"""
    try:
        # Lê o arquivo HTML
        df = pd.read_html(arquivo, header=6)[0].iloc[:-4]
        
        # Mapeamento de colunas
        colunas_mapeamento = {
            'Cadastro': 'data_cadastro',
            'Codigo': 'codigo',
            'Código': 'codigo',
            'CÃ³digo': 'codigo',
            'Unidade': 'unidade',
            'Paciente': 'paciente',
            'Convenio': 'convenio',
            'Convênio': 'convenio',
            'ConvÃªnio': 'convenio',
            'Subtotal R$': 'subtotal',
            'Acrés. R$': 'acrescimo',
            'Acres. R$': 'acrescimo',
            'Desc. R$': 'desconto',
            'Total R$': 'total',
            'Pago R$': 'pago',
            'Form.Pag': 'forma_pagamento',
            'Form. Pag.': 'forma_pagamento',
            'Atendente': 'atendente',
            'A pag.': 'a_pagar',
            'A Pag. R$': 'a_pagar'
        }
        
        # Renomeia colunas
        colunas_existentes = {k: v for k, v in colunas_mapeamento.items() if k in df.columns}
        df = df.rename(columns=colunas_existentes)
        
        # Converte colunas monetárias do laboratório (formato "R$ 37,60")
        colunas_monetarias = ['subtotal', 'acrescimo', 'desconto', 'total', 'pago', 'a_pagar']
        
        def converter_valor_laboratorio(valor):
            """Converte valores do formato 'R$ 37,60' para float 37.60"""
            if pd.isna(valor) or valor == '':
                return 0.0
            
            # Converte para string se não for
            valor_str = str(valor)
            
            # Remove 'R$', espaços e converte vírgula para ponto
            valor_limpo = re.sub(r'[R$\s]', '', valor_str)
            valor_limpo = valor_limpo.replace(',', '.')
            
            try:
                return float(valor_limpo)
            except ValueError:
                return 0.0
        
        for col in colunas_monetarias:
            if col in df.columns:
                df[col] = df[col].apply(converter_valor_laboratorio)
        
        # Converte data
        if 'data_cadastro' in df.columns:
            df['data_cadastro'] = pd.to_datetime(df['data_cadastro'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['data_cadastro'])

        # Adiciona identificadores
        df['origem'] = 'laboratorio'
        df['data_importacao'] = datetime.now()

        # GERAÇÃO DE ID ÚNICO
        df['id_unico'] = (
            pd.to_datetime(df['data_cadastro']).dt.strftime('%Y%m%d') + '_' +
            df['codigo'].astype(str) + '_' +
            df['total'].astype(str) + '_' +
            df['origem']
        ).apply(lambda x: x + '_' + gerar_id_aleatorio())
        
        return df
        
    except Exception as e:
        raise Exception(f"Erro ao processar movimento laboratório: {str(e)}")

def processar_convenios_detalhados(arquivo):
    """Processa arquivo de convênios detalhados"""
    try:
        # Lê o arquivo Excel
        df = pd.read_excel(arquivo, header=5)
        
        # Mapeamento de colunas
        colunas_mapeamento = {
            'Data': 'data_cadastro',
            'Paciente': 'paciente',
            'Convenio': 'convenio',
            'Convênio': 'convenio',
            'ConvÃªnio': 'convenio',
            'Exame': 'exame',
            'Valor': 'valor',
            'Codigo': 'codigo',
            'Código': 'codigo',
            'CÃ³digo': 'codigo'
        }
        
        # Renomeia colunas
        colunas_existentes = {k: v for k, v in colunas_mapeamento.items() if k in df.columns}
        df = df.rename(columns=colunas_existentes)
        
        # Converte coluna de valor (formato com vírgula para separador decimal)
        def converter_valor_convenio(valor):
            """Converte valores do formato '123,45' para float 123.45"""
            if pd.isna(valor) or valor == '':
                return 0.0
            
            # Converte para string se não for
            valor_str = str(valor)
            
            # Se já é um número (float/int), retorna convertido
            try:
                if ',' not in valor_str and '.' not in valor_str:
                    return float(valor_str)
                elif ',' in valor_str and '.' not in valor_str:
                    # Formato brasileiro: vírgula como separador decimal
                    return float(valor_str.replace(',', '.'))
                elif '.' in valor_str and ',' not in valor_str:
                    # Formato americano: ponto como separador decimal
                    return float(valor_str)
                else:
                    # Formato com milhares e decimais (ex: 1.234,56 ou 1,234.56)
                    if valor_str.rfind(',') > valor_str.rfind('.'):
                        # Formato brasileiro: 1.234,56
                        valor_limpo = valor_str.replace('.', '').replace(',', '.')
                    else:
                        # Formato americano: 1,234.56
                        valor_limpo = valor_str.replace(',', '')
                    return float(valor_limpo)
            except ValueError:
                return 0.0
        
        if 'valor' in df.columns:
            df['valor'] = df['valor'].apply(converter_valor_convenio)
        
        # Converte data
        if 'data_cadastro' in df.columns:
            df['data_cadastro'] = pd.to_datetime(df['data_cadastro'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['data_cadastro'])

        # Adiciona identificadores
        df['origem'] = 'convenios'
        df['data_importacao'] = datetime.now()

        # GERAÇÃO DE ID ÚNICO
        df['id_unico'] = (
            pd.to_datetime(df['data_cadastro']).dt.strftime('%Y%m%d') + '_' +
            df['codigo'].astype(str) + '_' +
            df['valor'].astype(str) + '_' +
            df['origem']
        ).apply(lambda x: x + '_' + gerar_id_aleatorio())
        
        return df
        
    except Exception as e:
        raise Exception(f"Erro ao processar convênios detalhados: {str(e)}")

def processar_arquivos(arquivo_clinica, arquivo_laboratorio, arquivo_convenio_pdf, arquivo_mulvi=None, arquivo_getnet=None):
    """
    Processa todos os arquivos de importação e JÁ VERIFICA OS CONFLITOS.
    """
    resultado = {
        'sucesso': False,
        'dados_clinica': None,
        'dados_laboratorio': None,
        'dados_convenios': None,
        'dados_mulvi': None,
        'dados_getnet': None,
        'erro': None,
        'conflitos': {}  # Adicionado para armazenar conflitos
    }
    
    try:
        # --- PASSO 1: PROCESSAR TODOS OS ARQUIVOS ---
        if arquivo_clinica is not None:
            resultado['dados_clinica'] = processar_movimento_clinica(arquivo_clinica)
        if arquivo_laboratorio is not None:
            resultado['dados_laboratorio'] = processar_movimento_laboratorio(arquivo_laboratorio)
        if arquivo_convenio_pdf:
            df_convenio_ipes, msg_convenio = processar_pdf_convenio_ipes(arquivo_convenio_pdf)
            if df_convenio_ipes is not None:
                resultado['dados_convenios'] = df_convenio_ipes
            else:
                resultado['erro'] = f"Erro no PDF de convênio: {msg_convenio}"
                return resultado
        if arquivo_mulvi:
            df_mulvi, msg_mulvi = processar_cartao_credito(arquivo_mulvi)
            if df_mulvi is not None:
                resultado['dados_mulvi'] = df_mulvi
            else:
                resultado['erro'] = f"Erro no arquivo MULVI: {msg_mulvi}"
                return resultado
        if arquivo_getnet:
            df_getnet, msg_getnet = processar_cartao_detalhado_getnet(arquivo_getnet)
            if df_getnet is not None:
                resultado['dados_getnet'] = df_getnet
            else:
                resultado['erro'] = f"Erro no arquivo GETNET: {msg_getnet}"
                return resultado

        # --- PASSO 2: VERIFICAR CONFLITOS IMEDIATAMENTE APÓS O PROCESSAMENTO ---
        dados_para_verificar = {
            'clinica': resultado['dados_clinica'],
            'laboratorio': resultado['dados_laboratorio'],
            'ipes': resultado['dados_convenios'],
            'mulvi': resultado['dados_mulvi'],
            'getnet': resultado['dados_getnet']
        }
        conflitos = verificar_conflitos_de_data(dados_para_verificar)
        resultado['conflitos'] = conflitos

        resultado['sucesso'] = True
        return resultado
        
    except Exception as e:
        resultado['erro'] = str(e)
        return resultado

def salvar_importacao(df_clinica, df_laboratorio, df_convenio_ipes, df_mulvi=None, df_getnet=None):
    """
    Salva os dados processados. A verificação de conflitos já foi feita antes.
    """
    resultado = {
        'sucesso': False,
        'clinica_linhas': 0, 'laboratorio_linhas': 0,
        'ipes_linhas': 0, 'mulvi_linhas': 0,
        'getnet_linhas': 0,
        'erro': None
    }
    try:
        # A verificação de conflitos foi movida para 'processar_arquivos'.
        # Esta função agora apenas salva os dados.
        mapa_dados = {
            'clinica': {'df': df_clinica, 'path': 'data/movimento_clinica.pkl'},
            'laboratorio': {'df': df_laboratorio, 'path': 'data/movimento_laboratorio.pkl'},
            'ipes': {'df': df_convenio_ipes, 'path': 'data/convenio_ipes.pkl'},
            'mulvi': {'df': df_mulvi, 'path': 'data/credito_mulvi.pkl'},
            'getnet': {'df': df_getnet, 'path': 'data/credito_getnet.pkl'}
        }

        for tipo, info in mapa_dados.items():
            df_novo = info['df']
            if df_novo is None or df_novo.empty:
                continue
            
            caminho = info['path']
            if os.path.exists(caminho):
                dados_existentes = pd.read_pickle(caminho)
                dados_combinados = pd.concat([dados_existentes, df_novo], ignore_index=True)
            else:
                dados_combinados = df_novo
            
            dados_combinados.to_pickle(caminho)
            resultado[f'{tipo}_linhas'] = len(df_novo)

        # --- Bloco 2: Atualizar movimentacao_contas.pkl ---
        
        caminho_movimentacao = 'data/movimentacao_contas.pkl'
        if os.path.exists(caminho_movimentacao):
            df_movimentacao_contas = pd.read_pickle(caminho_movimentacao)
        else:
            df_movimentacao_contas = pd.DataFrame()
        mapeamento_contas = {
            'Dinheiro': 'DINHEIRO', 'PIX JULIO': 'CONTA PIX',
            'Cartão de crédito': 'MULVI', 'Cartão de débito': 'MULVI'
        }
        novas_movimentacoes = []
        colunas_finais = ['data_cadastro', 'paciente', 'medico', 'forma_pagamento',
                          'convenio', 'servicos', 'origem', 'pago', 'conta']
        for df_original in [df_clinica, df_laboratorio]:
            if df_original is not None and not df_original.empty:
                df_proc = df_original.copy()
                if 'forma_pagamento' in df_proc.columns:
                    df_proc['conta'] = df_proc['forma_pagamento'].str.strip().map(
                        mapeamento_contas).fillna(df_proc['forma_pagamento'])
                else:
                    df_proc['conta'] = ''
                df_filtrado = df_proc[(df_proc.get('pago', 0) > 0) & (df_proc['conta'] != 'MULVI')].copy()
                if not df_filtrado.empty:
                    for c in colunas_finais:
                        if c not in df_filtrado.columns:
                            df_filtrado[c] = ''
                    novas_movimentacoes.append(df_filtrado[colunas_finais])
        if novas_movimentacoes:
            df_para_add = pd.concat(novas_movimentacoes, ignore_index=True)
            df_atualizado = pd.concat([df_movimentacao_contas, df_para_add], ignore_index=True)
            mask_saldo_inicial = df_atualizado['servicos'] == 'SALDO INICIAL'
            df_saldos = df_atualizado[mask_saldo_inicial]
            df_trans = df_atualizado[~mask_saldo_inicial]
            df_trans.drop_duplicates(subset=['data_cadastro','paciente','servicos','pago'], keep='last', inplace=True)
            df_final = pd.concat([df_saldos, df_trans], ignore_index=True)
            df_final.to_pickle(caminho_movimentacao)

        resultado['sucesso'] = True
        return resultado
    except Exception as e:
        resultado['erro'] = str(e)
        return resultado

def atualizar_recebimentos_pendentes():
    """
    Atualiza recebimentos pendentes de forma incremental usando id_unico.
    Preserva o status de pendências existentes.
    """
    try:
        caminho_pendentes = 'data/recebimentos_pendentes.pkl'
        
        # Carrega dados de origem
        df_clinica = carregar_dados_atendimentos('clinica')
        df_laboratorio = carregar_dados_atendimentos('laboratorio') 

        # Carrega pendentes existentes
        df_pendentes_existente = pd.read_pickle(caminho_pendentes) if os.path.exists(caminho_pendentes) else pd.DataFrame()

        # Gera a lista de TODAS as pendências potenciais a partir dos arquivos de origem
        pendencias_potenciais = []
        
        # Processa Clínica
        if not df_clinica.empty and 'forma_pagamento' in df_clinica.columns:
            df_pend_clinica = df_clinica[df_clinica['forma_pagamento'].str.contains('Cartão de crédito', case=False, na=False)].copy()
            if not df_pend_clinica.empty:
                df_pend_clinica['valor_pendente'] = df_pend_clinica['pago']
                df_pend_clinica.rename(columns={'data_cadastro': 'data_operacao'}, inplace=True)
                df_pend_clinica['origem_recebimento'] = df_pend_clinica['forma_pagamento']
                pendencias_potenciais.append(df_pend_clinica[['id_unico', 'data_operacao', 'paciente', 'origem_recebimento', 'valor_pendente', 'origem', 'forma_pagamento']])

        # Processa Laboratório
        if not df_laboratorio.empty and 'forma_pagamento' in df_laboratorio.columns:
            cond_lab = (df_laboratorio['forma_pagamento'].str.contains('Cartão de crédito', na=False)) | \
                       (df_laboratorio['forma_pagamento'].isna()) | \
                       (df_laboratorio['forma_pagamento'].str.strip().isin(['', '-']))
            df_pend_lab = df_laboratorio[cond_lab].copy()
            if not df_pend_lab.empty:
                df_pend_lab['valor_pendente'] = df_pend_lab.apply(lambda r: r['pago'] if 'Cartão' in str(r['forma_pagamento']) else r.get('a_pagar', 0), axis=1)
                df_pend_lab.rename(columns={'data_cadastro': 'data_operacao'}, inplace=True)
                df_pend_lab['origem_recebimento'] = df_pend_lab.apply(lambda r: r['convenio'] if pd.isna(r['forma_pagamento']) or str(r['forma_pagamento']).strip() in ['-',''] else r['forma_pagamento'], axis=1)
                pendencias_potenciais.append(df_pend_lab[['id_unico', 'data_operacao', 'paciente', 'origem_recebimento', 'valor_pendente', 'origem', 'forma_pagamento']])

        if not pendencias_potenciais:
            return True, "Nenhuma pendência potencial encontrada nos arquivos de origem."

        df_potenciais = pd.concat(pendencias_potenciais, ignore_index=True)
        df_potenciais = df_potenciais[df_potenciais['valor_pendente'] > 0]

        # Identifica os novos pendentes (cujo id_unico não existe nos pendentes atuais)
        ids_existentes = set(df_pendentes_existente['id_unico']) if 'id_unico' in df_pendentes_existente.columns else set()
        df_novos_pendentes = df_potenciais[~df_potenciais['id_unico'].isin(ids_existentes)].copy()

        if df_novos_pendentes.empty:
            return True, "Nenhum novo recebimento pendente para adicionar."

        # Prepara os novos pendentes para concatenação
        df_novos_pendentes['status'] = 'pendente'
        df_novos_pendentes['baixa_parcial'] = False
        df_novos_pendentes['valor_residual'] = df_novos_pendentes['valor_pendente']
        df_novos_pendentes['valor_parcial'] = 0.0
        
        # Gera ID de pendência sequencial
        max_id = 0
        if not df_pendentes_existente.empty and 'id_pendencia' in df_pendentes_existente.columns:
            ids_num = pd.to_numeric(df_pendentes_existente['id_pendencia'].str.replace('PEND_', ''), errors='coerce').dropna()
            if not ids_num.empty:
                max_id = int(ids_num.max())
        df_novos_pendentes['id_pendencia'] = [f"PEND_{max_id + i + 1:06d}" for i in range(len(df_novos_pendentes))]

        # Concatena e salva
        df_final = pd.concat([df_pendentes_existente, df_novos_pendentes], ignore_index=True)
        df_final.to_pickle(caminho_pendentes)

        return True, f"{len(df_novos_pendentes)} novos recebimentos pendentes foram criados."

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Erro ao atualizar recebimentos pendentes: {str(e)}"
    
def carregar_dados_atendimentos(tipo):
    """Carrega dados de atendimentos salvos (inclui cartões)."""
    import streamlit as st
    try:
        arquivo_map = {
            'clinica': 'data/movimento_clinica.pkl',
            'laboratorio': 'data/movimento_laboratorio.pkl',
            'convenios': 'data/convenios_detalhados.pkl',
            'convenio_ipes': 'data/convenio_ipes.pkl',
            'credito_mulvi': 'data/credito_mulvi.pkl',
            'credito_getnet': 'data/credito_getnet.pkl'
        }
        
        caminho = arquivo_map.get(tipo)
        
        if caminho and os.path.exists(caminho):
            df = pd.read_pickle(caminho)
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()
    
def inicializar_movimentacao_contas():
    """
    Cria ou atualiza o arquivo de movimentação de contas.
    - Cria com saldos iniciais e novas colunas se não existir.
    - Adiciona as novas colunas se o arquivo existir mas não as contiver.
    """
    caminho_arquivo = 'data/movimentacao_contas.pkl'
    colunas_desejadas = [
        'data_cadastro', 'paciente', 'medico', 'forma_pagamento', 'convenio', 
        'servicos', 'origem', 'pago', 'conta', 'categoria_pagamento', 
        'subcategoria_pagamento', 'observacoes'
    ]

    if not os.path.exists(caminho_arquivo):
        os.makedirs('data', exist_ok=True)
        
        saldos_iniciais = {
            "DINHEIRO": 0.0, "SANTANDER": 0.0, "BANESE": 0.0, "C6": 0.0,
            "CAIXA": 0.0, "BNB": 0.0, "MERCADO PAGO": 0.0, "CONTA PIX": 0.0,
        }
        
        dados_iniciais = []
        for conta, saldo in saldos_iniciais.items():
            dados_iniciais.append({
                'data_cadastro': pd.to_datetime('2025-01-01'), 'paciente': 'SALDO INICIAL',
                'medico': '', 'forma_pagamento': '', 'convenio': '', 'servicos': 'SALDO INICIAL',
                'origem': 'SISTEMA', 'pago': saldo, 'conta': conta,
                'categoria_pagamento': '', 'subcategoria_pagamento': '', 'observacoes': ''
            })
        
        df_inicial = pd.DataFrame(dados_iniciais, columns=colunas_desejadas)
        df_inicial.to_pickle(caminho_arquivo)
        print(f"Arquivo '{caminho_arquivo}' criado com saldos iniciais e novas colunas.")
    else:
        # LÓGICA DE MIGRAÇÃO: Verifica se o arquivo existente precisa ser atualizado
        df_existente = pd.read_pickle(caminho_arquivo)
        colunas_para_adicionar = False
        
        for col in ['categoria_pagamento', 'subcategoria_pagamento', 'observacoes']:
            if col not in df_existente.columns:
                df_existente[col] = '' # Adiciona a coluna com valor padrão
                colunas_para_adicionar = True
        
        if colunas_para_adicionar:
            df_existente.to_pickle(caminho_arquivo)
            print(f"Arquivo '{caminho_arquivo}' atualizado com novas colunas.")

    return False

def verificar_conflitos_de_data(dados_processados):
    """
    Verifica se alguma data nos dados processados já existe nos arquivos .pkl salvos.
    Retorna um dicionário com os conflitos encontrados.
    """
    conflitos = {}
    mapa_arquivos = {
        'clinica': 'data/movimento_clinica.pkl',
        'laboratorio': 'data/movimento_laboratorio.pkl',
        'convenios': 'data/convenios_detalhados.pkl'
    }
    mapa_coluna_data = {
        'clinica': 'data_cadastro',
        'laboratorio': 'data_cadastro',
        'convenios': 'data_cadastro',
        'ipes': 'data_cadastro',
        'mulvi': 'Data_Lançamento',
        'getnet': 'DATA DE VENCIMENTO'
    }

    for tipo, df_novo in dados_processados.items():
        if df_novo is None or df_novo.empty:
            continue

        # Usa a função centralizada para carregar os dados existentes
        df_existente = carregar_dados_atendimentos(tipo)
        coluna_data = mapa_coluna_data.get(tipo)

        if not df_existente.empty and coluna_data in df_existente.columns and coluna_data in df_novo.columns:
            # Garante que ambas as colunas de data sejam do mesmo tipo para comparação
            datas_existentes = pd.to_datetime(df_existente[coluna_data]).dt.date
            datas_novas = pd.to_datetime(df_novo[coluna_data]).dt.date
            
            # Encontra as datas em comum
            datas_conflitantes = set(datas_novas).intersection(set(datas_existentes))
            
            if datas_conflitantes:
                # Formata as datas para exibição
                conflitos[tipo] = sorted([d.strftime('%d/%m/%Y') for d in datas_conflitantes])
    
    return conflitos

def processar_cartao_credito(arquivo):
    """Processa arquivo de movimentação do cartão de crédito com regras específicas"""
    try:
        # Lê o arquivo Excel com cabeçalho na linha 1
        df = pd.read_excel(arquivo, header=1)
        
        # Remove as duas últimas linhas (sempre ignoradas)
        df = df.iloc[:-2]
        
        # Remove linhas vazias
        df = df.dropna(how='all')
        
        # Filtro 1: Remove linhas com 'Aluguel' no Tipo_Transação (case insensitive)
        if 'Tipo_Transação' in df.columns:
            df = df[~df['Tipo_Transação'].str.contains('aluguel', case=False, na=False)]
        
        # NOVO FILTRO: Remove linhas com 'DÉBITO' no Tipo_Transação
        if 'Tipo_Transação' in df.columns:
            df = df[~df['Tipo_Transação'].str.contains('DÉBITO', case=False, na=False)]
        
        # Filtro 2: Remove linhas com ValorBruto negativo (que começam com '-R$')
        if 'ValorBruto' in df.columns:
            df = df[~df['ValorBruto'].astype(str).str.contains(r'^\-R\$', na=False)]
        
        # Conversão de datas
        for col_data in ['Data_Lançamento', 'Data_Transação']:
            if col_data in df.columns:
                df[col_data] = pd.to_datetime(df[col_data], format='%d/%m/%Y', errors='coerce')
        
        # Conversão de valores monetários
        for col_valor in ['ValorBruto', 'ValorLiquido']:
            if col_valor in df.columns:
                df[col_valor] = (df[col_valor]
                               .astype(str)
                               .str.replace('R$', '', regex=False)
                               .str.replace(' ', '', regex=False)
                               .str.replace(',', '.', regex=False)
                               .replace('nan', pd.NA))
                df[col_valor] = pd.to_numeric(df[col_valor], errors='coerce')
        
        # Adiciona colunas padrão do sistema
        df['origem'] = 'cartao_credito_mulvi'
        df['data_importacao'] = datetime.now()
        df['status'] = 'pendente'

        # Mapeia bandeira para máquina
        if 'Bandeira' in df.columns:
            df['maquina'] = df['Bandeira'].map({
                'BANESE CARD': 'BANESE',
                'VISA': 'GETNET',
                'MASTERCARD': 'GETNET'
            }).fillna(df['Bandeira'])

        # GERAÇÃO DE ID ÚNICO
        df['id_unico'] = (
            pd.to_datetime(df['Data_Lançamento']).dt.strftime('%Y%m%d') + '_' +
            df['NSU'].astype(str) + '_' +
            df['ValorLiquido'].astype(str) + '_' +
            df['origem'] + '_' +
            df['maquina'].astype(str)
        ).apply(lambda x: x + '_' + gerar_id_aleatorio())
        
        return df, f"Cartão processado com sucesso! {len(df)} registros válidos."
        
    except Exception as e:
        return None, f"Erro ao processar cartão: {str(e)}"

def processar_cartao_detalhado_getnet(arquivo):
    """
    Processa arquivo de cartão (GETNET) aba 'Detalhado'
    Regras:
      - Ignora linhas 1-7 (header=7)
      - Linha 8 = cabeçalho
      - Remove linhas com 'Total Recebido' ou 'TOTAL' na primeira coluna
      - Mantém apenas colunas definidas
      - Converte valores (troca vírgula por ponto e trata negativos)
      - Datas já vêm corretas do Excel, não precisa converter
    """
    COLS_KEEP = [
        'DATA DE VENCIMENTO','TIPO DE LANÇAMENTO','LANÇAMENTO','VALOR LÍQUIDO','VALOR LIQUIDADO',
        'DATA DA VENDA','HORA DA VENDA','VALOR DA VENDA','PARCELAS','VALOR DA PARCELA',
        'DESCONTOS','VALOR LIQUIDO DA PARCELA'
    ]
    COLS_MONEY = [
        'VALOR LÍQUIDO','VALOR LIQUIDADO','VALOR DA VENDA','VALOR DA PARCELA',
        'DESCONTOS','VALOR LIQUIDO DA PARCELA'
    ]
    try:
        df = pd.read_excel(arquivo, sheet_name='Detalhado', header=7, dtype=str)
        df = df.dropna(how='all')
        primeira_col = df.columns[0]
        df = df[~df[primeira_col].astype(str).str.upper().str.contains(r'(TOTAL RECEBIDO|^TOTAL$)', na=False)]

        # Mantém somente colunas alvo existentes
        cols_exist = [c for c in COLS_KEEP if c in df.columns]
        df = df[cols_exist].copy()

        # Datas: NÃO MODIFICAR - já vêm corretas do Excel
        for c in ['DATA DE VENCIMENTO','DATA DA VENDA']:
            if c in df.columns:
                # Converte diretamente para datetime - pandas reconhece automaticamente
                df[c] = pd.to_datetime(df[c], errors='coerce')

        # CORREÇÃO: Conversão monetária simplificada
        def conv_money(series):
            s = series.astype(str).str.strip()
            # Substitui vírgula por ponto
            s = s.str.replace(',', '.', regex=False)
            # Remove espaços extras e caracteres não numéricos exceto ponto e sinal de menos
            s = s.str.replace(r'[^\d\.\-]', '', regex=True)
            # Converte para numérico
            nums = pd.to_numeric(s, errors='coerce')
            return nums

        for c in COLS_MONEY:
            if c in df.columns:
                df[c] = conv_money(df[c])

        if 'PARCELAS' in df.columns:
            df['PARCELAS'] = df['PARCELAS'].astype(str).str.strip()

        df['origem'] = 'cartao_getnet'
        df['data_importacao'] = datetime.now()
        df['status'] = 'pendente'

        # GERAÇÃO DE ID ÚNICO
        df['id_unico'] = (
            pd.to_datetime(df['DATA DE VENCIMENTO']).dt.strftime('%Y%m%d') + '_' +
            df['VALOR DA VENDA'].astype(str) + '_' +
            df['PARCELAS'].astype(str) + '_' +
            df['VALOR LIQUIDO DA PARCELA'].astype(str) + '_' +
            df['origem']
        ).apply(lambda x: x + '_' + gerar_id_aleatorio())
        
        return df, f"Cartão GETNET detalhado processado: {len(df)} registros."
    except Exception as e:
        return None, f"Erro cartão GETNET: {e}"

def excluir_dados_por_data(tipo, datas_para_excluir):
    """
    Exclui registros de um arquivo .pkl com base em uma lista de datas.
    """
    try:
        # Mapa de arquivos e colunas de data
        mapa_info = {
            'clinica': {'path': 'data/movimento_clinica.pkl', 'col': 'data_cadastro'},
            'laboratorio': {'path': 'data/movimento_laboratorio.pkl', 'col': 'data_cadastro'},
            'ipes': {'path': 'data/convenio_ipes.pkl', 'col': 'data_cadastro'},
            'mulvi': {'path': 'data/credito_mulvi.pkl', 'col': 'Data_Lançamento'},
            'getnet': {'path': 'data/credito_getnet.pkl', 'col': 'DATA DE VENCIMENTO'}
        }

        info = mapa_info.get(tipo)
        if not info:
            return False, f"Tipo de arquivo '{tipo}' desconhecido."

        caminho = info['path']
        coluna_data = info['col']

        if not os.path.exists(caminho):
            return True, "Arquivo não existe, nenhuma exclusão necessária."

        df = pd.read_pickle(caminho)
        if df.empty:
            return True, "Arquivo vazio, nenhuma exclusão necessária."

        if coluna_data not in df.columns:
            return False, f"Coluna de data '{coluna_data}' não encontrada no arquivo."

        # Converte a coluna de data do DataFrame para o tipo 'date' para uma comparação segura
        df[coluna_data] = pd.to_datetime(df[coluna_data]).dt.date
        
        # Garante que as datas para excluir também sejam do tipo 'date'
        datas_formatadas = [pd.to_datetime(d).date() for d in datas_para_excluir]

        # Filtra o DataFrame, mantendo apenas as linhas cuja data NÃO está na lista de exclusão
        df_filtrado = df[~df[coluna_data].isin(datas_formatadas)]

        # Salva o dataframe modificado, sobrescrevendo o original
        df_filtrado.to_pickle(caminho)

        linhas_excluidas = len(df) - len(df_filtrado)
        
        return True, f"{linhas_excluidas} registros excluídos com sucesso."

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Erro ao excluir dados: {str(e)}"