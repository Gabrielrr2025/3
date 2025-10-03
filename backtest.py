import pandas as pd
import numpy as np

# =========================
# Métricas auxiliares
# =========================
def annualized_return(equity: pd.Series, periods_per_year: float = 365.25) -> float:
    """
    CAGR a partir da curva de equity.
    """
    s = equity.dropna().astype(float)
    if len(s) < 2:
        return 0.0
    start_val = s.iloc[0]
    end_val = s.iloc[-1]
    if start_val <= 0:
        return 0.0
    years = len(s) / periods_per_year
    if years <= 0:
        return 0.0
    return (end_val / start_val) ** (1.0 / years) - 1.0

def max_drawdown(equity: pd.Series) -> float:
    """
    Máximo drawdown da curva de equity (valor negativo).
    """
    s = equity.dropna().astype(float)
    if s.empty:
        return 0.0
    peak = s.cummax()
    dd = s / peak - 1.0
    return float(dd.min() if not dd.empty else 0.0)

# =========================
# Backtest
# =========================
def run_backtest(
    df: pd.DataFrame,
    buy_th: int = 30,
    sell_th: int = 70,
    initial_capital: float = 10000.0,
    trade_on_close: bool = True,
    reinvest: bool = True,   # mantido para compatibilidade; a lógica é 100% alocado/zerado
    fee_bps: int = 10        # taxa aplicada em cada operação (compra e venda). 10 bps = 0,10%
):
    """
    Estratégia:
      - Compra quando FGI < buy_th
      - Vende quando FGI > sell_th
      - Execução no fechamento do dia (close) OU na abertura do dia seguinte (open_next)
      - Sem alavancagem; posição "tudo ou nada"
      - fee_bps é aplicado em cada operação (reduzindo o valor investido/recebido)

    Parâmetros:
      df: DataFrame com colunas ['Open','Close','FGI'] e índice de datas
    Retorna:
      trades_df: DataFrame com operações
      portfolio: DataFrame com a curva de equity (coluna 'equity')
    """
    data = df.copy().dropna(subset=["Close", "Open", "FGI"])

    # Sinais
    data["signal_buy"] = data["FGI"] < buy_th
    data["signal_sell"] = data["FGI"] > sell_th
    data["Open_next"] = data["Open"].shift(-1)

    # Estado da carteira
    cash = float(initial_capital)
    btc = 0.0
    positioned = False  # False = 0% alocado, True = 100% alocado
    fee_mult = 1.0 - (fee_bps / 10000.0)

    trades = []
    equity_rows = []

    for ts, row in data.iterrows():
        exec_price = row["Close"] if trade_on_close else row["Open_next"]

        # Se não há preço válido (ex.: última linha e next open), só marca equity e segue
        if pd.isna(exec_price):
            equity_rows.append((ts, cash + btc * row["Close"]))
            continue

        # Regras de entrada/saída
        if not positioned and row["signal_buy"]:
            # Comprar tudo
            if cash > 0:
                btc = (cash * fee_mult) / exec_price
                cash = 0.0
                positioned = True
                trades.append({"date": ts, "side": "buy", "price": float(exec_price), "fgi": float(row["FGI"])})

        elif positioned and row["signal_sell"]:
            # Vender tudo
            if btc > 0:
                cash = btc * exec_price * fee_mult
                btc = 0.0
                positioned = False
                trades.append({"date": ts, "side": "sell", "price": float(exec_price), "fgi": float(row["FGI"])})

        # Marca equity ao final do dia (mark-to-market no Close)
        equity_rows.append((ts, cash + btc * row["Close"]))

    portfolio = pd.DataFrame(equity_rows, columns=["date", "equity"]).set_index("date")
    trades_df = pd.DataFrame(trades)
    return trades_df, portfolio

# =========================
# Métricas e curvas
# =========================
def summary_metrics(portfolio: pd.DataFrame, close_prices: pd.Series, initial_capital: float) -> dict:
    """
    Calcula métricas da estratégia e do buy&hold:
      - Retorno total
      - CAGR
      - Máximo drawdown (estratégia)
    """
    if portfolio is None or portfolio.empty:
        return {
            "strategy_return": 0.0,
            "strategy_cagr": 0.0,
            "strategy_mdd": 0.0,
            "bh_return": 0.0,
            "bh_cagr": 0.0,
            "n_trades": 0,
        }

    # Estratégia
    strat_equity = portfolio["equity"].astype(float)
    strategy_return = float(strat_equity.iloc[-1] / float(initial_capital) - 1.0)
    strategy_cagr = float(annualized_return(strat_equity, periods_per_year=365.25))
    strategy_mdd = float(max_drawdown(strat_equity))

    # Buy & Hold
    s = close_prices.dropna().astype(float)
    if s.empty:
        bh_return = 0.0
        bh_cagr = 0.0
    else:
        first_close = float(s.iloc[0])
        last_close = float(s.iloc[-1])
        bh_equity = (s / first_close) * float(initial_capital)
        bh_return = float(last_close / first_close - 1.0)
        bh_cagr = float(annualized_return(bh_equity, periods_per_year=365.25))

    return {
        "strategy_return": strategy_return,
        "strategy_cagr": strategy_cagr,
        "strategy_mdd": strategy_mdd,
        "bh_return": bh_return,
        "bh_cagr": bh_cagr,
        "n_trades": 0,  # será substituído no app por len(trades)
    }

def equity_curves(portfolio: pd.DataFrame, close_prices: pd.Series, initial_capital: float) -> pd.DataFrame:
    """
    DataFrame com 'Strategy' e 'Buy&Hold' para plot.
    """
    if portfolio is None or portfolio.empty or close_prices is None or close_prices.empty:
        return pd.DataFrame(columns=["Strategy", "Buy&Hold"])

    strat = portfolio["equity"].rename("Strategy").astype(float)

    s = close_prices.dropna().astype(float)
    base = float(s.iloc[0])
    bh = ((s / base) * float(initial_capital)).rename("Buy&Hold")

    curves = pd.concat([strat, bh], axis=1).dropna()
    return curves
