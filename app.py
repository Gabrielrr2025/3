import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from data import get_fgi_history, get_btc_history, align_series
from backtest import run_backtest

st.set_page_config(page_title="FGI Backtest", layout="wide", page_icon="📊")

st.title("📊 Backtest Fear & Greed Index (Bitcoin)")
st.markdown("---")

# 📌 Carregar dados do FGI (via CSV GitHub) com cache
@st.cache_data(ttl=3600)  # Cache por 1 hora
def load_fgi_data():
    return get_fgi_history()

with st.spinner("Carregando dados do Fear & Greed Index..."):
    fgi = load_fgi_data()

if not fgi.empty:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📅 Período FGI", f"{fgi.index.min().date()} - {fgi.index.max().date()}")
    with col2:
        st.metric("📊 Total de dias", f"{len(fgi):,}")
    with col3:
        st.metric("🔴 FGI Atual", f"{fgi['FGI'].iloc[-1]:.0f}")
    
    st.success("✅ Dados do Fear & Greed Index carregados do GitHub")
else:
    st.error("⚠️ Não foi possível carregar os dados do FGI")
    st.stop()

st.markdown("---")

# 📌 Inputs do usuário
col_sidebar1, col_sidebar2 = st.columns([1, 3])

with col_sidebar1:
    st.subheader("⚙️ Parâmetros")
    
    # Datas
    st.markdown("**📅 Período**")
    start_date = st.date_input("Data inicial", value=date(2020, 1, 1), key="start")
    end_date = st.date_input("Data final", value=date.today(), key="end")
    
    # Thresholds
    st.markdown("**🎯 Estratégia**")
    buy_threshold = st.slider("Comprar se FGI ≤", 0, 100, 30, help="Valores baixos = medo extremo")
    sell_threshold = st.slider("Vender se FGI ≥", 0, 100, 70, help="Valores altos = ganância")
    
    # Taxa
    st.markdown("**💰 Custos**")
    trade_fee = st.number_input("Taxa por trade (%)", 0.0, 5.0, 0.1, step=0.05)
    
    # Botão
    run_button = st.button("▶️ Rodar Backtest", type="primary", use_container_width=True)

with col_sidebar2:
    st.subheader("📈 Resultados")
    
    if run_button:
        # 🔍 SEÇÃO DE DEBUG
        with st.expander("🔍 Debug: Log de Carregamento", expanded=True):
            debug_output = st.empty()
            
        with st.spinner("📡 Baixando dados do Bitcoin..."):
            # Carregar dados BTC
            btc = get_btc_history(start_date, end_date)
            
            # Debug BTC
            with debug_output.container():
                st.markdown("#### 📊 Status do carregamento:")
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.markdown("**FGI Data:**")
                    if not fgi.empty:
                        st.success(f"✅ {len(fgi)} dias carregados")
                        st.caption(f"Período: {fgi.index.min().date()} até {fgi.index.max().date()}")
                    else:
                        st.error("❌ FGI vazio")
                
                with col_d2:
                    st.markdown("**BTC Data:**")
                    if not btc.empty:
                        st.success(f"✅ {len(btc)} dias carregados")
                        st.caption(f"Período: {btc.index.min().date()} até {btc.index.max().date()}")
                    else:
                        st.error("❌ BTC vazio")
                        st.warning("**Possíveis causas:**")
                        st.markdown("""
                        - ⚠️ Yahoo Finance offline
                        - ⚠️ Período sem dados
                        - ⚠️ Problema de conexão
                        """)
            
            if btc.empty:
                st.error("❌ Não foi possível carregar dados do Bitcoin")
                st.info("💡 **Soluções:**")
                st.markdown("""
                1. Verifique sua conexão com a internet
                2. Tente um período diferente (ex: últimos 365 dias)
                3. Aguarde alguns minutos e tente novamente
                4. Verifique os logs no terminal/console
                """)
                st.stop()
        
        with st.spinner("🔗 Alinhando séries temporais..."):
            df = align_series(fgi, btc, start_date, end_date)
            
            # Debug do alinhamento
            with debug_output.container():
                st.markdown("---")
                st.markdown("#### 🔗 Alinhamento de séries:")
                
                if df.empty:
                    st.error("❌ Nenhum dado após alinhamento")
                    
                    # Diagnóstico detalhado
                    st.warning("**Diagnóstico:**")
                    
                    fgi_range = (fgi.index.min().date(), fgi.index.max().date())
                    btc_range = (btc.index.min().date(), btc.index.max().date())
                    user_range = (start_date, end_date)
                    
                    st.markdown(f"""
                    - 📅 **Período solicitado:** {user_range[0]} até {user_range[1]}
                    - 📊 **FGI disponível:** {fgi_range[0]} até {fgi_range[1]}
                    - 💰 **BTC disponível:** {btc_range[0]} até {btc_range[1]}
                    """)
                    
                    # Verifica sobreposição
                    overlap_start = max(fgi_range[0], btc_range[0], user_range[0])
                    overlap_end = min(fgi_range[1], btc_range[1], user_range[1])
                    
                    if overlap_start > overlap_end:
                        st.error("🚫 **Não há sobreposição de datas!**")
                        st.info(f"💡 Tente um período entre **{max(fgi_range[0], btc_range[0])}** e **{min(fgi_range[1], btc_range[1])}**")
                    else:
                        st.info(f"✅ Sobreposição detectada: {overlap_start} até {overlap_end}")
                        st.warning("⚠️ Mas o alinhamento retornou vazio. Verifique os logs do terminal.")
                    
                    st.stop()
                else:
                    st.success(f"✅ {len(df)} dias alinhados com sucesso")
                    st.caption(f"Período final: {df.index.min().date()} até {df.index.max().date()}")

        with st.spinner("🧮 Executando backtest..."):
            results, trades = run_backtest(df, buy_threshold, sell_threshold, trade_fee)

            # 📊 Métricas principais
            st.markdown("### 💵 Performance")
            col1, col2, col3, col4 = st.columns(4)
            
            strategy_return = results[results["Estrategia"] == "FGI Strategy"]["Retorno (%)"].values[0]
            hold_return = results[results["Estrategia"] == "Buy & Hold"]["Retorno (%)"].values[0]
            outperformance = strategy_return - hold_return
            num_trades = len(trades)
            
            with col1:
                st.metric("🎯 Estratégia FGI", f"{strategy_return:+.2f}%")
            with col2:
                st.metric("📌 Buy & Hold", f"{hold_return:+.2f}%")
            with col3:
                st.metric("⚡ Diferença", f"{outperformance:+.2f}%", 
                         delta=f"{outperformance:+.2f}%")
            with col4:
                st.metric("🔄 Trades", num_trades)

            # 📊 Gráfico de comparação
            st.markdown("### 📈 Comparação Visual")
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                name="FGI Strategy",
                x=["Retorno (%)"],
                y=[strategy_return],
                marker_color="#00cc96" if strategy_return > hold_return else "#ef553b"
            ))
            
            fig.add_trace(go.Bar(
                name="Buy & Hold",
                x=["Retorno (%)"],
                y=[hold_return],
                marker_color="#636efa"
            ))
            
            fig.update_layout(
                height=300,
                showlegend=True,
                barmode='group',
                template="plotly_white"
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # 📊 Tabela de resultados
            st.markdown("### 📋 Tabela Comparativa")
            st.dataframe(results, use_container_width=True, hide_index=True)

            # 📜 Histórico de trades
            st.markdown("### 📜 Histórico de Trades")
            if not trades.empty:
                st.dataframe(trades, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum trade executado no período selecionado")

            # 📥 Exportar para Excel
            st.markdown("### 📥 Exportar Resultados")
            output_excel = "backtest_results.xlsx"
            with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
                results.to_excel(writer, sheet_name="Resumo", index=False)
                trades.to_excel(writer, sheet_name="Trades", index=False)
                df.to_excel(writer, sheet_name="Dados")

            with open(output_excel, "rb") as f:
                st.download_button(
                    label="📥 Baixar resultados em Excel",
                    data=f,
                    file_name=f"backtest_fgi_{start_date}_{end_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

st.markdown("---")
st.caption("📊 Dados atualizados diariamente via GitHub Actions | Fear & Greed Index by Alternative.me")
