import pandas as pd
import pickle
import os
from datetime import datetime, date
from components.importacao import carregar_dados_atendimentos
from components.functions import salvar_dados

CAMINHO_PENDENTES = 'data/recebimentos_pendentes.pkl'
CAMINHO_MOVIMENTACAO = 'data/movimentacao_contas.pkl'

# ========== FUNÇÕES DE LEITURA DE DADOS ==========

def obter_recebimentos_pendentes():
    """Carrega TODOS os recebimentos pendentes do arquivo pkl."""
    if os.path.exists(CAMINHO_PENDENTES):
        return pd.read_pickle(CAMINHO_PENDENTES)
    return pd.DataFrame()

def obter_recebimentos_convenios_outros():
    """
    Obtém apenas recebimentos de convênios (exceto IPES e cartões).
    Usado na aba GERAL.
    """
    df = obter_recebimentos_pendentes()
    if df.empty:
        return df
    
    # IMPORTANTE: Filtra apenas pendentes
    if 'status' in df.columns:
        df = df[df['status'] == 'pendente']
    else:
        # Se não tem coluna status, adiciona como pendente (compatibilidade)
        df['status'] = 'pendente'
    
    # Exclui IPES e cartões
    df = df[
        ~df['origem_recebimento'].str.contains('IPES', case=False, na=False) &
        ~df['origem_recebimento'].str.contains('Cartão de crédito', case=False, na=False) &
        ~df['origem_recebimento'].str.contains('MULVI', case=False, na=False) &
        ~df['origem_recebimento'].str.contains('GETNET', case=False, na=False)
    ]
    
    return df

def obter_recebimentos_cartao(tipo_cartao=None):
    """
    Obtém recebimentos pendentes de cartão de crédito.
    Args:
        tipo_cartao: 'MULVI', 'GETNET' ou None para todos
    """
    df = obter_recebimentos_pendentes()
    if df.empty:
        return df
    
    # Filtra apenas pendentes
    df = df[df['status'] == 'pendente'] if 'status' in df.columns else df
    
    # Filtra cartões
    df = df[df['origem_recebimento'].str.contains('Cartão de crédito', case=False, na=False)]
    
    # Filtra tipo específico se solicitado
    if tipo_cartao:
        df = df[df['origem_recebimento'].str.contains(tipo_cartao, case=False, na=False)]
    
    return df

def obter_recebimentos_ipes():
    """
    Obtém apenas recebimentos pendentes do convênio IPES.
    Usado na aba IPES.
    """
    df = obter_recebimentos_pendentes()
    if df.empty:
        return df
    
    # Filtra apenas pendentes
    df = df[df['status'] == 'pendente'] if 'status' in df.columns else df
    
    # Filtra apenas IPES
    df = df[df['origem_recebimento'].str.contains('IPES', case=False, na=False)]
    
    return df

def obter_dados_cartao(tipo_cartao):
    """
    Obtém dados importados do cartão (MULVI ou GETNET) com status pendente.
    Lê o arquivo pickle diretamente para garantir a ordem original.
    """
    try:
        caminho_arquivo = f'data/credito_{tipo_cartao.lower()}.pkl'
        if not os.path.exists(caminho_arquivo):
            return pd.DataFrame()

        # Carrega o arquivo original diretamente
        df_original = pd.read_pickle(caminho_arquivo)
        if df_original.empty:
            return pd.DataFrame()

        # Adiciona o índice original como uma coluna ANTES de filtrar
        df_com_indice = df_original.reset_index().rename(columns={'index': 'indice_arquivo'})

        # Adiciona a coluna 'status' se não existir
        if 'status' not in df_com_indice.columns:
            df_com_indice['status'] = 'pendente'

        # Filtra apenas as linhas com status 'pendente'
        df_pendentes = df_com_indice[df_com_indice['status'] == 'pendente'].copy()

        # Filtros adicionais para GETNET
        if tipo_cartao.upper() == 'GETNET' and not df_pendentes.empty:
            if 'LANÇAMENTO' in df_pendentes.columns:
                df_pendentes = df_pendentes[~df_pendentes['LANÇAMENTO'].str.contains('saldo|débito', case=False, na=False)]
            if 'VALOR LÍQUIDO' in df_pendentes.columns:
                df_pendentes['VALOR LÍQUIDO'] = pd.to_numeric(df_pendentes['VALOR LÍQUIDO'], errors='coerce')
                df_pendentes.dropna(subset=['VALOR LÍQUIDO'], inplace=True)
                df_pendentes = df_pendentes[df_pendentes['VALOR LÍQUIDO'] > 0]

        return df_pendentes

    except Exception as e:
        print(f"Erro fatal em obter_dados_cartao: {e}")
        return pd.DataFrame()

def obter_dados_ipes():
    """
    Obtém dados de pagamentos IPES com status pendente, preservando o índice original.
    """
    try:
        caminho_arquivo = 'data/convenio_ipes.pkl' 
        if not os.path.exists(caminho_arquivo):
            return pd.DataFrame()

        df_original = pd.read_pickle(caminho_arquivo)
        if df_original.empty:
            return df_original

        # Adiciona o índice original como uma coluna ANTES de filtrar
        df_com_indice = df_original.reset_index().rename(columns={'index': 'indice_arquivo'})

        # Garante que a coluna 'status' exista
        if 'status' not in df_com_indice.columns:
            df_com_indice['status'] = 'pendente'
        
        # Retorna apenas os pagamentos que ainda estão pendentes
        df_pendentes = df_com_indice[df_com_indice['status'] == 'pendente'].copy()
        
        return df_pendentes

    except Exception as e:
        print(f"Erro ao carregar dados do IPES: {e}")
        return pd.DataFrame()

# ========== FUNÇÕES DE PROCESSAMENTO ==========

def registrar_baixa_convenio(ids_pendentes, data_recebimento, conta_destino, valor_baixado=None):
    """
    Registra baixa de convênios (usado na aba GERAL).
    Cria UMA entrada de movimentação para o valor baixado, mas baixa todos os recebimentos selecionados.
    """
    try:
        # Carrega arquivo de pendentes
        df_pendentes = pd.read_pickle(CAMINHO_PENDENTES)

        # Filtra recebimentos selecionados
        recebimentos_baixados = df_pendentes[df_pendentes['id_pendencia'].isin(ids_pendentes)]

        if recebimentos_baixados.empty:
            return False, f"Nenhum recebimento encontrado com os IDs: {ids_pendentes}"

        print(f"Encontrados {len(recebimentos_baixados)} recebimentos para baixar")

        # Carrega arquivo de movimentação
        if os.path.exists(CAMINHO_MOVIMENTACAO):
            df_movimentacao = pd.read_pickle(CAMINHO_MOVIMENTACAO)
        else:
            df_movimentacao = pd.DataFrame()

        # Calcula valor total dos recebimentos selecionados
        valor_total = recebimentos_baixados['valor_pendente'].sum()
        valor_para_conta = valor_baixado if valor_baixado is not None else valor_total

        # Cria UMA entrada de movimentação para o valor baixado
        nova_entrada = {
            'data_cadastro': pd.to_datetime(data_recebimento),
            'paciente': ', '.join(recebimentos_baixados['paciente'].astype(str).unique()[:3]) + ('...' if len(recebimentos_baixados['paciente'].unique()) > 3 else ''),
            'medico': '',
            'forma_pagamento': recebimentos_baixados['origem_recebimento'].iloc[0] if len(recebimentos_baixados) > 0 else '',
            'convenio': recebimentos_baixados['origem_recebimento'].iloc[0] if len(recebimentos_baixados) > 0 else '',
            'servicos': '',
            'origem': recebimentos_baixados['origem'].iloc[0] if 'origem' in recebimentos_baixados.columns and len(recebimentos_baixados) > 0 else 'RECEBIMENTO',
            'pago': float(valor_para_conta),
            'conta': conta_destino,
            'total': float(valor_para_conta),
            'a_pagar': 0,
            'desconto': 0
        }

        # Adiciona a nova entrada ao DataFrame de movimentação
        df_nova_entrada = pd.DataFrame([nova_entrada])
        if not df_movimentacao.empty:
            df_movimentacao = pd.concat([df_movimentacao, df_nova_entrada], ignore_index=True)
        else:
            df_movimentacao = df_nova_entrada

        # Salva movimentação atualizada
        df_movimentacao.to_pickle(CAMINHO_MOVIMENTACAO)
        print(f"Movimentação salva com {len(df_movimentacao)} registros totais")

        # Atualiza status para 'baixado'
        df_pendentes.loc[df_pendentes['id_pendencia'].isin(ids_pendentes), 'status'] = 'baixado'
        df_pendentes.to_pickle(CAMINHO_PENDENTES)
        print(f"Status atualizado para 'baixado' em {len(ids_pendentes)} registros")

        return True, f"✅ Baixa registrada! {len(recebimentos_baixados)} recebimento(s) - Valor baixado: R$ {valor_para_conta:,.2f}"

    except Exception as e:
        print(f"ERRO na baixa: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, f"Erro ao registrar baixa: {str(e)}"

def registrar_conciliacao_cartao(ids_pendentes, indices_cartao, tipo_cartao, conta_destino, baixa_parcial=False, valores_parciais=[], parcela_antiga=False):
    """
    Registra conciliação entre recebimentos e transações de cartão.
    IMPORTANTE: indices_cartao são os índices do arquivo original.
    """
    try:
        print(f"\n=== INÍCIO CONCILIAÇÃO {tipo_cartao} ===")
        print(f"IDs pendentes recebidos: {ids_pendentes}")
        print(f"Índices do arquivo recebidos: {indices_cartao}")
        print(f"Parcela antiga: {parcela_antiga}")
        
        # Carrega arquivos
        df_pendentes = pd.read_pickle(CAMINHO_PENDENTES)
        
        caminho_cartao = f'data/credito_{tipo_cartao.lower()}.pkl'
        if not os.path.exists(caminho_cartao):
            return False, f"Arquivo de cartão {tipo_cartao} não encontrado."
        
        df_cartao = pd.read_pickle(caminho_cartao)
        print(f"Total de transações no arquivo {tipo_cartao}: {len(df_cartao)}")
        
        # Adiciona status se não existir
        if 'status' not in df_cartao.columns:
            df_cartao['status'] = 'pendente'
        
        print(f"Transações pendentes: {len(df_cartao[df_cartao['status'] == 'pendente'])}")
        
        if os.path.exists(CAMINHO_MOVIMENTACAO):
            df_movimentacao = pd.read_pickle(CAMINHO_MOVIMENTACAO)
        else:
            df_movimentacao = pd.DataFrame()
        
        # Filtra dados selecionados
        if not parcela_antiga:
            recebimentos = df_pendentes[df_pendentes['id_pendencia'].isin(ids_pendentes)]
        else:
            recebimentos = pd.DataFrame()  # Para parcelas antigas, não há recebimentos
        
        # Usa loc com os índices do arquivo original
        try:
            transacoes = df_cartao.loc[indices_cartao]
            print(f"Transações selecionadas: {len(transacoes)}")
                                
        except Exception as e:
            print(f"Erro ao selecionar transações: {e}")
            return False, f"Erro ao selecionar transações: índices inválidos"
        
        # NOVO: Verificação ajustada para parcelas antigas
        if (not parcela_antiga and recebimentos.empty) or transacoes.empty:
            return False, "Dados selecionados não encontrados."
        
        # Calcula valores
        if baixa_parcial:
            # Para baixa parcial, usa o valor bruto da transação
            valor_bruto = float(transacoes['ValorBruto'].sum() if tipo_cartao.upper() == 'MULVI' else transacoes['VALOR DA PARCELA'].sum())
        elif parcela_antiga:
            # Para parcelas antigas, usa o valor líquido como "bruto" (sem taxa)
            valor_bruto = float(transacoes['ValorLiquido'].sum() if tipo_cartao.upper() == 'MULVI' else transacoes['VALOR LÍQUIDO'].sum())
        else:
            # Para baixa total, usa o valor total do recebimento pendente
            valor_bruto = float(recebimentos['valor_pendente'].sum())
        
        # Determina coluna de valor líquido baseado no tipo de cartão
        if tipo_cartao.upper() == 'MULVI':
            if 'ValorLiquido' in transacoes.columns:
                valor_liquido = pd.to_numeric(transacoes['ValorLiquido'], errors='coerce').fillna(0).sum()
            else:
                return False, "Coluna ValorLiquido não encontrada"
            
            if 'Data_Lançamento' in transacoes.columns:
                data_recebimento = pd.to_datetime(transacoes['Data_Lançamento']).max()
            else:
                data_recebimento = pd.Timestamp.now()
                
        else:  # GETNET
            if 'VALOR LÍQUIDO' in transacoes.columns:
                valor_liquido = pd.to_numeric(transacoes['VALOR LÍQUIDO'], errors='coerce').fillna(0).sum()
            else:
                return False, "Coluna VALOR LÍQUIDO não encontrada"
            
            if 'DATA DE VENCIMENTO' in transacoes.columns:
                data_recebimento = pd.to_datetime(transacoes['DATA DE VENCIMENTO']).max()
            else:
                data_recebimento = pd.Timestamp.now()
        
        valor_liquido = float(valor_liquido)
        taxa = float(valor_bruto - valor_liquido) if not parcela_antiga else 0.0  # Sem taxa para parcelas antigas
        
        print(f"\nVALORES CALCULADOS:")
        print(f"  Valor Bruto: R$ {valor_bruto:.2f}")
        print(f"  Valor Líquido: R$ {valor_liquido:.2f}")
        print(f"  Taxa: R$ {taxa:.2f}")
        
        # Cria entradas de movimentação
        novas_movimentacoes = []
        
        # ENTRADA 1: Valor Líquido recebido (sempre positivo, sem bruto para parcelas antigas)
        entrada_liquido = {
            'data_cadastro': pd.to_datetime(data_recebimento),
            'paciente': 'PARCELA ANTIGA' if parcela_antiga else ', '.join(recebimentos['paciente'].unique()[:3]) + ('...' if len(recebimentos['paciente'].unique()) > 3 else ''),
            'medico': '',
            'forma_pagamento': f'RECEBIMENTO CARTÃO {tipo_cartao.upper()}',
            'convenio': f'Cartão {tipo_cartao.upper()}',
            'servicos': 'Recebimento de Parcela Antiga' if parcela_antiga else 'Recebimento de Cartão de Crédito',
            'origem': f'CONCILIACAO_{tipo_cartao.upper()}',
            'pago': valor_liquido,  # Sempre usa valor líquido
            'conta': conta_destino,
            'total': valor_liquido,
            'a_pagar': 0,
            'desconto': 0
        }
        novas_movimentacoes.append(pd.DataFrame([entrada_liquido]))
        print(f"  Entrada na conta {conta_destino}: R$ {valor_liquido:.2f}")
        
        # ENTRADA 2: Taxa cobrada (apenas se não for parcela antiga)
        if not parcela_antiga and abs(taxa) > 0.01:
            entrada_taxa = {
                'data_cadastro': pd.to_datetime(data_recebimento),
                'paciente': 'DESPESA FINANCEIRA',
                'medico': '',
                'forma_pagamento': f'TAXA CARTÃO {tipo_cartao.upper()}',
                'convenio': '',
                'servicos': f'Taxa sobre recebimento - {tipo_cartao.upper()}',
                'origem': f'TAXA_{tipo_cartao.upper()}',
                'pago': -abs(taxa),
                'conta': conta_destino,
                'total': abs(taxa),
                'a_pagar': 0,
                'desconto': 0
            }
            novas_movimentacoes.append(pd.DataFrame([entrada_taxa]))
            print(f"  Taxa debitada da conta {conta_destino}: R$ {abs(taxa):.2f}")
        
        # Atualiza movimentação
        df_movimentacao = pd.concat([df_movimentacao] + novas_movimentacoes, ignore_index=True)
        df_movimentacao.to_pickle(CAMINHO_MOVIMENTACAO)
        
        if not parcela_antiga:
            # Processar baixa parcial ou total apenas se não for parcela antiga
            if baixa_parcial and valores_parciais:
                for i, id_pend in enumerate(ids_pendentes):
                    idx = df_pendentes[df_pendentes['id_pendencia'] == id_pend].index[0]
                    valor_parcial = valores_parciais[i] if i < len(valores_parciais) else 0.0
                    df_pendentes.loc[idx, 'valor_residual'] -= valor_parcial
                    if df_pendentes.loc[idx, 'valor_residual'] <= 0:
                        df_pendentes.loc[idx, 'status'] = 'baixado'
            else:
                df_pendentes.loc[df_pendentes['id_pendencia'].isin(ids_pendentes), 'status'] = 'baixado'
                
        df_pendentes.to_pickle(CAMINHO_PENDENTES)
        
        # CORREÇÃO CRÍTICA: Atualiza status das transações usando iloc
        
        print(f"Atualizando status das transações nos índices: {indices_cartao}")

        # Carrega o arquivo original NOVAMENTE para garantir que não há dados em cache
        df_cartao_para_salvar = pd.read_pickle(caminho_cartao)

        # Adiciona a coluna 'status' se ela não existir no arquivo original
        if 'status' not in df_cartao_para_salvar.columns:
            df_cartao_para_salvar['status'] = 'pendente'

        # NOVO: Reseta os índices para garantir que sejam 0,1,2,... (padrão)
        df_cartao_para_salvar = df_cartao_para_salvar.reset_index(drop=True)

        for idx in indices_cartao:
            # Verifica se o índice é válido
            if idx < len(df_cartao_para_salvar):
                # Usa .loc para definir o valor baseado no índice
                df_cartao_para_salvar.loc[idx, 'status'] = 'baixado'
                print(f"  Índice {idx} do arquivo original marcado como 'baixado'.")
            else:
                print(f"  AVISO: Índice {idx} está fora do alcance do arquivo original. Ignorando.")

        # Salva o DataFrame modificado
        df_cartao_para_salvar.to_pickle(caminho_cartao)
        
        print(f"\n✅ Conciliação concluída com sucesso")
        print(f"=== FIM CONCILIAÇÃO ===\n")
        
        msg = f"Conciliação realizada! Valor: R$ {valor_liquido:.2f}"
        if parcela_antiga:
            msg += " (Parcela Antiga)"
        else:
            msg += f", Taxa: R$ {abs(taxa):.2f}"
        return True, msg
        
    except Exception as e:
        import traceback
        print(f"\n❌ ERRO na conciliação: {str(e)}")
        traceback.print_exc()
        return False, f"Erro na conciliação: {str(e)}"

def registrar_conciliacao_ipes(ids_pendentes, indices_ipes, conta_destino, valor_pago=None):
    """
    Registra conciliação entre recebimentos e pagamentos IPES.
    valor_pago: valor a ser registrado na movimentação (lado direito da tela).
    """
    try:
        print(f"\n=== INÍCIO CONCILIAÇÃO IPES ===")
        print(f"IDs pendentes recebidos: {ids_pendentes}")
        print(f"Índices do arquivo IPES recebidos: {indices_ipes}")

        # Carrega arquivos
        df_pendentes = pd.read_pickle(CAMINHO_PENDENTES)
        caminho_ipes = 'data/convenio_ipes.pkl'
        df_ipes_original = pd.read_pickle(caminho_ipes)
        
        if os.path.exists(CAMINHO_MOVIMENTACAO):
            df_movimentacao = pd.read_pickle(CAMINHO_MOVIMENTACAO)
        else:
            df_movimentacao = pd.DataFrame()
        
        # Filtra dados selecionados
        recebimentos = df_pendentes[df_pendentes['id_pendencia'].isin(ids_pendentes)]
        pagamentos = df_ipes_original.iloc[indices_ipes] # Usa .iloc nos índices corretos
        
        print(f"Transações IPES selecionadas: {len(pagamentos)}")
        for idx, row in pagamentos.iterrows():
             print(f"  Índice {idx}: Valor = {row.get('valor', 'N/A')}")

        if recebimentos.empty or pagamentos.empty:
            return False, "Dados selecionados não encontrados."
        
        # Calcula valores
        valor_pendente = recebimentos['valor_pendente'].sum()
        if valor_pago is None:
            valor_pago = pagamentos['valor'].sum()
        data_recebimento = date.today()
        
        # Cria entrada de movimentação (valor_pago é o valor da direita)
        nova_entrada = pd.DataFrame([{
            'data_cadastro': pd.to_datetime(data_recebimento),
            'paciente': ', '.join(recebimentos['paciente'].unique()),
            'servicos': 'Recebimento Convênio IPES',
            'forma_pagamento': 'CONVÊNIO IPES',
            'convenio': 'IPES',
            'origem': 'CONCILIACAO_IPES',
            'pago': valor_pago,
            'conta': conta_destino,
            'total': valor_pago,
            'a_pagar': 0,
            'desconto': 0
        }])
        
        # Atualiza movimentação
        df_movimentacao = pd.concat([df_movimentacao, nova_entrada], ignore_index=True)
        df_movimentacao.to_pickle(CAMINHO_MOVIMENTACAO)
        
        # Atualiza status dos recebimentos
        df_pendentes.loc[df_pendentes['id_pendencia'].isin(ids_pendentes), 'status'] = 'baixado'
        df_pendentes.to_pickle(CAMINHO_PENDENTES)
        
        # Atualiza status dos pagamentos IPES no arquivo original
        if 'status' not in df_ipes_original.columns:
            df_ipes_original['status'] = 'pendente'
        df_ipes_original.loc[indices_ipes, 'status'] = 'baixado'
        df_ipes_original.to_pickle(caminho_ipes)
        print(f"Status dos pagamentos IPES nos índices {indices_ipes} atualizado para 'baixado'.")

        # Salva diferença se houver
        if abs(valor_pago - valor_pendente) > 0.01:
            salvar_diferenca_baixa_ipes(data_recebimento, valor_pendente, valor_pago)

        print("✅ Conciliação IPES concluída com sucesso!")
        return True, f"Conciliação IPES realizada! Valor recebido: R$ {valor_pago:,.2f}"
        
    except Exception as e:
        import traceback
        print(f"\n❌ ERRO na conciliação IPES: {str(e)}")
        traceback.print_exc()
        return False, f"Erro na conciliação IPES: {str(e)}"


def salvar_diferenca_baixa(data_baixa, valor_original, valor_baixado):
    """
    Salva diferença de baixa em arquivo pkl.
    """
    caminho_arquivo = 'data/diferencas_baixa_convenios.pkl'
    
    # Cria DataFrame se arquivo não existir
    if not os.path.exists(caminho_arquivo):
        df_diferencas = pd.DataFrame(columns=['data_baixa', 'valor_original', 'valor_baixado', 'diferenca'])
    else:
        df_diferencas = pd.read_pickle(caminho_arquivo)
    
    # Adiciona nova linha
    diferenca = valor_baixado - valor_original
    nova_linha = {
        'data_baixa': data_baixa,
        'valor_original': valor_original,
        'valor_baixado': valor_baixado,
        'diferenca': diferenca
    }
    df_diferencas = pd.concat([df_diferencas, pd.DataFrame([nova_linha])], ignore_index=True)
    
    # Salva
    df_diferencas.to_pickle(caminho_arquivo)

def salvar_diferenca_baixa_ipes(data_baixa, valor_original, valor_baixado):
    """
    Salva diferença de baixa IPES em arquivo pkl.
    """
    caminho_arquivo = 'data/diferencas_baixa_ipes.pkl'
    if not os.path.exists(caminho_arquivo):
        df_diferencas = pd.DataFrame(columns=['data_baixa', 'valor_original', 'valor_baixado', 'diferenca'])
    else:
        df_diferencas = pd.read_pickle(caminho_arquivo)
    diferenca = valor_baixado - valor_original
    nova_linha = {
        'data_baixa': data_baixa,
        'valor_original': valor_original,
        'valor_baixado': valor_baixado,
        'diferenca': diferenca
    }
    df_diferencas = pd.concat([df_diferencas, pd.DataFrame([nova_linha])], ignore_index=True)
    df_diferencas.to_pickle(caminho_arquivo)

# ========== FUNÇÕES AUXILIARES ==========

def obter_contas_disponiveis():
    """Retorna lista de contas disponíveis para movimentação."""
    # Importa do módulo centralizado
    from components.contas import obter_lista_contas
    return obter_lista_contas()