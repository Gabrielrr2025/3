#!/usr/bin/env python3
import io
from datetime import date, timedelta
import pandas as pd
import streamlit as st

from backtest import run_backtest, summary_metrics, equity_curves
from data import get_fgi_history, get_btc_history, align_series

st.set_page_config(page_title="BTC Fear & Greed Backtest", layout="wide")
st.title("📈 Backtest BTC usando Fear & Greed Index")
st.caption("Compra quando FGI < limiar de 'medo' e vende quando FGI > limiar de 'ganância'. Dados diários.")

# ===== Sidebar =====
with st.sidebar:
    st.header("Parâmetros")
    start = st.date_input("Data inicial", value=date(2018, 2, 1), help="FGI tem histórico desde 2018.")
    end = st.date_input("Data final", value=date.today() - timedelta(days=1))
    buy_th = st.number_input("Comprar quando FGI < ", value=30, min_value=0, max_value=49, step=1)
    sell_th = st.number_input("Vender quando FGI > ", value=70, min_value=51, max_value=100, step=1)
    initial_capital = st.number_input("Capital inicial (USD)", value=10000.0, min_value=10.0, step=100.0, format="%.2f")
    trade_on_close = st.selectbox(
        "Preço da execução",
        ["Fechamento (close)", "Abertura do dia seguinte (open)"]
    ) == "Fechamento (close)"
    fee_bps = st.number_input("Taxa por trade (bps)", value=10, min_value=0, max_value=2000, help="1 bps = 0,01%.")

# ===== Baixar dados =====
st.info("Buscando dados do Fear & Greed Index e do preço do BTC...")
try:
    fgi = get_fgi_history()
    px = get_btc_history(start, end)
    df = align_series(fgi, px, start, end)
except Exception as e:
    st.error(f"Falha ao obter dados: {e}")
    st.stop()

if df is None or df.empty:
    st.error("Sem dados no período (ou a fonte não retornou valores).")
    st.caption(f"Debug — FGI linhas: {0 if fgi is None else len(fgi)} | BTC linhas: {0 if px is None else len(px)}")
    st.stop()

st.subheader("Amostra de dados")
st.dataframe(df.head(10))

# ===== Botão para rodar o backtest =====
if st.button("▶️ Rodar backtest"):
    trades, portfolio = run_backtest(
        df=df,
        buy_th=buy_th,
        sell_th=sell_th,
        initial_capital=initial_capital,
        trade_on_close=trade_on_close,
        reinvest=True,
        fee_bps=fee_bps
    )

    metrics = summary_metrics(portfolio, df["Close"], initial_capital)
    metrics["n_trades"] = len(trades)

    # ===== Resultados =====
    st.subheader("Resultados da estratégia")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Retorno Estratégia", f"{metrics['strategy_return']*100:,.2f}%", f"{metrics['strategy_cagr']*100:,.2f}% a.a.")
    c2.metric("Retorno Buy&Hold", f"{metrics['bh_return']*100:,.2f}%", f"{metrics['bh_cagr']*100:,.2f}% a.a.")
    c3.metric("Máx. Drawdown (Estrat.)", f"{metrics['strategy_mdd']*100:,.2f}%")
    c4.metric("Nº de operações", int(metrics["n_trades"]))

    # ===== Curva de capital =====
    st.subheader("Curva de capital")
    curves = equity_curves(portfolio, df["Close"], initial_capital)
    st.line_chart(curves)

    # ===== Trades =====
    with st.expander("Operações (trades)"):
        st.dataframe(trades)

    # ===== Exportação =====
    st.subheader("Exportar resultados")
    def to_excel_bytes(trades_df, portfolio_df, curves_df):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as w:
            trades_df.to_excel(w, sheet_name="trades", index=False)
            portfolio_df.to_excel(w, sheet_name="portfolio", index=True)
            curves_df.to_excel(w, sheet_name="equity_curves", index=True)
        return output.getvalue()

    excel_bytes = to_excel_bytes(trades, portfolio, curves)
    st.download_button("📥 Baixar Excel", data=excel_bytes, file_name="fgi_backtest.xlsx")
    st.download_button("📥 Baixar Trades (CSV)", data=trades.to_csv(index=False).encode("utf-8"), file_name="trades.csv")

    st.caption("Aviso: backtests não garantem resultados futuros. Uso educacional.")

# ===== Fonte =====
st.caption("Fonte do Fear & Greed Index: alternative.me")
