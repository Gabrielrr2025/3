from flask import Flask, render_template, request, jsonify
from datetime import date, timedelta
from app import get_fgi_history, get_btc_history, align_series
from backtest import run_fgi_strategy, analyze_threshold_sensitivity
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/backtest', methods=['POST'])
def backtest():
    try:
        # Parâmetros da requisição
        data = request.get_json()
        buy_threshold = int(data.get('buy_threshold', 30))
        sell_threshold = int(data.get('sell_threshold', 70))
        
        # Define período (últimos 2 anos por padrão)
        end_date = data.get('end_date')
        start_date = data.get('start_date')
        
        if end_date:
            end_date = date.fromisoformat(end_date)
        else:
            end_date = date.today()
        
        if start_date:
            start_date = date.fromisoformat(start_date)
        else:
            start_date = end_date - timedelta(days=730)  # 2 anos
        
        # Baixa dados
        fgi_df = get_fgi_history()
        btc_df = get_btc_history(start_date, end_date)
        
        # Alinha séries
        df = align_series(fgi_df, btc_df, start_date, end_date)
        
        if df.empty:
            return jsonify({
                'erro': 'Não há dados suficientes para o período selecionado'
            }), 400
        
        # Executa backtest
        results = run_fgi_strategy(df, buy_threshold, sell_threshold)
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/optimize', methods=['POST'])
def optimize():
    try:
        # Define período
        end_date = date.today()
        start_date = end_date - timedelta(days=730)
        
        # Baixa dados
        fgi_df = get_fgi_history()
        btc_df = get_btc_history(start_date, end_date)
        df = align_series(fgi_df, btc_df, start_date, end_date)
        
        if df.empty:
            return jsonify({
                'erro': 'Não há dados suficientes'
            }), 400
        
        # Analisa diferentes thresholds
        sensitivity = analyze_threshold_sensitivity(df)
        
        return jsonify({
            'melhores_parametros': sensitivity.head(10).to_dict('records')
        })
    
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)