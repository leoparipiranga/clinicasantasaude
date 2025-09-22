import pandas as pd
import pickle
import os
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from components.importacao import carregar_dados_atendimentos
from components.functions import salvar_dados

CAMINHO_PENDENTES = 'data/recebimentos_pendentes.pkl'
CAMINHO_MOVIMENTACAO = 'data/movimentacao_contas.pkl'
CAMINHO_IPES_CONSOLIDADO = 'data/ipes_consolidado.pkl'

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
    if os.path.exists(CAMINHO_IPES_CONSOLIDADO):
        df = pd.read_pickle(CAMINHO_IPES_CONSOLIDADO)
    else:
        df = pd.DataFrame()

    if df.empty:
        return df
    
    # Filtra apenas pendentes
    df = df[df['status_conciliacao'] == 'pendente'] if 'status_conciliacao' in df.columns else df
        
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
        df_com_indice = df_original.copy()
        df_com_indice['indice_arquivo'] = df_com_indice.index.astype('int64')

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
        if 'status_conciliacao' not in df_com_indice.columns:
            df_com_indice['status_conciliacao'] = 'pendente'

        # Retorna apenas os pagamentos que ainda estão pendentes
        df_pendentes = df_com_indice[df_com_indice['status_conciliacao'] == 'pendente'].copy()

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

        # Garante coluna 'indice_arquivo' com valores derivados do index atual (sempre em int)
        if 'indice_arquivo' not in df_cartao_para_salvar.columns:
            df_cartao_para_salvar['indice_arquivo'] = df_cartao_para_salvar.index.astype('int64')
        else:
            # normaliza tipo por precaução
            df_cartao_para_salvar['indice_arquivo'] = df_cartao_para_salvar['indice_arquivo'].astype('int64')

        # Marca linhas comparando valores inteiros (robusto a diferenças de index labels)
        for original_idx in indices_cartao:
            try:
                oid = int(original_idx)
            except:
                print(f"  AVISO: índice recebido inválido: {original_idx}. Pulando.")
                continue
            mask = df_cartao_para_salvar['indice_arquivo'] == oid
            if mask.any():
                df_cartao_para_salvar.loc[mask, 'status'] = 'baixado'
                print(f"  Índice original {oid} marcado como 'baixado' (via 'indice_arquivo').")
            else:
                # fallback: comparar com label do índice
                if oid in df_cartao_para_salvar.index:
                    df_cartao_para_salvar.loc[oid, 'status'] = 'baixado'
                    print(f"  Índice {oid} marcado por label do índice como 'baixado' (fallback).")
                else:
                    print(f"  AVISO: Índice original {oid} não encontrado. Ignorando.")

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
    Atualiza status_conciliacao baseado em data/paciente dos recebimentos selecionados.
    """
    try:
        print(f"\n=== INÍCIO CONCILIAÇÃO IPES ===")
        print(f"IDs pendentes recebidos: {ids_pendentes}")
        print(f"Índices do arquivo IPES recebidos: {indices_ipes}")

        # Carrega arquivos
        if os.path.exists(CAMINHO_IPES_CONSOLIDADO):
            df_ipes_consol = pd.read_pickle(CAMINHO_IPES_CONSOLIDADO)
        else:
            df_ipes_consol = pd.DataFrame()

        # NOVO: Carrega também o arquivo convenio_ipes.pkl para atualizar status
        caminho_ipes_pag = 'data/convenio_ipes.pkl'
        if os.path.exists(caminho_ipes_pag):
            df_ipes_pag = pd.read_pickle(caminho_ipes_pag)
        else:
            df_ipes_pag = pd.DataFrame()

        if os.path.exists(CAMINHO_MOVIMENTACAO):
            df_movimentacao = pd.read_pickle(CAMINHO_MOVIMENTACAO)
        else:
            df_movimentacao = pd.DataFrame()

        if df_ipes_consol.empty:
            return False, "Arquivo ipes_consolidado vazio ou não encontrado."

        # Filtra recebimentos selecionados do consolidado usando os ids_pendentes
        recebimentos = df_ipes_consol[df_ipes_consol['id_pendencia'].isin(ids_pendentes)] if ids_pendentes else pd.DataFrame()
        
        # Seleciona pagamentos do IPES usando indices_ipes
        pagamentos = pd.DataFrame()
        if indices_ipes and not df_ipes_pag.empty:
            if 'indice_arquivo' in df_ipes_pag.columns:
                pagamentos = df_ipes_pag[df_ipes_pag['indice_arquivo'].isin(indices_ipes)].copy()
            else:
                try:
                    pagamentos = df_ipes_pag.iloc[indices_ipes].copy()
                except Exception:
                    pagamentos = pd.DataFrame()

        print(f"Recebimentos selecionados (consolidado): {len(recebimentos)}")
        print(f"Pagamentos IPES selecionados: {len(pagamentos)}")

        if recebimentos.empty:
            return False, "Nenhum recebimento encontrado para os IDs fornecidos."

        if pagamentos.empty:
            return False, "Nenhum pagamento IPES encontrado para os índices fornecidos."

        # Calcula valores
        valor_pendente = recebimentos['valor'].sum()
        if valor_pago is None:
            # soma valores dos pagamentos selecionados
            if 'valor_exec' in pagamentos.columns:
                valor_pago = pagamentos['valor_exec'].sum()
            elif 'valor' in pagamentos.columns:
                valor_pago = pagamentos['valor'].sum()
            else:
                valor_pago = 0.0
        data_recebimento = date.today()

        # Cria entrada de movimentação
        pacientes_unicos = recebimentos['paciente'].unique()
        pacientes_str = ', '.join(pacientes_unicos[:3])
        if len(pacientes_unicos) > 3:
            pacientes_str += '...'

        nova_entrada = pd.DataFrame([{
            'data_cadastro': pd.to_datetime(data_recebimento),
            'paciente': pacientes_str,
            'servicos': 'Recebimento Convênio IPES',
            'forma_pagamento': 'CONVÊNIO IPES',
            'convenio': 'IPES',
            'origem': 'CONCILIACAO_IPES',
            'pago': float(valor_pago),
            'conta': conta_destino,
            'total': float(valor_pago),
            'a_pagar': 0,
            'desconto': 0,
            'medico': '',
            'categoria_pagamento': '',
            'subcategoria_pagamento': '',
            'observacoes': ''
        }])

        # Atualiza movimentação
        df_movimentacao = pd.concat([df_movimentacao, nova_entrada], ignore_index=True)
        os.makedirs(os.path.dirname(CAMINHO_MOVIMENTACAO) or '.', exist_ok=True)
        df_movimentacao.to_pickle(CAMINHO_MOVIMENTACAO)

        # CORREÇÃO PRINCIPAL: Atualiza status_conciliacao baseado em data/paciente dos recebimentos selecionados
        recebimentos_grouped = recebimentos.groupby(['data_cadastro', 'paciente']).size().reset_index()
        
        for _, grupo in recebimentos_grouped.iterrows():
            data_grupo = grupo['data_cadastro']
            paciente_grupo = grupo['paciente']
            
            # Atualiza TODAS as linhas do consolidado que correspondem a essa data/paciente
            mask_atualizar_consol = (
                (df_ipes_consol['data_cadastro'].dt.date == pd.to_datetime(data_grupo).date()) &
                (df_ipes_consol['paciente'] == paciente_grupo) &
                (df_ipes_consol['status_conciliacao'] == 'pendente')
            )
            
            linhas_atualizadas_consol = mask_atualizar_consol.sum()
            if linhas_atualizadas_consol > 0:
                df_ipes_consol.loc[mask_atualizar_consol, 'status_conciliacao'] = 'baixado'
                print(f"Consolidado: Atualizadas {linhas_atualizadas_consol} linhas para paciente {paciente_grupo} em {data_grupo}")

        # CORREÇÃO: Atualiza o arquivo convenio_ipes.pkl usando DOIS métodos
        if not df_ipes_pag.empty:
            # Adiciona coluna status_conciliacao se não existir
            if 'status_conciliacao' not in df_ipes_pag.columns:
                df_ipes_pag['status_conciliacao'] = 'pendente'
            
            # MÉTODO 1: Atualiza por índices específicos (mais direto)
            if indices_ipes:
                print(f"Método 1: Atualizando por índices específicos: {indices_ipes}")
                for idx in indices_ipes:
                    try:
                        if 'indice_arquivo' in df_ipes_pag.columns:
                            mask_idx = df_ipes_pag['indice_arquivo'] == idx
                            if mask_idx.any():
                                df_ipes_pag.loc[mask_idx, 'status_conciliacao'] = 'baixado'
                                print(f"  Índice {idx} atualizado via indice_arquivo")
                        else:
                            # Fallback: usa índice direto
                            if idx < len(df_ipes_pag):
                                df_ipes_pag.iloc[idx, df_ipes_pag.columns.get_loc('status_conciliacao')] = 'baixado'
                                print(f"  Índice {idx} atualizado via iloc")
                    except Exception as e:
                        print(f"  Erro ao atualizar índice {idx}: {e}")
            
            # MÉTODO 2: Também atualiza por data/paciente (redundância para garantir)
            for _, grupo in recebimentos_grouped.iterrows():
                data_grupo = grupo['data_cadastro']
                paciente_grupo = grupo['paciente']
                
                # Mapeia nome do paciente (pode ser beneficiario_nome no arquivo ipes)
                coluna_paciente_ipes = 'paciente'
                if 'beneficiario_nome' in df_ipes_pag.columns and 'paciente' not in df_ipes_pag.columns:
                    coluna_paciente_ipes = 'beneficiario_nome'
                elif 'paciente' in df_ipes_pag.columns:
                    coluna_paciente_ipes = 'paciente'
                
                if coluna_paciente_ipes in df_ipes_pag.columns and 'data_cadastro' in df_ipes_pag.columns:
                    try:
                        # Converte ambas as datas para o mesmo formato
                        df_ipes_pag['data_cadastro'] = pd.to_datetime(df_ipes_pag['data_cadastro'], errors='coerce')
                        
                        mask_atualizar_pag = (
                            (df_ipes_pag['data_cadastro'].dt.date == pd.to_datetime(data_grupo).date()) &
                            (df_ipes_pag[coluna_paciente_ipes].astype(str) == str(paciente_grupo)) &
                            (df_ipes_pag['status_conciliacao'] == 'pendente')
                        )
                        
                        linhas_atualizadas_pag = mask_atualizar_pag.sum()
                        if linhas_atualizadas_pag > 0:
                            df_ipes_pag.loc[mask_atualizar_pag, 'status_conciliacao'] = 'baixado'
                            print(f"Método 2: Atualizadas {linhas_atualizadas_pag} linhas para paciente {paciente_grupo} em {data_grupo}")
                    except Exception as e:
                        print(f"Erro no método 2 para {paciente_grupo}: {e}")

        # Salva consolidado atualizado
        df_ipes_consol.to_pickle(CAMINHO_IPES_CONSOLIDADO)

        # NOVO: Salva também o arquivo convenio_ipes.pkl atualizado
        if not df_ipes_pag.empty:
            df_ipes_pag.to_pickle(caminho_ipes_pag)
            print("Arquivo convenio_ipes.pkl atualizado com novos status")

        # Salva diferença se houver
        if abs(float(valor_pago) - float(valor_pendente)) > 0.01:
            salvar_diferenca_baixa_ipes(data_recebimento, float(valor_pendente), float(valor_pago))

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

def calcular_taxa_bandeira(valor_bruto, bandeira, parcelas=1, modalidade=None):
    """Estima a taxa da operadora com base na bandeira e no número de parcelas."""
    b = (bandeira or "").strip().lower()
    is_debito = modalidade and modalidade.strip().lower().startswith('deb')
    
    # Taxas por bandeira (valores em %)
    if is_debito:
        taxas_debito = {'visa': 1.10, 'mastercard': 1.12, 'elo': 1.85}
        taxa = taxas_debito.get(b, 1.10)
        return valor_bruto * (taxa / 100)
    
    if b == 'visa':
        if parcelas == 1:
            taxa = 2.09
        elif 2 <= parcelas <= 6:
            taxa = 1.98
        else:  # 7-12 e acima
            taxa = 2.20
    elif b in ('mastercard', 'master card', 'master-card'):
        if parcelas == 1:
            taxa = 1.85
        elif 2 <= parcelas <= 6:
            taxa = 2.04
        else:
            taxa = 2.20
    elif b == 'elo':
        if parcelas == 1:
            taxa = 2.55
        elif 2 <= parcelas <= 6:
            taxa = 2.78
        else:
            taxa = 2.94
    elif b in ('amex', 'american express', 'americanexpress'):
        if parcelas == 1:
            taxa = 3.30
        elif 2 <= parcelas <= 6:
            taxa = 3.46
        else:
            taxa = 3.70
    else:
        # Fallback genérico
        if parcelas == 1:
            taxa = 2.00
        elif 2 <= parcelas <= 6:
            taxa = 2.00
        else:
            taxa = 2.00
    
    return valor_bruto * (taxa / 100)

def calcular_antecipacao_banco(
    valores_parcelas: list[float],
    taxa_antecipacao_mes: float,
    data_venda: date,
    datas_vencimento: list[date] = None
) -> dict:
    """
    Calcula a antecipação exatamente como o banco faz,
    com a opção de fornecer datas específicas de vencimento.
    """
    numero_parcelas = len(valores_parcelas)
    valor_liquido_pos_taxa = sum(valores_parcelas)
    
    # Antecipação no dia seguinte
    data_antecipacao = data_venda + timedelta(days=1)
    
    # Taxa diária (usando 30 dias)
    taxa_antecipacao_dia = (taxa_antecipacao_mes / 100) / 30
    
    total_desconto_antecipacao = 0.0
    parcelas_detalhe = []
    
    primeira_venc = None
    for i, valor_parcela_atual in enumerate(valores_parcelas, 1):
        # Usa datas fornecidas se existirem
        if datas_vencimento and len(datas_vencimento) >= i:
            vencimento_parcela = datas_vencimento[i-1]
        else:
            # Regra: primeira = data_venda + 31 dias; subsequentes = primeira + (i-1) meses
            if i == 1:
                primeira_venc = data_venda + timedelta(days=31)
                vencimento_parcela = primeira_venc
            else:
                if primeira_venc is None:
                    primeira_venc = data_venda + timedelta(days=31)
                vencimento_parcela = primeira_venc + relativedelta(months=(i-1))
        
        # Calcula dias para antecipação
        dias_para_antecipar = (vencimento_parcela - data_antecipacao).days
        
        # Aplica a fórmula do banco
        desconto_parcela = 0.0
        if dias_para_antecipar > 0:
            desconto_parcela = valor_parcela_atual * taxa_antecipacao_dia * dias_para_antecipar
        
        total_desconto_antecipacao += desconto_parcela
        
        parcelas_detalhe.append({
            "parcela": i,
            "vencimento": vencimento_parcela.strftime('%d/%m/%Y'),
            "valor_liquido": round(valor_parcela_atual, 2),
            "dias_antecipacao": dias_para_antecipar,
            "desconto": round(desconto_parcela, 2)
        })
    
    valor_liquido_final = valor_liquido_pos_taxa - total_desconto_antecipacao
    
    return {
        "valor_liquido_pos_taxa": round(valor_liquido_pos_taxa, 2),
        "total_desconto_antecipacao": round(total_desconto_antecipacao, 2),
        "valor_liquido_recebido": round(valor_liquido_final, 2),
        "detalhe_parcelas": parcelas_detalhe,
        "prazo_medio": calcular_prazo_medio(parcelas_detalhe)
    }

def calcular_prazo_medio(parcelas_detalhe):
    """Calcula o prazo médio baseado nas parcelas."""
    if not parcelas_detalhe:
        return 0
    
    soma_dias_ponderados = sum(p["dias_antecipacao"] for p in parcelas_detalhe)
    return round(soma_dias_ponderados / len(parcelas_detalhe))

def registrar_antecipacao_cartao(
    ids_rec, 
    indices_trans_arquivo, 
    cartao, 
    conta_destino,
    valor_bruto_total,
    taxa_operadora_total,
    taxa_antecipacao_total,
    valor_liquido_final,
    baixa_parcial=False,
    valores_parciais=None,
    parcela_antiga=False
):
    """
    Registra antecipação de cartão com taxas detalhadas.
    """
    try:
        print(f"\n=== INÍCIO ANTECIPAÇÃO {cartao} ===")
        print(f"IDs pendentes recebidos: {ids_rec}")
        print(f"Índices do arquivo recebidos: {indices_trans_arquivo}")
        print(f"Parcela antiga: {parcela_antiga}")
        
        data_atual = datetime.now()
        
        # Carrega arquivos
        df_pendentes = pd.read_pickle(CAMINHO_PENDENTES)
        
        caminho_cartao = f'data/credito_{cartao.lower()}.pkl'
        if not os.path.exists(caminho_cartao):
            return False, f"Arquivo de cartão {cartao} não encontrado."
        
        df_cartao = pd.read_pickle(caminho_cartao)
        print(f"Total de transações no arquivo {cartao}: {len(df_cartao)}")
        
        # Adiciona status se não existir
        if 'status' not in df_cartao.columns:
            df_cartao['status'] = 'pendente'
        
        print(f"Transações pendentes: {len(df_cartao[df_cartao['status'] == 'pendente'])}")
        
        if os.path.exists(CAMINHO_MOVIMENTACAO):
            df_movimentacao = pd.read_pickle(CAMINHO_MOVIMENTACAO)
        else:
            df_movimentacao = pd.DataFrame()
        
        # 1. Processa recebimentos (se não for parcela antiga)
        if not parcela_antiga and ids_rec:
            for i, id_rec in enumerate(ids_rec):
                mask = df_pendentes['id_pendencia'] == id_rec
                if mask.any():
                    if baixa_parcial and valores_parciais:
                        valor_baixado = valores_parciais[i]
                        valor_residual = df_pendentes.loc[mask, 'valor_pendente'].iloc[0] - valor_baixado
                        
                        if valor_residual > 0.01:
                            df_pendentes.loc[mask, 'valor_pendente'] = valor_residual
                        else:
                            df_pendentes.loc[mask, 'status'] = 'baixado'
                            df_pendentes.loc[mask, 'data_baixa'] = data_atual
                    else:
                        df_pendentes.loc[mask, 'status'] = 'baixado'
                        df_pendentes.loc[mask, 'data_baixa'] = data_atual
            
            # Salva recebimentos atualizados
            df_pendentes.to_pickle(CAMINHO_PENDENTES)
        
        # 2. Marca transações como processadas usando a mesma lógica da conciliação
        print(f"Atualizando status das transações nos índices: {indices_trans_arquivo}")

        # Carrega o arquivo original NOVAMENTE para garantir que não há dados em cache
        df_cartao_para_salvar = pd.read_pickle(caminho_cartao)

        # Adiciona a coluna 'status' se ela não existir no arquivo original
        if 'status' not in df_cartao_para_salvar.columns:
            df_cartao_para_salvar['status'] = 'pendente'

        # Reseta os índices para garantir que sejam 0,1,2,... (padrão)
        df_cartao_para_salvar = df_cartao_para_salvar.reset_index(drop=True)

        for idx in indices_trans_arquivo:
            # Verifica se o índice é válido
            if idx < len(df_cartao_para_salvar):
                # Usa .loc para definir o valor baseado no índice
                df_cartao_para_salvar.loc[idx, 'status'] = 'processado'
                df_cartao_para_salvar.loc[idx, 'data_processamento'] = data_atual
                print(f"  Índice {idx} do arquivo original marcado como 'processado'.")
            else:
                print(f"  AVISO: Índice {idx} está fora do alcance do arquivo original. Ignorando.")

        # Salva o DataFrame modificado
        df_cartao_para_salvar.to_pickle(caminho_cartao)
        
        # 3. Registra movimentações na conta
        novas_movimentacoes = []
        
        # ENTRADA 1: Valor Bruto recebido (entrada positiva)
        entrada_bruto = {
            'data_cadastro': pd.to_datetime(data_atual),
            'paciente': 'ANTECIPAÇÃO CARTÃO' if parcela_antiga else ', '.join(df_pendentes[df_pendentes['id_pendencia'].isin(ids_rec)]['paciente'].unique()[:3]) + ('...' if len(df_pendentes[df_pendentes['id_pendencia'].isin(ids_rec)]['paciente'].unique()) > 3 else ''),
            'medico': '',
            'forma_pagamento': f'ANTECIPAÇÃO CARTÃO {cartao.upper()}',
            'convenio': f'Cartão {cartao.upper()}',
            'servicos': f'Antecipação de Cartão de Crédito - {cartao.upper()}',
            'origem': f'ANTECIPACAO_{cartao.upper()}',
            'pago': valor_bruto_total,
            'conta': conta_destino,
            'total': valor_bruto_total,
            'a_pagar': 0,
            'desconto': 0
        }
        novas_movimentacoes.append(pd.DataFrame([entrada_bruto]))
        print(f"  Entrada na conta {conta_destino}: R$ {valor_bruto_total:.2f}")
        
        # ENTRADA 2: Taxa da operadora (saída negativa)
        if abs(taxa_operadora_total) > 0.01:
            entrada_taxa_operadora = {
                'data_cadastro': pd.to_datetime(data_atual),
                'paciente': 'DESPESA FINANCEIRA',
                'medico': '',
                'forma_pagamento': f'TAXA OPERADORA {cartao.upper()}',
                'convenio': '',
                'servicos': f'Taxa da Operadora - {cartao.upper()}',
                'origem': f'TAXA_OPERADORA_{cartao.upper()}',
                'pago': -abs(taxa_operadora_total),
                'conta': conta_destino,
                'total': abs(taxa_operadora_total),
                'a_pagar': 0,
                'desconto': 0
            }
            novas_movimentacoes.append(pd.DataFrame([entrada_taxa_operadora]))
            print(f"  Taxa operadora debitada da conta {conta_destino}: R$ {abs(taxa_operadora_total):.2f}")
        
        # ENTRADA 3: Taxa de antecipação (saída negativa)
        if abs(taxa_antecipacao_total) > 0.01:
            entrada_taxa_antecipacao = {
                'data_cadastro': pd.to_datetime(data_atual),
                'paciente': 'DESPESA FINANCEIRA',
                'medico': '',
                'forma_pagamento': f'TAXA ANTECIPAÇÃO {cartao.upper()}',
                'convenio': '',
                'servicos': f'Taxa de Antecipação - {cartao.upper()}',
                'origem': f'TAXA_ANTECIPACAO_{cartao.upper()}',
                'pago': -abs(taxa_antecipacao_total),
                'conta': conta_destino,
                'total': abs(taxa_antecipacao_total),
                'a_pagar': 0,
                'desconto': 0
            }
            novas_movimentacoes.append(pd.DataFrame([entrada_taxa_antecipacao]))
            print(f"  Taxa antecipação debitada da conta {conta_destino}: R$ {abs(taxa_antecipacao_total):.2f}")
        
        # Atualiza movimentação
        df_movimentacao = pd.concat([df_movimentacao] + novas_movimentacoes, ignore_index=True)
        df_movimentacao.to_pickle(CAMINHO_MOVIMENTACAO)
        
        print(f"\n✅ Antecipação concluída com sucesso")
        print(f"=== FIM ANTECIPAÇÃO ===\n")
        
        return True, f"Antecipação {cartao} registrada com sucesso! Valor líquido: R$ {valor_liquido_final:,.2f}"
        
    except Exception as e:
        import traceback
        print(f"\n❌ ERRO na antecipação: {str(e)}")
        traceback.print_exc()
        return False, f"Erro ao registrar antecipação: {str(e)}"