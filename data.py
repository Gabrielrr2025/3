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
        csv_url = "https://raw.githubusercontent.com/Gabrielrr2025/csv/refs/heads/main/fear_greed.csv"
        fgi = pd.read_csv(csv_url, parse_dates=["date"], index_col="date")
        fgi["FGI"] = fgi["FGI"].astype(float)
        print(f"✅ FGI carregado do GitHub ({len(fgi)} dias)")
        
        # Salva localmente para uso futuro
        try:
            fgi.to_csv(csv_path)
            print(f"💾 CSV salvo localmente em {csv_path}")
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
                # Tenta timestamp Unix primeiro
                try:
                    ts_int = int(ts)
                    day = pd.to_datetime(ts_int, unit='s').date()
                except (ValueError, TypeError):
                    # Fallback para string MM-DD-YYYY
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

def get_btc_history(start: date, end: date, max_retries: int = 3) -> pd.DataFrame:
    """
    Preço diário do BTC-USD com múltiplos fallbacks e retry logic.
    
    Tentativas em ordem:
    1. Yahoo Finance (yfinance) - retry até 3x com delay
    2. CoinGecko API
    3. Binance API (sem autenticação necessária)
    
    Args:
        start: Data inicial
        end: Data final
        max_retries: Número máximo de tentativas por fonte
    
    Returns:
        DataFrame com colunas ['Open', 'Close'] e índice date
    """
    print(f"📊 Buscando BTC de {start} até {end}...")
    
    # Validação de datas
    if start > end:
        print("❌ Data inicial não pode ser maior que data final")
        return pd.DataFrame(columns=["Open", "Close"])
    
    # Ajusta end para hoje se for no futuro
    today = date.today()
    if end > today:
        end = today
        print(f"⚠️ Data final ajustada para hoje: {end}")
    
    # MÉTODO 1: Yahoo Finance com retry
    for attempt in range(max_retries):
        try:
            print(f"🔄 Tentativa {attempt + 1}/{max_retries} - Yahoo Finance...")
            
            # Adiciona 1 dia ao end para incluir a data final
            end_adjusted = end + timedelta(days=1)
            
            df = yf.download(
                "BTC-USD", 
                start=start, 
                end=end_adjusted, 
                progress=False,
                repair=True  # Tenta reparar dados quebrados
            )
            
            if df is not None and not df.empty:
                # Normaliza índice para date apenas (remove timezone)
                df.index = pd.to_datetime(df.index).date
                df.index = pd.to_datetime(df.index)
                
                # Valida se tem as colunas necessárias
                required_cols = ["Open", "Close"]
                missing_cols = [col for col in required_cols if col not in df.columns]
                
                if missing_cols:
                    print(f"⚠️ Colunas faltando: {missing_cols}")
                    raise ValueError(f"Colunas necessárias não encontradas: {missing_cols}")
                
                result = df[["Open", "Close"]].dropna()
                
                if len(result) > 0:
                    print(f"✅ Yahoo Finance: {len(result)} dias de dados")
                    return result
                else:
                    print("⚠️ Yahoo Finance retornou dados mas todos são NaN")
                    
            raise ValueError("Yahoo Finance retornou vazio")
            
        except Exception as e:
            print(f"⚠️ Tentativa {attempt + 1} falhou: {str(e)[:100]}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Backoff exponencial
                print(f"⏳ Aguardando {wait_time}s antes de tentar novamente...")
                time.sleep(wait_time)
            else:
                print("❌ Yahoo Finance falhou após todas as tentativas")
    
    # MÉTODO 2: CoinGecko
    try:
        print("🔄 Tentando CoinGecko API...")
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
        
        start_ts = int(pd.Timestamp(start).timestamp())
        end_ts = int(pd.Timestamp(end).timestamp())
        
        params = {
            "vs_currency": "usd", 
            "from": start_ts, 
            "to": end_ts
        }
        
        headers = {"User-Agent": "BTC-Backtest/1.0"}
        
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        
        data = r.json().get("prices", [])
        
        if not data:
            raise ValueError("CoinGecko retornou lista vazia")
        
        # Processa dados do CoinGecko
        rows = []
        for ts_ms, price in data:
            day = pd.to_datetime(ts_ms, unit="ms").date()
            rows.append({
                "date": pd.to_datetime(day), 
                "Open": float(price), 
                "Close": float(price)
            })
        
        df = pd.DataFrame(rows).drop_duplicates("date").set_index("date")
        print(f"✅ CoinGecko: {len(df)} dias de dados")
        return df
        
    except Exception as e:
        print(f"❌ CoinGecko falhou: {str(e)[:100]}")
    
    # MÉTODO 3: Binance (sem autenticação)
    try:
        print("🔄 Tentando Binance API...")
        
        # Binance usa milissegundos
        start_ts = int(pd.Timestamp(start).timestamp() * 1000)
        end_ts = int(pd.Timestamp(end).timestamp() * 1000)
        
        url = "https://api.binance.com/api/v3/klines"
        
        all_data = []
        current_start = start_ts
        
        # Binance limita a 1000 velas por request
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
            
            # Atualiza para próximo batch
            last_timestamp = batch[-1][0]
            current_start = last_timestamp + 86400000  # +1 dia em ms
            
            if len(batch) < 1000:
                break
        
        if not all_data:
            raise ValueError("Binance retornou vazio")
        
        # Processa dados da Binance
        # Formato: [timestamp, open, high, low, close, volume, ...]
        rows = []
        for candle in all_data:
            day = pd.to_datetime(candle[0], unit="ms").date()
            rows.append({
                "date": pd.to_datetime(day),
                "Open": float(candle[1]),
                "Close": float(candle[4])
            })
        
        df = pd.DataFrame(rows).drop_duplicates("date").set_index("date")
        print(f"✅ Binance: {len(df)} dias de dados")
        return df
        
    except Exception as e:
        print(f"❌ Binance falhou: {str(e)[:100]}")
    
    # Se tudo falhar
    print("❌ ERRO: Todas as fontes de dados falharam!")
    print("   Verifique sua conexão com a internet")
    print("   Tente novamente em alguns minutos")
    return pd.DataFrame(columns=["Open", "Close"])

def align_series(fgi: pd.DataFrame, px: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """
    Alinha séries por data (inner join) e recorta intervalo solicitado.
    """
    if fgi is None or fgi.empty:
        print("❌ DataFrame FGI vazio ou inválido")
        return pd.DataFrame(columns=["Open", "Close", "FGI"])
    
    if px is None or px.empty:
        print("❌ DataFrame de preços vazio ou inválido")
        return pd.DataFrame(columns=["Open", "Close", "FGI"])
    
    print(f"🔗 Alinhando séries...")
    print(f"   FGI: {len(fgi)} dias ({fgi.index.min()} - {fgi.index.max()})")
    print(f"   BTC: {len(px)} dias ({px.index.min()} - {px.index.max()})")
    
    df = px.join(fgi, how="inner")
    
    print(f"   Após join: {len(df)} dias")
    
    # Filtra por data
    df = df.loc[(df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))]
    
    print(f"   Após filtro de datas: {len(df)} dias")
    
    if df.empty:
        print("⚠️ Nenhum dado após alinhamento. Verifique se os períodos se sobrepõem.")
    
    return df
