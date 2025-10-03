import pandas as pd
import requests
import yfinance as yf
from datetime import datetime, date

def _empty_fgi_df():
    # DataFrame vazio com índice datetime nomeado "date" e coluna FGI float
    return pd.DataFrame({"FGI": pd.Series(dtype="float")}).set_index(
        pd.DatetimeIndex([], name="date")
    )

def get_fgi_history() -> pd.DataFrame:
    """
    Baixa histórico do Fear & Greed Index (FGI) em formato JSON.
    Retorna DF com índice 'date' (datetime) e coluna 'FGI' (float).
    Em caso de falha/sem dados, retorna DF vazio (não quebra o app).
    """
    url = "https://api.alternative.me/fng/"
    params = {"limit": 0, "format": "json", "date_format": "us"}
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FGI-Backtest/1.0; +https://example.com)"
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data", [])
        if not data:
            # Sem dados retornados
            return _empty_fgi_df()

        rows = []
        for d in data:
            # Esperado: d["timestamp"] e d["value"]
            ts = d.get("timestamp")
            val = d.get("value")
            if ts is None or val is None:
                continue
            try:
                ts_int = int(ts)
                day = datetime.utcfromtimestamp(ts_int).date()
                rows.append({"date": pd.to_datetime(day), "FGI": float(val)})
            except Exception:
                # Pula entradas inesperadas
                continue

        if not rows:
            return _empty_fgi_df()

        fgi = (
            pd.DataFrame(rows)
            .drop_duplicates(subset=["date"])
            .sort_values("date")
            .set_index("date")
        )
        # Garante tipo float
        fgi["FGI"] = fgi["FGI"].astype(float)
        return fgi

    except Exception:
        # Em qualquer erro de rede/JSON, retorna vazio
        return _empty_fgi_df()

def get_btc_history(start: date, end: date) -> pd.DataFrame:
    """
    Preço diário do BTC-USD via Yahoo Finance (yfinance).
    Retorna colunas Open/Close e índice por dia (datetime).
    """
    ticker = yf.Ticker("BTC-USD")
    df = ticker.history(start=start, end=end)
    if df is None or df.empty:
        return pd.DataFrame(columns=["Open", "Close"])

    df = df.rename(columns={"Open": "Open", "Close": "Close"})
    # Usa somente a data (diário)
    df.index = pd.to_datetime(df.index.date)
    return df[["Open", "Close"]].dropna()

def align_series(fgi: pd.DataFrame, px: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """
    Alinha séries por data (inner join) e recorta intervalo solicitado.
    Se alguma vier vazia, o resultado tende a ser vazio (tratado no app).
    """
    if fgi is None or fgi.empty or px is None or px.empty:
        return pd.DataFrame(columns=["Open", "Close", "FGI"])

    df = px.join(fgi, how="inner")
    df = df.loc[(df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))]
    return df