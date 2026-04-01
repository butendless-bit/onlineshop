"""Background removal providers with graceful fallback."""

from __future__ import annotations

import base64
import os
from typing import Any

import requests


def _cloudinary_provider(image_url: str) -> dict[str, Any] | None:
    cloudinary_url = os.getenv("CLOUDINARY_URL", "").strip()
    if not cloudinary_url:
        return None
    return {
        "background_removed": False,
        "provider": "cloudinary",
        "processed_url": image_url,
        "transparent_png_url": "",
        "warning": "Cloudinary 자동 누끼는 계정별 설정이 필요해 현재 원본 이미지를 사용합니다.",
    }


def _remove_bg_provider(image_url: str) -> dict[str, Any] | None:
    api_key = os.getenv("REMOVE_BG_API_KEY", "").strip()
    if not api_key:
        return None
    response = requests.post(
        "https://api.remove.bg/v1.0/removebg",
        data={"image_url": image_url, "size": "auto"},
        headers={"X-Api-Key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    encoded = base64.b64encode(response.content).decode("ascii")
    data_url = f"data:image/png;base64,{encoded}"
    return {
        "background_removed": True,
        "provider": "remove.bg",
        "processed_url": data_url,
        "transparent_png_url": data_url,
        "warning": "",
    }


def remove_background(image_url: str) -> dict[str, Any]:
    if not image_url:
        return {
            "background_removed": False,
            "provider": "noop",
            "processed_url": "",
            "transparent_png_url": "",
            "warning": "이미지 URL이 없어 원본 이미지를 사용할 수 없습니다.",
        }

    try:
        result = _remove_bg_provider(image_url)
        if result:
            return result
    except Exception as exc:
        return {
            "background_removed": False,
            "provider": "remove.bg",
            "processed_url": image_url,
            "transparent_png_url": "",
            "warning": f"누끼 처리에 실패해 원본 이미지를 사용합니다: {exc}",
        }

    result = _cloudinary_provider(image_url)
    if result:
        return result

    return {
        "background_removed": False,
        "provider": "noop",
        "processed_url": image_url,
        "transparent_png_url": "",
        "warning": "사용 가능한 누끼 공급자가 없어 원본 이미지를 사용합니다.",
    }
