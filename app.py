"""
HiMart Intelligence — Flask 애플리케이션
"""
import os
from flask import Flask, jsonify, render_template, request
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, STORE_NAME, CATEGORIES, SUB_FILTERS
from database import (
    init_db, get_status, get_conn,
    get_subscription_products, add_subscription_product,
    update_subscription_product, delete_subscription_product,
    get_subscription_recommendations,
)
from ranker import get_all_recommendations, rank_category
import threading

app = Flask(__name__)

# Vercel 서버리스: 모듈 임포트 시점에 DB 초기화 (main 블록이 실행되지 않으므로)
if os.environ.get("VERCEL"):
    init_db()


# ── 기본 라우트 ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", store_name=STORE_NAME)


# ── API: 전체 추천 ──────────────────────────────────────────────────────────────
@app.route("/api/recommendations")
def api_recommendations():
    category = request.args.get("category")

    # spec 필터 파라미터 수집 ('category', 'days' 제외한 나머지)
    reserved = {"category", "days"}
    filters = {k: v for k, v in request.args.items() if k not in reserved and v}

    if category:
        if category not in CATEGORIES:
            return jsonify({"error": "잘못된 카테고리"}), 400
        items = rank_category(category, filters=filters or None)
        return jsonify({
            "category_key":  category,
            "category_name": CATEGORIES[category]["name"],
            "items":         items,
            "filters_applied": filters,
        })
    return jsonify(get_all_recommendations())


# ── API: 서브 필터 정의 ────────────────────────────────────────────────────────
@app.route("/api/filters")
def api_filters():
    """카테고리별 서브 필터 정의 반환"""
    return jsonify(SUB_FILTERS)


# ── API: 카테고리 목록 ─────────────────────────────────────────────────────────
@app.route("/api/categories")
def api_categories():
    return jsonify([
        {"key": k, "name": v["name"]}
        for k, v in CATEGORIES.items()
    ])


# ── API: 크롤러 상태 ───────────────────────────────────────────────────────────
@app.route("/api/status")
def api_status():
    from scheduler import get_next_run_time
    status = get_status()
    status["next_run"] = get_next_run_time()
    return jsonify(status)


# ── API: 크롤러 수동 실행 ──────────────────────────────────────────────────────
@app.route("/api/crawl", methods=["POST"])
def api_crawl():
    from crawler import run_crawler
    def _run():
        run_crawler()
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"message": "크롤링 시작됨. 잠시 후 새로고침하세요."})


# ── API: 구독상품 CRUD ────────────────────────────────────────────────────────

@app.route("/api/subscription", methods=["GET"])
def api_subscription_list():
    active_only = request.args.get("active") == "1"
    return jsonify(get_subscription_products(active_only=active_only))


@app.route("/api/subscription", methods=["POST"])
def api_subscription_add():
    d = request.get_json(force=True) or {}
    required = ("product_name", "monthly_fee")
    if not all(d.get(k) for k in required):
        return jsonify({"error": "product_name, monthly_fee 필수"}), 400
    try:
        new_id = add_subscription_product(
            product_name    = d["product_name"],
            model_no        = d.get("model_no", ""),
            category        = d.get("category", ""),
            monthly_fee     = int(d["monthly_fee"]),
            contract_months = int(d.get("contract_months", 36)),
            install_fee     = int(d.get("install_fee", 0)),
            image_url       = d.get("image_url", ""),
            product_url     = d.get("product_url", ""),
            notes           = d.get("notes", ""),
        )
        return jsonify({"id": new_id, "message": "구독상품 추가됨"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/subscription/<int:sub_id>", methods=["PUT"])
def api_subscription_update(sub_id):
    d = request.get_json(force=True) or {}
    if not d:
        return jsonify({"error": "변경 필드 없음"}), 400
    # 숫자 필드 형변환
    for key in ("monthly_fee", "contract_months", "install_fee", "is_active"):
        if key in d:
            d[key] = int(d[key])
    ok = update_subscription_product(sub_id, **d)
    if ok:
        return jsonify({"message": "업데이트 완료"})
    return jsonify({"error": "변경 항목 없음"}), 400


@app.route("/api/subscription/<int:sub_id>", methods=["DELETE"])
def api_subscription_delete(sub_id):
    delete_subscription_product(sub_id)
    return jsonify({"message": "삭제 완료"})


@app.route("/api/subscription/crawl", methods=["POST"])
def api_subscription_crawl():
    from crawler import run_subscription_crawler
    def _run():
        run_subscription_crawler()
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"message": "구독상품 크롤링 시작됨"})


# ── API: 구독 추천 (카테고리별 TOP 5, 월 요금 기준) ───────────────────────────
@app.route("/api/subscription/recommended")
def api_subscription_recommended():
    category = request.args.get("category")
    return jsonify(get_subscription_recommendations(category))


# ── API: 가격 히스토리 ─────────────────────────────────────────────────────────
@app.route("/api/history/<model_no>")
def api_price_history(model_no):
    """7일 / 30일 가격 히스토리 반환"""
    days = request.args.get("days", 30, type=int)
    if days not in (7, 30, 60, 90):
        days = 30
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            DATE(crawled_at)    AS date,
            MIN(original_price) AS original_price,
            MIN(sale_price)     AS sale_price,
            MIN(benefit_price)  AS benefit_price
        FROM price_history
        WHERE model_no = ?
          AND crawled_at >= DATE('now', ? || ' days')
        GROUP BY DATE(crawled_at)
        ORDER BY date ASC
    """, (model_no, f"-{days}")).fetchall()
    conn.close()

    return jsonify({
        "model_no":  model_no,
        "days":      days,
        "labels":    [r["date"]          for r in rows],
        "original":  [r["original_price"] for r in rows],
        "sale":      [r["sale_price"]     for r in rows],
        "benefit":   [r["benefit_price"]  for r in rows],
    })


# ── 이미지 CORS 프록시 ────────────────────────────────────────────────────────
@app.route("/proxy/image")
def proxy_image():
    import requests as req
    import base64
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "url 파라미터 필요"}), 400
    # e-himart CDN 도메인만 허용
    allowed = ("e-himart.co.kr", "static1.e-himart.co.kr", "static2.e-himart.co.kr",
               "mstatic1.e-himart.co.kr", "mstatic2.e-himart.co.kr")
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    if not any(host.endswith(d) for d in allowed):
        return jsonify({"error": "허용되지 않은 도메인"}), 403
    try:
        resp = req.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        b64  = base64.b64encode(resp.content).decode()
        return jsonify({"data": f"data:{mime};base64,{b64}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── 앱 시작 ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()

    # Vercel 서버리스 환경에서는 스케줄러 미실행
    if not os.environ.get("VERCEL"):
        from scheduler import start_scheduler
        start_scheduler()

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
