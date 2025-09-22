import re
import pdfplumber
import pandas as pd
from datetime import datetime
import os

def normalize_line(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()

RX_SEP1 = re.compile(r'N.? ?Guia ?Operad\.:\s*(\d+)\s+Benefici[áa]rio:\s*([0-9]+)\s*-\s*(.+)$', re.I)
RX_SEP2 = re.compile(r'Senha:\s*([0-9]+).*?Data\s+Solicit\.:\s*(\d{2}/\d{2}/\d{4})', re.I)

# Reconhece início de linha de tabela
RX_ROW_START = re.compile(r'^\s*\d+\s+\d{2}\s+\d+\s*-\s*', re.I)
# Reconhece final de linha completa (tem valor monetário no fim)
RX_MONEY_END = re.compile(r'R\$\s*[\d\.,]+\s*$', re.I)

def parse_row_buffer(buf: str):
    """
    Parser que trata casos onde "R$" se separa e vira apenas "$" com números espalhados
    """
    s = normalize_line(buf)

    # 1) Extrai seq, tabela, procedimento_codigo do início
    m_inicio = re.match(r'^\s*(\d+)\s+(\d{2})\s+(\d{8})', s)
    if not m_inicio:
        return None
    
    seq = int(m_inicio.group(1))
    tabela = m_inicio.group(2)
    proc_cod = m_inicio.group(3)
    
    # 2) Tenta extrair valor normal primeiro (R$ junto)
    m_valor = re.search(r'R\$\s*([\d\.,]+)', s)
    if m_valor:
        valor = float(m_valor.group(1).replace(".", "").replace(",", "."))
        return {
            "seq": seq,
            "tabela": tabela,
            "procedimento_codigo": proc_cod,
            "valor_exec": valor,
        }
    
    # 3) Se não achou "R$", procura por "$" isolado e reconstrói o valor
    m_cifrao = re.search(r'\$', s)
    if m_cifrao:
        # Pega tudo após o "$"
        parte_pos_cifrao = s[m_cifrao.end():]
        
        # Primeiro tenta encontrar vírgula e pegar números ao redor
        if ',' in parte_pos_cifrao:
            # Tem vírgula - pega números antes e depois da primeira vírgula
            pos_virgula = parte_pos_cifrao.find(',')
            antes_virgula = parte_pos_cifrao[:pos_virgula]
            depois_virgula = parte_pos_cifrao[pos_virgula+1:]
            
            nums_antes = re.findall(r'(\d)', antes_virgula)
            nums_depois = re.findall(r'(\d)', depois_virgula)
            
            if nums_antes and nums_depois:
                # Junta números antes e depois da vírgula
                parte_inteira = ''.join(nums_antes)
                parte_decimal = ''.join(nums_depois[:2])  # máximo 2 casas decimais
                valor_str = f"{parte_inteira},{parte_decimal}"
                valor = float(valor_str.replace(",", "."))
            else:
                return None
        else:
            # Sem vírgula - pega todos os números e assume últimos 2 são centavos
            nums = re.findall(r'(\d)', parte_pos_cifrao)
            
            if len(nums) >= 2:
                # Assume que os últimos 2 dígitos são centavos
                parte_inteira = ''.join(nums[:-2]) if len(nums) > 2 else '0'
                parte_decimal = ''.join(nums[-2:])
                valor_str = f"{parte_inteira},{parte_decimal}"
                valor = float(valor_str.replace(",", "."))
            elif len(nums) == 1:
                # Apenas um número, assume centavos
                valor = float("0.0" + nums[0])
            else:
                return None
        
        return {
            "seq": seq,
            "tabela": tabela,
            "procedimento_codigo": proc_cod,
            "valor_exec": valor,
        }
    
    # Se não encontrou nem "R$" nem "$", falha
    return None

def parse_pdf_text_as_table(pdf_path: str):
    """
    Extrai dados do PDF de convênio IPES e retorna DataFrame processado
    """
    registros = []
    falhas = []

    contexto = {
        "guia_operadora": None,
        "beneficiario_codigo": None,
        "beneficiario_nome": None,
        "senha": None,
        "data_solicitacao": None,
    }

    with pdfplumber.open(pdf_path) as pdf:
        for pidx, page in enumerate(pdf.pages, start=1):
            buffer = ""
            text = page.extract_text() or ""
            
            for raw in text.splitlines():
                linha = normalize_line(raw)

                # Separadores
                m1 = RX_SEP1.search(linha)
                if m1:
                    # Flush buffer antes de mudar contexto
                    if buffer.strip():
                        parsed = parse_row_buffer(buffer)
                        if parsed:
                            registros.append({**contexto, **parsed, "_pagina": pidx, "_linha": buffer})
                        else:
                            falhas.append({"_pagina": pidx, "linha": buffer})
                        buffer = ""
                    
                    contexto["guia_operadora"] = m1.group(1)
                    contexto["beneficiario_codigo"] = m1.group(2)
                    contexto["beneficiario_nome"] = m1.group(3).strip()
                    continue

                m2 = RX_SEP2.search(linha)
                if m2:
                    # Flush buffer antes de mudar contexto
                    if buffer.strip():
                        parsed = parse_row_buffer(buffer)
                        if parsed:
                            registros.append({**contexto, **parsed, "_pagina": pidx, "_linha": buffer})
                        else:
                            falhas.append({"_pagina": pidx, "linha": buffer})
                        buffer = ""
                    
                    contexto["senha"] = m2.group(1)
                    contexto["data_solicitacao"] = m2.group(2)
                    continue

                # Linhas da tabela - ajustar para detectar "$" isolado também
                if RX_ROW_START.match(linha) or buffer:
                    buffer = (buffer + " " + linha).strip() if buffer else linha
                    
                    # Se linha terminou (tem "R$" ou "$"), processa
                    if RX_MONEY_END.search(buffer) or re.search(r'\$', buffer):
                        parsed = parse_row_buffer(buffer)
                        if parsed:
                            registros.append({**contexto, **parsed, "_pagina": pidx, "_linha": buffer})
                        else:
                            falhas.append({"_pagina": pidx, "linha": buffer})
                        buffer = ""

            # Flush final da página
            if buffer.strip():
                parsed = parse_row_buffer(buffer)
                if parsed:
                    registros.append({**contexto, **parsed, "_pagina": pidx, "_linha": buffer})
                else:
                    falhas.append({"_pagina": pidx, "linha": buffer})

    df = pd.DataFrame(registros)
    df_falhas = pd.DataFrame(falhas)
    return df, df_falhas

# --- NOVO: função para extrair tabela de procedimentos (código + descrição) ---
def extrair_tabela_procedimentos(pdf_path: str):
    """
    Extrai somente pares (codigo_procedimento, descricao_procedimento) do PDF IPES.
    Retorna (df_procedimentos, df_falhas).
    """
    procedimentos = []
    falhas = []

    RX_PROC = re.compile(r'(?<!\d)(\d{8,9})(?!\d)\s*-\s*([^\n\r]+)', re.I)

    def extrair_descricao_por_caixa(descricao_bruta: str) -> str:
        # procura primeiro caractere alfabético minúsculo
        idx_lower = None
        for i, ch in enumerate(descricao_bruta):
            if ch.isalpha() and ch.islower():
                idx_lower = i
                break
        if idx_lower is not None:
            # recua até o último " - " antes do primeiro lowercase
            pos_sep = descricao_bruta.rfind(' - ', 0, idx_lower)
            if pos_sep != -1:
                desc = descricao_bruta[:pos_sep].strip()
            else:
                desc = descricao_bruta.split(' - ')[0].strip()
        else:
            desc = descricao_bruta.split(' - ')[0].strip()
        desc = re.sub(r'\s+', ' ', desc).strip()
        desc = re.sub(r'[\s\-\–_:]+$', '', desc).strip()
        return desc

    with pdfplumber.open(pdf_path) as pdf:
        for pidx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            buffer = ""
            for raw in text.splitlines():
                linha = normalize_line(raw)

                # acumula linhas que possam pertencer a um registro de procedimento
                if re.match(r'^\s*\d+\s+\d{2}\s+\d+', linha) or buffer:
                    buffer = (buffer + " " + linha).strip() if buffer else linha

                    # tenta encontrar padrão código - descrição no buffer
                    m = RX_PROC.search(buffer)
                    if m:
                        codigo = m.group(1)
                        descricao_bruta = m.group(2).strip()
                        descricao_limpa = extrair_descricao_por_caixa(descricao_bruta)
                        procedimentos.append({
                            'codigo_procedimento': str(codigo),
                            'descricao_procedimento': descricao_limpa,
                            'pagina': pidx,
                            'linha_original': buffer
                        })
                        buffer = ""
                else:
                    # linha isolada pode conter código - descrição
                    m2 = RX_PROC.search(linha)
                    if m2:
                        codigo = m2.group(1)
                        descricao_bruta = m2.group(2).strip()
                        descricao_limpa = extrair_descricao_por_caixa(descricao_bruta)
                        procedimentos.append({
                            'codigo_procedimento': str(codigo),
                            'descricao_procedimento': descricao_limpa,
                            'pagina': pidx,
                            'linha_original': linha
                        })
                    else:
                        # se linha tem muitos dígitos e traço pode ser contexto de beneficiário - capture como falha para revisão
                        if re.search(r'\d{6,}\s*-\s*', linha):
                            falhas.append({'pagina': pidx, 'linha': linha})

            # flush buffer final
            if buffer.strip():
                m = RX_PROC.search(buffer)
                if m:
                    codigo = m.group(1)
                    descricao_bruta = m.group(2).strip()
                    descricao_limpa = extrair_descricao_por_caixa(descricao_bruta)
                    procedimentos.append({
                        'codigo_procedimento': str(codigo),
                        'descricao_procedimento': descricao_limpa,
                        'pagina': pidx,
                        'linha_original': buffer
                    })
                else:
                    if buffer.strip():
                        falhas.append({'pagina': pidx, 'linha': buffer})
                buffer = ""

    df_proc = pd.DataFrame(procedimentos)
    df_falhas = pd.DataFrame(falhas)

    if not df_proc.empty:
        df_proc = df_proc.drop_duplicates(subset=['codigo_procedimento'], keep='first').reset_index(drop=True)
        df_proc = df_proc.sort_values('codigo_procedimento').reset_index(drop=True)

    return df_proc, df_falhas

def processar_pdf_convenio_ipes(uploaded_file):
    """
    Processa o arquivo PDF uploadado e retorna DataFrame formatado para o sistema
    """
    try:
        # Salva temporariamente o arquivo
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        # Processa o PDF
        df_raw, df_falhas = parse_pdf_text_as_table(tmp_path)

        # --- NOVO: extrai tabela de procedimentos e atualiza procedimentos.pkl ---
        try:
            df_proc_new, df_proc_falhas = extrair_tabela_procedimentos(tmp_path)
            caminho_proc = 'data/procedimentos.pkl'
            os.makedirs('data', exist_ok=True)
            if not df_proc_new.empty:
                if os.path.exists(caminho_proc):
                    try:
                        df_exist = pd.read_pickle(caminho_proc)
                        # concatena mantendo descrições existentes como prioridade
                        df_concat = pd.concat([df_exist, df_proc_new], ignore_index=True)
                        df_concat = df_concat.drop_duplicates(subset=['codigo_procedimento'], keep='first').reset_index(drop=True)
                        df_concat.to_pickle(caminho_proc)
                        df_proc_salvo = df_concat
                    except Exception:
                        # fallback: salva apenas os novos
                        df_proc_new.to_pickle(caminho_proc)
                        df_proc_salvo = df_proc_new
                else:
                    df_proc_new.to_pickle(caminho_proc)
                    df_proc_salvo = df_proc_new
            else:
                # arquivo existente ou vazio
                if os.path.exists(caminho_proc):
                    df_proc_salvo = pd.read_pickle(caminho_proc)
                else:
                    df_proc_salvo = pd.DataFrame(columns=['codigo_procedimento', 'descricao_procedimento'])
        except Exception:
            df_proc_salvo = pd.DataFrame(columns=['codigo_procedimento', 'descricao_procedimento'])

        # Remove arquivo temporário
        os.unlink(tmp_path)
        
        if df_raw.empty:
            return None, f"Nenhum dado extraído do PDF. Falhas: {len(df_falhas)}"
        
        # Converte para formato padrão do sistema
        df_processado = df_raw.copy()
        
        # Adiciona colunas necessárias
        df_processado['paciente'] = df_processado['beneficiario_nome']
        df_processado['convenio'] = 'IPES'
        df_processado['origem'] = 'CONVENIO_PDF'
        df_processado['valor'] = df_processado['valor_exec']
        
        # Converte data_solicitacao para datetime
        if 'data_solicitacao' in df_processado.columns:
            df_processado['data_cadastro'] = pd.to_datetime(df_processado['data_solicitacao'], format='%d/%m/%Y', errors='coerce')
        else:
            df_processado['data_cadastro'] = datetime.now()
        
        # Seleciona apenas colunas necessárias
        colunas_finais = [
            'data_cadastro', 'paciente', 'convenio', 'origem', 'valor',
            'guia_operadora', 'beneficiario_codigo', 'senha', 'seq', 
            'tabela', 'procedimento_codigo', 'valor_exec'
        ]
        
        df_final = df_processado[colunas_finais]
        df_final['status_conciliacao'] = 'pendente'
        
        # ETAPA 3: Adiciona coluna indice_paciente após o processamento
        if 'data_cadastro' in df_final.columns and 'paciente' in df_final.columns:
            df_final['data_cadastro'] = pd.to_datetime(df_final['data_cadastro'])
            df_final['indice_paciente'] = (
                df_final['data_cadastro'].dt.strftime('%Y-%m-%d') + '_' + 
                df_final['paciente'].astype(str)
            )

        # --- NOVO: adiciona coluna descricao via merge com procedimentos salvos ---
        try:
            caminho_proc = 'data/procedimentos.pkl'
            if os.path.exists(caminho_proc):
                df_proc_master = pd.read_pickle(caminho_proc)
            else:
                df_proc_master = pd.DataFrame(columns=['codigo_procedimento', 'descricao_procedimento'])

            # Garante tipos string para merge e remove espaços
            df_final['procedimento_codigo'] = df_final['procedimento_codigo'].astype(str).str.strip()
            df_proc_master['codigo_procedimento'] = df_proc_master['codigo_procedimento'].astype(str).str.strip()

            df_final = df_final.merge(
                df_proc_master[['codigo_procedimento', 'descricao_procedimento']],
                left_on='procedimento_codigo',
                right_on='codigo_procedimento',
                how='left'
            )
            # Renomeia coluna para 'descricao' esperada pelo sistema
            if 'descricao_procedimento' in df_final.columns:
                df_final.rename(columns={'descricao_procedimento': 'descricao'}, inplace=True)
            else:
                df_final['descricao'] = None

            # remove coluna auxiliar código duplicada
            if 'codigo_procedimento' in df_final.columns:
                df_final.drop(columns=['codigo_procedimento'], inplace=True)
        except Exception:
            df_final['descricao'] = None
        
        return df_final, f"PDF processado com sucesso! {len(df_final)} registros extraídos. Falhas: {len(df_falhas)}"
        
    except Exception as e:
        return None, f"Erro ao processar PDF: {str(e)}"