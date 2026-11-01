"""Credit balances. Only what the providers actually expose is reported as real;
anything computed locally is flagged as an estimate."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from .llm import OPENROUTER_URL
from .store import Store


def _get(path: str, key: str) -> dict:
    r = httpx.get(f"{OPENROUTER_URL}{path}", headers={"Authorization": f"Bearer {key}"}, timeout=15)
    r.raise_for_status()
    return r.json().get("data") or {}


def credits(store: Store) -> dict:
    out: dict = {"openrouter": None, "anthropic": None, "app": {}}

    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        info: dict = {}
        try:
            k = _get("/key", key)  # works with a standard key
            info.update({
                "key_usage_usd": k.get("usage"), "key_limit_usd": k.get("limit"),
                "key_limit_remaining_usd": k.get("limit_remaining"),
                "usage_daily_usd": k.get("usage_daily"), "usage_monthly_usd": k.get("usage_monthly"),
            })
        except httpx.HTTPError as e:
            info["error"] = f"clé : {e}"
        mkey = os.getenv("OPENROUTER_MANAGEMENT_KEY")
        if mkey:
            try:
                c = _get("/credits", mkey)  # account balance requires a management key
                info["account_balance_usd"] = (c.get("total_credits") or 0) - (c.get("total_usage") or 0)
            except httpx.HTTPError as e:
                info["error"] = f"crédits : {e}"
        out["openrouter"] = info

    if os.getenv("ANTHROPIC_API_KEY"):
        info = {"api_balance": None,
                "note": "L'API Anthropic n'expose pas le solde avec une clé standard (voir la console Anthropic)."}
        start, since = os.getenv("ANTHROPIC_CREDIT_BALANCE"), os.getenv("ANTHROPIC_CREDIT_DATE")
        if start and since:
            try:
                spent = store.spend_since("anthropic", since)
                info.update({"estimated_balance_usd": float(start) - spent, "spent_since_usd": spent,
                             "reference": f"{start} $ au {since}"})
            except ValueError:
                info["note"] += " ANTHROPIC_CREDIT_BALANCE invalide."
        out["anthropic"] = info

    today = datetime.now(timezone.utc).date().isoformat()
    for provider in ("anthropic", "openai_compat"):
        out["app"][provider] = {
            "today_usd": store.spend_since(provider, today),
            "total_usd": store.spend_since(provider, "0000"),
        }
    return out
