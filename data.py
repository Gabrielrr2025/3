import pandas as pd
import requests
import yfinance as yf
from datetime import datetime, date

def _empty_fgi_df():
    return pd.DataFrame({"FGI": pd.Series(dtype="float")}).set_index(
        pd.DatetimeIndex([], name="date")
    )

def get_fgi_history() -> pd.DataFrame:
    """
    Baixa histórico do Fear & Greed Index (FGI) em formato JSON.
    Fonte oficial: https://api.alternative.me/fng/
    Retorna DF com índice 'date' (datetime) e coluna 'FGI' (float).
    """
    url = "https://api.alternative.me/fng/"
    params = {"limit": 0, "format": "json", "date_format": "us"}
    headers = {"User-Agent": "FGI-Backtest/1.0"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data", [])
        if not data:
            return _empty_fgi_df()

        rows = []
        for d in data:
            ts = d.get("timestamp")
            val = d.get("value")
            if ts is None or val is None:
                continue
            try:
                ts_int = int(ts)
                day = datetime.utcfromtimestamp(ts_int).date()
                rows.append({"date": pd.to_datetime(day), "FGI": float(val)})
            except Exception:
                continue

        if not rows:
            return _empty_fgi_df()

        fgi = (
            pd.DataFrame(rows)
            .drop_duplicates(subset=["date"])
            .sort_values("date")
            .set_index("date")
        )
        fgi["FGI"] = fgi["FGI"].astype(float)
        return fgi

    except Exception:
        return _empty_fgi_df()

def get_btc_history(start: date, end: date) -> pd.DataFrame:
    """
    Preço diário do BTC-USD.
    1) Tenta via Yahoo Finance (yfinance)
    2) Se falhar, usa CoinGecko como fallback
    """
    try:
        # Yahoo Finance mais estável com yf.download
        df = yf.download("BTC-USD", start=start, end=end, progress=False)
        if df is not None and not df.empty:
            df.index = pd.to_datetime(df.index.date)
            return df[["Open", "Close"]].dropna()
        raise ValueError("Yahoo retornou vazio")
    except Exception:
        # Fallback CoinGecko (Close = preço único do dia)
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
