import pandas as pd
import requests
import yfinance as yf
from datetime import datetime, date
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ===== Helpers =====
def _requests_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.8,  # 0.8s, 1.6s, 3.2s
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; FGI-Backtest/1.0; +https://example.com)"
    })
    return session

def _empty_fgi_df():
    return pd.DataFrame({"FGI": pd.Series(dtype="float")}).set_index(
        pd.DatetimeIndex([], name="date")
    )

# ===== Funções principais =====
def get_fgi_history() -> pd.DataFrame:
    """
    Baixa histórico do Fear & Greed Index (FGI).
    Retorna DF com índice 'date' e coluna 'FGI' (float entre 0..100).
    """
    url = "https://api.alternative.me/fng/"
    params = {"limit": 0, "format": "json", "date_format": "us"}

    try:
        s = _requests_session()
        r = s.get(url, params=params, timeout=30)
        if r.status_code >= 400:
            return _empty_fgi_df()

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
        fgi["FGI"] = pd.to_numeric(fgi["FGI"], errors="coerce").clip(0, 100)
        fgi.index = pd.DatetimeIndex(fgi.index, name="date")
        return fgi

    except Exception:
        return _empty_fgi_df()

def get_btc_history(start: date, end: date) -> pd.DataFrame:
    """
    Preço diário do BTC-USD via Yahoo Finance (yfinance).
    Retorna colunas Open/Close e índice diário.
    """
    if start is None or end is None:
        return pd.DataFrame(columns=["Open", "Close"])

    df = yf.Ticker("BTC-USD").history(start=start, end=end, interval="1d")
    if df is None or df.empty:
        return pd.DataFrame(columns=["Open", "Close"])

    df = df.rename(columns={"Open": "Open", "Close": "Close"})
    df.index = pd.to_datetime(df.index.date)
    df.index.name = "date"
    out = df[["Open", "Close"]].dropna()
    out["Open"] = pd.to_numeric(out["Open"], errors="coerce")
    out["Close"] = pd.to_numeric(out["Close"], errors="coerce")
    return out.dropna()

def align_series(fgi: pd.DataFrame, px: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """
    Alinha por data:
      - usa calendário do preço (px) como base
      - FGI é forward-filled
      - recorta pelo intervalo
    """
    if fgi is None or fgi.empty or px is None or px.empty:
        return pd.DataFrame(columns=["Open", "Close", "FGI"])

    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)

    fgi_re = fgi.reindex(px.index).ffill()
    df = px.join(fgi_re, how="left")
    df = df.loc[(df.index >= start_dt) & (df.index <= end_dt)]
    df = df.dropna(subset=["Open", "Close"])
    df["FGI"] = pd.to_numeric(df["FGI"], errors="coerce").clip(0, 100).ffill()

    return df[["Open", "Close", "FGI"]]
