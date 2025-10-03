import streamlit as st
import pandas as pd
from datetime import date
from data import get_fgi_history, get_btc_history, align_series
from backtest import run_backtest

st.set_page_config(page_title="FGI Backtest", layout="wide")
st.title("📊 Backtest Fear & Greed Index (Bitcoin)")

# 📌 Carregar dados do FGI (via CSV GitHub)
fgi = get_fgi_history()
if not fgi.empty:
    st.success("✅ Dados do Fear & Greed Index carregados do CSV no GitHub")
else:
    st.error("⚠️ Não foi possível carregar os dados do FGI a partir do GitHub")

# 📌 Inputs do usuário
st.sidebar.header("⚙️ Parâmetros do Backtest")
start_date = st.sidebar.date_input("Data inicial", value=date(2019, 1, 1))
end_date = st.sidebar.date_input("Data final", value=date.today())
buy_threshold = st.sidebar.slider("Comprar se FGI ≤", 0, 100, 30)
sell_threshold = st.sidebar.slider("Vender se FGI ≥", 0, 100, 70)
trade_fee = st.sidebar.number_input("Taxa por trade (%)", 0.0, 5.0, 0.1)

# 📌 Rodar backtest
if st.button("▶️ Rodar backtest"):
    btc = get_btc_history(start_date, end_date)
    df = align_series(fgi, btc, start_date, end_date)

    if df.empty:
        st.warning("⚠️ Sem dados disponíveis para o período selecionado.")
    else:
        results, trades = run_backtest(df, buy_threshold, sell_threshold, trade_fee)

        st.subheader("📈 Comparação de Estratégias")
        st.table(results)

        st.subheader("📜 Histórico de Trades")
        st.dataframe(trades, use_container_width=True)

        # Exportar para Excel
        output_excel = pd.ExcelWriter("backtest_results.xlsx", engine="openpyxl")
        results.to_excel(output_excel, sheet_name="Resumo", index=False)
        trades.to_excel(output_excel, sheet_name="Trades", index=False)
        output_excel.close()

        with open("backtest_results.xlsx", "rb") as f:
            st.download_button(
                label="📥 Baixar resultados em Excel",
                data=f,
                file_name="backtest_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
