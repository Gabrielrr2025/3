import pandas as pd
import numpy as np

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
    portfolio_values = []  # Para tracking do drawdown

    for date, row in df.iterrows():
        price = row["Close"]
        fgi = row["FGI"]
        
        # Calcula valor atual do portfolio
        current_value = cash + (btc * price if btc > 0 else 0)
        portfolio_values.append(current_value)

        if position is None and fgi <= buy_threshold:
            btc = (cash * (1 - fee_rate)) / price
            cash = 0.0
            position = "long"
            trades.append({
                "date": date, 
                "action": "BUY", 
                "price": price, 
                "fgi": fgi, 
                "btc": btc,
                "portfolio_value": btc * price
            })

        elif position == "long" and fgi >= sell_threshold:
            cash = btc * price * (1 - fee_rate)
            btc = 0.0
            position = None
            trades.append({
                "date": date, 
                "action": "SELL", 
                "price": price, 
                "fgi": fgi, 
                "cash": cash,
                "portfolio_value": cash
            })

    final_price = df["Close"].iloc[-1]
    if position == "long":
        cash = btc * final_price * (1 - fee_rate)
        btc = 0.0
        trades.append({
            "date": df.index[-1], 
            "action": "FINAL SELL", 
            "price": final_price, 
            "fgi": df["FGI"].iloc[-1], 
            "cash": cash,
            "portfolio_value": cash
        })

    # Resultado da estratégia
    final_value = cash
    roi_strategy = (final_value - 1000) / 1000 * 100
    
    # Calcula max drawdown
    max_dd = calculate_max_drawdown(portfolio_values)
    
    # Calcula número de trades vencedores
    winning_trades = 0
    losing_trades = 0
    if len(trades) >= 2:
        for i in range(1, len(trades), 2):
            if i < len(trades):
                buy_price = trades[i-1].get("price", 0)
                sell_price = trades[i].get("price", 0)
                if sell_price > buy_price:
                    winning_trades += 1
                else:
                    losing_trades += 1
    
    win_rate = (winning_trades / (winning_trades + losing_trades) * 100) if (winning_trades + losing_trades) > 0 else 0

    # Resultado do Buy & Hold
    start_price = df["Close"].iloc[0]
    end_price = final_price
    roi_hold = (end_price - start_price) / start_price * 100
    final_hold_value = 1000 * (1 + roi_hold / 100)
    
    # Calcula drawdown do Buy & Hold
    hold_values = [1000 * (1 + (price - start_price) / start_price) for price in df["Close"]]
    max_dd_hold = calculate_max_drawdown(hold_values)

    results = pd.DataFrame([
        {
            "Estrategia": "FGI Strategy", 
            "Valor Final (USD)": round(final_value, 2), 
            "Retorno (%)": round(roi_strategy, 2),
            "Max Drawdown (%)": round(max_dd, 2),
            "Num Trades": len(trades),
            "Win Rate (%)": round(win_rate, 1)
        },
        {
            "Estrategia": "Buy & Hold", 
            "Valor Final (USD)": round(final_hold_value, 2), 
            "Retorno (%)": round(roi_hold, 2),
            "Max Drawdown (%)": round(max_dd_hold, 2),
            "Num Trades": 1,
            "Win Rate (%)": 100.0 if roi_hold > 0 else 0.0
        },
    ])

    trades_df = pd.DataFrame(trades)
    
    # Formata datas no trades
    if not trades_df.empty and "date" in trades_df.columns:
        trades_df["date"] = pd.to_datetime(trades_df["date"]).dt.strftime("%Y-%m-%d")
    
    return results, trades_df

def calculate_max_drawdown(portfolio_values):
    """
    Calcula o máximo drawdown (maior queda do pico ao vale)
    """
    if not portfolio_values or len(portfolio_values) < 2:
        return 0.0
    
    peak = portfolio_values[0]
    max_dd = 0.0
    
    for value in portfolio_values:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak * 100
        if drawdown > max_dd:
            max_dd = drawdown
    
    return max_dd
