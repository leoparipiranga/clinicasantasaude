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

        # ETAPA 2: Adiciona coluna indice_paciente

        df['indice_paciente'] = (
            df['data_cadastro'].dt.strftime('%Y-%m-%d') + '_' +
            df['paciente'].astype(str)
        )

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
            'Documento': 'documento',
            'Empresa': 'empresa',
            'Código': 'codigo',
            'Exame': 'exame',
            'Descrição Exame': 'descricao',
            'Código Exame': 'codigo_exame',
            'Paciente': 'paciente',
            'Data Nascimento': 'data_nascimento',
            'Endereço': 'endereco',
            'Valor': 'valor',
            'Unidade': 'unidade',
            'Local': 'local',
            'Convênio': 'convenio',
            'Matricula': 'matricula'           
            
        }
        

        # Renomeia colunas
        colunas_existentes = {k: v for k, v in colunas_mapeamento.items() if k in df.columns}
        df = df.rename(columns=colunas_existentes)

        df = df[df['convenio']=='IPES']
        
        # Trata campo codigo_exame: remove pontos e converte para int
        if 'codigo_exame' in df.columns:
            def tratar_codigo_exame(valor):
                """Remove pontos e converte para int, substituindo NaN por 0"""
                if pd.isna(valor) or valor == '':
                    return 0
                
                # Converte para string e remove pontos
                valor_str = str(valor).replace('.', '')
                
                try:
                    return int(valor_str)
                except ValueError:
                    return 0
            
            df['codigo_exame'] = df['codigo_exame'].apply(tratar_codigo_exame)


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

        # ETAPA 2: Garante que indice_paciente existe
        if 'indice_paciente' not in df.columns:
            df['data_cadastro'] = pd.to_datetime(df['data_cadastro'])
            df['indice_paciente'] = (
                df['data_cadastro'].dt.strftime('%Y-%m-%d') + '_' +
                df['paciente'].astype(str)
            )

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

def processar_arquivos(arquivo_clinica, arquivo_laboratorio, arquivo_convenio_detalhado, arquivo_convenio_pdf, arquivo_mulvi=None, arquivo_getnet=None):
    """
    Processa todos os arquivos de importação e JÁ VERIFICA OS CONFLITOS.
    """
    resultado = {
        'sucesso': False,
        'dados_clinica': None,
        'dados_laboratorio': None,
        'dados_convenio_detalhado': None,
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
        if arquivo_convenio_detalhado is not None:
            resultado['dados_convenio_detalhado'] = processar_convenios_detalhados(arquivo_convenio_detalhado)
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
            'convenio_detalhado': resultado['dados_convenio_detalhado'],
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

def salvar_importacao(df_clinica, df_laboratorio, df_convenio_detalhado, df_convenio_ipes, df_mulvi=None, df_getnet=None):
    """
    Salva os dados processados. A verificação de conflitos já foi feita antes.
    """
    resultado = {
        'sucesso': False,
        'clinica_linhas': 0, 'laboratorio_linhas': 0,
        'convenio_detalhado_linhas': 0, 'ipes_linhas': 0, 'mulvi_linhas': 0,
        'getnet_linhas': 0,
        'erro': None,
        'debitos_registrados': 0,
        'consolidacao_ipes': None # Novo campo para retorno do DataFrame consolidado IPES
    }
    try:
        # A verificação de conflitos foi movida para 'processar_arquivos'.
        # Esta função agora apenas salva os dados.
        mapa_dados = {
            'clinica': {'df': df_clinica, 'path': 'data/movimento_clinica.pkl'},
            'laboratorio': {'df': df_laboratorio, 'path': 'data/movimento_laboratorio.pkl'},
            'convenio_detalhado': {'df': df_convenio_detalhado, 'path': 'data/convenio_detalhado.pkl'},
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
        
        # NOVO: Mapeamento atualizado para débito automático
        mapeamento_contas = {
            'Dinheiro': 'DINHEIRO', 
            'PIX JULIO': 'CONTA PIX',
            'Cartão de crédito': 'MULVI',  # Crédito vai para MULVI (será processado na conciliação)
            'Cartão de débito MULVI': 'BANESE',  # NOVO: Débito MULVI vai direto para BANESE
            'Cartão de débito GETNET': 'SANTANDER',  # NOVO: Débito GETNET vai direto para SANTANDER
            'Cartão de débito': 'BANESE'  # Default para BANESE se não especificar máquina
        }
        
        novas_movimentacoes = []
        colunas_finais = ['data_cadastro', 'paciente', 'medico', 'forma_pagamento',
                          'convenio', 'servicos', 'origem', 'pago', 'conta', 'total', 'a_pagar', 'desconto']
        
        contador_debitos = 0
        
        for df_original in [df_clinica, df_laboratorio]:
            if df_original is not None and not df_original.empty:
                df_proc = df_original.copy()
                
                # NOVO: Lógica especial para débito
                if 'forma_pagamento' in df_proc.columns:
                    def mapear_conta_debito(forma_pag):
                        if pd.isna(forma_pag):
                            return ''
                        forma_str = str(forma_pag).strip()
                        
                        # Verifica se é débito
                        if 'débito' in forma_str.lower() or 'debito' in forma_str.lower():
                            if 'MULVI' in forma_str.upper():
                                return 'BANESE'
                            elif 'GETNET' in forma_str.upper():
                                return 'SANTANDER'
                            else:
                                return 'BANESE'  # Default para MULVI/BANESE
                        
                        # Para outros tipos, usa o mapeamento original
                        return mapeamento_contas.get(forma_str, forma_str)
                    
                    df_proc['conta'] = df_proc['forma_pagamento'].apply(mapear_conta_debito)
                else:
                    df_proc['conta'] = ''
                
                # MODIFICADO: Inclui débitos (que antes eram excluídos) e exclui apenas créditos
                df_filtrado = df_proc[
                    (df_proc.get('pago', 0) > 0) & 
                    (~df_proc['forma_pagamento'].str.contains('Cartão de crédito', case=False, na=False))
                ].copy()
                
                # Conta débitos registrados
                if not df_filtrado.empty:
                    debitos_df = df_filtrado[
                        df_filtrado['forma_pagamento'].str.contains('débito', case=False, na=False)
                    ]
                    contador_debitos += len(debitos_df)
                
                if not df_filtrado.empty:
                    # Garante que todas as colunas existam
                    for c in colunas_finais:
                        if c not in df_filtrado.columns:
                            df_filtrado[c] = '' if c in ['medico', 'convenio', 'servicos'] else 0
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
        
        # --- NOVO: Bloco 3: Atualizar consolidação IPES se dados relevantes foram importados ---
        dados_ipes_importados = (
            (df_clinica is not None and not df_clinica.empty) or 
            (df_convenio_detalhado is not None and not df_convenio_detalhado.empty)
        )
        
        if dados_ipes_importados:
            try:
                sucesso_consolidacao, msg_consolidacao = atualizar_consolidacao_ipes()
                resultado['consolidacao_ipes'] = {
                    'sucesso': sucesso_consolidacao,
                    'mensagem': msg_consolidacao
                }
            except Exception as e:
                resultado['consolidacao_ipes'] = {
                    'sucesso': False,
                    'mensagem': f"Erro na consolidação IPES: {str(e)}"
                }

        resultado['debitos_registrados'] = contador_debitos
        resultado['sucesso'] = True
        return resultado
    except Exception as e:
        resultado['erro'] = str(e)
        return resultado

def atualizar_recebimentos_pendentes():
    """
    Atualiza recebimentos pendentes de forma incremental usando id_unico.
    Preserva o status de pendências existentes.
    MODIFICADO: Exclui débitos (que agora são registrados automaticamente nas contas).
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
        
        # --- Helper: parse forma_pagamento para extrair máquina e parcelas ---
        def _parse_forma_pagamento(s):
            """
            Retorna (forma_pagamento2, maquina, n_parcelas).
            Ex: 'Cartão de crédito GETNET 6' -> ('Cartão de crédito', 'GETNET', 6)
            MODIFICADO: Não processa mais débito.
            """
            if pd.isna(s):
                return (s, '', 1)
            txt = str(s).strip()
            low = txt.lower()
            
            # MODIFICADO: Só processa crédito, débito é ignorado
            if 'crédito' in low or 'credito' in low:
                forma2 = 'Cartão de crédito'
            elif 'cart' in low and 'débito' not in low and 'debito' not in low:
                forma2 = 'Cartão de crédito'  # default para compatibilidade
            else:
                forma2 = txt
            
            # Detecta máquina
            maquina = ''
            if 'getnet' in txt.upper():
                maquina = 'GETNET'
            elif 'mulvi' in txt.upper() or 'mulvipay' in txt.upper() or 'mulvi' in txt.lower():
                maquina = 'MULVI'
            # Extrai último número como parcelas, se houver
            n = 1
            import re
            m = re.search(r'(\d+)\s*$', txt)
            if m:
                try:
                    n = int(m.group(1))
                except:
                    n = 1
            return (forma2, maquina, n)
        
        # Processa Clínica
        if not df_clinica.empty and 'forma_pagamento' in df_clinica.columns:
            # MODIFICADO: Exclui débito (apenas crédito vira pendência)
            df_pend_clinica = df_clinica[
                df_clinica['forma_pagamento'].str.contains('Cartão de crédito', case=False, na=False)
            ].copy()
            if not df_pend_clinica.empty:
                df_pend_clinica['valor_pendente'] = df_pend_clinica['pago']
                df_pend_clinica.rename(columns={'data_cadastro': 'data_operacao'}, inplace=True)
                # Origem_recebimento mantém o valor original informado
                df_pend_clinica['origem_recebimento'] = df_pend_clinica['forma_pagamento']
                # Novas colunas: forma_pagamento2, maquina, n_parcelas
                parsed = df_pend_clinica['forma_pagamento'].apply(lambda s: pd.Series(_parse_forma_pagamento(s), index=['forma_pagamento2','maquina','n_parcelas']))
                df_pend_clinica = pd.concat([df_pend_clinica, parsed], axis=1)
                pendencias_potenciais.append(df_pend_clinica[['id_unico', 'data_operacao', 'paciente', 'origem_recebimento', 'valor_pendente', 'origem', 'forma_pagamento', 'forma_pagamento2', 'maquina', 'n_parcelas']])

        # Processa Laboratório
        if not df_laboratorio.empty and 'forma_pagamento' in df_laboratorio.columns or ('Form.Pag' in df_laboratorio.columns) or ('Form. Pag.' in df_laboratorio.columns):
            # Normaliza nome da coluna de forma de pagamento no df de laboratório
            if 'Form.Pag' in df_laboratorio.columns and 'forma_pagamento' not in df_laboratorio.columns:
                df_laboratorio = df_laboratorio.rename(columns={'Form.Pag':'forma_pagamento'})
            if 'Form. Pag.' in df_laboratorio.columns and 'forma_pagamento' not in df_laboratorio.columns:
                df_laboratorio = df_laboratorio.rename(columns={'Form. Pag.':'forma_pagamento'})

            # ETAPA 2: Garante que indice_paciente existe no laboratório
            if 'indice_paciente' not in df_laboratorio.columns:
                df_laboratorio['data_cadastro'] = pd.to_datetime(df_laboratorio['data_cadastro'])
                df_laboratorio['indice_paciente'] = (
                    df_laboratorio['data_cadastro'].dt.strftime('%Y-%m-%d') + '_' + 
                    df_laboratorio['paciente'].astype(str)
                )

            # MODIFICADO: Apenas crédito e convênios (exclui débito)
            cond_lab = (df_laboratorio['forma_pagamento'].astype(str).str.contains('Cartão de crédito', na=False)) | \
                       (df_laboratorio['forma_pagamento'].isna()) | \
                       (df_laboratorio['forma_pagamento'].str.strip().isin(['', '-']))
            df_pend_lab = df_laboratorio[cond_lab].copy()
            if not df_pend_lab.empty:
                # Para crédito usa 'pago', para convênios usa a_pagar
                df_pend_lab['valor_pendente'] = df_pend_lab.apply(
                    lambda r: r['pago'] if 'Cartão' in str(r.get('forma_pagamento','')) and 'crédito' in str(r.get('forma_pagamento','')).lower()
                    else r.get('a_pagar', 0), axis=1
                )
                df_pend_lab.rename(columns={'data_cadastro': 'data_operacao'}, inplace=True)
                df_pend_lab['origem_recebimento'] = df_pend_lab.apply(lambda r: r['convenio'] if pd.isna(r.get('forma_pagamento')) or str(r.get('forma_pagamento')).strip() in ['-',''] else r.get('forma_pagamento'), axis=1)
                # Parse forma_pagamento para máquina e parcelas
                parsed_lab = df_pend_lab['origem_recebimento'].apply(lambda s: pd.Series(_parse_forma_pagamento(s), index=['forma_pagamento2','maquina','n_parcelas']))
                df_pend_lab = pd.concat([df_pend_lab, parsed_lab], axis=1)
                pendencias_potenciais.append(df_pend_lab[['id_unico', 'data_operacao', 'paciente', 'origem_recebimento', 'valor_pendente', 'origem', 'forma_pagamento', 'forma_pagamento2', 'maquina', 'n_parcelas']])

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
            'convenio_detalhado': 'data/convenio_detalhado.pkl',
            'convenio_ipes': 'data/convenio_ipes.pkl',
            'ipes': 'data/convenio_ipes.pkl',
            'credito_mulvi': 'data/credito_mulvi.pkl',
            'mulvi': 'data/credito_mulvi.pkl',
            'credito_getnet': 'data/credito_getnet.pkl',
            'getnet': 'data/credito_getnet.pkl',
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
                df[col_data] = pd.to_datetime(df[col_data], format='%d/%m/%Y', errors='coerce').dt.date
        
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
      - Exclui qualquer linha em que a primeira coluna seja vazia
      - Mantém apenas colunas definidas
      - Converte valores (troca vírgula por ponto e trata negativos e tira R$, se houver)
    """
    COLS_KEEP = [
        'Cartões', 'Data/Hora \nda Venda', "Data Prevista do 1º Pagamento", 
        "Descrição do Lançamento", "Total de Parcelas", "Valor Bruto",
        'Valor da Taxa \ne/ou Tarifa', "Valor Líquido"
    ]
    COLS_MONEY = [
        "valor_bruto", "valor_taxa", "valor_liquido"
    ]
    
    try:
        df = pd.read_excel(arquivo, sheet_name='ANALITICO', header=7, dtype=str)
        df = df.dropna(subset=['Cód. Estabelecimento'])
        df = df.dropna(axis=1, how='all')
        # Exclui linhas onde a primeira coluna seja vazia
        primeira_col = df.columns[0]
        df = df[df[primeira_col].notna()]
        df = df[df[primeira_col].astype(str).str.strip() != '']
        # Mantém somente colunas alvo existentes
        cols_exist = [c for c in COLS_KEEP if c in df.columns]
        df = df[cols_exist].copy()
        df.columns = ['cartoes','data_venda','data_prevista_1_pagamento','descricao_lancamento','n_parcelas','valor_bruto','valor_taxa','valor_liquido']
        if 'cartoes' in df.columns:
            df = df[~df['cartoes'].str.contains('DÉBITO', case=False, na=False)]
        # Tratamento de datas
        if "data_venda" in df.columns:
            df["data_venda"] = pd.to_datetime(df["data_venda"], dayfirst=True, errors='coerce').dt.date
        if "data_prevista_1_pagamento" in df.columns:
            df["data_prevista_1_pagamento"] = pd.to_datetime(df["data_prevista_1_pagamento"], dayfirst=True, errors='coerce').dt.date

        # Conversão de valores monetários
        for col_valor in ['valor_bruto', 'valor_taxa', 'valor_liquido']:
            if col_valor in df.columns:
                df[col_valor] = (df[col_valor]
                               .astype(str)
                               .str.replace('R$', '', regex=False)
                               .str.replace(' ', '', regex=False)
                               .str.replace(',', '.', regex=False)
                               .replace('nan', pd.NA))
                df[col_valor] = pd.to_numeric(df[col_valor], errors='coerce')

        df['origem'] = 'cartao_getnet'
        df['data_importacao'] = datetime.now()
        df['status'] = 'pendente'
        # GERAÇÃO DE ID ÚNICO (adaptado para as novas colunas) - CORREÇÃO AQUI
        # Converte valores para string tratando NaN
        def safe_str(value):
            if pd.isna(value):
                return 'nan'
            return str(value)

        df['id_unico'] = (
            pd.to_datetime(df["data_prevista_1_pagamento"], errors='coerce').dt.strftime('%Y%m%d').fillna('00000000') + '_' +
            df["valor_bruto"].apply(safe_str) + '_' +
            df["n_parcelas"].apply(safe_str) + '_' +
            df["valor_liquido"].apply(safe_str) + '_' +
            df['origem']
        ).apply(lambda x: x + '_' + gerar_id_aleatorio())
        
        return df, f"Cartão GETNET detalhado processado: {len(df)} registros."
    except Exception as e:
        import traceback
        traceback.print_exc()
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

def consolidar_dados_ipes_completo():
    """
    Consolida dados do IPES extraindo transações da clínica (convenio = IPES) 
    e combinando com dados detalhados do laboratório.
    
    Cria um arquivo unificado 'data/ipes_consolidado.pkl' com todas as transações IPES
    para uso na conciliação automatizada.
    
    Returns:
        tuple: (sucesso: bool, mensagem: str, df_consolidado: DataFrame ou None)
    """
    try:
        # Carrega dados da clínica
        try:
            df_clinica = pd.read_pickle('data/movimento_clinica.pkl')
        except:
            df_clinica = pd.DataFrame()
        
        # Carrega dados detalhados do laboratório
        try:
            df_convenio_detalhado = pd.read_pickle('data/convenio_detalhado.pkl')
        except:
            df_convenio_detalhado = pd.DataFrame()
        
        if df_clinica.empty and df_convenio_detalhado.empty:
            return False, "Nenhum dado encontrado nos arquivos de origem", None
        
        dados_consolidados = []
        
        # --- PROCESSA DADOS DA CLÍNICA (CONVENIO = IPES) ---
        if not df_clinica.empty and 'convenio' in df_clinica.columns:
            # Filtra apenas registros do IPES
            df_clinica_ipes = df_clinica[
                df_clinica['convenio'].str.contains('IPES', case=False, na=False)
            ].copy()
            
            if not df_clinica_ipes.empty:
                # Mapeia colunas da clínica para o formato consolidado
                for _, row in df_clinica_ipes.iterrows():
                    dados_consolidados.append({
                        'data_cadastro': row.get('data_cadastro'),
                        'paciente': row.get('paciente', ''),
                        'codigo': row.get('codigo', ''),
                        'codigo_exame': 0,  # Clínica não tem código de exame específico
                        'descricao': row.get('servicos', ''),
                        'medico': row.get('medico', ''),
                        'unidade': row.get('unidade', ''),
                        'valor': row.get('subtotal', 0.0),  # Usa subtotal como valor
                        'origem_dados': 'clinica',
                        'convenio': 'IPES',
                        'tipo_procedimento': 'consulta_exame'
                    })
        
        # --- PROCESSA DADOS DETALHADOS DO LABORATÓRIO ---
        if not df_convenio_detalhado.empty:
            # Já está filtrado para IPES na função processar_convenios_detalhados
            for _, row in df_convenio_detalhado.iterrows():
                dados_consolidados.append({
                    'data_cadastro': row.get('data_cadastro'),
                    'paciente': row.get('paciente', ''),
                    'codigo': row.get('codigo', ''),
                    'codigo_exame': row.get('codigo_exame', 0),
                    'descricao': row.get('descricao', ''),
                    'medico': '',  # Laboratório não tem médico específico
                    'unidade': row.get('unidade', ''),
                    'valor': row.get('valor', 0.0),
                    'origem_dados': 'laboratorio_detalhado',
                    'convenio': 'IPES',
                    'tipo_procedimento': 'exame_laboratorio'
                })
        
        if not dados_consolidados:
            return False, "Nenhum dado do IPES encontrado para consolidação", None
        
        # Cria DataFrame consolidado
        df_consolidado = pd.DataFrame(dados_consolidados)
        
        # Converte data_cadastro para datetime
        df_consolidado['data_cadastro'] = pd.to_datetime(df_consolidado['data_cadastro'], errors='coerce')
        
        # Remove registros com data inválida
        df_consolidado = df_consolidado.dropna(subset=['data_cadastro'])
        
        # Cria indice_paciente para compatibilidade com funções existentes
        df_consolidado['indice_paciente'] = (
            df_consolidado['data_cadastro'].dt.strftime('%Y-%m-%d') + '_' + 
            df_consolidado['paciente'].astype(str)
        )
        
        # NOVO: Gera ID de pendência sequencial PEND_###### para cada registro
        # Verifica se já existem pendências para determinar o próximo número
        max_id = 0
        caminho_pendentes = 'data/recebimentos_pendentes.pkl'
        if os.path.exists(caminho_pendentes):
            try:
                df_pendentes_existente = pd.read_pickle(caminho_pendentes)
                if not df_pendentes_existente.empty and 'id_pendencia' in df_pendentes_existente.columns:
                    ids_num = pd.to_numeric(df_pendentes_existente['id_pendencia'].astype(str).str.replace(r'[^0-9]', '', regex=True), errors='coerce').dropna()
                    if not ids_num.empty:
                        max_id = int(ids_num.max())
            except Exception:
                max_id = 0
        
        df_consolidado['id_pendencia'] = [f"PEND_{max_id + i + 1:06d}" for i in range(len(df_consolidado))]
        
        # Gera ID único para cada registro
        df_consolidado['id_unico'] = (
            df_consolidado['data_cadastro'].dt.strftime('%Y%m%d') + '_' +
            df_consolidado['codigo'].astype(str) + '_' +
            df_consolidado['codigo_exame'].astype(str) + '_' +
            df_consolidado['valor'].astype(str) + '_' +
            df_consolidado['origem_dados']
        ).apply(lambda x: x + '_' + gerar_id_aleatorio())
        
        # Adiciona metadados
        df_consolidado['data_consolidacao'] = datetime.now()
        df_consolidado['origem'] = 'ipes_consolidado'
        df_consolidado['status_conciliacao'] = 'pendente'
        
        # Ordena por data e paciente
        df_consolidado = df_consolidado.sort_values(['data_cadastro', 'paciente', 'codigo_exame']).reset_index(drop=True)
        
        # Salva arquivo consolidado
        os.makedirs('data', exist_ok=True)
        df_consolidado.to_pickle('data/ipes_consolidado.pkl')
        
        # Estatísticas
        total_registros = len(df_consolidado)
        registros_clinica = len(df_consolidado[df_consolidado['origem_dados'] == 'clinica'])
        registros_lab = len(df_consolidado[df_consolidado['origem_dados'] == 'laboratorio_detalhado'])
        
        mensagem = (
            f"Consolidação concluída com sucesso!\n"
            f"• Total: {total_registros} registros\n"
            f"• Clínica: {registros_clinica} registros\n"
            f"• Laboratório: {registros_lab} registros\n"
            f"• Arquivo salvo: data/ipes_consolidado.pkl"
        )
        
        return True, mensagem, df_consolidado
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Erro na consolidação: {str(e)}", None

def obter_dados_ipes_consolidado():
    """
    Carrega dados consolidados do IPES ou cria se não existir.
    Usado pelas funções de conciliação IPES.
    
    Returns:
        DataFrame: Dados consolidados do IPES
    """
    try:
        caminho_arquivo = 'data/ipes_consolidado.pkl'
        
        if os.path.exists(caminho_arquivo):
            df = pd.read_pickle(caminho_arquivo)
            return df
        else:
            # Se não existe, tenta criar automaticamente
            sucesso, msg, df = consolidar_dados_ipes_completo()
            if sucesso and df is not None:
                return df
            else:
                return pd.DataFrame()
                
    except Exception as e:
        print(f"Erro ao carregar dados consolidados IPES: {e}")
        return pd.DataFrame()

def atualizar_consolidacao_ipes():
    """
    Atualiza a consolidação dos dados IPES.
    Deve ser chamada sempre que novos dados da clínica ou laboratório forem importados.
    
    Returns:
        tuple: (sucesso: bool, mensagem: str)
    """
    try:
        sucesso, mensagem, _ = consolidar_dados_ipes_completo()
        return sucesso, mensagem
    except Exception as e:
        return False, f"Erro ao atualizar consolidação: {str(e)}"
