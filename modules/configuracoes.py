import streamlit as st
import pandas as pd
import os
from datetime import date, datetime
from components.functions import (
    carregar_dados_github_api,
    carregar_descricoes_personalizadas,
    salvar_nova_descricao
)
from components.importacao import carregar_dados_atendimentos
import pickle

def show():
    """Página de Configurações"""
    
    st.header("⚙️ Configurações")
    st.markdown("**Configurações e manutenção do sistema**")
    
    # Abas para diferentes configurações
    tab1, tab2, tab3, tab4 = st.tabs([
        "🗃️ Gestão de Dados", 
        "📝 Descrições Personalizadas", 
        "📊 Informações do Sistema",
        "🔧 Manutenção"
    ])
    
    with tab1:
        st.markdown("### 🗃️ Gestão de Dados")
        st.markdown("Visualize e gerencie os dados armazenados no sistema")
        
        # Seção de dados importados
        st.markdown("#### 📁 Dados de Atendimentos")
        
        col_info1, col_info2, col_info3 = st.columns(3)
        
        # Verifica arquivos de dados
        arquivos_dados = ['movimento_clinica', 'movimento_laboratorio', 'convenios_detalhados']
        
        for i, arquivo in enumerate(arquivos_dados):
            with [col_info1, col_info2, col_info3][i]:
                try:
                    df = carregar_dados_atendimentos(arquivo)
                    
                    nome_exibicao = {
                        'movimento_clinica': '🏥 Clínica',
                        'movimento_laboratorio': '🔬 Laboratório',
                        'convenios_detalhados': '🩺 Convênios'
                    }
                    
                    if not df.empty:
                        # Calcula estatísticas
                        total_registros = len(df)
                        
                        if 'data' in df.columns:
                            df['data'] = pd.to_datetime(df['data'], errors='coerce')
                            data_min = df['data'].min().strftime('%d/%m/%Y') if pd.notna(df['data'].min()) else 'N/A'
                            data_max = df['data'].max().strftime('%d/%m/%Y') if pd.notna(df['data'].max()) else 'N/A'
                        else:
                            data_min = data_max = 'N/A'
                        
                        st.markdown(f"""
                        **{nome_exibicao[arquivo]}**
                        
                        📊 **{total_registros:,} registros**
                        
                        📅 **Período:**
                        De: {data_min}
                        Até: {data_max}
                        """)
                        
                        # Botão para visualizar dados
                        if st.button(f"👁️ Visualizar {nome_exibicao[arquivo]}", key=f"view_{arquivo}"):
                            st.session_state[f'show_data_{arquivo}'] = True
                    else:
                        st.markdown(f"""
                        **{nome_exibicao[arquivo]}**
                        
                        📊 **Nenhum dado**
                        
                        ⚠️ Arquivo vazio ou não encontrado
                        """)
                        
                except Exception as e:
                    st.error(f"Erro ao carregar {arquivo}: {str(e)}")
        
        # Exibição de dados se solicitado
        for arquivo in arquivos_dados:
            if st.session_state.get(f'show_data_{arquivo}', False):
                st.markdown(f"#### 📋 Dados: {arquivo.replace('_', ' ').title()}")
                
                try:
                    df = carregar_dados_atendimentos(arquivo)
                    
                    if not df.empty:
                        # Filtros básicos
                        col_f1, col_f2 = st.columns(2)
                        
                        with col_f1:
                            linhas_exibir = st.selectbox(
                                "Linhas para exibir:",
                                [50, 100, 500, "Todas"],
                                key=f"linhas_{arquivo}"
                            )
                        
                        with col_f2:
                            if 'data' in df.columns:
                                df['data'] = pd.to_datetime(df['data'], errors='coerce')
                                ordenar_por_data = st.checkbox(
                                    "Ordenar por data (mais recente primeiro)",
                                    value=True,
                                    key=f"ordenar_{arquivo}"
                                )
                                
                                if ordenar_por_data:
                                    df = df.sort_values('data', ascending=False)
                        
                        # Aplica filtro de linhas
                        if linhas_exibir != "Todas":
                            df_exibir = df.head(linhas_exibir)
                        else:
                            df_exibir = df
                        
                        st.dataframe(df_exibir, use_container_width=True, hide_index=True)
                        
                        # Botão para fechar
                        if st.button(f"❌ Fechar visualização", key=f"close_{arquivo}"):
                            st.session_state[f'show_data_{arquivo}'] = False
                            st.rerun()
                    
                except Exception as e:
                    st.error(f"Erro ao exibir dados: {str(e)}")
        
        # Seção de limpeza de dados
        st.markdown("---")
        st.markdown("#### 🗑️ Limpeza de Dados")
        
        st.warning("⚠️ **ATENÇÃO:** As operações abaixo são irreversíveis!")
        
        col_clean1, col_clean2 = st.columns(2)
        
        with col_clean1:
            st.markdown("**Limpar dados específicos:**")
            
            arquivo_limpar = st.selectbox(
                "Selecione o arquivo para limpar:",
                ["movimento_clinica", "movimento_laboratorio", "convenios_detalhados"],
                key="arquivo_limpar"
            )
            
            if st.button(f"🗑️ Limpar {arquivo_limpar}", type="secondary"):
                if st.checkbox("Confirmo que quero limpar estes dados", key="confirm_clean_specific"):
                    try:
                        caminho = f'data/{arquivo_limpar}.pkl'
                        if os.path.exists(caminho):
                            os.remove(caminho)
                            st.success(f"✅ Dados de {arquivo_limpar} removidos com sucesso!")
                            st.rerun()
                        else:
                            st.info("📝 Arquivo não encontrado")
                    except Exception as e:
                        st.error(f"❌ Erro ao limpar dados: {str(e)}")
        
        with col_clean2:
            st.markdown("**Limpar todos os dados:**")
            
            if st.button("🗑️ Limpar TODOS os dados", type="secondary"):
                if st.checkbox("Confirmo que quero limpar TODOS os dados", key="confirm_clean_all"):
                    try:
                        arquivos_removidos = []
                        for arquivo in arquivos_dados:
                            caminho = f'data/{arquivo}.pkl'
                            if os.path.exists(caminho):
                                os.remove(caminho)
                                arquivos_removidos.append(arquivo)
                        
                        if arquivos_removidos:
                            st.success(f"✅ Removidos: {', '.join(arquivos_removidos)}")
                            st.rerun()
                        else:
                            st.info("📝 Nenhum arquivo encontrado para remover")
                    except Exception as e:
                        st.error(f"❌ Erro ao limpar dados: {str(e)}")
    
    with tab2:
        st.markdown("### 📝 Gestão de Descrições Personalizadas")
        st.markdown("Gerencie as descrições salvas para pagamentos")
        
        # Carrega descrições existentes
        descricoes = carregar_descricoes_personalizadas()
        
        col_desc1, col_desc2 = st.columns(2)
        
        with col_desc1:
            st.markdown("#### ➕ Adicionar Nova Descrição")
            
            with st.form("form_nova_descricao"):
                nova_descricao = st.text_input(
                    "Digite a nova descrição:",
                    placeholder="Ex: Pagamento fornecedor de material de limpeza"
                )
                
                if st.form_submit_button("➕ Adicionar", type="primary"):
                    if nova_descricao and nova_descricao not in descricoes:
                        try:
                            salvar_nova_descricao(nova_descricao)
                            st.success("✅ Descrição adicionada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao salvar descrição: {str(e)}")
                    elif nova_descricao in descricoes:
                        st.warning("⚠️ Esta descrição já existe!")
                    else:
                        st.warning("⚠️ Digite uma descrição válida!")
        
        with col_desc2:
            st.markdown("#### 📋 Descrições Existentes")
            
            if descricoes:
                st.markdown(f"**Total: {len(descricoes)} descrições**")
                
                # Lista as descrições
                for i, desc in enumerate(descricoes, 1):
                    st.markdown(f"{i}. {desc}")
                
                # Opção de remover descrição (funcionalidade futura)
                st.markdown("---")
                descricao_remover = st.selectbox(
                    "Remover descrição:",
                    ["Selecione..."] + descricoes,
                    key="desc_remover"
                )
                
                if descricao_remover != "Selecione...":
                    if st.button("🗑️ Remover Descrição", type="secondary"):
                        st.info("🔧 Funcionalidade de remoção em desenvolvimento")
            else:
                st.info("📝 Nenhuma descrição personalizada salva ainda")
    
    with tab3:
        st.markdown("### 📊 Informações do Sistema")
        
        # Informações gerais
        col_sys1, col_sys2 = st.columns(2)
        
        with col_sys1:
            st.markdown("#### 🖥️ Sistema")
            
            st.markdown(f"""
            **Nome:** Santa Saúde - Sistema de Gestão
            **Versão:** 2.0
            **Data de Atualização:** {date.today().strftime('%d/%m/%Y')}
            **Usuário Logado:** {st.session_state.get('nome_completo', 'N/A')}
            """)
            
            # Informações de sessão
            st.markdown("#### 🔐 Sessão Atual")
            
            if 'authenticated' in st.session_state:
                st.success("🟢 Usuário autenticado")
            else:
                st.error("🔴 Usuário não autenticado")
        
        with col_sys2:
            st.markdown("#### 💾 Armazenamento")
            
            # Verifica espaço usado pelos arquivos
            try:
                total_size = 0
                arquivos_info = []
                
                for arquivo in ['movimento_clinica', 'movimento_laboratorio', 'convenios_detalhados']:
                    caminho = f'data/{arquivo}.pkl'
                    if os.path.exists(caminho):
                        size = os.path.getsize(caminho)
                        total_size += size
                        arquivos_info.append(f"📁 {arquivo}: {size/1024:.1f} KB")
                    else:
                        arquivos_info.append(f"📁 {arquivo}: Não encontrado")
                
                st.markdown("**Arquivos de dados:**")
                for info in arquivos_info:
                    st.markdown(info)
                
                st.markdown(f"**Total usado:** {total_size/1024:.1f} KB")
                
            except Exception as e:
                st.error(f"Erro ao verificar armazenamento: {str(e)}")
        
        # Estatísticas de uso
        st.markdown("---")
        st.markdown("#### 📈 Estatísticas de Dados")
        
        try:
            # Carrega dados de movimentações
            df_movimentacoes = carregar_dados_github_api(
                "movimentacoes.csv",
                st.secrets["github"]["github_token"],
                "leoparipiranga/clinicasantasaude"
            )
            
            if not df_movimentacoes.empty:
                # Estatísticas gerais
                total_movimentacoes = len(df_movimentacoes)
                entradas = len(df_movimentacoes[df_movimentacoes['tipo'] == 'ENTRADA'])
                saidas = len(df_movimentacoes[df_movimentacoes['tipo'] == 'SAIDA'])
                
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                
                with col_stat1:
                    st.metric("Total Movimentações", total_movimentacoes)
                
                with col_stat2:
                    st.metric("Entradas", entradas)
                
                with col_stat3:
                    st.metric("Saídas", saidas)
                
                # Última movimentação
                if 'data' in df_movimentacoes.columns:
                    df_movimentacoes['data'] = pd.to_datetime(df_movimentacoes['data'], errors='coerce')
                    ultima_movimentacao = df_movimentacoes['data'].max()
                    
                    if pd.notna(ultima_movimentacao):
                        st.info(f"📅 Última movimentação: {ultima_movimentacao.strftime('%d/%m/%Y')}")
            else:
                st.info("📝 Nenhuma movimentação registrada ainda")
                
        except Exception as e:
            st.error(f"Erro ao carregar estatísticas: {str(e)}")
    
    with tab4:
        st.markdown("### 🔧 Manutenção do Sistema")
        
        # Cache e performance
        st.markdown("#### 🚀 Performance")
        
        col_perf1, col_perf2 = st.columns(2)
        
        with col_perf1:
            st.markdown("**Cache do Sistema:**")
            
            if st.button("🗑️ Limpar Cache", type="secondary"):
                st.cache_data.clear()
                st.success("✅ Cache limpo com sucesso!")
                st.info("🔄 Recarregue a página para ver as mudanças")
        
        with col_perf2:
            st.markdown("**Session State:**")
            
            if st.button("🔄 Limpar Session State", type="secondary"):
                # Mantém apenas dados essenciais
                keys_manter = ['authenticated', 'usuario_logado', 'nome_completo']
                keys_remover = [k for k in st.session_state.keys() if k not in keys_manter]
                
                for key in keys_remover:
                    del st.session_state[key]
                
                st.success("✅ Session State limpo!")
                st.rerun()
        
        # Backup e restore
        st.markdown("---")
        st.markdown("#### 💾 Backup e Restore")
        
        col_backup1, col_backup2 = st.columns(2)
        
        with col_backup1:
            st.markdown("**Criar Backup:**")
            
            if st.button("📦 Gerar Backup", type="primary"):
                try:
                    # Cria um backup simples dos dados
                    backup_data = {}
                    
                    for arquivo in ['movimento_clinica', 'movimento_laboratorio', 'convenios_detalhados']:
                        try:
                            df = carregar_dados_atendimentos(arquivo)
                            if not df.empty:
                                backup_data[arquivo] = df.to_dict('records')
                        except:
                            backup_data[arquivo] = []
                    
                    # Adiciona timestamp
                    backup_data['backup_timestamp'] = datetime.now().isoformat()
                    backup_data['backup_user'] = st.session_state.get('usuario_logado', 'unknown')
                    
                    # Converte para JSON para download
                    import json
                    backup_json = json.dumps(backup_data, default=str, ensure_ascii=False, indent=2)
                    
                    st.download_button(
                        label="⬇️ Download Backup",
                        data=backup_json,
                        file_name=f"santa_saude_backup_{date.today().strftime('%Y%m%d')}.json",
                        mime="application/json"
                    )
                    
                    st.success("✅ Backup gerado com sucesso!")
                    
                except Exception as e:
                    st.error(f"❌ Erro ao gerar backup: {str(e)}")
        
        with col_backup2:
            st.markdown("**Restaurar Backup:**")
            
            arquivo_backup = st.file_uploader(
                "Selecione o arquivo de backup:",
                type=['json'],
                help="Arquivo JSON gerado pela função de backup"
            )
            
            if arquivo_backup and st.button("🔄 Restaurar Backup", type="secondary"):
                st.warning("🔧 Funcionalidade de restore em desenvolvimento")
        
        # Logs do sistema
        st.markdown("---")
        st.markdown("#### 📋 Logs do Sistema")
        
        if st.button("📄 Visualizar Session State"):
            st.json(dict(st.session_state))
        
        # Informações de debug
        st.markdown("---")
        st.markdown("#### 🐛 Debug")
        
        with st.expander("🔍 Informações de Debug"):
            st.markdown("**Variáveis de Ambiente:**")
            
            # Verifica secrets (sem mostrar valores sensíveis)
            try:
                st.markdown("✅ GitHub Token: Configurado" if "github" in st.secrets else "❌ GitHub Token: Não configurado")
                st.markdown("✅ Usuários: Configurado" if "usuarios" in st.secrets else "❌ Usuários: Não configurado")
            except:
                st.markdown("❌ Secrets não acessíveis")
            
            st.markdown("**Estrutura de Diretórios:**")
            
            # Verifica diretórios
            diretorios = ['data', 'pages', 'components']
            for diretorio in diretorios:
                if os.path.exists(diretorio):
                    st.markdown(f"✅ {diretorio}/: Existe")
                else:
                    st.markdown(f"❌ {diretorio}/: Não encontrado")
            
            st.markdown("**Arquivos de Dados:**")
            
            # Verifica arquivos
            for arquivo in ['movimento_clinica', 'movimento_laboratorio', 'convenios_detalhados']:
                caminho = f'data/{arquivo}.pkl'
                if os.path.exists(caminho):
                    size = os.path.getsize(caminho)
                    st.markdown(f"✅ {arquivo}.pkl: {size} bytes")
                else:
                    st.markdown(f"❌ {arquivo}.pkl: Não encontrado")