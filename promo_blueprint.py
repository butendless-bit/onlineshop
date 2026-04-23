"""Promo workflow Flask blueprint."""

from __future__ import annotations

from urllib.parse import urlencode

from flask import Blueprint, jsonify, render_template, request

from config import STORE_NAME
from promo_repository import (
    DEFAULT_DISCLAIMER,
    build_landing_payload,
    create_campaign,
    delete_campaign,
    get_cached_image_asset,
    get_campaign,
    get_default_store_info,
    init_promo_db,
    list_campaigns,
    record_campaign_event,
    resolve_selected_products,
    save_generated_asset,
    save_image_asset,
    save_tracked_link,
    update_tracked_link,
    update_campaign,
)
from services.background_removal import remove_background
from services.claude_service import (
    ClaudeServiceError as OpenAIServiceError,
    generate_blog_prompt,
    generate_creative_title,
    generate_instagram_prompt,
    generate_short_product_name,
    recommend_campaign_info,
    recommend_landing_copy,
)

promo_bp = Blueprint("promo", __name__)


def _base_context(page_key: str) -> dict:
    embed_mode = request.args.get("embed") == "1"
    return {
        "store_name": STORE_NAME,
        "embed_mode": embed_mode,
        "nav_items": [
            {"label": "추천 상품", "href": "/main", "key": "recommendations"},
            {"label": "온라인 홍보", "href": "/promo", "key": "promo"},
        ],
        "active_nav": page_key,
    }


@promo_bp.record_once
def _on_load(_: object) -> None:
    init_promo_db()


@promo_bp.route("/promo")
def promo_hub():
    context = _base_context("promo")
    context["store_info"] = get_default_store_info()
    return render_template("promo/hub.html", **context)


@promo_bp.route("/promo/creative")
def promo_creative():
    return render_template("promo/creative.html", **_base_context("promo"))


@promo_bp.route("/promo/landing")
def promo_landing():
    return render_template(
        "promo/landing_builder.html",
        disclaimer=DEFAULT_DISCLAIMER,
        **_base_context("promo"),
    )


@promo_bp.route("/promo/instagram")
def promo_instagram():
    return render_template("promo/instagram.html", **_base_context("promo"))


@promo_bp.route("/promo/blog")
def promo_blog():
    return render_template("promo/blog.html", **_base_context("promo"))


@promo_bp.route("/promo/links")
def promo_links():
    return render_template("promo/links.html", **_base_context("promo"))


@promo_bp.route("/promo/saved")
def promo_saved():
    return render_template("promo/saved.html", **_base_context("saved"))


@promo_bp.route("/promo/<campaign_id>")
def promo_campaign(campaign_id: str):
    return render_template("promo/campaign.html", campaign_id=campaign_id, **_base_context("promo"))


@promo_bp.route("/api/promo/selection/resolve", methods=["POST"])
def api_promo_selection_resolve():
    payload = request.get_json(force=True) or {}
    selections = payload.get("selections") or []
    products = resolve_selected_products(selections)
    print(f"[promo] selection_resolve selections={len(selections)} resolved={len(products)}")
    return jsonify({"items": products, "store_info": get_default_store_info()})


@promo_bp.route("/api/promo/create-campaign", methods=["POST"])
def api_promo_create_campaign():
    payload = request.get_json(force=True) or {}
    try:
        selected = payload.get("selected_product_ids") or []
        print(f"[promo] create_campaign requested selected={len(selected)}")
        if not selected:
            print("[promo] create_campaign rejected: no selected_product_ids")
            return jsonify({"error": "선택된 상품이 없어 캠페인을 만들 수 없습니다."}), 400
        products = resolve_selected_products(selected)
        recommended = recommend_campaign_info(
            products,
            store_name=payload.get("store_name", STORE_NAME),
        )
        payload["event_title"] = payload.get("event_title") or recommended["event_title"]
        payload["campaign_name"] = payload.get("campaign_name") or recommended["campaign_name"]
        campaign = create_campaign(payload)
        print(f"[promo] create_campaign success id={campaign.get('id')} products={len(campaign.get('products', []))}")
        return jsonify(campaign), 201
    except Exception as exc:
        print(f"[promo] create_campaign error: {exc}")
        return jsonify({"error": str(exc)}), 500


@promo_bp.route("/api/promo/recommend-campaign", methods=["POST"])
def api_promo_recommend_campaign():
    payload = request.get_json(force=True) or {}
    selections = payload.get("selections") or []
    products = resolve_selected_products(selections)
    recommendation = recommend_campaign_info(
        products,
        store_name=(payload.get("store_name") or get_default_store_info().get("store_name") or STORE_NAME),
    )
    return jsonify({"recommendation": recommendation, "items": products})


@promo_bp.route("/api/promo/recommend-landing", methods=["POST"])
def api_promo_recommend_landing():
    payload = request.get_json(force=True) or {}
    campaign_id = payload.get("campaign_id")
    campaign = get_campaign(campaign_id) if campaign_id else None
    if campaign:
        products = campaign.get("products", [])
        store_name = campaign.get("store_name", STORE_NAME)
        event_title = campaign.get("event_title", "")
    else:
        selections = payload.get("selections") or []
        products = resolve_selected_products(selections)
        store_name = payload.get("store_name") or get_default_store_info().get("store_name") or STORE_NAME
        event_title = payload.get("event_title") or ""
    recommendation = recommend_landing_copy(
        products,
        store_name=store_name,
        event_title=event_title,
    )
    return jsonify({"recommendation": recommendation})


@promo_bp.route("/api/promo/generate-creative", methods=["POST"])
def api_promo_generate_creative():
    payload = request.get_json(force=True) or {}
    try:
        campaign_id = payload.get("campaign_id")
        campaign = get_campaign(campaign_id) if campaign_id else None
        c = campaign or {}
        # campaign이 DB에 없으면 payload 데이터 fallback 사용
        products = c.get("products") or payload.get("products") or []
        if not products:
            return jsonify({"error": "상품 정보가 없습니다. 캠페인을 다시 시작해 주세요."}), 400
        print(f"[promo] generate_creative campaign_id={campaign_id} products={len(products)}")
        enriched_products = []
        for product in products:
            enriched_products.append(
                {
                    **product,
                    "display_name": generate_short_product_name(
                        product.get("product_name", ""),
                        category=product.get("category", ""),
                    ),
                    "creative_title": generate_creative_title(
                        product.get("product_name", ""),
                        category=product.get("category", ""),
                    ),
                }
            )
        creative_payload = {
            "style": payload.get("style", "깔끔형"),
            "tone": payload.get("tone", "가성비 강조"),
            "price_display": payload.get("price_display", "혜택가"),
            "layout": payload.get("layout", "상품별 1장씩"),
            "products": enriched_products,
            "event_title": c.get("event_title") or payload.get("event_title", ""),
            "campaign_name": c.get("campaign_name") or payload.get("campaign_name", ""),
            "store_name": c.get("store_name") or payload.get("store_name", STORE_NAME),
            "phone": c.get("phone") or payload.get("phone", ""),
            "kakao_channel_url": c.get("kakao_channel_url") or payload.get("kakao_channel_url", ""),
        }
        saved = save_generated_asset(campaign_id, "square-creative", creative_payload) if campaign_id else None
        return jsonify(saved or {"type": "square-creative", "payload": creative_payload})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@promo_bp.route("/api/promo/generate-landing", methods=["POST"])
def api_promo_generate_landing():
    payload = request.get_json(force=True) or {}
    try:
        campaign_id = payload.get("campaign_id")
        campaign = get_campaign(campaign_id) if campaign_id else None
        c = campaign or {}
        # Vercel 인스턴스 불일치 대응: DB에 캠페인 없으면 클라이언트 payload 데이터 사용
        if not c.get("products") and payload.get("products"):
            c = {
                **c,
                "products": payload["products"],
                "store_name": payload.get("store_name") or c.get("store_name", STORE_NAME),
                "phone": payload.get("phone") or c.get("phone", ""),
                "kakao_channel_url": payload.get("kakao_channel_url") or c.get("kakao_channel_url", ""),
                "event_title": payload.get("event_title") or c.get("event_title", ""),
            }
        print(f"[promo] generate_landing campaign_id={campaign_id} products={len(c.get('products', []))}")
        landing_payload = build_landing_payload(payload, c)
        if campaign_id and campaign:
            update_campaign(campaign_id, metadata={**c.get("metadata", {}), "landing": landing_payload})
        saved = save_generated_asset(campaign_id, "landing", landing_payload) if campaign_id else None
        return jsonify({"campaign_id": campaign_id, "landing": landing_payload, "asset": saved})
    except Exception as exc:
        print(f"[promo] generate_landing error: {exc}")
        return jsonify({"error": str(exc)}), 500


@promo_bp.route("/api/promo/generate-instagram-copy", methods=["POST"])
def api_promo_generate_instagram_copy():
    payload = request.get_json(force=True) or {}
    try:
        campaign_id = payload.get("campaign_id")
        campaign = get_campaign(campaign_id) if campaign_id else None
        c = campaign or {}
        if not payload.get("products"):
            payload["products"] = c.get("products", [])
        payload["event_title"] = payload.get("event_title") or c.get("event_title", "")
        payload["store_name"] = payload.get("store_name") or c.get("store_name", STORE_NAME)
        payload["phone"] = payload.get("phone") or c.get("phone", "")
        payload["kakao_channel_url"] = payload.get("kakao_channel_url") or c.get("kakao_channel_url", "")
        prompt = generate_instagram_prompt(payload)
        result = {"prompt": prompt, "prompt_package": {"single_prompt": prompt}}
        saved = save_generated_asset(campaign_id, "instagram-copy", result) if campaign_id else None
        print(f"[promo] instagram prompt generated campaign_id={campaign_id} len={len(prompt)}")
        return jsonify({"result": result, "asset": saved})
    except Exception as exc:
        print(f"[promo] instagram copy error: {exc}")
        return jsonify({"error": str(exc)}), 500


@promo_bp.route("/api/promo/generate-blog-copy", methods=["POST"])
def api_promo_generate_blog_copy():
    payload = request.get_json(force=True) or {}
    try:
        campaign_id = payload.get("campaign_id")
        campaign = get_campaign(campaign_id) if campaign_id else None
        c = campaign or {}
        if not payload.get("products"):
            payload["products"] = c.get("products", [])
        payload["event_title"] = payload.get("event_title") or c.get("event_title", "")
        payload["store_name"] = payload.get("store_name") or c.get("store_name", STORE_NAME)
        payload["phone"] = payload.get("phone") or c.get("phone", "")
        payload["kakao_channel_url"] = payload.get("kakao_channel_url") or c.get("kakao_channel_url", "")
        prompt = generate_blog_prompt(payload)
        result = {"prompt": prompt, "prompt_package": {"single_prompt": prompt}}
        saved = save_generated_asset(campaign_id, "blog-copy", result) if campaign_id else None
        print(f"[promo] blog prompt generated campaign_id={campaign_id} len={len(prompt)}")
        return jsonify({"result": result, "asset": saved})
    except Exception as exc:
        print(f"[promo] blog copy error: {exc}")
        return jsonify({"error": str(exc)}), 500


@promo_bp.route("/api/promo/generate-track-link", methods=["POST"])
def api_promo_generate_track_link():
    payload = request.get_json(force=True) or {}
    campaign_id = payload.get("campaign_id")
    campaign = get_campaign(campaign_id) if campaign_id else None
    if not campaign:
        return jsonify({"error": "캠페인을 먼저 생성해 주세요."}), 400

    source = payload.get("source", "direct")
    params = {
        "store": campaign.get("store_code") or "default",
        "staff": campaign.get("staff_code") or "",
        "campaign": campaign_id,
        "source": source,
        "products": ",".join([item.get("model_no") for item in campaign.get("products", []) if item.get("model_no")]),
    }
    link = save_tracked_link(campaign_id, source, "", "")
    params["link"] = link["id"]
    full_url = f"{request.url_root.rstrip('/')}/promo/{campaign_id}?{urlencode(params)}"
    short_url = f"{request.url_root.rstrip('/')}/promo/{campaign_id}?src={source}&link={link['id']}"
    link = update_tracked_link(link["id"], url=full_url, short_url=short_url) or link
    return jsonify(link)


@promo_bp.route("/api/promo/save-package", methods=["POST"])
def api_promo_save_package():
    payload = request.get_json(force=True) or {}
    campaign_id = payload.get("campaign_id")
    campaign = get_campaign(campaign_id) if campaign_id else None
    if not campaign:
        return jsonify({"error": "저장할 캠페인이 없습니다."}), 400
    metadata = {**campaign.get("metadata", {}), "saved_package": payload.get("package", {})}
    updated = update_campaign(campaign_id, metadata=metadata)
    return jsonify(updated or campaign)


@promo_bp.route("/api/promo/campaign/<campaign_id>")
def api_promo_campaign(campaign_id: str):
    campaign = get_campaign(campaign_id)
    if not campaign:
        return jsonify({"error": "캠페인을 찾을 수 없습니다."}), 404
    return jsonify(campaign)


@promo_bp.route("/api/promo/campaign/<campaign_id>/track", methods=["POST"])
def api_promo_track(campaign_id: str):
    payload = request.get_json(force=True) or {}
    event_type = payload.get("event_type")
    if event_type not in {"landing_visit", "call_click", "kakao_click"}:
        return jsonify({"error": "지원하지 않는 추적 이벤트입니다."}), 400
    event = record_campaign_event(
        campaign_id,
        event_type=event_type,
        metadata=payload.get("metadata") or {},
        link_id=payload.get("link_id", ""),
    )
    return jsonify(event), 201


@promo_bp.route("/api/image/remove-background", methods=["POST"])
def api_remove_background():
    payload = request.get_json(force=True) or {}
    product_id = payload.get("product_id") or payload.get("model_no") or ""
    image_url = payload.get("image_url") or ""
    force = bool(payload.get("force"))
    if not product_id or not image_url:
        return jsonify({"error": "product_id와 image_url이 필요합니다."}), 400

    if not force:
        cached = get_cached_image_asset(product_id, image_url)
        if cached:
            return jsonify(cached)

    result = remove_background(image_url)
    saved = save_image_asset(
        product_id=product_id,
        original_url=image_url,
        processed_url=result.get("processed_url", image_url),
        transparent_png_url=result.get("transparent_png_url", ""),
        background_removed=bool(result.get("background_removed")),
        provider=result.get("provider", "noop"),
        metadata={"warning": result.get("warning", "")},
    )
    return jsonify(saved)


@promo_bp.route("/api/promo/campaign/<campaign_id>", methods=["DELETE"])
def api_delete_campaign(campaign_id: str):
    delete_campaign(campaign_id)
    return jsonify({"message": "홍보 패키지를 삭제했습니다."})


@promo_bp.route("/api/promo/campaigns")
def api_campaigns():
    return jsonify({"items": list_campaigns()})
