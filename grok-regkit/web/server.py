#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI control plane for grok-regkit."""

from __future__ import annotations

import asyncio
import collections
import hashlib
import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

# Project root = parent of web/
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

import grok_register_ttk as engine  # noqa: E402

ACCESS_PASSWORD = (os.getenv("GROK_REGISTER_ACCESS_PASSWORD") or "").strip()
HOST = (os.getenv("GROK_REGISTER_HOST") or "127.0.0.1").strip()
PORT = int(os.getenv("GROK_REGISTER_PORT") or "8092")

WEB_DIR = Path(__file__).resolve().parent
INDEX_HTML = WEB_DIR / "index.html"

SECRET_FIELDS = {
    "cloudflare_api_key",
    "litensi_api_key",
    "nine_router_password",
    "proxy",
    "proxy_pass",
}

# In-memory sessions: token -> expiry ts
_sessions: Dict[str, float] = {}
_SESSION_TTL = 86400 * 7

_job_lock = threading.Lock()
_job_thread: Optional[threading.Thread] = None
_controller: Optional[engine.CliStopController] = None
_log_buffer: Deque[str] = collections.deque(maxlen=2000)
_log_seq = 0
_log_cond = threading.Condition()
_job_state: Dict[str, Any] = {
    "running": False,
    "success": 0,
    "fail": 0,
    "target": 0,
    "last_accounts_file": "",
    "started_at": None,
    "finished_at": None,
    "error": "",
    "email_unit_price": 0.0,
    "email_total_cost": 0.0,
    "email_currency": "IDR",
}


app = FastAPI(title="Grok Register", version="1.0.0")


def _beijing_hms() -> str:
    try:
        from zoneinfo import ZoneInfo
        import datetime as _dt

        return _dt.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S")
    except Exception:
        # fall back to UTC+8 when zoneinfo is unavailable
        return time.strftime("%H:%M:%S", time.gmtime(time.time() + 8 * 3600))


def _append_log(message: str) -> None:
    global _log_seq
    ts = _beijing_hms()
    line = f"[{ts}] {message}"
    with _log_cond:
        _log_buffer.append(line)
        _log_seq += 1
        _log_cond.notify_all()


def _mask_value(key: str, value: Any) -> Any:
    if key not in SECRET_FIELDS:
        return value
    s = "" if value is None else str(value)
    if not s:
        return ""
    if len(s) <= 6:
        return "*" * len(s)
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


def _public_config() -> Dict[str, Any]:
    engine.load_config()
    cfg = dict(engine.config)
    masked = {k: _mask_value(k, v) for k, v in cfg.items()}
    # Keep unmasked non-secrets fully; secret fields show mask + has_* flags
    for key in SECRET_FIELDS:
        raw = cfg.get(key, "")
        masked[f"has_{key}"] = bool(str(raw or "").strip())
    return masked


def _require_auth(x_access_key: Optional[str]) -> None:
    if not ACCESS_PASSWORD:
        return
    key = (x_access_key or "").strip()
    if not key:
        raise HTTPException(status_code=401, detail="access key required")
    # Accept raw password or issued session token
    if key == ACCESS_PASSWORD:
        return
    exp = _sessions.get(key)
    if exp and exp > time.time():
        return
    if exp:
        _sessions.pop(key, None)
    raise HTTPException(status_code=403, detail="invalid access key")


def _issue_token(password: str) -> str:
    raw = f"{password}:{secrets.token_hex(16)}:{time.time()}"
    token = hashlib.sha256(raw.encode()).hexdigest()
    _sessions[token] = time.time() + _SESSION_TTL
    return token


class AuthBody(BaseModel):
    password: str = ""


class StartBody(BaseModel):
    # single-task cap (still recommended to batch on 2G machines; 1000 allowed for one-shot panel submit)
    count: int = Field(default=1, ge=1, le=1000)


class ConfigBody(BaseModel):
    cloudflare_api_base: Optional[str] = None
    cloudflare_api_key: Optional[str] = None
    cloudflare_auth_mode: Optional[str] = None
    cloudflare_path_domains: Optional[str] = None
    cloudflare_path_accounts: Optional[str] = None
    cloudflare_path_token: Optional[str] = None
    cloudflare_path_messages: Optional[str] = None
    proxy: Optional[str] = None
    proxy_mode: Optional[str] = None
    proxy_airport_url: Optional[str] = None
    proxy_api_url: Optional[str] = None
    proxy_api_num: Optional[int] = None
    proxy_api_format: Optional[str] = None
    proxy_api_type: Optional[str] = None
    proxy_quality_api: Optional[str] = None
    proxy_host_lookup_api: Optional[str] = None
    proxy_quality_check: Optional[bool] = None
    proxy_check_entry_host: Optional[bool] = None
    proxy_check_exit_ippure: Optional[bool] = None
    proxy_max_fraud_score: Optional[int] = None
    proxy_require_residential: Optional[bool] = None
    proxy_require_country_match: Optional[bool] = None
    proxy_reject_datacenter_org: Optional[bool] = None
    proxy_reject_hosting_flag: Optional[bool] = None
    proxy_quality_max_tries: Optional[int] = None
    proxy_host: Optional[str] = None
    proxy_port: Optional[str] = None
    proxy_user: Optional[str] = None
    proxy_pass: Optional[str] = None
    proxy_country: Optional[str] = None
    proxy_delimiter: Optional[str] = None
    proxy_duration: Optional[str] = None
    proxy_user_template: Optional[str] = None
    proxy_session: Optional[str] = None
    enable_nsfw: Optional[bool] = None
    nsfw_async: Optional[bool] = None
    post_success_async: Optional[bool] = None
    register_count: Optional[int] = None
    register_mode: Optional[str] = None
    user_agent: Optional[str] = None
    nine_router_enabled: Optional[bool] = None
    nine_router_base: Optional[str] = None
    nine_router_password: Optional[str] = None
    nine_router_push_mode: Optional[str] = None
    profile_given_names: Optional[str] = None
    profile_family_names: Optional[str] = None
    defaultDomains: Optional[str] = None
    email_provider: Optional[str] = None
    litensi_api_id: Optional[str] = None
    litensi_api_key: Optional[str] = None
    litensi_zone: Optional[str] = None
    litensi_site: Optional[str] = None


def _litensi_unit_price() -> float:
    """Resolve the cheapest in-stock Litensi price for the configured zone."""
    if str(engine.config.get("email_provider", "")).strip().lower() != "litensi":
        return 0.0
    try:
        prices = engine.litensi_get_prices()
        zone = str(engine.config.get("litensi_zone") or "").strip()
        matches = [p for p in prices if not zone or str(p.get("zone")) == zone]
        available = [p for p in matches if float(p.get("stock") or 0) > 0]
        if available:
            return float(available[0].get("price") or 0)
    except Exception:
        pass
    return 0.0


def _run_job(count: int) -> None:
    global _controller
    controller = engine.CliStopController()
    with _job_lock:
        _controller = controller
        _job_state["running"] = True
        _job_state["success"] = 0
        _job_state["fail"] = 0
        _job_state["target"] = count
        _job_state["error"] = ""
        _job_state["started_at"] = time.time()
        _job_state["finished_at"] = None
        _job_state["email_unit_price"] = 0.0
        _job_state["email_total_cost"] = 0.0

    def log_cb(msg: str) -> None:
        _append_log(str(msg))

    try:
        engine.load_config()
        unit_price = _litensi_unit_price()
        with _job_lock:
            _job_state["email_unit_price"] = unit_price
        result = engine.run_registration_job(
            count, log_callback=log_cb, controller=controller
        )
        with _job_lock:
            _job_state["success"] = int(result.get("success") or 0)
            _job_state["fail"] = int(result.get("fail") or 0)
            _job_state["email_total_cost"] = round(
                (_job_state["success"] + _job_state["fail"]) * unit_price, 2
            )
            _job_state["last_accounts_file"] = str(result.get("accounts_file") or "")
    except Exception as exc:
        _append_log(f"[!] job error: {exc}")
        with _job_lock:
            _job_state["error"] = str(exc)
    finally:
        with _job_lock:
            _job_state["running"] = False
            _job_state["finished_at"] = time.time()
            _controller = None
        _append_log("[*] web job thread finished")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(INDEX_HTML, headers={"Cache-Control": "no-store"})


@app.head("/", include_in_schema=False)
async def root_head():
    return Response(status_code=200, headers={"Cache-Control": "no-store"})


@app.get("/health")
async def health():
    return {"ok": True, "service": "grok-register"}


@app.get("/monitor/status")
async def monitor_status():
    with _job_lock:
        running = bool(_job_state["running"])
    return {
        "ok": True,
        "service": "grok-register",
        "running_job": running,
    }

@app.get("/monitor/status")
async def api_auth(body: AuthBody):
    if not ACCESS_PASSWORD:
        return {"ok": True, "needs_auth": False, "token": ""}
    if (body.password or "").strip() != ACCESS_PASSWORD:
        return JSONResponse({"ok": False, "detail": "invalid password"}, status_code=403)
    token = _issue_token(body.password.strip())
    return {"ok": True, "needs_auth": True, "token": token}


@app.get("/api/config")
async def api_get_config(x_access_key: Optional[str] = Header(None)):
    _require_auth(x_access_key)
    return {"ok": True, "config": _public_config(), "needs_auth": bool(ACCESS_PASSWORD)}


@app.put("/api/config")
async def api_put_config(body: ConfigBody, x_access_key: Optional[str] = Header(None)):
    _require_auth(x_access_key)
    engine.load_config()
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key in SECRET_FIELDS and isinstance(value, str):
            stripped = value.strip()
            # Empty string clears the secret.
            if stripped == "":
                engine.config[key] = ""
                continue
            # Masked placeholder from GET — keep previous value.
            if "*" in stripped:
                continue
        engine.config[key] = value
    # Server hard-forces proxy quality (env GROK_FORCE_PROXY_QUALITY default on).
    # Cliproxy white: judge EXIT residential via IPPure; entry gateway may be Zenlayer.
    force_q = os.environ.get("GROK_FORCE_PROXY_QUALITY", "1").strip().lower()
    if force_q in ("1", "true", "yes", "on"):
        engine.config["proxy_quality_check"] = True
        engine.config["proxy_check_exit_ippure"] = True
        engine.config["proxy_reject_datacenter_org"] = True
        # Do not force entry hard-reject — white API entry is shared DC by design.
        engine.config["proxy_entry_hard_reject"] = False
    engine.save_config()
    return {"ok": True, "config": _public_config()}


@app.get("/api/status")
async def api_status(x_access_key: Optional[str] = Header(None)):
    _require_auth(x_access_key)
    with _job_lock:
        state = dict(_job_state)
    return {"ok": True, **state}


@app.post("/api/proxy/test")
async def api_proxy_test(x_access_key: Optional[str] = Header(None)):
    """Test current proxy mode (airport / Cliproxy / custom) and probe exit via IPPure."""
    _require_auth(x_access_key)
    engine.load_config()
    logs: List[str] = []

    def _log(msg: str) -> None:
        logs.append(str(msg))

    try:
        mode = str(engine.config.get("proxy_mode") or "").strip().lower()
        if mode in ("cliproxy_white", "cliproxy", "white_api", "api"):
            proxy = engine.fetch_cliproxy_white_proxy(engine.config, log_callback=_log)
        else:
            proxy = engine.resolve_runtime_proxy(
                engine.config, log_callback=_log, fetch_live=True
            )
            if not proxy:
                raise RuntimeError("no proxy available for current mode (direct or not configured)")
            _log(f"[+] current proxy: {proxy}")
        quality = None
        try:
            quality = engine.probe_proxy_with_ippure(
                proxy,
                quality_api=str(
                    engine.config.get("proxy_quality_api") or "https://my.ippure.com/v1/info"
                ),
            )
            if quality:
                _log(
                    f"[*] exit IPPure: ip={quality.get('ip')} "
                    f"country={quality.get('countryCode')} "
                    f"fraud={quality.get('fraudScore')} "
                    f"residential={quality.get('isResidential')} "
                    f"org={quality.get('asOrganization') or quality.get('org') or ''}"
                )
        except Exception as qe:
            logs.append(f"[!] re-check IPPure failed: {qe}")
        return {"ok": True, "proxy": proxy, "quality": quality, "logs": logs}
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "detail": str(exc), "logs": logs},
            status_code=400,
        )


@app.post("/api/mail/litensi-prices")
async def api_litensi_prices(x_access_key: Optional[str] = Header(None)):
    """Check available Litensi zones/prices/stock for the configured site."""
    _require_auth(x_access_key)
    engine.load_config()
    try:
        prices = engine.litensi_get_prices()
    except Exception as exc:
        return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)
    in_stock = [p for p in prices if p.get("stock", 0) > 0]
    in_stock.sort(key=lambda p: p.get("price", 0))
    return {"ok": True, "prices": prices, "in_stock": in_stock}


@app.post("/api/nine-router/test")
async def api_nine_router_test(x_access_key: Optional[str] = Header(None)):
    """Probe the configured 9router instance (GET /api/providers)."""
    _require_auth(x_access_key)
    engine.load_config()
    ok, msg = engine.test_nine_router_connection()
    return {"ok": ok, "message": msg}


@app.post("/api/start")
async def api_start(body: StartBody, x_access_key: Optional[str] = Header(None)):
    global _job_thread
    _require_auth(x_access_key)
    with _job_lock:
        if _job_state["running"]:
            raise HTTPException(status_code=409, detail="job already running")
        # clear log for new run but keep last few
        _append_log(f"[*] starting registration count={body.count}")
        t = threading.Thread(target=_run_job, args=(body.count,), daemon=True)
        _job_thread = t
        t.start()
    return {"ok": True, "started": True, "count": body.count}


@app.post("/api/stop")
async def api_stop(x_access_key: Optional[str] = Header(None)):
    _require_auth(x_access_key)
    with _job_lock:
        ctrl = _controller
        running = _job_state["running"]
    if not running or ctrl is None:
        return {"ok": True, "stopped": False, "detail": "no running job"}
    ctrl.stop()
    _append_log("[!] stop requested from web")
    return {"ok": True, "stopped": True}


@app.get("/api/logs")
async def api_logs(
    request: Request,
    x_access_key: Optional[str] = Header(None),
    after: int = Query(0, ge=0),
):
    _require_auth(x_access_key)

    async def event_stream():
        last = after
        while True:
            if await request.is_disconnected():
                break
            with _log_cond:
                # snapshot
                buf = list(_log_buffer)
                seq = _log_seq
            # emit new lines relative to after
            start_idx = max(0, len(buf) - (seq - last)) if seq >= last else 0
            if last == 0:
                start_idx = 0
            else:
                # lines with global indices (seq - len + i)
                start_idx = max(0, len(buf) - (seq - last))
            new_lines = buf[start_idx:]
            for line in new_lines:
                yield f"data: {line}\n\n"
            last = seq
            # wait a bit for more
            await asyncio.sleep(0.5)
            with _log_cond:
                if _log_seq == last and not _job_state["running"]:
                    # keep connection for a short idle then continue
                    pass

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/logs/snapshot")
async def api_logs_snapshot(
    x_access_key: Optional[str] = Header(None),
    limit: int = Query(200, ge=1, le=2000),
):
    _require_auth(x_access_key)
    with _log_cond:
        lines = list(_log_buffer)[-limit:]
        seq = _log_seq
    return {"ok": True, "seq": seq, "lines": lines}


@app.get("/api/accounts")
async def api_accounts_list(x_access_key: Optional[str] = Header(None)):
    _require_auth(x_access_key)
    files = sorted(ROOT.glob("accounts_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    items = [
        {
            "name": f.name,
            "size": f.stat().st_size,
            "mtime": f.stat().st_mtime,
        }
        for f in files[:50]
    ]
    return {"ok": True, "files": items}


@app.get("/api/accounts/download")
async def api_accounts_download(
    x_access_key: Optional[str] = Header(None),
    name: Optional[str] = Query(None),
):
    _require_auth(x_access_key)
    if name:
        # prevent path traversal
        safe = Path(name).name
        path = ROOT / safe
        if not safe.startswith("accounts_") or not safe.endswith(".txt") or not path.is_file():
            raise HTTPException(status_code=404, detail="file not found")
    else:
        files = sorted(ROOT.glob("accounts_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            raise HTTPException(status_code=404, detail="no accounts file")
        path = files[0]
    return FileResponse(
        path,
        filename=path.name,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "web.server:app",
        host=HOST,
        port=PORT,
        workers=1,
        log_level="info",
    )


if __name__ == "__main__":
    main()
