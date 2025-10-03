import pandas as pd
import numpy as np
from datetime import date
from typing import Dict, Any

def run_fgi_strategy(df: pd.DataFrame, buy_threshold: int = 30, sell_threshold: int = 70) -> Dict[str, Any]:
    """
    Executa backtest da estratégia Fear & Greed Index.
    
    Lógica:
    - Compra quando FGI <= buy_threshold (padrão: 30)
    - Vende quando FGI >= sell_threshold (padrão: 70)
    
    Args:
        df: DataFrame com colunas ['Open', 'Close', 'FGI']
        buy_threshold: Nível de FGI para comprar
        sell_threshold: Nível de FGI para vender
    
    Returns:
        Dicionário com estatísticas da estratégia
    """
    if df is None or df.empty:
        return {
            "erro": "Dados insuficientes para análise",
            "total_dias": 0
        }
    
    df = df.copy()
    df = df.sort_index()
    
    # Inicializa variáveis
    position = None  # None = sem posição, 'long' = comprado
    buy_price = 0
    trades = []
    capital_inicial = 10000  # $10k inicial
    capital_atual = capital_inicial
    
    for idx, row in df.iterrows():
        fgi = row['FGI']
        close_price = row['Close']
        
        # Sinal de COMPRA
        if position is None and fgi <= buy_threshold:
            position = 'long'
            buy_price = close_price
            buy_date = idx
        
        # Sinal de VENDA
        elif position == 'long' and fgi >= sell_threshold:
            sell_price = close_price
            sell_date = idx
            
            # Calcula retorno da operação
            retorno_pct = ((sell_price - buy_price) / buy_price) * 100
            capital_atual = capital_atual * (1 + retorno_pct/100)
            
            trades.append({
                'compra_data': buy_date,
                'compra_preco': buy_price,
                'compra_fgi': df.loc[buy_date, 'FGI'],
                'venda_data': sell_date,
                'venda_preco': sell_price,
                'venda_fgi': fgi,
                'retorno_pct': retorno_pct,
                'dias_trade': (sell_date - buy_date).days
            })
            
            position = None
            buy_price = 0
    
    # Se ainda está em posição aberta, considera preço final
    if position == 'long':
        last_price = df.iloc[-1]['Close']
        retorno_pct = ((last_price - buy_price) / buy_price) * 100
        capital_atual = capital_atual * (1 + retorno_pct/100)
        
        trades.append({
            'compra_data': buy_date,
            'compra_preco': buy_price,
            'compra_fgi': df.loc[buy_date, 'FGI'],
            'venda_data': df.index[-1],
            'venda_preco': last_price,
            'venda_fgi': df.iloc[-1]['FGI'],
            'retorno_pct': retorno_pct,
            'dias_trade': (df.index[-1] - buy_date).days,
            'posicao_aberta': True
        })
    
    # Calcula Buy & Hold para comparação
    preco_inicial = df.iloc[0]['Close']
    preco_final = df.iloc[-1]['Close']
    retorno_buy_hold_pct = ((preco_final - preco_inicial) / preco_inicial) * 100
    capital_buy_hold = capital_inicial * (1 + retorno_buy_hold_pct/100)
    
    # Estatísticas gerais
    if trades:
        trades_df = pd.DataFrame(trades)
        trades_positivos = trades_df[trades_df['retorno_pct'] > 0]
        trades_negativos = trades_df[trades_df['retorno_pct'] <= 0]
        
        stats = {
            # Período
            "periodo_inicio": df.index[0].strftime('%Y-%m-%d'),
            "periodo_fim": df.index[-1].strftime('%Y-%m-%d'),
            "total_dias": len(df),
            
            # Performance Estratégia
            "capital_inicial": capital_inicial,
            "capital_final_estrategia": round(capital_atual, 2),
            "retorno_total_estrategia_pct": round(((capital_atual - capital_inicial) / capital_inicial) * 100, 2),
            
            # Performance Buy & Hold
            "capital_final_buy_hold": round(capital_buy_hold, 2),
            "retorno_total_buy_hold_pct": round(retorno_buy_hold_pct, 2),
            
            # Comparação
            "diferenca_vs_buy_hold_pct": round(((capital_atual - capital_buy_hold) / capital_buy_hold) * 100, 2),
            "melhor_estrategia": "FGI Strategy" if capital_atual > capital_buy_hold else "Buy & Hold",
            
            # Trades
            "numero_trades": len(trades),
            "trades_positivos": len(trades_positivos),
            "trades_negativos": len(trades_negativos),
            "taxa_acerto_pct": round((len(trades_positivos) / len(trades)) * 100, 2) if trades else 0,
            
            # Retornos
            "retorno_medio_por_trade_pct": round(trades_df['retorno_pct'].mean(), 2),
            "melhor_trade_pct": round(trades_df['retorno_pct'].max(), 2),
            "pior_trade_pct": round(trades_df['retorno_pct'].min(), 2),
            
            # Duração
            "duracao_media_trade_dias": round(trades_df['dias_trade'].mean(), 1),
            
            # Preços
            "preco_btc_inicial": round(preco_inicial, 2),
            "preco_btc_final": round(preco_final, 2),
            
            # Detalhes dos trades
            "trades_detalhados": trades
        }
    else:
        stats = {
            "erro": "Nenhum trade foi executado com esses parâmetros",
            "periodo_inicio": df.index[0].strftime('%Y-%m-%d'),
            "periodo_fim": df.index[-1].strftime('%Y-%m-%d'),
            "total_dias": len(df),
            "numero_trades": 0,
            "retorno_total_buy_hold_pct": round(retorno_buy_hold_pct, 2)
        }
    
    return stats


def analyze_threshold_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Testa diferentes combinações de thresholds para encontrar os melhores parâmetros.
    """
    results = []
    
    for buy_lvl in range(20, 45, 5):
        for sell_lvl in range(60, 85, 5):
            if sell_lvl <= buy_lvl:
                continue
            
            stats = run_fgi_strategy(df, buy_threshold=buy_lvl, sell_threshold=sell_lvl)
            
            if 'erro' not in stats:
                results.append({
                    'buy_threshold': buy_lvl,
                    'sell_threshold': sell_lvl,
                    'retorno_pct': stats['retorno_total_estrategia_pct'],
                    'num_trades': stats['numero_trades'],
                    'taxa_acerto': stats['taxa_acerto_pct']
                })
    
    return pd.DataFrame(results).sort_values('retorno_pct', ascending=False)