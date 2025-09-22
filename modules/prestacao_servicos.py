import streamlit as st
import pandas as pd
from components.importacao import *

def _ajuda_pill(conteudo_md: str, titulo: str = "Ajuda"):
    """
    Renderiza um pequeno botão/pill de ajuda logo após o label.
    Usa st.popover se disponível; fallback para expander compacto.
    """
    if hasattr(st, "popover"):
        with st.popover("❓", use_container_width=False):
            st.markdown(conteudo_md)
    else:
        with st.expander(f"❓ {titulo}"):
            st.markdown(conteudo_md)

def uploader_com_ajuda(label: str, tipos, chave: str, ajuda_md: str):
    """
    Mostra o label + pill de ajuda na MESMA linha e em seguida o componente de upload.
    """
    linha = st.columns([0.7, 0.3])
    with linha[0]:
        st.markdown(f"**{label}**", help=None)
    with linha[1]:
        _ajuda_pill(ajuda_md)
    return st.file_uploader(label, type=tipos, key=chave, label_visibility="collapsed")


AJUDA_CLINICA = """**Sistema:** WorkLab
**Caminho:** Clínica ➜ Atendimento por Data
**Parâmetros:** Data do dia anterior
**Instruções:** Gerar Excel ➜ Excel Resumido
**Nome padrão:** relConsultaData(-data-).xlsx"""
AJUDA_LAB = """**Sistema:** WorkLab
**Caminho:** Relatórios ➜ Movimento Diário
**Parâmetros:** Data do dia anterior
**Instruções:** Pesquisar ➜ Botão Excel ➜ Gerar Excel Detalhado
**Nome padrão:** relMovimentoDiarioDetalhado(-data-).xls"""
AJUDA_CONVENIO_DETALHADO = """**Sistema:** WorkLab
**Caminho:** Relatórios ➜ Convênio ➜ Por Convênio Individual 
**Parâmetros:** Mês anterior
**Instruções:** Preencher parâmetros ➜ Gerar Excel ➜ Detalhado por Linha
**Nome padrão:** relConvDetalhadoPorLinha_(-data-).xlsx"""
AJUDA_IPES = """**Sistema:** https://portalconectasaude.com.br
**Caminho:** Extrato de Utilização
**Parâmetros:** Mês anterior; Situação: Autorizada, Autorizada parcialmente, Autorizada em Contingência
**Instruções:** Preencher parâmetros ➜ Emitir
**Nome padrão:** relat_utilizacao(-data-).pdf"""
AJUDA_MULVI = """**Sistema:** https://app.mulvipay.com.br
**Caminho:** Movimentações ➜ Movimentação Financeira
**Parâmetros:** Data do dia anterior
**Instruções:** Consultar ➜ Analítico ➜ Baixar Relatório em Excel
**Nome padrão:** MovimentoFinanceiro41416978000116_(-data-).xlsx"""
AJUDA_GETNET = """**Sistema:** https://minhaconta.getnet.com.br
**Caminho:** Financeiro ➜ Recebimentos ➜ Baixar extrato
**Parâmetros:** Dia anterior; Apresentação: Detalhado
**Instruções:** Financeiro ➜ Recebimentos ➜ Baixar extrato ➜ Período personalizado (dia anterior) ➜ Apresentação: Detalhado ➜ Formato: Excel ➜ Baixar
**Nome padrão:** Recebivel_Completos_(...).xlsx"""


def show():
    """Página de Importações - antiga prestação de serviços."""
    st.header("📂 Importações")
    st.markdown("**Importação de arquivos para o sistema da clínica.**")
    # Upload de arquivos
    st.markdown("##### 📁 Upload de Arquivos")
    
    col1, col2 = st.columns(2)

    with col1:
        arquivo_clinica = uploader_com_ajuda(
            "Arquivo da Clínica (XLS/XLSX)",
            ['xls','xlsx'],
            f"arquivo_clinica_{st.session_state.get('upload_counter', 0)}",
            AJUDA_CLINICA
        )
        arquivo_laboratorio = uploader_com_ajuda(
            "Arquivo do Laboratório (XLS/XLSX)",
            ['xls','xlsx'],
            f"arquivo_laboratorio_{st.session_state.get('upload_counter', 0)}",
            AJUDA_LAB
        )
        arquivo_convenio_detalhado = uploader_com_ajuda(
            "Arquivo de Convênio Detalhado (XLSX)",
            ['xlsx','xls'],
            f"arquivo_convenio_detalhado_{st.session_state.get('upload_counter', 0)}",
            AJUDA_CONVENIO_DETALHADO
        )

    with col2:
        arquivo_convenio_pdf = uploader_com_ajuda(
            "Arquivo de Convênio IPES (PDF)",
            ['pdf'],
            f"arquivo_convenio_pdf_{st.session_state.get('upload_counter', 0)}",
            AJUDA_IPES
        )
        arquivo_mulvi = uploader_com_ajuda(
            "Arquivo MULVI (XLSX)",
            ['xlsx','xls'],
            f"arquivo_mulvi_{st.session_state.get('upload_counter', 0)}",
            AJUDA_MULVI
        )
        arquivo_getnet = uploader_com_ajuda(
            "Cartão GETNET Detalhado (XLSX)",
            ['xlsx','xls'],
            f"arquivo_getnet_{st.session_state.get('upload_counter', 0)}",
            AJUDA_GETNET
        )

    
    # Botão de processamento
    st.markdown("---")
    if st.button("🔄 Processar Arquivos", use_container_width=True):
        if any([arquivo_clinica, arquivo_laboratorio, arquivo_convenio_detalhado,arquivo_convenio_pdf, arquivo_mulvi, arquivo_getnet]):
            with st.spinner("Processando arquivos..."):
                resultado = processar_arquivos(arquivo_clinica, arquivo_laboratorio, arquivo_convenio_detalhado, arquivo_convenio_pdf, arquivo_mulvi, arquivo_getnet)

                if resultado['sucesso']:
                    st.success("Arquivos processados. Verifique os resultados abaixo.")
                    
                    # Popula os dados processados na sessão
                    dados_processados = {}
                    if resultado.get('dados_clinica') is not None:
                        dados_processados['clinica'] = resultado['dados_clinica']
                    if resultado.get('dados_laboratorio') is not None:
                        dados_processados['laboratorio'] = resultado['dados_laboratorio']
                    if resultado.get('dados_convenio_detalhado') is not None:
                        dados_processados['convenio_detalhado'] = resultado['dados_convenio_detalhado']
                    if resultado.get('dados_convenios') is not None:
                        dados_processados['convenio_ipes'] = resultado['dados_convenios']
                    if resultado.get('dados_mulvi') is not None:
                        dados_processados['mulvi'] = resultado['dados_mulvi']
                    if resultado.get('dados_getnet') is not None:
                        dados_processados['credito_getnet'] = resultado['dados_getnet']
                    
                    st.session_state.dados_processados = dados_processados
                                        
                    st.session_state.conflitos_data = resultado.get('conflitos', {})
                    
                    st.rerun() # Força a re-renderização para mostrar os resultados e a mensagem de conflito
                else:
                    st.error(f"Erro no processamento: {resultado.get('erro', 'Erro desconhecido')}")
        else:
            st.warning("Por favor, envie pelo menos um arquivo.")

    # Seção de confirmação e salvamento
    if 'dados_processados' in st.session_state:
        st.markdown("---")
        st.markdown("### 💾 Confirmação da Importação")

        conflitos = st.session_state.get('conflitos_data', {})
        
        # CASO 1: NÃO HÁ CONFLITOS
        if not conflitos:
            st.info("✅ Nenhuma data conflitante encontrada. Você pode realizar a importação.")
            if st.button("🔴 Realizar Importação", type="primary", use_container_width=True):
                with st.spinner("Salvando dados..."):
                    df_clinica = st.session_state.dados_processados.get('clinica')
                    df_laboratorio = st.session_state.dados_processados.get('laboratorio')
                    df_convenio_detalhado = st.session_state.dados_processados.get('convenio_detalhado')
                    df_convenio_ipes = st.session_state.dados_processados.get('convenio_ipes')
                    df_mulvi = st.session_state.dados_processados.get('mulvi')
                    df_getnet = st.session_state.dados_processados.get('credito_getnet')
                    resultado_save = salvar_importacao(df_clinica, df_laboratorio, df_convenio_detalhado,
                                                       df_convenio_ipes, df_mulvi, df_getnet)

                    if resultado_save['sucesso']:
                        st.success("✅ Dados importados com sucesso!")

                        # Mostra débitos registrados automaticamente
                        if resultado_save.get('debitos_registrados', 0) > 0:
                            st.success(f"💳 {resultado_save['debitos_registrados']} pagamentos em débito foram registrados automaticamente nas contas:")
                            st.info("• Débito MULVI → Conta BANESE\n• Débito GETNET → Conta SANTANDER")
                        
                        # NOVO: Mostra resultado da consolidação IPES
                        consolidacao_ipes = resultado_save.get('consolidacao_ipes')
                        if consolidacao_ipes:
                            if consolidacao_ipes['sucesso']:
                                st.success(f"🏥 IPES: {consolidacao_ipes['mensagem']}")
                            else:
                                st.warning(f"⚠️ IPES: {consolidacao_ipes['mensagem']}")
                                                
                        try:
                            sucesso_recebimentos, msg_recebimentos = atualizar_recebimentos_pendentes()
                            if sucesso_recebimentos:
                                st.success(f"💰 Recebimentos: {msg_recebimentos}")
                            else:
                                st.warning(f"⚠️ Recebimentos: {msg_recebimentos}")
                        except Exception as e:
                            st.warning(f"⚠️ Problema ao atualizar recebimentos: {str(e)}")
                        
                        st.markdown("### 📊 Resumo da Importação")
                        col_res1, col_res2, col_res3, col_res4, col_res5, col_res6 = st.columns(6)
                        # ... (código das métricas, sem alterações)
                        with col_res1:
                            if resultado_save.get('clinica_linhas', 0) > 0:
                                st.metric("Clínica", f"{resultado_save['clinica_linhas']} registros")
                        with col_res2:
                            if resultado_save.get('laboratorio_linhas', 0) > 0:
                                st.metric("Laboratório", f"{resultado_save['laboratorio_linhas']} registros")
                        with col_res3:
                            if resultado_save.get('convenio_detalhado_linhas', 0) > 0:
                                st.metric("Convênio Detalhado", f"{resultado_save['convenio_detalhado_linhas']} registros")
                        with col_res4:
                            if resultado_save.get('ipes_linhas', 0) > 0:
                                st.metric("Convênio IPES", f"{resultado_save['ipes_linhas']} registros")
                        with col_res5:
                            if resultado_save.get('mulvi_linhas', 0) > 0:
                                st.metric("MULVI", f"{resultado_save['mulvi_linhas']} registros")
                        with col_res6:
                            if resultado_save.get('getnet_linhas', 0) > 0:
                                st.metric("GETNET", f"{resultado_save['getnet_linhas']} registros")

                        del st.session_state.dados_processados
                        if 'conflitos_data' in st.session_state:
                            del st.session_state.conflitos_data
                        if 'upload_counter' not in st.session_state:
                            st.session_state.upload_counter = 0
                        st.session_state.upload_counter += 1
                        st.rerun()
                        
                    else:
                        st.error(f"❌ Erro ao salvar dados: {resultado_save['erro']}")
        
        # CASO 2: HÁ CONFLITOS (NOVO BLOCO ELSE)
        else:
            mensagens_erro = []
            for tipo, datas in conflitos.items():
                nome_amigavel = tipo.replace('_', ' ').title()
                datas_str = ", ".join(datas)
                mensagens_erro.append(f"**{nome_amigavel}** (Datas: {datas_str})")
            
            erro_final = (
                "❌ **Importação Bloqueada por Conflito de Datas.**\n\n"
                "Os seguintes arquivos contêm dados para datas que já existem no sistema:\n- " +
                "\n- ".join(mensagens_erro) +
                "\n\n**Ação Necessária:** Cancele esta importação. Se desejar sobrescrever os dados, primeiro exclua os registros antigos na seção 'Histórico de Atendimentos Importados' abaixo."
            )
            st.error(erro_final)

            if st.button("❌ Cancelar Importação", use_container_width=True):
                del st.session_state.dados_processados
                if 'conflitos_data' in st.session_state:
                    del st.session_state.conflitos_data
                st.rerun()

        # Visualização dos dados processados (agora fora do if/else principal)
        st.markdown("---")
        st.markdown("### 📊 Dados Processados (Pré-visualização)")
        
        tab_names = []
        if st.session_state.dados_processados.get('clinica') is not None:
            tab_names.append("Clínica")
        if st.session_state.dados_processados.get('laboratorio') is not None:
            tab_names.append("Laboratório")
        if st.session_state.dados_processados.get('convenio_detalhado') is not None:
            tab_names.append("Convênio Detalhado")
        if st.session_state.dados_processados.get('convenio_ipes') is not None:
            tab_names.append("Convênio IPES")
        if st.session_state.dados_processados.get('mulvi') is not None:
            tab_names.append("MULVI")
        if st.session_state.dados_processados.get('credito_getnet') is not None:
            tab_names.append("GETNET")
            
        if tab_names:
            tabs = st.tabs(tab_names)
            tab_index = 0
            if st.session_state.dados_processados.get('clinica') is not None:
                with tabs[tab_index]:
                    df_clinica = st.session_state.dados_processados['clinica']
                    st.write(f"**Total de registros:** {len(df_clinica)}")
                    st.dataframe(df_clinica, use_container_width=True, hide_index=True)
                tab_index += 1
            if st.session_state.dados_processados.get('laboratorio') is not None:
                with tabs[tab_index]:
                    df_laboratorio = st.session_state.dados_processados['laboratorio']
                    st.write(f"**Total de registros:** {len(df_laboratorio)}")
                    st.dataframe(df_laboratorio, use_container_width=True, hide_index=True)
                tab_index += 1
            if st.session_state.dados_processados.get('convenio_detalhado') is not None:
                with tabs[tab_index]:
                    df_convenio_detalhado = st.session_state.dados_processados['convenio_detalhado']
                    st.write(f"**Total de registros:** {len(df_convenio_detalhado)}")
                    st.dataframe(df_convenio_detalhado, use_container_width=True, hide_index=True)
                tab_index += 1
            if st.session_state.dados_processados.get('convenio_ipes') is not None:
                with tabs[tab_index]:
                    df_convenio = st.session_state.dados_processados['convenio_ipes']
                    st.write(f"**Total de registros:** {len(df_convenio)}")
                    st.dataframe(df_convenio, use_container_width=True, hide_index=True)
                tab_index += 1
            if st.session_state.dados_processados.get('mulvi') is not None:
                with tabs[tab_index]:
                    df_mulvi = st.session_state.dados_processados['mulvi']
                    st.write(f"**Total de registros:** {len(df_mulvi)}")
                    st.dataframe(df_mulvi, use_container_width=True, hide_index=True)
                tab_index += 1
            if st.session_state.dados_processados.get('credito_getnet') is not None:
                with tabs[tab_index]:
                    df_getnet = st.session_state.dados_processados['credito_getnet']
                    st.write(f"**Total de registros:** {len(df_getnet)}")
                    st.dataframe(df_getnet, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum dado foi processado nos arquivos enviados.")

    # Seção para visualizar dados importados (dados já salvos)
    st.markdown("---")
    st.markdown("### 📈 Histórico de Atendimentos Importados")

    opcoes_map = {
        "Clínica": "clinica",
        "Laboratório": "laboratorio",
        "Convênio Detalhado": "convenio_detalhado",
        "Convênio IPES": "ipes",
        "Cartão MULVI": "mulvi",
        "Cartão GETNET": "getnet"
    }

    opcao_selecionada_nome = st.radio(
        "Selecione os dados para visualizar:",
        options=opcoes_map.keys(), # Mostra os nomes amigáveis
        horizontal=True,
        key="vis_dados_salvos"
    )
    
    # Pega a chave interna correspondente ao nome selecionado
    opcao_visualizacao = opcoes_map[opcao_selecionada_nome]

    try:
        df_visualizacao = carregar_dados_atendimentos(opcao_visualizacao)
        
        if not df_visualizacao.empty:
            # Filtro por data - usar a coluna correta dependendo do tipo
            data_col = (
                'Data_Lançamento' if opcao_visualizacao == 'mulvi'
                else 'DATA DE VENCIMENTO' if opcao_visualizacao == 'getnet'
                else 'data_cadastro'
            )
            
            if data_col in df_visualizacao.columns:
                df_viz_copy = df_visualizacao.copy()
                df_viz_copy[data_col] = pd.to_datetime(df_viz_copy[data_col]).dt.date
                
                data_min = df_viz_copy[data_col].min()
                data_max = df_viz_copy[data_col].max()
                
                col_data1, col_data2 = st.columns(2)
                with col_data1:
                    data_inicio = st.date_input(
                        "Data Início", value=data_min, min_value=data_min, 
                        max_value=data_max, key=f"data_inicio_{opcao_visualizacao}"
                    )
                with col_data2:
                    data_fim = st.date_input(
                        "Data Fim", value=data_max, min_value=data_min, 
                        max_value=data_max, key=f"data_fim_{opcao_visualizacao}"
                    )
                
                mask = (df_viz_copy[data_col] >= data_inicio) & (df_viz_copy[data_col] <= data_fim)
                df_filtrado = df_viz_copy[mask]
                
                st.markdown(f"**Registros no período selecionado:** {len(df_filtrado)}")
                if not df_filtrado.empty:
                    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

                    # --- LÓGICA DE EXCLUSÃO ---
                    st.markdown("---")
                    st.warning("**Atenção:** A exclusão é permanente e não pode ser desfeita.")
                    
                    if st.button("🗑️ Excluir Registros do Período Selecionado", key=f"delete_btn_{opcao_visualizacao}"):
                        st.session_state.confirm_delete = True
                        st.session_state.dates_to_delete = df_filtrado[data_col].unique().tolist()
                        st.session_state.type_to_delete = opcao_visualizacao

                    if st.session_state.get('confirm_delete') and st.session_state.get('type_to_delete') == opcao_visualizacao:
                        datas_str = ", ".join([d.strftime('%d/%m/%Y') for d in st.session_state.dates_to_delete])
                        if st.button(f"🔴 CONFIRMAR EXCLUSÃO de {len(st.session_state.dates_to_delete)} dia(s)", type="primary"):
                            with st.spinner("Excluindo registros..."):
                                sucesso, msg = excluir_dados_por_data(
                                    st.session_state.type_to_delete, 
                                    st.session_state.dates_to_delete
                                )
                                if sucesso:
                                    st.success(msg)
                                else:
                                    st.error(msg)
                                
                                # Limpa o estado de confirmação e recarrega a página
                                del st.session_state.confirm_delete
                                del st.session_state.dates_to_delete
                                del st.session_state.type_to_delete
                                st.rerun()

            else:
                st.dataframe(df_visualizacao, use_container_width=True, hide_index=True)
            
        else:
            st.info("📝 Nenhum dado encontrado. Faça a importação dos arquivos primeiro.")
            
    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar o histórico: {e}")