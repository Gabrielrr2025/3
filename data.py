import pandas as pd
import requests
import yfinance as yf
from datetime import date, datetime, timedelta
import os
import time

def _empty_fgi_df():
    return pd.DataFrame({"FGI": pd.Series(dtype="float")}).set_index(
        pd.DatetimeIndex([], name="date")
    )

def _empty_btc_df():
    return pd.DataFrame({"Open": pd.Series(dtype="float"), "Close": pd.Series(dtype="float")}).set_index(
        pd.DatetimeIndex([], name="date")
    )

def get_fgi_history(csv_path: str = "fear_greed.csv") -> pd.DataFrame:
    """
    Carrega o Fear & Greed Index com fallback em 3 níveis:
    1. CSV local (se existir)
    2. GitHub raw URL
    3. API alternative.me (último recurso)
    
    Retorna DF com índice 'date' (datetime) e coluna 'FGI' (float).
    """
    # PRIORIDADE 1: CSV local
    if os.path.exists(csv_path):
        try:
            fgi = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")
            if not fgi.empty and "FGI" in fgi.columns:
                fgi["FGI"] = fgi["FGI"].astype(float)
                print(f"✅ FGI carregado do CSV local ({len(fgi)} dias)")
                return fgi
        except Exception as e:
            print(f"⚠️ Erro ao ler CSV local: {e}")
    
    # PRIORIDADE 2: GitHub raw URL
    try:
        csv_url = "https://raw.githubusercontent.com/Gabrielrr2025/csvexportFGI/refs/heads/main/fear_greed.csv"
        fgi = pd.read_csv(csv_url, parse_dates=["date"], index_col="date")
        fgi["FGI"] = fgi["FGI"].astype(float)
        print(f"✅ FGI carregado do GitHub ({len(fgi)} dias)")
        
        # Salva localmente para uso futuro
        try:
            fgi.to_csv(csv_path)
            print(f"💾 CSV FGI salvo localmente")
        except:
            pass
            
        return fgi
    except Exception as e:
        print(f"⚠️ Erro ao carregar CSV do GitHub: {e}")
    
    # PRIORIDADE 3: API como último recurso
    print("📡 Tentando API alternative.me como fallback...")
    return _fetch_fgi_from_api()

def _fetch_fgi_from_api() -> pd.DataFrame:
    """
    Baixa FGI diretamente da API (fallback final).
    """
    url = "https://api.alternative.me/fng/"
    params = {"limit": 0, "format": "json"}
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
                try:
                    ts_int = int(ts)
                    day = pd.to_datetime(ts_int, unit='s').date()
                except (ValueError, TypeError):
                    day = pd.to_datetime(str(ts), format="%m-%d-%Y").date()
                
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
        print(f"✅ FGI baixado da API ({len(fgi)} dias)")
        return fgi

    except Exception as e:
        print(f"❌ Erro ao buscar API: {e}")
        return _empty_fgi_df()

def get_btc_history(start: date, end: date, csv_path: str = "btc_prices.csv") -> pd.DataFrame:
    """
    Preço diário do BTC-USD com múltiplos fallbacks.
    
    Prioridade:
    1. CSV local (se existir e cobrir o período)
    2. GitHub raw URL (atualizado diariamente)
    3. Yahoo Finance com retry
    4. CoinGecko API
    5. Binance API
    
    Args:
        start: Data inicial
        end: Data final
        csv_path: Caminho do CSV local
    
    Returns:
        DataFrame com colunas ['Open', 'Close'] e índice date
    """
    print(f"📊 Buscando BTC de {start} até {end}...")
    
    # Validação de datas
    if start > end:
        print("❌ Data inicial maior que final")
        return _empty_btc_df()
    
    today = date.today()
    if end > today:
        end = today
        print(f"⚠️ Data final ajustada para hoje: {end}")
    
    # PRIORIDADE 1: CSV local
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")
            if not df.empty:
                # Filtra pelo período solicitado
                df_filtered = df.loc[(df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))]
                
                if len(df_filtered) > 0:
                    print(f"✅ BTC carregado do CSV local ({len(df_filtered)} dias)")
                    return df_filtered[["Open", "Close"]]
        except Exception as e:
            print(f"⚠️ Erro ao ler CSV local: {e}")
    
    # PRIORIDADE 2: GitHub raw URL
    try:
        csv_url = "https://raw.githubusercontent.com/Gabrielrr2025/exportbtc/refs/heads/main/btc_prices.csv"
        df = pd.read_csv(csv_url, parse_dates=["date"], index_col="date")
        
        if not df.empty:
            # Salva localmente
            try:
                df.to_csv(csv_path)
                print(f"💾 CSV BTC salvo localmente")
            except:
                pass
            
            # Filtra período
            df_filtered = df.loc[(df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))]
            
            if len(df_filtered) > 0:
                print(f"✅ BTC carregado do GitHub ({len(df_filtered)} dias)")
                return df_filtered[["Open", "Close"]]
    except Exception as e:
        print(f"⚠️ Erro ao carregar CSV do GitHub: {e}")
    
    # PRIORIDADE 3+: APIs (fallback)
    print("📡 CSV não disponível, buscando das APIs...")
    return _fetch_btc_from_apis(start, end)

def _fetch_btc_from_apis(start: date, end: date, max_retries: int = 2) -> pd.DataFrame:
    """
    Fallback: busca BTC de múltiplas APIs.
    """
    # Método 1: Yahoo Finance
    for attempt in range(max_retries):
        try:
            print(f"🔄 Tentativa {attempt + 1}/{max_retries} - Yahoo Finance...")
            
            end_adjusted = end + timedelta(days=1)
            df = yf.download("BTC-USD", start=start, end=end_adjusted, progress=False, repair=True)
            
            if df is not None and not df.empty:
                df.index = pd.to_datetime(df.index).date
                df.index = pd.to_datetime(df.index)
                
                if "Open" in df.columns and "Close" in df.columns:
                    result = df[["Open", "Close"]].dropna()
                    if len(result) > 0:
                        print(f"✅ Yahoo Finance: {len(result)} dias")
                        return result
                        
        except Exception as e:
            print(f"⚠️ Yahoo tentativa {attempt + 1} falhou: {str(e)[:80]}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    # Método 2: CoinGecko
    try:
        print("🔄 Tentando CoinGecko...")
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
        
        start_ts = int(pd.Timestamp(start).timestamp())
        end_ts = int(pd.Timestamp(end).timestamp())
        
        params = {"vs_currency": "usd", "from": start_ts, "to": end_ts}
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        
        data = r.json().get("prices", [])
        if data:
            rows = []
            for ts_ms, price in data:
                day = pd.to_datetime(ts_ms, unit="ms").date()
                rows.append({"date": pd.to_datetime(day), "Open": float(price), "Close": float(price)})
            
            df = pd.DataFrame(rows).drop_duplicates("date").set_index("date")
            print(f"✅ CoinGecko: {len(df)} dias")
            return df
    except Exception as e:
        print(f"❌ CoinGecko falhou: {str(e)[:80]}")
    
    # Método 3: Binance
    try:
        print("🔄 Tentando Binance...")
        url = "https://api.binance.com/api/v3/klines"
        
        start_ts = int(pd.Timestamp(start).timestamp() * 1000)
        end_ts = int(pd.Timestamp(end).timestamp() * 1000)
        
        all_data = []
        current_start = start_ts
        
        while current_start < end_ts:
            params = {
                "symbol": "BTCUSDT",
                "interval": "1d",
                "startTime": current_start,
                "endTime": end_ts,
                "limit": 1000
            }
            
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            batch = r.json()
            
            if not batch:
                break
            
            all_data.extend(batch)
            current_start = batch[-1][0] + 86400000
            
            if len(batch) < 1000:
                break
        
        if all_data:
            rows = []
            for candle in all_data:
                day = pd.to_datetime(candle[0], unit="ms").date()
                rows.append({"date": pd.to_datetime(day), "Open": float(candle[1]), "Close": float(candle[4])})
            
            df = pd.DataFrame(rows).drop_duplicates("date").set_index("date")
            print(f"✅ Binance: {len(df)} dias")
            return df
    except Exception as e:
        print(f"❌ Binance falhou: {str(e)[:80]}")
    
    print("❌ Todas as fontes falharam!")
    return _empty_btc_df()

def align_series(fgi: pd.DataFrame, px: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """
    Alinha séries por data (inner join) e recorta intervalo solicitado.
    """
    if fgi is None or fgi.empty:
        print("❌ DataFrame FGI vazio")
        return pd.DataFrame(columns=["Open", "Close", "FGI"])
    
    if px is None or px.empty:
        print("❌ DataFrame BTC vazio")
        return pd.DataFrame(columns=["Open", "Close", "FGI"])
    
    print(f"🔗 Alinhando séries...")
    print(f"   FGI: {len(fgi)} dias ({fgi.index.min().date()} - {fgi.index.max().date()})")
    print(f"   BTC: {len(px)} dias ({px.index.min().date()} - {px.index.max().date()})")
    
    df = px.join(fgi, how="inner")
    print(f"   Após join: {len(df)} dias")
    
    df = df.loc[(df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))]
    print(f"   Após filtro: {len(df)} dias")
    
    if df.empty:
        print("⚠️ Vazio após alinhamento. Verifique sobreposição de datas.")
    
    return df
