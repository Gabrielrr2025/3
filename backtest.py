import pandas as pd

def run_backtest(df, buy_threshold=30, sell_threshold=70, fee=0.1):
    """
    Backtest baseado no Fear & Greed Index.
    Compra se FGI <= buy_threshold, vende se FGI >= sell_threshold.
    Também calcula o retorno do Buy & Hold no mesmo período.
    """

    cash = 1000.0  # capital inicial em USD
    btc = 0.0
    trades = []
    position = None
    fee_rate = fee / 100

    for date, row in df.iterrows():
        price = row["Close"]
        fgi = row["FGI"]

        if position is None and fgi <= buy_threshold:
            btc = (cash * (1 - fee_rate)) / price
            cash = 0.0
            position = "long"
            trades.append({"date": date, "action": "BUY", "price": price, "fgi": fgi, "btc": btc})

        elif position == "long" and fgi >= sell_threshold:
            cash = btc * price * (1 - fee_rate)
            btc = 0.0
            position = None
            trades.append({"date": date, "action": "SELL", "price": price, "fgi": fgi, "cash": cash})

    final_price = df["Close"].iloc[-1]
    if position == "long":
        cash = btc * final_price * (1 - fee_rate)
        btc = 0.0
        trades.append({"date": df.index[-1], "action": "FINAL SELL", "price": final_price, "fgi": fgi, "cash": cash})

    # Resultado da estratégia
    final_value = cash
    roi_strategy = (final_value - 1000) / 1000 * 100

    # Resultado do Buy & Hold
    start_price = df["Close"].iloc[0]
    end_price = final_price
    roi_hold = (end_price - start_price) / start_price * 100
    final_hold_value = 1000 * (1 + roi_hold / 100)

    results = pd.DataFrame([
        {"Estrategia": "FGI Strategy", "Valor Final (USD)": round(final_value, 2), "Retorno (%)": round(roi_strategy, 2)},
        {"Estrategia": "Buy & Hold", "Valor Final (USD)": round(final_hold_value, 2), "Retorno (%)": round(roi_hold, 2)},
    ])

    trades_df = pd.DataFrame(trades)
    return results, trades_df
