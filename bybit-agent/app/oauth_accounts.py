"""AI Subaccount list/create/verify wrappers."""
from __future__ import annotations

from fastapi import HTTPException

from app.oauth_accounts_core import (
    OAuthAccountsRequest,
    OAuthSelectRequest,
    bybit_oauth_get,
    oauth_extract_credential_account,
    oauth_result_accounts,
    verify_ai_subaccount_credentials,
)

def list_accounts(body: OAuthAccountsRequest) -> dict:
    payload = bybit_oauth_get(body.access_token, body.environment, "/oauth/v1/resource/restrict/ai_accounts")
    accounts = oauth_result_accounts(payload)
    resolved_environment = payload.get("_resolved_environment", body.environment)
    can_create = len(accounts) < 5
    if accounts:
        next_step = "Select an AI subaccount explicitly, then click Verify. Never auto-selected."
    elif can_create:
        next_step = (
            "No AI subaccounts yet. On Bybit's website, AI Subaccount creation shows "
            "'NOT CONNECTED — TRY TO CONNECT VIA AI AGENT' until the agent creates one. "
            "Use Create AI Subaccount via agent (calls official is_create=true). "
            "Creation is never automatic; you must click the button."
        )
    else:
        next_step = "You already have 5 AI subaccounts (Bybit maximum). Select an existing one."
    return {
        "environment": resolved_environment,
        "accounts": accounts,
        "count": len(accounts),
        "can_create": can_create,
        "next_step": next_step,
        "create_endpoint": "/api/bybit/oauth/create-account" if can_create else None,
        "official_create_param": "is_create=true",
        "storage": "browser-session-only",
        "trading_enabled": False,
    }


def create_account(body: OAuthAccountsRequest) -> dict:
    """Official agent create: GET ai_accounts?is_create=true (user-initiated only)."""
    list_payload = bybit_oauth_get(body.access_token, body.environment, "/oauth/v1/resource/restrict/ai_accounts")
    existing = oauth_result_accounts(list_payload)
    resolved_from_list = list_payload.get("_resolved_environment", body.environment)
    if len(existing) >= 5:
        raise HTTPException(
            status_code=400,
            detail="Bybit allows at most 5 AI subaccounts. Select an existing one instead of creating another.",
        )
    env = resolved_from_list if body.environment == "auto" else body.environment
    payload = bybit_oauth_get(
        body.access_token,
        env,
        "/oauth/v1/resource/restrict/ai_accounts",
        {"is_create": "true"},
    )
    resolved_environment = payload.get("_resolved_environment", resolved_from_list)
    account = oauth_extract_credential_account(payload)
    if account is None:
        accounts = oauth_result_accounts(payload)
        if accounts:
            return {
                "created": True,
                "credentials_included": False,
                "environment": resolved_environment,
                "accounts": accounts,
                "count": len(accounts),
                "can_create": len(accounts) < 5,
                "next_step": "AI subaccount was created. Select it in the list, then click Verify selected account.",
                "trading_enabled": False,
                "storage": "browser-session-only",
            }
        raise HTTPException(
            status_code=502,
            detail=(
                "Bybit accepted is_create=true but did not return AI subaccount credentials. "
                "Load AI subaccounts again, then select and verify. If the list is still empty, "
                "re-authorize OAuth and ensure 2FA is bound on your Bybit account."
            ),
        )
    verified = verify_ai_subaccount_credentials(account, resolved_environment)
    verified["created"] = True
    verified["credentials_included"] = True
    verified["message"] = (
        "AI subaccount created via official is_create=true and verified read-only. "
        "No credentials are returned to the browser. Trading remains disabled in this app."
    )
    return verified


def verify_account(body: OAuthSelectRequest) -> dict:
    payload = bybit_oauth_get(
        body.access_token,
        body.environment,
        "/oauth/v1/resource/restrict/ai_accounts",
        {"sub_member_id": body.sub_member_id},
    )
    resolved_environment = payload.get("_resolved_environment", body.environment)
    account = oauth_extract_credential_account(payload)
    if account is None:
        raise HTTPException(
            status_code=502,
            detail=(
                "Bybit did not return credentials for the selected AI subaccount. "
                "Confirm the sub_member_id, re-load the list, or re-authorize if the token expired."
            ),
        )
    return verify_ai_subaccount_credentials(account, resolved_environment, body.sub_member_id)
