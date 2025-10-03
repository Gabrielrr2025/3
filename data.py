import pandas as pd
import requests
import yfinance as yf
from datetime import date

def _empty_fgi_df():
    return pd.DataFrame({"FGI": pd.Series(dtype="float")}).set_index(
        pd.DatetimeIndex([], name="date")
    )

def get_fgi_history() -> pd.DataFrame:
    """
    Carrega o Fear & Greed Index diretamente do CSV no GitHub.
    O CSV é atualizado automaticamente via GitHub Actions.
    """
    try:
        csv_url = "https://raw.githubusercontent.com/Gabrielrr2025/csv/refs/heads/main/fear_greed.csv"
        fgi = pd.read_csv(csv_url, parse_dates=["date"], index_col="date")
        fgi["FGI"] = fgi["FGI"].astype(float)
        print(f"✅ FGI carregado do GitHub ({len(fgi)} linhas)")
        return fgi
    except Exception as e:
        print(f"⚠️ Erro ao carregar CSV do GitHub: {e}")
        return _empty_fgi_df()

def get_btc_history(start: date, end: date) -> pd.DataFrame:
    """
    Preço diário do BTC-USD.
    1) Tenta via Yahoo Finance
    2) Se falhar, usa CoinGecko como fallback
    """
    try:
        df = yf.download("BTC-USD", start=start, end=end, progress=False)
        if df is not None and not df.empty:
            df.index = pd.to_datetime(df.index.date)
            return df[["Open", "Close"]].dropna()
        raise ValueError("Yahoo retornou vazio")
    except Exception:
        try:
            url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
            start_ts = int(pd.Timestamp(start).timestamp())
            end_ts = int(pd.Timestamp(end).timestamp())
            params = {"vs_currency": "usd", "from": start_ts, "to": end_ts}
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json().get("prices", [])
            if not data:
                return pd.DataFrame(columns=["Open", "Close"])
            rows = []
            for ts, price in data:
                day = pd.to_datetime(ts, unit="ms").date()
                rows.append({"date": day, "Open": float(price), "Close": float(price)})
            df = pd.DataFrame(rows).drop_duplicates("date").set_index("date")
            return df
        except Exception:
            return pd.DataFrame(columns=["Open", "Close"])

def align_series(fgi: pd.DataFrame, px: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """
    Alinha séries por data (inner join) e recorta intervalo solicitado.
    """
    if fgi is None or fgi.empty or px is None or px.empty:
        return pd.DataFrame(columns=["Open", "Close", "FGI"])
    df = px.join(fgi, how="inner")
    df = df.loc[(df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))]
    return df
