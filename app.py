from flask import Flask, request, jsonify, render_template
from data import get_fgi_history, get_btc_history, align_series  # corrigido: não importa de app, mas de data
from backtest import run_backtest, summary_metrics, equity_curves

app = Flask(__name__)

@app.route("/")
def index():
    # Healthcheck simples
    return jsonify({"status": "ok", "message": "Fear & Greed Backtest API rodando"})

@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    try:
        data = request.get_json(force=True)

        start_date = data.get("start_date")
        end_date = data.get("end_date")
        buy_threshold = int(data.get("buy_threshold", 30))
        sell_threshold = int(data.get("sell_threshold", 70))
        initial_capital = float(data.get("initial_capital", 10000.0))

        # Validações básicas
        if not start_date or not end_date:
            return jsonify({"erro": "start_date e end_date são obrigatórios"}), 400
        if sell_threshold <= buy_threshold:
            return jsonify({"erro": "sell_threshold deve ser maior que buy_threshold"}), 400

        fgi = get_fgi_history()
        btc = get_btc_history(start_date, end_date)
        df = align_series(fgi, btc, start_date, end_date)

        if df.empty:
            return jsonify({"erro": "Sem dados disponíveis no período informado"}), 404

        trades, portfolio = run_backtest(
            df=df,
            buy_th=buy_threshold,
            sell_th=sell_threshold,
            initial_capital=initial_capital,
            trade_on_close=True,
            reinvest=True,
            fee_bps=10
        )

        metrics = summary_metrics(portfolio, df["Close"], initial_capital)
        metrics["n_trades"] = len(trades)

        return jsonify({
            "metrics": metrics,
            "trades": trades.to_dict(orient="records"),
            "portfolio": portfolio.reset_index().to_dict(orient="records")
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    # endpoint futuro para rodar testes de sensibilidade
    return jsonify({"status": "em construção"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
