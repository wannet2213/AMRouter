#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grok Registrar - TTK GUI version
Integrates DrissionPage_example.py, openai_register.py, batch_open_nsfw.py
"""

import threading
import datetime
import time
import os
import sys
import gc
import queue
import secrets
import struct
import random
import re
import string
import json
import base64
import select
import socket
import socketserver
import ssl
import urllib.parse
from zoneinfo import ZoneInfo

os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

# Run log uses Beijing time (independent of server UTC)
_BJ_TZ = ZoneInfo("Asia/Shanghai")


def now_beijing(fmt: str = "%H:%M:%S") -> str:
    return datetime.datetime.now(_BJ_TZ).strftime(fmt)

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    HAS_TK = True
except Exception:
    tk = None  # type: ignore
    ttk = None  # type: ignore
    messagebox = None  # type: ignore
    scrolledtext = None  # type: ignore
    HAS_TK = False

from DrissionPage import Chromium, ChromiumOptions
from DrissionPage.errors import PageDisconnectedError
from curl_cffi import requests


CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
MEMORY_CLEANUP_INTERVAL = 5

UI_BG = "#242424"
UI_PANEL_BG = "#2b2b2b"
UI_FG = "#f2f2f2"
UI_MUTED_FG = "#b8b8b8"
UI_ENTRY_BG = "#333333"
UI_BUTTON_BG = "#3a3a3a"
UI_ACTIVE_BG = "#4a6078"

DEFAULT_CONFIG = {
    "cloudflare_api_base": "",
    "cloudflare_api_key": "",
    "cloudflare_auth_mode": "none",
    "cloudflare_path_domains": "/api/domains",
    "cloudflare_path_accounts": "/api/new_address",
    "cloudflare_path_token": "/api/token",
    "cloudflare_path_messages": "/api/mails",
    "litensi_api_id": "",
    "litensi_api_key": "",
    # Optional custom profile name pools (comma-separated); empty = built-in defaults
    "profile_given_names": "",
    "profile_family_names": "",
    "litensi_zone": "",
    "litensi_site": "",
    # 9router integration: push minted OAuth creds to a (remote) 9router instance
    "nine_router_enabled": False,
    "nine_router_base": "",
    "nine_router_password": "",
    # push mode: device = persistent grok-cli (device flow, refresh token), token = xai api-key fallback
    "nine_router_push_mode": "device",
    "proxy": "",
    # proxy_mode: direct | custom | whitelist | cliproxy_white | airport
    "proxy_mode": "airport",
    # airport (Mihomo) local HTTP endpoint: subscription on the server's Mihomo REGISTER-RESIDENTIAL group
    "proxy_airport_url": "http://127.0.0.1:7893",
    # Cliproxy whitelist API: returns ip:port text
    # e.g. https://api.cliproxy.io/white/api?region=US&num=1&time=10&format=n&type=txt
    "proxy_api_url": "https://api.cliproxy.io/white/api",
    "proxy_api_num": 5,
    "proxy_api_format": "n",
    "proxy_api_type": "txt",
    # IP quality check
    # 1) first check the "entry IP"(host returned by Cliproxy) -- no proxy, saves residential bandwidth
    # 2) optionally check the exit IP through the proxy (IPPure)
    "proxy_quality_api": "https://my.ippure.com/v1/info",
    "proxy_host_lookup_api": "http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,org,as,hosting,proxy,mobile,query,isp",
    "proxy_quality_check": True,
    # Cliproxy white API returns shared DC gateway host:port; real residential is EXIT via proxy.
    # Entry host check is informational only by default (do not hard-reject Zenlayer gateways).
    "proxy_check_entry_host": False,
    "proxy_check_exit_ippure": True,
    "proxy_max_fraud_score": 40,
    "proxy_require_residential": True,
    "proxy_require_country_match": True,
    "proxy_reject_datacenter_org": True,
    "proxy_reject_hosting_flag": True,
    "proxy_quality_max_tries": 8,
    # whitelist / proxy group (username carries country, legacy mode)
    "proxy_host": "",
    "proxy_port": "",
    "proxy_user": "",
    "proxy_pass": "",
    # country/region: Cliproxy uses region, US recommended
    "proxy_country": "US",
    # username join delimiter, e.g. - or _
    "proxy_delimiter": "-",
    # rotation/sticky duration (minutes): Cliproxy time param
    "proxy_duration": "10",
    # template variables: {user} {pass} {host} {port} {country} {delimiter} {session} {duration}
    "proxy_user_template": "{user}{delimiter}region{delimiter}{country}",
    "proxy_session": "",
    "enable_nsfw": True,
    # True=NSFW runs in background (still runs); False=enable NSFW synchronously right after getting sso
    "nsfw_async": True,
    "register_count": 1,
    # register_mode: browser (full UI) | hybrid (protocol + short browser tokens)
    "register_mode": "browser",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    # ===== CPA / free Grok 4.5 (OIDC via Grok Build, NOT SSO) =====
    # SSO → web model pool; OIDC → CLIProxyAPI → cli-chat-proxy → grok-4.5
    "cpa_export_enabled": True,
    "cpa_auth_dir": "./cpa_auths",
    "cpa_copy_to_hotload": True,
    "cpa_hotload_dir": "",  # set to CPA auth-dir on server, e.g. /opt/cliproxyapi/auths
    "cpa_base_url": "https://cli-chat-proxy.grok.com/v1",
    "cpa_proxy": "",  # empty = fall back to runtime proxy / airport
    # Protocol mint needs no browser; fallback browser MUST be headed (Xvfb) on servers.
    "cpa_headless": False,
    "cpa_force_standalone": True,
    "cpa_mint_timeout_sec": 300,
    "cpa_mint_required": False,
    "cpa_probe_after_write": True,
    "cpa_probe_required": False,
    "cpa_probe_chat": False,
    "cpa_prefer_protocol": True,
    "cpa_protocol_only": False,
    "cpa_protocol_poll_timeout_sec": 90,
    "cpa_mint_cookie_inject": True,
    "cpa_gui_close_mint_browser": True,
    "cpa_mint_browser_reuse": False,
    "cpa_mint_browser_recycle_every": 15,
    # Gap between CPA mints to avoid auth.x.ai device-code 429/slow_down
    "cpa_mint_gap_sec": 25,
    # registration fast path: after sso is written, CPA mint goes to a background queue (functionality preserved)
    "post_success_async": True,
}

config = DEFAULT_CONFIG.copy()
_cf_domain_index = 0
_cpa_export_lock = threading.Lock()
_cpa_last_mint_ts = 0.0  # wall clock; serialize + gap between mints
_post_success_q = queue.Queue()
_post_success_worker_lock = threading.Lock()
_post_success_worker_started = False
_post_success_pending = 0
_post_success_pending_lock = threading.Lock()


class RegistrationCancelled(Exception):
    pass


class AccountRetryNeeded(Exception):
    pass


def load_config():
    global config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            config = {**DEFAULT_CONFIG, **loaded}
        except Exception:
            config = DEFAULT_CONFIG.copy()
    return config


def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except Exception:
            pass
    except Exception as e:
        print(f"Failed to save config: {e}")


def ensure_stable_python_runtime():
    if sys.version_info < (3, 14) or os.environ.get("DPE_REEXEC_DONE") == "1":
        return

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(local_app_data, "Programs", "Python", "Python312", "python.exe"),
        os.path.join(local_app_data, "Programs", "Python", "Python313", "python.exe"),
    ]

    current_python = os.path.normcase(os.path.abspath(sys.executable))
    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        if os.path.normcase(os.path.abspath(candidate)) == current_python:
            return

        print(
            f"[*] Detected Python {sys.version.split()[0]}, auto-switching to a more stable interpreter: {candidate}"
        )
        env = os.environ.copy()
        env["DPE_REEXEC_DONE"] = "1"
        os.execve(candidate, [candidate, os.path.abspath(__file__), *sys.argv[1:]], env)


def warn_runtime_compatibility():
    if sys.version_info >= (3, 14):
        print(
            "[Tip] Current Python is 3.14+; if you hit Mail.tm TLS errors, consider Python 3.12 or 3.13."
        )


ensure_stable_python_runtime()
warn_runtime_compatibility()

load_config()

EXTENSION_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "turnstilePatch")
)
def _proxy_quote(part: str) -> str:
    return urllib.parse.quote(str(part or ""), safe="")


def _cliproxy_build_url(c, region, num, duration, fmt, typ) -> str:
    base = str(c.get("proxy_api_url", "") or "https://api.cliproxy.io/white/api").strip()
    if not base:
        raise ValueError("proxy_api_url not configured")
    if "?" in base:
        return (
            base.replace("{region}", region)
            .replace("{country}", region)
            .replace("{num}", str(num))
            .replace("{time}", duration)
            .replace("{duration}", duration)
            .replace("{format}", fmt)
            .replace("{type}", typ)
        )
    qs = urllib.parse.urlencode(
        {
            "region": region,
            "num": str(num),
            "time": duration,
            "format": fmt,
            "type": typ,
        }
    )
    return f"{base.rstrip('/')}?{qs}"


def _parse_proxy_hostports(text: str) -> list:
    """Parse ip:port lines from Cliproxy txt/json response."""
    text = (text or "").strip()
    if not text:
        return []
    lines = []
    # try full JSON first
    if text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                raw_list = data.get("data") or data.get("list") or data.get("proxies") or []
                if isinstance(raw_list, str):
                    text = raw_list
                elif isinstance(raw_list, list):
                    for item in raw_list:
                        if isinstance(item, str):
                            lines.append(item)
                        elif isinstance(item, dict):
                            lines.append(
                                str(item.get("proxy") or item.get("ip") or item.get("addr") or "")
                            )
                else:
                    one = str(data.get("proxy") or data.get("ip") or "")
                    if one:
                        lines.append(one)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        lines.append(item)
                    elif isinstance(item, dict):
                        lines.append(str(item.get("proxy") or item.get("ip") or ""))
        except Exception:
            pass
    if not lines:
        lines = text.replace("\r\n", "\n").replace(",", "\n").split("\n")

    out = []
    seen = set()
    for raw in lines:
        cand = str(raw or "").strip()
        if not cand or cand.startswith("#"):
            continue
        cand = cand.replace("http://", "").replace("https://", "").strip()
        if ":" not in cand:
            continue
        host, port = cand.rsplit(":", 1)
        host = host.strip().strip("[]")
        port = port.strip()
        if not host or not port.isdigit():
            continue
        item = f"{host}:{port}"
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


_DATACENTER_ORG_KEYWORDS = (
    "amazon",
    "aws",
    "google cloud",
    "google llc",
    "microsoft",
    "azure",
    "digitalocean",
    "linode",
    "akamai",
    "cloudflare",
    "ovh",
    "hetzner",
    "vultr",
    "contabo",
    "choopa",
    "leaseweb",
    "colocrossing",
    "psychz",
    "quadranet",
    "m247",
    "datacamp",
    "zenlayer",
    "server",
    "hosting",
    "vps",
    "dedicated",
    "data center",
    "datacenter",
    "colocation",
    "colo ",
)


def _normalize_quality_info(info: dict) -> dict:
    """Normalize IPPure / ip-api style payloads into one shape."""
    info = dict(info or {})
    # ip-api.com fields -> common
    if not info.get("ip") and info.get("query"):
        info["ip"] = info.get("query")
    if not info.get("countryCode") and info.get("countryCode") is None:
        # already ok
        pass
    if not info.get("asOrganization"):
        info["asOrganization"] = (
            info.get("asOrganization")
            or info.get("org")
            or info.get("isp")
            or info.get("as")
            or ""
        )
    if "isResidential" not in info or info.get("isResidential") is None:
        # ip-api: hosting/proxy/mobile
        if "hosting" in info or "mobile" in info:
            hosting = bool(info.get("hosting"))
            mobile = bool(info.get("mobile"))
            if hosting:
                info["isResidential"] = False
            elif mobile:
                info["isResidential"] = True
    if info.get("hosting") is True and info.get("isResidential") is None:
        info["isResidential"] = False
    return info


def lookup_entry_ip_quality(ip: str, cfg=None, timeout: int = 12) -> dict:
    """Lookup Cliproxy *entry host* IP quality WITHOUT going through proxy.

    Saves residential bandwidth. Uses ip-api.com free endpoint by default.
    """
    c = cfg if isinstance(cfg, dict) else config
    ip = str(ip or "").strip()
    if not ip:
        raise ValueError("empty ip")
    template = str(
        c.get("proxy_host_lookup_api")
        or "http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,org,as,hosting,proxy,mobile,query,isp"
    ).strip()
    url = template.replace("{ip}", urllib.parse.quote(ip))
    # direct, no proxy
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "grok-register/1.0"})
    if resp.status_code >= 400:
        raise RuntimeError(f"Entry IP query HTTP {resp.status_code}: {(resp.text or '')[:160]}")
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"Entry IP query returned non-JSON: {(resp.text or '')[:160]}")
    if not isinstance(data, dict):
        raise RuntimeError("Entry IP query had bad format")
    if str(data.get("status", "")).lower() == "fail":
        raise RuntimeError(f"Entry IP query failed: {data.get('message') or data}")
    data = _normalize_quality_info(data)
    data["ip"] = data.get("ip") or ip
    data["_source"] = "entry-host"
    return data


def probe_proxy_with_ippure(proxy_url: str, quality_api: str = "", timeout: int = 15) -> dict:
    """Call IPPure *through proxy* to get exit IP quality info.

    Docs: https://my.ippure.com/v1/info  (returns exit IP of the proxy path)
    Note: free responses often omit fraudScore/isResidential.
    """
    api = (quality_api or "https://my.ippure.com/v1/info").strip()
    proxies = {"http": proxy_url, "https": proxy_url}
    resp = requests.get(
        api,
        proxies=proxies,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"IPPure HTTP {resp.status_code}: {(resp.text or '')[:160]}")
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"IPPure returned non-JSON: {(resp.text or '')[:160]}")
    if not isinstance(data, dict):
        raise RuntimeError(f"IPPure returned bad format: {type(data)}")
    data = _normalize_quality_info(data)
    data["_source"] = "exit-ippure"
    return data


def evaluate_proxy_quality(info: dict, cfg=None, *, stage: str = "exit") -> tuple:
    """Return (ok: bool, reason: str, summary: str).

    stage: entry|exit — entry is Cliproxy host IP; exit is path after proxy.
    """
    c = cfg if isinstance(cfg, dict) else config
    info = _normalize_quality_info(info or {})
    fraud = info.get("fraudScore")
    try:
        fraud_i = int(fraud) if fraud is not None and str(fraud) != "" else None
    except Exception:
        fraud_i = None
    is_res = info.get("isResidential")
    is_broadcast = bool(info.get("isBroadcast"))
    hosting_flag = info.get("hosting")
    country_code = str(info.get("countryCode") or "").strip().upper()
    ip = str(info.get("ip") or "").strip()
    org = str(info.get("asOrganization") or info.get("org") or info.get("isp") or "").strip()
    org_l = org.lower()
    expected = str(c.get("proxy_country", "US") or "US").strip().upper()
    if expected == "RAND":
        expected = ""

    max_fraud = int(c.get("proxy_max_fraud_score", 40) or 40)
    require_res = bool(c.get("proxy_require_residential", True))
    require_country = bool(c.get("proxy_require_country_match", True))
    reject_dc_org = bool(c.get("proxy_reject_datacenter_org", True))
    reject_hosting = bool(c.get("proxy_reject_hosting_flag", True))

    summary = (
        f"[{stage}] ip={ip or '?'} country={country_code or '?'} "
        f"fraud={fraud_i if fraud_i is not None else '?'} "
        f"residential={is_res} hosting={hosting_flag} org={org or '?'}"
    )

    # High risk score (IPPure full plan / web)
    if fraud_i is not None:
        if fraud_i >= 70:
            return False, f"extreme risk fraudScore={fraud_i}", summary
        if fraud_i > max_fraud:
            return False, f"fraud score too high fraudScore={fraud_i}>{max_fraud}", summary

    if is_broadcast:
        return False, "broadcast/abnormal IP (isBroadcast)", summary

    # Explicit datacenter flags
    if reject_hosting and hosting_flag is True:
        return False, "datacenter IP (hosting=true)", summary
    if require_res and is_res is False:
        return False, "non-residential IP (isResidential=false)", summary

    if require_country and expected and country_code and country_code != expected:
        return False, f"country mismatch want={expected} got={country_code}", summary

    # ASN / org heuristics (Zenlayer etc.)
    if reject_dc_org and org_l and any(k in org_l for k in _DATACENTER_ORG_KEYWORDS):
        return False, f"suspected datacenter/cloud ASN: {org}", summary

    # Entry host: if no residential/fraud fields, do NOT soft-pass when org empty either
    if stage == "entry":
        if require_res and is_res is None and fraud_i is None and hosting_flag is None:
            # only org-based pass; if org missing, reject to be safe
            if not org_l:
                return False, "entry IP info insufficient, cannot confirm non-datacenter", summary
        return True, "ok", summary

    # Exit path via IPPure free API often lacks fraud/residential
    if require_res and is_res is None and fraud_i is None:
        # require org not datacenter already checked; still warn-level ok only if org present
        if not org_l:
            return False, "exit IP info insufficient (no fraud/residential/org)", summary
        return True, "ok (exit fields incomplete, judged by country+ASN)", summary
    return True, "ok", summary


# Cache entry-host quality within one process run: host -> (ok, reason, summary)
_entry_host_quality_cache = {}


def quality_check_cliproxy_hostport(hostport: str, cfg=None, log_callback=None) -> tuple:
    """Full quality gate for one Cliproxy host:port.

    Cliproxy white API returns a shared DC gateway (e.g. 107.151.x.x:port). The real
    residential IP is the *exit* seen when traffic goes through that port — different
    ports on the same gateway often map to different residential exits.

    1) Optional entry host note (informational; NOT a hard reject by default)
    2) IPPure via proxy for exit IP (authoritative for residential / country / fraud)
    Returns (ok, proxy_url, detail)
    """
    global _entry_host_quality_cache
    c = cfg if isinstance(cfg, dict) else config
    hostport = str(hostport or "").strip()
    host, port = hostport.rsplit(":", 1)
    proxy_url = f"http://{hostport}"
    # Default OFF: entry is almost always Zenlayer/VpsQuan gateway for white API.
    check_entry = bool(c.get("proxy_check_entry_host", False))
    # Hard reject on entry only if user explicitly opts in (legacy / non-Cliproxy).
    entry_hard = bool(c.get("proxy_entry_hard_reject", False))
    check_exit = bool(c.get("proxy_check_exit_ippure", True))
    quality_api = str(c.get("proxy_quality_api") or "https://my.ippure.com/v1/info").strip()

    if check_entry:
        cached = _entry_host_quality_cache.get(host)
        if cached is not None:
            ok, reason, summary = cached
            if log_callback:
                mark = "[+]" if ok else ("[-]" if entry_hard else "[*]")
                log_callback(
                    f"{mark} entry (cached) host={host} | {reason}"
                    + ("" if ok or entry_hard else " (gateway ignorable, exit is authoritative)")
                )
            if not ok and entry_hard:
                return False, proxy_url, reason
        else:
            try:
                entry = lookup_entry_ip_quality(host, c)
                ok, reason, summary = evaluate_proxy_quality(entry, c, stage="entry")
                _entry_host_quality_cache[host] = (ok, reason, summary)
                if log_callback:
                    if ok:
                        log_callback(f"[+] entry check {summary} | {reason}")
                    elif entry_hard:
                        log_callback(f"[-] entry check {summary} | {reason}")
                    else:
                        log_callback(
                            f"[*] entry gateway {summary} | {reason} "
                            f" (Cliproxy shared entry ignorable; exit residential authoritative)"
                        )
                if not ok and entry_hard:
                    return False, proxy_url, reason
            except Exception as exc:
                if log_callback:
                    log_callback(f"[*] entry check skipped {host}: {exc}")
                _entry_host_quality_cache[host] = (True, f"entry query failed, ignored: {exc}", "")

    exit_info = None
    if check_exit:
        try:
            exit_info = probe_proxy_with_ippure(proxy_url, quality_api=quality_api, timeout=15)
            ok, reason, summary = evaluate_proxy_quality(exit_info, c, stage="exit")
            if log_callback:
                mark = "[+]" if ok else "[-]"
                log_callback(f"{mark} exit check {summary} | {reason}")
            if not ok:
                return False, proxy_url, reason
        except Exception as exc:
            if log_callback:
                log_callback(f"[-] exit IPPure check failed {hostport}: {exc}")
            return False, proxy_url, f"exit check error: {exc}"
    else:
        if log_callback:
            log_callback("[!] exit check disabled, cannot confirm residential, not recommended for registration")

    # Attach last exit meta for logging (not part of public return contract)
    detail = "ok"
    if isinstance(exit_info, dict):
        exit_ip = str(exit_info.get("ip") or "").strip()
        exit_org = str(
            exit_info.get("asOrganization")
            or exit_info.get("org")
            or exit_info.get("isp")
            or ""
        ).strip()
        res = exit_info.get("isResidential")
        fraud = exit_info.get("fraudScore")
        detail = (
            f"ok | entry gateway={host}:{port} → exit residential={exit_ip or '?'} "
            f"org={exit_org or '?'} residential={res} fraud={fraud if fraud is not None else '?'}"
        )
        try:
            c["_last_proxy_exit"] = {
                "gateway": hostport,
                "exit_ip": exit_ip,
                "exit_org": exit_org,
                "isResidential": res,
                "fraudScore": fraud,
                "countryCode": exit_info.get("countryCode"),
            }
        except Exception:
            pass
    return True, proxy_url, detail


def fetch_cliproxy_white_proxy(cfg=None, log_callback=None) -> str:
    """Call Cliproxy white API, quality-check via IPPure, return http://ip:port.

    Cliproxy:
      https://api.cliproxy.io/white/api?region=US&num=5&time=10&format=n&type=txt
    IPPure (through proxy):
      https://my.ippure.com/v1/info
    """
    c = cfg if isinstance(cfg, dict) else config
    region = str(c.get("proxy_country", "US") or "US").strip() or "US"
    if region.upper() == "RAND":
        region = "Rand"
    duration = str(c.get("proxy_duration", "10") or "10").strip()
    if duration.lower().startswith("t-"):
        duration = duration[2:]
    duration = "".join(ch for ch in duration if ch.isdigit()) or "10"
    fmt = str(c.get("proxy_api_format", "n") or "n").strip() or "n"
    typ = str(c.get("proxy_api_type", "txt") or "txt").strip() or "txt"
    # Quality check is ON by default; env GROK_FORCE_PROXY_QUALITY=1 hard-forces it.
    quality_on = bool(c.get("proxy_quality_check", True))
    if os.environ.get("GROK_FORCE_PROXY_QUALITY", "1").strip() in ("1", "true", "TRUE", "yes", "YES"):
        quality_on = True
    max_tries = int(c.get("proxy_quality_max_tries", 8) or 8)
    batch = int(c.get("proxy_api_num", 5) or 5)
    if quality_on:
        batch = max(batch, 3)
    check_entry = bool(c.get("proxy_check_entry_host", False))
    check_exit = bool(c.get("proxy_check_exit_ippure", True))
    if log_callback:
        log_callback(
            f"[*] proxy quality check: {'ON' if quality_on else 'OFF'} "
            f"(entry note={'ON' if check_entry else 'OFF'} / "
            f"exit IPPure={'ON' if check_exit else 'OFF'}; "
            f"Cliproxy exit residential authoritative; different ports on same gateway = different exits)"
        )

    tested = 0
    last_err = ""
    # Track rejected host:port only — same gateway host can have good/bad exits per port.
    rejected_ports = set()
    for attempt in range(1, max_tries + 1):
        url = _cliproxy_build_url(c, region, batch, duration, fmt, typ)
        if log_callback:
            log_callback(
                f"[*] Requesting Cliproxy whitelist IP: region={region} time={duration}m "
                f"num={batch}  (batch {attempt}/{max_tries})"
            )
        try:
            resp = requests.get(url, timeout=20)
            text = (resp.text or "").strip()
            if resp.status_code >= 400:
                raise RuntimeError(f"Cliproxy API HTTP {resp.status_code}: {text[:200]}")
            if not text:
                raise RuntimeError("Cliproxy API returned empty")
        except Exception as exc:
            last_err = str(exc)
            if log_callback:
                log_callback(f"[!] Cliproxy fetch failed: {exc}")
            time.sleep(1)
            continue

        hostports = _parse_proxy_hostports(text)
        if not hostports:
            last_err = f"Could not parse IP: {text[:160]}"
            if log_callback:
                log_callback(f"[!] {last_err}")
            continue

        unique_hosts = sorted({hp.rsplit(":", 1)[0] for hp in hostports})
        fresh = [hp for hp in hostports if hp not in rejected_ports]
        if log_callback:
            log_callback(
                f"[*] this batch: {len(hostports)} entries, gateway entries: {len(unique_hosts)}: "
                f"{', '.join(unique_hosts[:8])}{'...' if len(unique_hosts) > 8 else ''}; "
                f"ports to test: {len(fresh)}"
            )
            if len(unique_hosts) == 1:
                log_callback(
                    f"[*] Tip: same entry {unique_hosts[0]}  with different ports usually means different residential exits, "
                    "will run IPPure exit check per port"
                )
        if not fresh:
            if log_callback:
                log_callback("[*] All ports in this batch already failed, continuing to next batch")
            continue

        for hp in fresh:
            tested += 1
            if not quality_on:
                proxy_url = f"http://{hp}"
                if log_callback:
                    log_callback(
                        f"[!] Warning: quality check disabled, using directly: {hp}（exit residential unverified）"
                    )
                return proxy_url
            ok, proxy_url, reason = quality_check_cliproxy_hostport(
                hp, c, log_callback=log_callback
            )
            if ok:
                if log_callback:
                    # reason already embeds gateway→exit when quality ran
                    if reason and reason != "ok" and "exit" in str(reason):
                        log_callback(f"[+] selected qualified proxy: {hp}")
                        log_callback(f"[+] {reason}")
                        log_callback(
                            "[*] Note: 107.x/128.x in the log are the Cliproxy 'entry gateway', "
                            "the site/Cloudflare sees the 'exit residential IP' above, not a datacenter IP."
                        )
                    else:
                        log_callback(f"[+] selected qualified proxy: {hp} (exit check passed)")
                return proxy_url
            last_err = reason
            rejected_ports.add(hp)
            continue

    raise RuntimeError(
        f"No qualified proxy found (checked about {tested} exit ports). Last reason: {last_err or 'none'}.\n"
        f"Cliproxy white returns a shared gateway:port; true quality is seen via the proxied exit。\n"
        f"Try raising region=US、proxy_quality_max_tries，or loosening fraud / country match。"
    )


def build_whitelist_proxy_url(cfg=None) -> str:
    """Build whitelist proxy URL with country/region and delimiter.

    Typical vendor username: user-region-US  (delimiter="-")
    Full URL: http://user-region-US:pass@host:port
    """
    c = cfg if isinstance(cfg, dict) else config
    host = str(c.get("proxy_host", "") or "").strip()
    port = str(c.get("proxy_port", "") or "").strip()
    user = str(c.get("proxy_user", "") or "").strip()
    password = str(c.get("proxy_pass", "") or "")
    country = str(c.get("proxy_country", "US") or "US").strip().upper()
    delim = str(c.get("proxy_delimiter", "-") or "-")
    duration = str(c.get("proxy_duration", "120") or "120").strip()
    # allow "120" or "t-120"
    if duration.lower().startswith("t-"):
        duration = duration[2:]
    duration = "".join(ch for ch in duration if ch.isdigit()) or "120"
    session = str(c.get("proxy_session", "") or "").strip()
    if not session:
        session = secrets.token_hex(4)
    template = str(
        c.get("proxy_user_template", "{user}{delimiter}region{delimiter}{country}")
        or "{user}{delimiter}region{delimiter}{country}"
    ).strip()
    if not host or not port:
        return ""
    username = template.format(
        user=user,
        pass_=password,
        password=password,
        host=host,
        port=port,
        country=country,
        delimiter=delim,
        session=session,
        duration=duration,
        t=f"t-{duration}",
    )
    # If no username, allow IP-whitelist-only host:port
    if username:
        auth = f"{_proxy_quote(username)}:{_proxy_quote(password)}@"
    else:
        auth = ""
    return f"http://{auth}{host}:{port}"


def resolve_airport_proxy(cfg=None, log_callback=None) -> str:
    """Local Mihomo mixed port backed by airport subscription (hysteria2/vless)."""
    c = cfg if isinstance(cfg, dict) else config
    url = str(
        c.get("proxy_airport_url")
        or c.get("proxy")
        or "http://127.0.0.1:7893"
    ).strip()
    if not url:
        url = "http://127.0.0.1:7893"
    if log_callback:
        log_callback(
            f"[*] Proxy mode: airport (Mihomo) | {url} "
            f"（subscription node group REGISTER-RESIDENTIAL，not a Cliproxy ip:port）"
        )
    return url


def resolve_runtime_proxy(cfg=None, log_callback=None, fetch_live=True) -> str:
    """Resolve effective proxy URL from mode + API / whitelist group / custom."""
    c = cfg if isinstance(cfg, dict) else config
    mode = str(c.get("proxy_mode", "") or "").strip().lower()
    custom = str(c.get("proxy", "") or "").strip()
    if not mode:
        return custom
    if mode in ("direct", "none", "off"):
        return ""
    if mode in ("airport", "mihomo", "kunlun", "airport_mihomo"):
        return resolve_airport_proxy(c, log_callback=log_callback)
    if mode in ("cliproxy_white", "cliproxy", "white_api", "api"):
        if not fetch_live:
            return custom
        return fetch_cliproxy_white_proxy(c, log_callback=log_callback)
    if mode in ("whitelist", "group", "proxy_group"):
        return build_whitelist_proxy_url(c)
    return custom


def apply_resolved_proxy_to_config(log_callback=None, fetch_live=True):
    """Write resolved proxy into config['proxy'] for existing get_proxies/browser code."""
    global config
    resolved = resolve_runtime_proxy(config, log_callback=log_callback, fetch_live=fetch_live)
    config["proxy"] = resolved
    return resolved


def get_configured_proxy():
    # After job start, cliproxy mode stores resolved ip:port into config['proxy'].
    # Do not re-fetch API on every request.
    mode = str(config.get("proxy_mode", "") or "").strip().lower()
    if mode in ("cliproxy_white", "cliproxy", "white_api", "api"):
        return str(config.get("proxy", "") or "").strip()
    if mode in ("airport", "mihomo", "kunlun", "airport_mihomo"):
        return str(
            config.get("proxy")
            or config.get("proxy_airport_url")
            or "http://127.0.0.1:7893"
        ).strip()
    if mode in ("whitelist", "group", "proxy_group"):
        return build_whitelist_proxy_url(config)
    if mode in ("direct", "none", "off"):
        return ""
    if mode:
        return str(config.get("proxy", "") or "").strip()
    return str(config.get("proxy", "") or "").strip()


def get_proxies():
    proxy = get_configured_proxy()
    if proxy:
        return {"http": proxy, "https": proxy}
    return {}


def _parse_proxy_url(proxy):
    raw = str(proxy or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "http://" + raw
    try:
        return urllib.parse.urlsplit(raw)
    except Exception:
        return None


def _safe_proxy_port(parsed):
    try:
        return parsed.port
    except Exception:
        return None


def _proxy_has_auth(proxy):
    parsed = _parse_proxy_url(proxy)
    return bool(parsed and parsed.hostname and (parsed.username is not None or parsed.password is not None))


def _strip_proxy_auth(proxy):
    raw = str(proxy or "").strip()
    parsed = _parse_proxy_url(raw)
    if not parsed or not parsed.hostname:
        return raw
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = _safe_proxy_port(parsed)
    netloc = f"{host}:{port}" if port else host
    stripped = urllib.parse.urlunsplit((parsed.scheme or "http", netloc, parsed.path, parsed.query, parsed.fragment))
    if "://" not in raw:
        return stripped.split("://", 1)[1]
    return stripped


def _proxy_endpoint_terms(proxy=None):
    parsed = _parse_proxy_url(proxy or get_configured_proxy())
    if not parsed or not parsed.hostname:
        return []
    terms = [parsed.hostname]
    port = _safe_proxy_port(parsed)
    if port:
        terms.append(f"{parsed.hostname}:{port}")
        terms.append(f"port {port}")
    return [x.lower() for x in terms if x]


def is_proxy_connection_error(exc):
    if not get_configured_proxy():
        return False
    err = str(exc or "").lower()
    if not err:
        return False
    if any(x in err for x in ("proxy", "tunnel", "socks")):
        return True
    connect_markers = (
        "could not connect",
        "failed to connect",
        "connection refused",
        "connection reset",
        "connect error",
        "timed out",
        "timeout",
    )
    if any(x in err for x in connect_markers):
        terms = _proxy_endpoint_terms()
        if not terms or any(t in err for t in terms):
            return True
    return False


def page_has_proxy_error(page_obj):
    try:
        url = str(getattr(page_obj, "url", "") or "")
        title = str(page_obj.run_js("return document.title || ''") or "")
        body = str(page_obj.run_js("return document.body ? document.body.innerText.slice(0, 2000) : ''") or "")
    except Exception:
        return False
    text = f"{url}\n{title}\n{body}".lower()
    return any(
        marker in text
        for marker in (
            "err_proxy",
            "proxy connection failed",
            "proxy server",
            "proxy authentication",
            "tunnel connection failed",
            "cannot connect to proxy server",
            "proxy server",
        )
    )


class _ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _proxy_recv_until_headers(sock, timeout=20, limit=65536):
    sock.settimeout(timeout)
    data = b""
    while b"\r\n\r\n" not in data and len(data) < limit:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def _proxy_relay(left, right, timeout=60):
    left.settimeout(timeout)
    right.settimeout(timeout)
    sockets = [left, right]
    while True:
        readable, _, _ = select.select(sockets, [], [], timeout)
        if not readable:
            return
        for sock in readable:
            data = sock.recv(65536)
            if not data:
                return
            peer = right if sock is left else left
            peer.sendall(data)


class _LocalAuthProxyBridgeHandler(socketserver.BaseRequestHandler):
    def handle(self):
        bridge = self.server.bridge
        upstream = None
        try:
            initial = _proxy_recv_until_headers(self.request, timeout=bridge.timeout)
            if not initial:
                return
            first_line = initial.split(b"\r\n", 1)[0].decode("latin1", "ignore")
            if first_line.upper().startswith("CONNECT "):
                target = first_line.split()[1]
                upstream = bridge.open_upstream()
                req = [f"CONNECT {target} HTTP/1.1", f"Host: {target}"]
                if bridge.auth_header:
                    req.append(f"Proxy-Authorization: Basic {bridge.auth_header}")
                upstream.sendall(("\r\n".join(req) + "\r\n\r\n").encode("latin1"))
                response = _proxy_recv_until_headers(upstream, timeout=bridge.timeout)
                if response:
                    self.request.sendall(response)
                status = response.split(b"\r\n", 1)[0]
                if b" 200 " not in status:
                    return
                _proxy_relay(self.request, upstream, timeout=bridge.relay_timeout)
            else:
                upstream = bridge.open_upstream()
                upstream.sendall(bridge.inject_proxy_auth(initial))
                _proxy_relay(self.request, upstream, timeout=bridge.relay_timeout)
        except Exception:
            return
        finally:
            if upstream is not None:
                try:
                    upstream.close()
                except Exception:
                    pass


class LocalAuthProxyBridge:
    def __init__(self, proxy_url):
        parsed = _parse_proxy_url(proxy_url)
        if not parsed or not parsed.hostname:
            raise ValueError("authenticated proxy address format invalid")
        if (parsed.scheme or "http").lower() not in ("http", "https"):
            raise ValueError("Chromium local authenticated-proxy bridge only supports http/https upstream proxies")
        self.upstream_scheme = (parsed.scheme or "http").lower()
        self.upstream_host = parsed.hostname
        self.upstream_port = _safe_proxy_port(parsed) or (443 if self.upstream_scheme == "https" else 80)
        username = urllib.parse.unquote(parsed.username or "")
        password = urllib.parse.unquote(parsed.password or "")
        raw_auth = f"{username}:{password}".encode("utf-8")
        self.auth_header = base64.b64encode(raw_auth).decode("ascii") if (username or password) else ""
        self.timeout = 20
        self.relay_timeout = 90
        self.server = None
        self.thread = None
        self.local_proxy = ""

    def open_upstream(self):
        sock = socket.create_connection((self.upstream_host, self.upstream_port), timeout=self.timeout)
        if self.upstream_scheme == "https":
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=self.upstream_host)
        sock.settimeout(self.timeout)
        return sock

    def inject_proxy_auth(self, data):
        if not self.auth_header or b"\r\n\r\n" not in data:
            return data
        if b"\r\nproxy-authorization:" in data.lower():
            return data
        head, body = data.split(b"\r\n\r\n", 1)
        auth_line = f"Proxy-Authorization: Basic {self.auth_header}".encode("latin1")
        return head + b"\r\n" + auth_line + b"\r\n\r\n" + body

    def start(self):
        self.server = _ReusableThreadingTCPServer(("127.0.0.1", 0), _LocalAuthProxyBridgeHandler)
        self.server.bridge = self
        port = self.server.server_address[1]
        self.local_proxy = f"http://127.0.0.1:{port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.local_proxy

    def stop(self):
        if self.server is not None:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
        self.server = None
        self.thread = None
        self.local_proxy = ""


def stop_browser_proxy_bridge():
    global browser_proxy_bridge
    if browser_proxy_bridge is not None:
        try:
            browser_proxy_bridge.stop()
        except Exception:
            pass
    browser_proxy_bridge = None


def prepare_browser_proxy(use_proxy=True, log_callback=None):
    proxy = get_configured_proxy()
    if not use_proxy or not proxy:
        return "", None
    if _proxy_has_auth(proxy):
        parsed = _parse_proxy_url(proxy)
        scheme = (parsed.scheme or "http").lower() if parsed else ""
        if scheme in ("http", "https"):
            bridge = LocalAuthProxyBridge(proxy)
            browser_proxy = bridge.start()
            if log_callback:
                log_callback(f"[*] Started local authenticated-proxy bridge for Chromium: {browser_proxy}")
            return browser_proxy, bridge
        stripped = _strip_proxy_auth(proxy)
        if log_callback:
            log_callback("[!] Chromium doesn't directly support that authenticated proxy protocol，used de-authenticated proxy address，will fall back to direct on failure")
        return stripped, None
    return proxy, None


def get_cloudflare_api_base():
    return str(config.get("cloudflare_api_base", "") or "").rstrip("/")


def get_cloudflare_api_key():
    return config.get("cloudflare_api_key", "")


def get_cloudflare_auth_mode():
    return str(config.get("cloudflare_auth_mode", "none") or "none").lower()


def get_cloudflare_path(key, default_path):
    raw = str(config.get(key, default_path) or default_path).strip()
    if not raw.startswith("/"):
        raw = "/" + raw
    return raw


def cloudflare_build_headers(content_type=False):
    headers = {"Content-Type": "application/json"} if content_type else {}
    key = get_cloudflare_api_key()
    mode = get_cloudflare_auth_mode()
    if key:
        if mode == "x-api-key":
            headers["X-API-Key"] = key
        elif mode == "x-admin-auth":
            headers["x-admin-auth"] = key
        elif mode != "none":
            headers["Authorization"] = f"Bearer {key}"
    return headers


def cloudflare_apply_auth_params(params=None):
    merged = dict(params or {})
    key = get_cloudflare_api_key()
    mode = get_cloudflare_auth_mode()
    if key and mode == "query-key":
        merged["key"] = key
    return merged


def cloudflare_next_default_domain():
    """Rotate and pick a Cloudflare temp-mail domain per config."""
    global _cf_domain_index
    domains = [x.strip() for x in str(config.get("defaultDomains", "") or "").split(",") if x.strip()]
    if not domains:
        return ""
    domain = domains[_cf_domain_index % len(domains)]
    _cf_domain_index += 1
    return domain


def cloudflare_is_admin_create_path(path):
    """Check whether the current mailbox-creation path is the cloudflare_temp_email admin creation API."""
    return str(path or "").rstrip("/").lower() == "/admin/new_address"


def _pick_list_payload(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            return data.get("results")
        if isinstance(data.get("hydra:member"), list):
            return data.get("hydra:member")
        if isinstance(data.get("data"), list):
            return data.get("data")
        if isinstance(data.get("messages"), list):
            return data.get("messages")
        if isinstance(data.get("data"), dict):
            nested = data.get("data")
            if isinstance(nested.get("messages"), list):
                return nested.get("messages")
    return []


def cloudflare_create_temp_address(api_base):
    """Adapt to the cloudflare_temp_email new-address API and support admin creation mode.

    Also supports Ammail-style responses: {"success": true, "inbox": {"address": ...}}.
    """
    path = get_cloudflare_path("cloudflare_path_accounts", "/api/new_address")
    url = f"{api_base}{path}"
    domain = cloudflare_next_default_domain()
    is_admin_create = cloudflare_is_admin_create_path(path)
    is_ammail = config.get("email_provider") == "ammail"
    if is_admin_create:
        payload = {"name": generate_username(10), "enablePrefix": True}
        if domain:
            payload["domain"] = domain
        headers = cloudflare_build_headers(content_type=True)
    else:
        payload = {}
        if domain:
            payload["domain"] = domain
        # Ammail needs X-API-Key even on non-admin path
        if is_ammail:
            headers = cloudflare_build_headers(content_type=True)
        else:
            headers = {"Content-Type": "application/json"}
    resp = http_post(url, json=payload, headers=headers)
    resp.raise_for_status()
    try:
        data = resp.json()
    except Exception:
        raise Exception(f"Cloudflare {path} returned non-JSON: {resp.text[:300]}")
    # Ammail-style: {"success": true, "inbox": {"alias","address","domain"}}
    if isinstance(data, dict) and isinstance(data.get("inbox"), dict):
        inbox = data["inbox"]
        address = inbox.get("address")
        if not address:
            raise Exception(f"Cloudflare {path} inbox missing address: {data}")
        alias = inbox.get("alias") or address.split("@")[0]
        return address, alias
    address = data.get("address")
    jwt = data.get("jwt")
    if not address or not jwt:
        raise Exception(f"Cloudflare {path} missing address/jwt: {data}")
    return address, jwt


def get_user_agent():
    return config.get(
        "user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    )


def _nine_router_login(base, password, log_callback=None):
    """Login to a 9router dashboard. Returns (cookie_str_or_None, reason).

    POST /api/auth/login sets an httpOnly auth_token cookie on success;
    `reason` explains any failure (HTTP status, body, rate-limit, no cookie).
    """
    log = log_callback or (lambda m: None)
    if not password:
        return None, "nine_router_password is empty"
    try:
        resp = http_post(
            f"{base}/api/auth/login",
            headers={"Content-Type": "application/json"},
            json={"password": password},
            timeout=15,
        )
    except Exception as exc:
        log(f"[9r] 9router login failed: {exc}")
        return None, f"login error: {exc}"
    status = int(resp.status_code)
    body = resp.text[:200]
    if status == 200:
        token = resp.cookies.get("auth_token")
        if not token:
            log("[9r] 9router login OK but no auth_token cookie returned")
            return None, "login OK but no auth_token cookie in response"
        return f"auth_token={token}", ""
    if status == 429:
        log(f"[9r] 9router login rate-limited (HTTP 429): {body}")
        return None, "login rate-limited (429): too many failed attempts, wait & retry"
    log(f"[9r] 9router login failed (HTTP {status}): {body}")
    return None, f"login HTTP {status}: {body or 'no response body'}"


def _nine_router_auth_cookie(log):
    """Return 9router dashboard auth_token cookie string, or None."""
    base = str(config.get("nine_router_base", "") or "").strip().rstrip("/")
    password = str(config.get("nine_router_password", "") or "").strip()
    if password:
        cookie, _ = _nine_router_login(base, password, log_callback=log)
        if cookie:
            return cookie
    return None


def _nine_router_push_grok_cli_device(sso, email, cookies, log):
    """Persistent grok-cli device flow: 9router generates the device code,
    we approve the consent with the fresh SSO session, 9router stores oauth
    tokens (incl. refresh token) so the connection stays alive."""
    base = str(config.get("nine_router_base", "") or "").strip().rstrip("/")
    cookie = _nine_router_auth_cookie(log)
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie

    # 1) Request device code from 9router (it talks to auth.x.ai upstream)
    try:
        resp = http_get(f"{base}/api/oauth/grok-cli/device-code", headers=headers, timeout=30)
    except Exception as exc:
        log(f"[9r] grok-cli device-code request failed: {exc}")
        return False
    if resp.status_code not in (200, 201):
        log(f"[9r] grok-cli device-code failed (HTTP {resp.status_code}): {resp.text[:200]}")
        return False
    data = {}
    try:
        parsed = resp.json()
        if isinstance(parsed, dict):
            data = parsed
    except Exception:
        data = {}
    device_code = str(data.get("device_code") or data.get("deviceCode") or "").strip()
    user_code = str(data.get("user_code") or data.get("userCode") or "").strip()
    verifier = str(data.get("codeVerifier") or "").strip()
    verify_uri = str(data.get("verification_uri_complete") or data.get("verificationUriComplete") or "").strip()
    interval = int(data.get("interval") or 5) or 5
    if not device_code or not user_code or not verify_uri:
        log(f"[9r] grok-cli device-code response missing fields: {list(data.keys())[:8]}")
        return False
    log(f"[9r] grok-cli device flow: user_code={user_code}")

    # 2) Approve consent with our SSO session
    try:
        from cpa_xai.protocol_mint import approve_device_consent
        approve_device_consent(
            sso_cookie=sso,
            user_code=user_code,
            verification_uri_complete=verify_uri,
            cookies=cookies,
            log=log,
        )
        log(f"[9r] grok-cli consent approved: {email}")
    except Exception as exc:
        log(f"[9r] grok-cli consent failed: {exc}")
        return False

    # 3) Poll 9router until it has the tokens
    poll_body = {"deviceCode": device_code}
    if verifier:
        poll_body["codeVerifier"] = verifier
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            resp = http_post(f"{base}/api/oauth/grok-cli/poll", headers=headers, json=poll_body, timeout=30)
            payload = resp.json()
        except Exception as exc:
            log(f"[9r] grok-cli poll error: {exc}")
            return False
        if isinstance(payload, dict) and payload.get("success"):
            log(f"[9r] pushed grok-cli connection (device flow, refresh token): {email}")
            return True
        time.sleep(interval)
    log("[9r] grok-cli device poll timed out")
    return False


def _nine_router_push_token_xai(auth_dict, email, log):
    """Fallback: push the minted token as an xai API-key connection (non-persistent)."""
    base = str(config.get("nine_router_base", "") or "").strip().rstrip("/")
    password = str(config.get("nine_router_password", "") or "").strip()
    payload = {
        "provider": "xai",
        "apiKey": str(auth_dict.get("access_token") or ""),
        "name": email,
        "displayName": email,
    }

    def _push(cookie=None):
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        return http_post(f"{base}/api/providers", headers=headers, json=payload, timeout=30)

    try:
        resp = _push()
        if resp.status_code in (200, 201):
            log(f"[9r] pushed xai connection: {email}")
            return True
        if resp.status_code in (401, 403) and password:
            cookie, reason = _nine_router_login(base, password, log_callback=log)
            if cookie:
                resp = _push(cookie)
                if resp.status_code in (200, 201):
                    log(f"[9r] pushed xai connection (authenticated): {email}")
                    return True
                log(f"[9r] 9router push failed after auth (HTTP {resp.status_code}): {resp.text[:200]}")
            elif reason:
                log(f"[9r] 9router auth failed: {reason}")
            return False
        log(
            f"[9r] 9router push failed (HTTP {resp.status_code}): {resp.text[:200]}"
            f" — set Require Login = off in 9router, or fill nine_router_password"
        )
    except Exception as exc:
        log(f"[9r] 9router push failed: {exc}")
    return False


def add_token_to_nine_router(auth_dict, log_callback=None, sso="", cookies=None):
    """Push a minted account to a 9router instance.

    Default mode is the persistent grok-cli device flow (honors an SSO cookie
    by approving the consent, so 9router stores oauth tokens + refresh token).
    Falls back to the non-persistent xai API-key POST when push mode is "token"
    or when no SSO is available.
    """
    log = log_callback or (lambda m: None)
    base = str(config.get("nine_router_base", "") or "").strip().rstrip("/")
    if not config.get("nine_router_enabled", False) or not base:
        return False
    email = "xai-account"
    if isinstance(auth_dict, dict) and (auth_dict.get("email") or "").strip():
        email = str(auth_dict["email"]).strip()

    mode = str(config.get("nine_router_push_mode", "device") or "device").strip().lower()
    if mode == "device" and sso:
        try:
            if _nine_router_push_grok_cli_device(sso, email, cookies, log):
                return True
            log("[9r] grok-cli device flow failed")
        except Exception as exc:
            log(f"[9r] grok-cli device flow error: {exc}")
        return False

    if not isinstance(auth_dict, dict) or not auth_dict.get("access_token"):
        log("[9r] no access_token in auth, skipping 9router push")
        return False
    return _nine_router_push_token_xai(auth_dict, email, log)


def test_nine_router_connection(log_callback=None):
    """Probe a 9router instance. Returns (ok, message).

    GET /api/providers with optional auth: try without auth first (covers
    requireLogin=false); on 401/403 log in with the dashboard password and
    retry with the auth_token cookie. Only a transport error means unreachable.
    """
    log = log_callback or (lambda m: None)
    base = str(config.get("nine_router_base", "") or "").strip().rstrip("/")
    if not base:
        return False, "9router base URL is empty"
    password = str(config.get("nine_router_password", "") or "").strip()

    def _get(cookie=None):
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        return http_get(f"{base}/api/providers", headers=headers, timeout=10)

    def _count(resp):
        try:
            data = resp.json()
        except Exception:
            return None
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict) and isinstance(data.get("connections"), list):
            return len(data["connections"])
        return None

    try:
        resp = _get()
        status = int(resp.status_code)
        if status == 200:
            count = _count(resp)
            msg = "9router online (HTTP 200)"
            if count is not None:
                msg += f", {count} connection(s)"
            return True, msg
        if status in (401, 403):
            if not password:
                return True, (
                    f"9router reachable but auth required (HTTP {status}) — "
                    f"fill nine_router_password, or set Require Login = off in 9router"
                )
            cookie, reason = _nine_router_login(base, password, log_callback=log)
            if cookie:
                resp = _get(cookie)
                if int(resp.status_code) == 200:
                    count = _count(resp)
                    msg = "9router online, authenticated (HTTP 200)"
                    if count is not None:
                        msg += f", {count} connection(s)"
                    return True, msg
                return True, f"9router reachable but auth failed (HTTP {resp.status_code})"
            return True, (
                f"9router reachable (HTTP {status}) but login failed — {reason or 'unknown'}"
            )
        return True, f"9router reachable (HTTP {status})"
    except Exception as exc:
        return False, f"9router unreachable: {exc}"


def _config_bool(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "on", "y"):
        return True
    if s in ("0", "false", "no", "off", "n", ""):
        return False
    return bool(default)


def _post_success_worker_loop():
    """Background worker: NSFW / CPA mint / 9router push (doesn't block the next account's registration)."""
    while True:
        job = _post_success_q.get()
        if job is None:
            _post_success_q.task_done()
            break
        log = job.get("log") or (lambda m: print(m, flush=True))
        email = job.get("email") or ""
        sso = job.get("sso") or ""
        try:
            log(f"[bg] post-processing started: {email}")
            if job.get("do_nsfw"):
                log(f"[bg] enabling NSFW: {email}")
                try:
                    nsfw_ok, nsfw_msg = enable_nsfw_for_token(sso, log_callback=log)
                    if nsfw_ok:
                        log(f"[bg] NSFW enabled: {nsfw_msg}")
                    else:
                        log(f"[bg] NSFW not enabled: {nsfw_msg}")
                except Exception as nsfw_exc:
                    log(f"[bg] NSFW error: {nsfw_exc}")
            if job.get("do_cpa") and config.get("cpa_export_enabled", True):
                try:
                    export_cpa_after_success(
                        email,
                        job.get("password") or "",
                        sso,
                        page=None,
                        cookies=job.get("cookies") or [],
                        log_callback=log,
                    )
                except Exception as cpa_exc:
                    log(f"[bg] CPA export failed: {cpa_exc}")
            if config.get("nine_router_enabled", False) and config.get("nine_router_base", ""):
                try:
                    auth_dict = {}
                    try:
                        from cpa_xai.schema import credential_file_name

                        auth_dir = os.path.dirname(os.path.abspath(__file__))
                        auth_path = os.path.join(
                            auth_dir,
                            str(config.get("cpa_auth_dir", "./cpa_auths") or "./cpa_auths"),
                            credential_file_name(email, ""),
                        )
                        if os.path.isfile(auth_path):
                            with open(auth_path, "r", encoding="utf-8") as f:
                                auth_dict = json.load(f)
                    except Exception:
                        auth_dict = {}
                    if not auth_dict and sso:
                        auth_dict = {"access_token": sso, "email": email}
                    add_token_to_nine_router(
                        auth_dict,
                        log_callback=log,
                        sso=sso,
                        cookies=job.get("cookies") or [],
                    )
                except Exception as nine_exc:
                    log(f"[bg] 9router push error: {nine_exc}")
            log(f"[bg] post-processing finished: {email}")
        except Exception as exc:
            log(f"[bg] post-processing error {email}: {exc}")
        finally:
            global _post_success_pending
            with _post_success_pending_lock:
                _post_success_pending = max(0, _post_success_pending - 1)
            _post_success_q.task_done()


def ensure_post_success_worker(log_callback=None):
    global _post_success_worker_started
    with _post_success_worker_lock:
        if _post_success_worker_started:
            return
        t = threading.Thread(
            target=_post_success_worker_loop,
            name="post-success-worker",
            daemon=True,
        )
        t.start()
        _post_success_worker_started = True
        if log_callback:
            log_callback("[*] post-processing background thread started (CPA/NSFW async)")


def wait_post_success_queue(timeout=300, log_callback=None):
    """Wait until background post-success jobs drain (call at job end)."""
    log = log_callback or (lambda m: None)
    deadline = time.time() + max(0.0, float(timeout or 0))
    last_log = 0.0
    while True:
        with _post_success_pending_lock:
            pending = _post_success_pending
        unfinished = getattr(_post_success_q, "unfinished_tasks", 0)
        if pending <= 0 and unfinished <= 0:
            log("[*] post-processing queue cleared")
            return True
        if time.time() >= deadline:
            log(f"[!] post-processing queue still has about {pending} unfinished (return on timeout, background continues)")
            return False
        now = time.time()
        # Log every 10s only — avoid flooding Web console every second
        if pending > 0 and (now - last_log) >= 10.0:
            log(f"[*] waiting for post-processing queue... about {pending} (CPA/NSFW in background)")
            last_log = now
        time.sleep(1.0)


def schedule_post_registration(
    email, password, sso, page=None, cookies=None, log_callback=None
):
    """After sso saved: NSFW + CPA (+ 9router push). Prefer async so next account starts sooner.

    - enable_nsfw + nsfw_async=False -> NSFW sync (when you need it enabled immediately)
    - post_success_async=True -> CPA (and async NSFW) go to background
    - cookies: optional pre-exported jar (hybrid path has no live page)
    """
    log = log_callback or (lambda m: print(m, flush=True))
    out_cookies = []
    if isinstance(cookies, list) and cookies:
        out_cookies = [c for c in cookies if isinstance(c, dict)]
        if out_cookies:
            log(f"[cpa] using caller cookies {len(out_cookies)} (for background OIDC mint)")
    try:
        import cpa_export

        if not out_cookies and page is not None:
            out_cookies = cpa_export.export_cookies_from_page(page) or []
            if out_cookies:
                log(f"[cpa] pre-exported cookies {len(out_cookies)} (for background OIDC mint)")
    except Exception as exc:
        log(f"[cpa] cookie pre-export failed (sso still usable): {exc}")
        if not out_cookies:
            out_cookies = []
    cookies = out_cookies

    do_nsfw = bool(config.get("enable_nsfw", True))
    nsfw_async = _config_bool(config.get("nsfw_async", True), default=True)
    post_async = _config_bool(config.get("post_success_async", True), default=True)
    do_cpa = bool(config.get("cpa_export_enabled", True))

    # Optional sync NSFW before queueing the rest
    if do_nsfw and not nsfw_async:
        log("[*] 6. enabling NSFW (sync)")
        try:
            nsfw_ok, nsfw_msg = enable_nsfw_for_token(sso, log_callback=log)
            if nsfw_ok:
                log(f"[+] NSFW enabled: {nsfw_msg}")
            else:
                log(f"[!] NSFW not enabled, continuing: {nsfw_msg}")
        except Exception as nsfw_exc:
            log(f"[!] NSFW error, continuing: {nsfw_exc}")
        do_nsfw = False  # already done

    need_queue = do_cpa or do_nsfw
    if not need_queue:
        return {"async": False, "queued": False}

    if not post_async:
        # Fully synchronous path (old behavior)
        if do_nsfw:
            log("[*] 6. enabling NSFW")
            try:
                nsfw_ok, nsfw_msg = enable_nsfw_for_token(sso, log_callback=log)
                if nsfw_ok:
                    log(f"[+] NSFW enabled: {nsfw_msg}")
                else:
                    log(f"[!] NSFW not enabled, continuing: {nsfw_msg}")
            except Exception as nsfw_exc:
                log(f"[!] NSFW error, continuing: {nsfw_exc}")
        if do_cpa:
            try:
                export_cpa_after_success(
                    email,
                    password or "",
                    sso,
                    page=None,
                    cookies=cookies,
                    log_callback=log,
                )
            except Exception as cpa_exc:
                log(f"[cpa] export not successful (SSO still saved): {cpa_exc}")
        return {"async": False, "queued": False}

    ensure_post_success_worker(log_callback=log)
    global _post_success_pending
    with _post_success_pending_lock:
        _post_success_pending += 1
    _post_success_q.put(
        {
            "email": email,
            "password": password or "",
            "sso": sso,
            "cookies": cookies,
            "do_nsfw": do_nsfw,
            "do_cpa": do_cpa,
            "log": log,
        }
    )
    parts = []
    if do_nsfw:
        parts.append("NSFW")
    if do_cpa:
        parts.append("CPA")
    log(f"[*] post-processing queued to background: {'+'.join(parts) or 'none'} -> starting next account immediately")
    return {"async": True, "queued": True}


def export_cpa_after_success(email, password, sso, page=None, cookies=None, log_callback=None):
    """After successful registration: mint OIDC for free Grok 4.5 (CPA / Build path).

    SSO alone powers web pool models (4.20/4.3). Free grok-4.5 needs OIDC
    via accounts.x.ai device-flow → cpa_auths/xai-*.json → CLIProxyAPI.
    """
    log = log_callback or (lambda m: print(m, flush=True))
    if not config.get("cpa_export_enabled", True):
        log("[cpa] export disabled, skip")
        return {"ok": False, "skipped": True, "reason": "disabled"}
    if not email:
        log("[cpa] missing email, skipping CPA export")
        return {"ok": False, "error": "missing email"}
    # protocol path only needs sso; password needed for browser fallback
    if not password and not sso:
        log("[cpa] missing password/sso, skipping CPA export")
        return {"ok": False, "error": "missing password/sso"}
    try:
        import cpa_export
    except Exception as exc:
        log(f"[cpa] failed to import cpa_export: {exc}")
        return {"ok": False, "error": f"import: {exc}"}

    if cookies is None:
        cookies = []
        try:
            cookies = cpa_export.export_cookies_from_page(page) if page is not None else []
        except Exception as exc:
            log(f"[cpa] cookie export failed, continuing with sso/protocol mint: {exc}")
            cookies = []
    if cookies:
        log(f"[cpa] exported cookies {len(cookies)} for OIDC mint")

    cpa_cfg = dict(config)
    # Prefer airport/local proxy for mint if cpa_proxy empty
    if not str(cpa_cfg.get("cpa_proxy") or "").strip():
        mode = str(cpa_cfg.get("proxy_mode") or "").strip().lower()
        if mode in ("airport", "mihomo", "kunlun", "airport_mihomo"):
            cpa_cfg["cpa_proxy"] = str(
                cpa_cfg.get("proxy_airport_url")
                or cpa_cfg.get("proxy")
                or "http://127.0.0.1:7893"
            ).strip()
        elif str(cpa_cfg.get("proxy") or "").strip():
            cpa_cfg["cpa_proxy"] = str(cpa_cfg.get("proxy")).strip()
    if _config_bool(config.get("cpa_gui_close_mint_browser", True), default=True):
        cpa_cfg["cpa_mint_browser_reuse"] = False

    with _cpa_export_lock:
        # Space out device-code mints — auth.x.ai rate-limits bursts (429/slow_down)
        global _cpa_last_mint_ts
        try:
            gap = float(config.get("cpa_mint_gap_sec", 25) or 0)
        except (TypeError, ValueError):
            gap = 25.0
        if gap > 0 and _cpa_last_mint_ts > 0:
            wait = gap - (time.time() - _cpa_last_mint_ts)
            if wait > 0.5:
                log(f"[cpa] mint interval protection: waiting {wait:.1f}s (gap={gap}s)")
                time.sleep(wait)
        try:
            result = cpa_export.export_cpa_xai_for_account(
                email,
                password or "",
                page=page,
                cookies=cookies,
                sso=sso,
                config=cpa_cfg,
                log_callback=log,
            )
        except Exception as exc:
            _cpa_last_mint_ts = time.time()
            log(f"[cpa] CPA export error: {exc}")
            if config.get("cpa_mint_required", False):
                raise
            return {"ok": False, "error": str(exc)}
        _cpa_last_mint_ts = time.time()

    if result.get("ok"):
        log(f"[cpa] CPA/OIDC exported: {result.get('path')}")
        if result.get("probe"):
            log(f"[cpa] probe: {result.get('probe')}")
    else:
        log(f"[cpa] CPA export failed: {result.get('error') or result}")
    return result


def apply_browser_proxy_option(options, proxy):
    if not proxy:
        return
    if hasattr(options, "set_proxy"):
        try:
            options.set_proxy(proxy)
            return
        except Exception:
            pass
    if not hasattr(options, "set_argument"):
        raise AttributeError("current DrissionPage ChromiumOptions doesn't support setting browser proxy")
    try:
        options.set_argument(f"--proxy-server={proxy}")
    except TypeError:
        options.set_argument("--proxy-server", proxy)


def _set_browser_argument(options, arg, value=None):
    if not hasattr(options, "set_argument"):
        return
    try:
        if value is None:
            options.set_argument(arg)
        else:
            options.set_argument(arg, value)
    except TypeError:
        if value is None:
            options.set_argument(arg)
        else:
            options.set_argument(f"{arg}={value}")


def _detect_linux_browser_path():
    """Prefer real Chromium binaries over snap wrapper (/snap/bin/chromium).

    DrissionPage fails to connect CDP when launched via the snap wrapper script,
    but works with .../usr/lib/chromium-browser/chrome.
    """
    env = os.environ.get("GROK_REGISTER_BROWSER_PATH", "").strip()
    # If user pointed at snap wrapper, rewrite to real binary when present.
    snap_real = "/snap/chromium/current/usr/lib/chromium-browser/chrome"
    if env in ("/snap/bin/chromium", "chromium") and os.path.exists(snap_real):
        env = snap_real
    candidates = [
        env,
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        snap_real,
        # versioned snap fallback
        "/snap/chromium/current/usr/lib/chromium-browser/chrome",
        "/snap/bin/chromium",
    ]
    seen = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.exists(path):
            return path
    return ""


def _linux_display_socket_ok(display: str = "") -> bool:
    display = (display or os.environ.get("DISPLAY", "") or "").strip()
    if not display:
        return False
    try:
        num = display.split(":")[-1].split(".")[0]
        if not num.isdigit():
            return False
        return os.path.exists(f"/tmp/.X11-unix/X{num}")
    except Exception:
        return False


def _ensure_xvfb(log_callback=None) -> bool:
    """Ensure Xvfb is up for DISPLAY (default :99). Returns True if socket ready."""
    if sys.platform == "win32":
        return False
    if sys.platform == "darwin":
        return True  # macOS: native GUI, no Xvfb needed
    display = os.environ.get("DISPLAY", "").strip() or ":99"
    os.environ["DISPLAY"] = display
    if _linux_display_socket_ok(display):
        return True
    # Only manage classic :N displays
    try:
        num = display.split(":")[-1].split(".")[0]
        if not num.isdigit():
            return False
    except Exception:
        return False
    if log_callback:
        log_callback(f"[*] DISPLAY={display} has no X socket, trying to start Xvfb...")
    try:
        import subprocess

        log_path = "/var/log/xvfb-99.log" if num == "99" else f"/tmp/xvfb-{num}.log"
        with open(log_path, "a", encoding="utf-8", errors="ignore") as lf:
            subprocess.Popen(
                [
                    "Xvfb",
                    display,
                    "-screen",
                    "0",
                    "1920x1080x24",
                    "-ac",
                    "+extension",
                    "GLX",
                    "+render",
                    "-noreset",
                ],
                stdout=lf,
                stderr=lf,
                start_new_session=True,
            )
        for _ in range(20):
            time.sleep(0.25)
            if _linux_display_socket_ok(display):
                if log_callback:
                    log_callback(f"[+] Xvfb ready DISPLAY={display}")
                return True
    except Exception as exc:
        if log_callback:
            log_callback(f"[!] failed to start Xvfb: {exc}")
    if log_callback:
        log_callback(f"[!] Xvfb still unavailable DISPLAY={display}")
    return False


def _linux_should_headless():
    """Prefer headed Chromium under Xvfb when DISPLAY works.

    Pure headless is heavily flagged by Cloudflare on accounts.x.ai.
    GROK_REGISTER_HEADLESS=1 forces headless.
    GROK_REGISTER_HEADLESS=0 prefers headed, but falls back to headless if no X.
    """
    flag = os.environ.get("GROK_REGISTER_HEADLESS", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if sys.platform == "darwin":
        return False  # headed native — best for Cloudflare
    # Prefer headed when X is available (auto-start Xvfb if needed)
    if _ensure_xvfb():
        if flag in ("0", "false", "no", "off"):
            return False
        return False
    # No display: must headless even if user asked for headed
    return True


def _pick_free_local_port():
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        try:
            sock.close()
        except Exception:
            pass


def create_browser_options(browser_proxy="", force_headless=None):
    options = ChromiumOptions()
    # DrissionPage auto_port() may leave address empty on some versions;
    # always pin an explicit local debugging port.
    try:
        options.auto_port()
    except Exception:
        pass
    if not getattr(options, "address", None) or ":" not in str(options.address):
        port = _pick_free_local_port()
        if hasattr(options, "set_local_port"):
            options.set_local_port(port)
        else:
            try:
                options._address = f"127.0.0.1:{port}"
            except Exception:
                pass
    # Give Chromium more time to open remote-debugging port (snap is slow)
    try:
        options.set_timeouts(base=3, page_load=30, script=20)
    except TypeError:
        try:
            options.set_timeouts(base=3)
        except Exception:
            pass
    apply_browser_proxy_option(options, browser_proxy)
    if sys.platform != "win32":
        browser_path = _detect_linux_browser_path()
        if browser_path and hasattr(options, "set_browser_path"):
            try:
                options.set_browser_path(browser_path)
            except Exception:
                pass
        # Fresh user-data dir per launch avoids SingletonLock / zombie chrome conflicts
        base_data = os.environ.get("GROK_REGISTER_USER_DATA", "").strip() or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".chrome-data"
        )
        user_data = os.path.join(
            base_data, f"run-{os.getpid()}-{int(time.time())}-{secrets.token_hex(2)}"
        )
        try:
            os.makedirs(user_data, exist_ok=True)
            if hasattr(options, "set_user_data_path"):
                options.set_user_data_path(user_data)
            elif hasattr(options, "set_paths"):
                options.set_paths(user_data_path=user_data)
        except Exception:
            pass
        _set_browser_argument(options, "--no-sandbox")
        _set_browser_argument(options, "--disable-setuid-sandbox")
        _set_browser_argument(options, "--disable-dev-shm-usage")
        _set_browser_argument(options, "--no-first-run")
        _set_browser_argument(options, "--no-default-browser-check")
        _set_browser_argument(options, "--window-size=1280,900")
        # Snap + Xvfb: disable GPU to avoid ANGLE/XCB init failures
        _set_browser_argument(options, "--disable-gpu")
        _set_browser_argument(options, "--disable-software-rasterizer")
        _set_browser_argument(options, "--disable-features=TranslateUI,BlinkGenPropertyTrees")
        # Reduce automation fingerprints (helps Cloudflare / Turnstile)
        _set_browser_argument(options, "--disable-blink-features=AutomationControlled")
        _set_browser_argument(options, "--lang=en-US")
        # Note: do not pass invalid --excludeSwitches=... as a bare chromium flag
        try:
            if hasattr(options, "set_pref"):
                options.set_pref("credentials_enable_service", False)
                options.set_pref("profile.password_manager_enabled", False)
        except Exception:
            pass
        if force_headless is None:
            headless = _linux_should_headless()
        else:
            headless = bool(force_headless)
        if headless:
            try:
                if hasattr(options, "headless"):
                    options.headless(True)
            except Exception:
                pass
            _set_browser_argument(options, "--headless=new")
        if os.path.exists(EXTENSION_PATH) and not headless:
            options.add_extension(EXTENSION_PATH)
        return options
    if os.path.exists(EXTENSION_PATH):
        options.add_extension(EXTENSION_PATH)
    return options


def _build_request_kwargs(**kwargs):
    request_kwargs = dict(kwargs)
    proxies = request_kwargs.pop("proxies", None)
    if proxies is None:
        proxies = get_proxies()
    if proxies:
        request_kwargs["proxies"] = proxies
    request_kwargs.setdefault("timeout", 15)
    return request_kwargs


def _is_local_url(url):
    try:
        host = urllib.parse.urlsplit(str(url or "")).hostname or ""
    except Exception:
        return False
    host = host.split(":")[0].lower()
    return host in ("localhost", "127.0.0.1", "::1") or host.startswith("127.")


def http_get(url, **kwargs):
    if _is_local_url(url):
        kwargs["proxies"] = {}
    request_kwargs = _build_request_kwargs(**kwargs)
    try:
        return requests.get(url, **request_kwargs)
    except Exception as exc:
        if request_kwargs.get("proxies") and is_proxy_connection_error(exc):
            retry_kwargs = dict(kwargs)
            retry_kwargs["proxies"] = {}
            return requests.get(url, **_build_request_kwargs(**retry_kwargs))
        raise


def http_post(url, **kwargs):
    if _is_local_url(url):
        kwargs["proxies"] = {}
    request_kwargs = _build_request_kwargs(**kwargs)
    try:
        return requests.post(url, **request_kwargs)
    except Exception as exc:
        if request_kwargs.get("proxies") and is_proxy_connection_error(exc):
            retry_kwargs = dict(kwargs)
            retry_kwargs["proxies"] = {}
            return requests.post(url, **_build_request_kwargs(**retry_kwargs))
        raise


def raise_if_cancelled(cancel_callback=None):
    if cancel_callback and cancel_callback():
        raise RegistrationCancelled("user stopped registration")


def sleep_with_cancel(seconds, cancel_callback=None):
    deadline = time.time() + max(seconds, 0)
    while True:
        raise_if_cancelled(cancel_callback)
        remaining = deadline - time.time()
        if remaining <= 0:
            return
        time.sleep(min(0.2, remaining))


def cloudflare_get_domains(api_base, api_key=None):
    headers = cloudflare_build_headers(content_type=False)
    if api_key and "Authorization" in headers:
        headers["Authorization"] = f"Bearer {api_key}"
    if api_key and "X-API-Key" in headers:
        headers["X-API-Key"] = api_key
    path = get_cloudflare_path("cloudflare_path_domains", "/domains")
    params = cloudflare_apply_auth_params()
    resp = http_get(f"{api_base}{path}", headers=headers, params=params)
    resp.raise_for_status()
    return _pick_list_payload(resp.json())


def cloudflare_create_account(api_base, address, password, api_key=None, expires_in=0):
    headers = cloudflare_build_headers(content_type=True)
    if api_key and "Authorization" in headers:
        headers["Authorization"] = f"Bearer {api_key}"
    if api_key and "X-API-Key" in headers:
        headers["X-API-Key"] = api_key
    payload = {"address": address, "password": password, "expiresIn": expires_in}
    path = get_cloudflare_path("cloudflare_path_accounts", "/accounts")
    params = cloudflare_apply_auth_params()
    resp = http_post(f"{api_base}{path}", json=payload, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()


def cloudflare_get_token(api_base, address, password, api_key=None):
    headers = cloudflare_build_headers(content_type=True)
    if api_key and "Authorization" in headers:
        headers["Authorization"] = f"Bearer {api_key}"
    if api_key and "X-API-Key" in headers:
        headers["X-API-Key"] = api_key
    path = get_cloudflare_path("cloudflare_path_token", "/token")
    resp = http_post(
        f"{api_base}{path}",
        json={"address": address, "password": password},
        headers=headers,
        params=cloudflare_apply_auth_params(),
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        if data.get("token"):
            return data.get("token")
        if isinstance(data.get("data"), dict) and data["data"].get("token"):
            return data["data"].get("token")
    return None


def cloudflare_get_messages(api_base, token):
    # Ammail mode: token = inbox alias; use X-API-Key header + /api/inboxes/:alias/messages
    if config.get("email_provider") == "ammail":
        headers = cloudflare_build_headers()
        alias = token
        path = f"/api/inboxes/{alias}/messages"
        resp = http_get(f"{api_base}{path}", headers=headers)
        resp.raise_for_status()
        try:
            data = resp.json()
        except Exception:
            raise Exception(f"Ammail messages returned non-JSON: {resp.text[:300]}")
        return _pick_list_payload(data)
    headers = {"Authorization": f"Bearer {token}"}
    path = get_cloudflare_path("cloudflare_path_messages", "/messages")
    params = {"limit": 20, "offset": 0}
    params = cloudflare_apply_auth_params(params)
    resp = http_get(f"{api_base}{path}", headers=headers, params=params)
    resp.raise_for_status()
    try:
        data = resp.json()
    except Exception:
        raise Exception(f"Cloudflare messages returned non-JSON: {resp.text[:300]}")
    return _pick_list_payload(data)


def cloudflare_get_message_detail(api_base, token, message_id):
    # Ammail mode: GET /api/messages/:id with X-API-Key
    if config.get("email_provider") == "ammail":
        headers = cloudflare_build_headers()
        url = f"{api_base}/api/messages/{message_id}"
        try:
            resp = http_get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                return data["data"]
            if isinstance(data, dict) and isinstance(data.get("message"), dict):
                return data["message"]
            return data
        except Exception as exc:
            raise Exception(f"Ammail failed to fetch mail details: {exc}")
    headers = {"Authorization": f"Bearer {token}"}
    candidates = [
        f"{api_base}/api/mail/{message_id}",
        f"{api_base}{get_cloudflare_path('cloudflare_path_messages', '/messages')}/{message_id}",
    ]
    last_err = None
    for url in candidates:
        try:
            resp = http_get(
                url,
                headers=headers,
                params=cloudflare_apply_auth_params(),
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                return data["data"]
            return data
        except Exception as exc:
            last_err = exc
            continue
    raise Exception(f"Cloudflare failed to fetch mail details: {last_err}")




LITENSI_API_BASE = "https://litensi.id/api/mail"


def get_litensi_api_id():
    return str(config.get("litensi_api_id", "") or "")


def get_litensi_api_key():
    return config.get("litensi_api_key", "")


def litensi_get_prices(api_id=None, api_key=None, site=None):
    api_id = api_id or get_litensi_api_id()
    api_key = api_key or get_litensi_api_key()
    site = site or config.get("litensi_site", "")
    if not api_id or not api_key:
        raise Exception("Litensi API ID / API Key not configured")
    if not site:
        raise Exception("Litensi site not configured")
    resp = http_post(
        f"{LITENSI_API_BASE}/prices",
        data={"api_id": api_id, "api_key": api_key, "site": site},
    )
    try:
        data = resp.json()
    except Exception:
        data = None
    if not resp.ok or not (data and data.get("success")):
        reason = data.get("data") if isinstance(data, dict) else None
        raise Exception(f"Litensi prices failed (HTTP {resp.status_code}): {reason or data or resp.text[:200]}")
    return data.get("data") or []


def litensi_pick_zone(api_id, api_key, site):
    zones = litensi_get_prices(api_id=api_id, api_key=api_key, site=site)
    stock = [z for z in zones if z.get("stock", 0) > 0]
    if not stock:
        raise Exception(f"Litensi has no zones for site {site}")
    stock.sort(key=lambda z: z.get("price", 0))
    return stock[0]["zone"]


def litensi_get_email_and_token(api_id=None, api_key=None, zone=None, site=None):
    api_id = api_id or get_litensi_api_id()
    api_key = api_key or get_litensi_api_key()
    site = site or config.get("litensi_site", "")
    if not api_id or not api_key:
        raise Exception("Litensi API ID / API Key not configured")
    if not site:
        raise Exception("Litensi site not configured")
    zone = zone or config.get("litensi_zone", "") or litensi_pick_zone(api_id, api_key, site)
    resp = http_post(
        f"{LITENSI_API_BASE}/order",
        data={"api_id": api_id, "api_key": api_key, "zone": zone, "site": site},
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise Exception(f"Litensi order failed: {data}")
    order = data.get("data") or {}
    address = order.get("email")
    order_id = order.get("order_id")
    if not address or order_id is None:
        raise Exception(f"Litensi order bad response: {data}")
    print(f"[*] created Litensi mailbox: {address}")
    return address, str(order_id)


def litensi_getstatus(order_id, api_id=None, api_key=None):
    api_id = api_id or get_litensi_api_id()
    api_key = api_key or get_litensi_api_key()
    resp = http_post(
        f"{LITENSI_API_BASE}/getstatus",
        data={"api_id": api_id, "api_key": api_key, "order_id": order_id},
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise Exception(f"Litensi getstatus failed: {data}")
    return data.get("data") or {}


def litensi_setstatus(order_id, status, api_id=None, api_key=None):
    api_id = api_id or get_litensi_api_id()
    api_key = api_key or get_litensi_api_key()
    resp = http_post(
        f"{LITENSI_API_BASE}/setstatus",
        data={"api_id": api_id, "api_key": api_key, "order_id": order_id, "status": status},
    )
    try:
        data = resp.json()
    except Exception:
        data = None
    if not resp.ok or not (data and data.get("success")):
        reason = data.get("data") if isinstance(data, dict) else None
        raise Exception(f"Litensi setstatus {status} failed (HTTP {resp.status_code}): {reason or data or resp.text[:200]}")
    return data.get("data") or {}


def litensi_get_oai_code(
    order_id,
    email,
    timeout=180,
    poll_interval=5,
    log_callback=None,
    cancel_callback=None,
):
    # litensi: getstatus must not be called faster than every 5s
    poll_interval = max(poll_interval, 5)
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            raise_if_cancelled(cancel_callback)
            try:
                data = litensi_getstatus(order_id)
            except Exception as exc:
                if log_callback:
                    log_callback(f"[Debug] Litensi getstatus failed: {exc}")
                sleep_with_cancel(poll_interval, cancel_callback)
                continue
            status = data.get("status", "")
            if log_callback:
                log_callback(f"[Debug] Litensi order {order_id} status: {status}")
            if status == "CANCELED":
                raise Exception("Litensi order canceled")
            if status in ("RECEIVED", "SUCCESS") or data.get("message") or data.get("full_message"):
                text = "\n".join(
                    x for x in (data.get("message", ""), data.get("full_message", "")) if x
                )
                code = extract_verification_code(text)
                if code:
                    if log_callback:
                        log_callback(f"[*] Litensi extracted verification code from mail: {code}")
                    return code
            sleep_with_cancel(poll_interval, cancel_callback)
        raise Exception(f"Litensi did not receive the verification code in {timeout}s")
    except Exception:
        if log_callback:
            log_callback("[*] Canceling Litensi order (no OTP received)")
        try:
            litensi_setstatus(order_id, "CANCELED")
        except Exception as exc:
            if log_callback:
                log_callback(f"[Debug] failed to cancel Litensi order: {exc}")
        raise


def generate_username(length=10):
    chars = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def get_email_provider():
    return config.get("email_provider", "litensi")


def get_email_and_token(api_key=None):
    provider = get_email_provider()
    if provider == "litensi":
        return litensi_get_email_and_token()
    if provider == "ammail":
        api_base = get_cloudflare_api_base()
        if not api_base:
            raise Exception("Ammail API Base not configured")
        return cloudflare_create_temp_address(api_base)
    if provider == "cloudflare":
        api_base = get_cloudflare_api_base()
        if not api_base:
            raise Exception("Cloudflare API Base not configured")
        try:
            # cloudflare_temp_email dedicated mode
            return cloudflare_create_temp_address(api_base)
        except Exception as primary_exc:
            # fallback to Mail.tm style
            key = api_key or get_cloudflare_api_key()
            domains = cloudflare_get_domains(api_base, api_key=key)
            if not domains:
                raise Exception(f"Cloudflare failed to create mailbox: {primary_exc}")
            verified = [d for d in domains if d.get("isVerified")]
            target = verified[0] if verified else domains[0]
            domain = target.get("domain")
            if not domain:
                raise Exception("Cloudflare domain data bad format, missing domain field")
            username = generate_username(10)
            address = f"{username}@{domain}"
            password = secrets.token_urlsafe(12)
            cloudflare_create_account(
                api_base, address, password, api_key=key, expires_in=0
            )
            token = cloudflare_get_token(api_base, address, password, api_key=key)
            if not token:
                raise Exception("Failed to get Cloudflare mailbox token")
            return address, token
    raise Exception(f"unknown email provider: {provider}")


def get_oai_code(
    dev_token,
    email,
    timeout=180,
    poll_interval=3,
    log_callback=None,
    cancel_callback=None,
    resend_callback=None,
):
    provider = get_email_provider()
    if provider == "litensi":
        return litensi_get_oai_code(
            dev_token,
            email,
            timeout=timeout,
            poll_interval=poll_interval,
            log_callback=log_callback,
            cancel_callback=cancel_callback,
        )
    if provider == "ammail":
        return cloudflare_get_oai_code(
            dev_token,
            email,
            timeout=timeout,
            poll_interval=poll_interval,
            log_callback=log_callback,
            cancel_callback=cancel_callback,
            resend_callback=resend_callback,
        )
    if provider == "cloudflare":
        return cloudflare_get_oai_code(
            dev_token,
            email,
            timeout=timeout,
            poll_interval=poll_interval,
            log_callback=log_callback,
            cancel_callback=cancel_callback,
            resend_callback=resend_callback,
        )
    raise Exception(f"unknown email provider: {provider}")


def extract_verification_code(text, subject=""):
    if subject:
        match = re.search(r"^([A-Z0-9]{3}-[A-Z0-9]{3})\s+xAI", subject, re.IGNORECASE)
        if match:
            return match.group(1)
    match = re.search(r"\b([A-Z0-9]{3}-[A-Z0-9]{3})\b", text, re.IGNORECASE)
    if match:
        return match.group(1)
    patterns = [
        r"verification\s+code[:\s]+(\d{4,8})",
        r"your\s+code[:\s]+(\d{4,8})",
        r"confirm(?:ation)?\s+code[:\s]+(\d{4,8})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def cloudflare_get_oai_code(
    dev_token,
    email,
    timeout=180,
    poll_interval=3,
    log_callback=None,
    cancel_callback=None,
    resend_callback=None,
):
    api_base = get_cloudflare_api_base()
    if not api_base:
        raise Exception("Cloudflare API Base not configured")
    deadline = time.time() + timeout
    # the same mail body may be read late，allowing multiple parse retries，avoid occasional missed codes
    seen_attempts = {}
    next_resend_at = time.time() + 35
    while time.time() < deadline:
        raise_if_cancelled(cancel_callback)
        if resend_callback and time.time() >= next_resend_at:
            try:
                resend_callback()
                if log_callback:
                    log_callback("[*] Resend of verification code triggered")
            except Exception as exc:
                if log_callback:
                    log_callback(f"[Debug] failed to trigger resend of verification code: {exc}")
            next_resend_at = time.time() + 35
        try:
            messages = cloudflare_get_messages(api_base, dev_token)
        except Exception as exc:
            if log_callback:
                log_callback(f"[Debug] Cloudflare failed to fetch mail list: {exc}")
            sleep_with_cancel(poll_interval, cancel_callback)
            continue
        if log_callback:
            log_callback(f"[Debug] Cloudflare mail count this round: {len(messages)}")

        for msg in messages:
            msg_id = msg.get("id") or msg.get("msgid")
            if not msg_id:
                continue
            attempt = int(seen_attempts.get(msg_id, 0))
            if attempt >= 5:
                continue
            seen_attempts[msg_id] = attempt + 1
            recipients = []
            to_field = msg.get("to")
            if isinstance(to_field, str):
                # Ammail-style: to is a plain string address
                recipients.append(to_field.lower())
            elif isinstance(to_field, list):
                recipients = [t.get("address", "").lower() for t in to_field if isinstance(t, dict)]
            msg_addr = str(msg.get("address", "")).lower()
            # Ammail-style messages: to_address is a plain string
            to_addr_str = str(msg.get("to_address", "") or "").lower()
            if to_addr_str:
                recipients.append(to_addr_str)
            # preferring to match the target mailbox; also allow parsing when structure differs, to avoid missed codes from API field drift
            address_matched = True
            if recipients:
                address_matched = email.lower() in recipients
            elif msg_addr:
                address_matched = msg_addr == email.lower()
            if not address_matched and log_callback:
                log_callback(f"[Debug] skipping non-target mail id={msg_id} address={msg_addr} to={recipients}")
                continue
            parts = []
            # first try list item content directly, avoiding missed codes from detail API differences
            for field in ("text", "raw", "content", "intro", "body", "snippet"):
                value = msg.get(field)
                if isinstance(value, str) and value.strip():
                    parts.append(value)
            html_list = msg.get("html") or []
            if isinstance(html_list, str):
                html_list = [html_list]
            for h in html_list:
                parts.append(re.sub(r"<[^>]+>", " ", h))
            subject = str(msg.get("subject", "") or "")
            combined = "\n".join(parts)
            # then try the detail API to complete content
            try:
                detail = cloudflare_get_message_detail(api_base, dev_token, msg_id)
                for field in ("text", "raw", "content", "intro", "body", "snippet"):
                    value = detail.get(field)
                    if isinstance(value, str) and value.strip():
                        combined += "\n" + value
                html_list2 = detail.get("html") or []
                if isinstance(html_list2, str):
                    html_list2 = [html_list2]
                for h in html_list2:
                    combined += "\n" + re.sub(r"<[^>]+>", " ", h)
                if not subject:
                    subject = str(detail.get("subject", "") or "")
            except Exception as exc:
                if log_callback:
                    log_callback(f"[Debug] Cloudflare detail API failed, falling back to list content parsing: {exc}")
            if log_callback:
                log_callback(f"[Debug] Cloudflare received mail: {subject}")
            code = extract_verification_code(combined, subject)
            if code:
                if log_callback:
                    log_callback(f"[*] Cloudflare extracted code from mail: {code}")
                return code
            elif log_callback:
                log_callback(f"[Debug] mail parsed but no code extracted id={msg_id} attempt={seen_attempts[msg_id]}")
        sleep_with_cancel(poll_interval, cancel_callback)
    raise Exception(f"Cloudflare did not receive the verification code in {timeout}s")


def generate_random_birthdate():
    import datetime as dt

    today = dt.date.today()
    age = random.randint(20, 40)
    birth_year = today.year - age
    birth_month = random.randint(1, 12)
    birth_day = random.randint(1, 28)
    return f"{birth_year}-{birth_month:02d}-{birth_day:02d}T16:00:00.000Z"


def response_preview(res, limit=200):
    try:
        text = str(res.text or "")
    except Exception:
        text = ""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def is_cloudflare_block_response(res):
    try:
        headers = {str(k).lower(): str(v).lower() for k, v in dict(res.headers).items()}
        text = str(res.text or "").lower()
        server = headers.get("server", "")
        content_type = headers.get("content-type", "")
        return (
            res.status_code in (403, 429, 503)
            and (
                "cloudflare" in server
                or "cloudflare" in text
                or "cf-error" in text
                or "__cf_chl" in text
                or "text/html" in content_type
            )
        )
    except Exception:
        return False


def set_birth_date(session, log_callback=None):
    url = "https://grok.com/rest/auth/set-birth-date"
    new_headers = {
        "content-type": "application/json",
        "origin": "https://grok.com",
        "referer": "https://grok.com/",
    }
    payload = {"birthDate": generate_random_birthdate()}
    try:
        res = session.post(url, json=payload, headers=new_headers, timeout=15)
        if log_callback:
            log_callback(
                f"[Debug] set_birth_date status: {res.status_code}, body: {response_preview(res)}"
            )
        if 200 <= res.status_code < 300:
            return True, "ok"
        if is_cloudflare_block_response(res):
            return (
                False,
                "set_birth_date blocked by grok.com's Cloudflare protection, HTTP "
                f"{res.status_code}",
            )
        return False, f"set_birth_date HTTP {res.status_code}: {response_preview(res)}"
    except Exception as e:
        if log_callback:
            log_callback(f"[set_birth_date] error: {e}")
        return False, f"set_birth_date error: {e}"


def set_tos_accepted(session, log_callback=None):
    url = "https://accounts.x.ai/auth_mgmt.AuthManagement/SetTosAcceptedVersion"
    payload = struct.pack("B", (2 << 3) | 0) + struct.pack("B", 1)
    data = b"\x00" + struct.pack(">I", len(payload)) + payload
    new_headers = {
        "content-type": "application/grpc-web+proto",
        "x-grpc-web": "1",
        "x-user-agent": "connect-es/2.1.1",
        "origin": "https://accounts.x.ai",
        "referer": "https://accounts.x.ai/accept-tos",
    }
    try:
        res = session.post(url, data=data, headers=new_headers, timeout=15)
        if log_callback:
            log_callback(f"[Debug] set_tos_accepted status: {res.status_code}")
        if 200 <= res.status_code < 300:
            return True, "ok"
        if is_cloudflare_block_response(res):
            return (
                False,
                "set_tos_accepted blocked by accounts.x.ai's Cloudflare protection, HTTP "
                f"{res.status_code}",
            )
        return False, f"set_tos_accepted HTTP {res.status_code}: {response_preview(res)}"
    except Exception as e:
        if log_callback:
            log_callback(f"[set_tos_accepted] error: {e}")
        return False, f"set_tos_accepted error: {e}"


def encode_grpc_nsfw_settings():
    field1_content = bytes([0x10, 0x01])
    field1 = bytes([0x0A, len(field1_content)]) + field1_content
    nsfw_string = b"always_show_nsfw_content"
    field2_inner = bytes([0x0A, len(nsfw_string)]) + nsfw_string
    field2 = bytes([0x12, len(field2_inner)]) + field2_inner
    payload = field1 + field2
    return b"\x00" + struct.pack(">I", len(payload)) + payload


def update_nsfw_settings(session, log_callback=None):
    url = "https://grok.com/auth_mgmt.AuthManagement/UpdateUserFeatureControls"
    data = encode_grpc_nsfw_settings()
    new_headers = {
        "content-type": "application/grpc-web+proto",
        "x-grpc-web": "1",
        "origin": "https://grok.com",
        "referer": "https://grok.com/",
    }
    try:
        res = session.post(url, data=data, headers=new_headers, timeout=15)
        if log_callback:
            log_callback(
                f"[Debug] update_nsfw status: {res.status_code}, body: {response_preview(res)}"
            )
        if 200 <= res.status_code < 300:
            return True, "ok"
        if is_cloudflare_block_response(res):
            return (
                False,
                "update_nsfw_settings blocked by grok.com's Cloudflare protection, HTTP "
                f"{res.status_code}",
            )
        return False, f"update_nsfw_settings HTTP {res.status_code}: {response_preview(res)}"
    except Exception as e:
        if log_callback:
            log_callback(f"[update_nsfw] error: {e}")
        return False, f"update_nsfw_settings error: {e}"


def enable_nsfw_for_token(token, cf_clearance="", log_callback=None):
    proxies = get_proxies()
    user_agent = get_user_agent()
    try:
        with requests.Session(impersonate="chrome120", proxies=proxies) as session:
            cookie_parts = [f"sso={token}", f"sso-rw={token}"]
            if cf_clearance:
                cookie_parts.append(f"cf_clearance={cf_clearance}")
            session.headers.update(
                {
                    "user-agent": user_agent,
                    "cookie": "; ".join(cookie_parts),
                }
            )
            ok, message = set_tos_accepted(session, log_callback)
            if not ok:
                return False, message
            ok, message = set_birth_date(session, log_callback)
            if not ok:
                return False, message
            ok, message = update_nsfw_settings(session, log_callback)
            if not ok:
                return False, message
            return True, "NSFW enabled successfully"
    except Exception as e:
        return False, f"error: {str(e)}"


SIGNUP_URL = "https://accounts.x.ai/sign-up?redirect=grok-com"

browser = None
page = None
browser_proxy_bridge = None
browser_started_with_proxy = False


def setup_light_theme(root):
    try:
        root.option_add("*Background", UI_BG)
        root.option_add("*Foreground", UI_FG)
        root.option_add("*selectBackground", UI_ACTIVE_BG)
        root.option_add("*selectForeground", UI_FG)
        root.option_add("*insertBackground", UI_FG)
        root.option_add("*Entry.Background", UI_ENTRY_BG)
        root.option_add("*Text.Background", UI_ENTRY_BG)
        root.option_add("*Menu.Background", UI_ENTRY_BG)
        root.option_add("*Menu.Foreground", UI_FG)
        style = ttk.Style(root)
        available = set(style.theme_names())
        if "clam" in available:
            style.theme_use("clam")
        elif "default" in available:
            style.theme_use("default")
        root.configure(bg=UI_BG)
        style.configure(".", background=UI_BG, foreground=UI_FG, fieldbackground=UI_ENTRY_BG)
        style.configure("TFrame", background=UI_BG)
        style.configure("TLabelframe", background=UI_BG, foreground=UI_FG)
        style.configure("TLabelframe.Label", background=UI_BG, foreground=UI_FG)
        style.configure("TLabel", background=UI_BG, foreground=UI_FG)
        style.configure("TCheckbutton", background=UI_BG, foreground=UI_FG)
        style.configure("TButton", background=UI_BUTTON_BG, foreground=UI_FG)
        style.configure("TEntry", fieldbackground=UI_ENTRY_BG, foreground=UI_FG)
        style.configure("TCombobox", fieldbackground=UI_ENTRY_BG, foreground=UI_FG)
        style.configure("TSpinbox", fieldbackground=UI_ENTRY_BG, foreground=UI_FG)
    except Exception:
        pass


def tk_label(parent, text="", **kwargs):
    return tk.Label(parent, text=text, bg=kwargs.pop("bg", UI_BG), fg=kwargs.pop("fg", UI_FG), **kwargs)


def tk_entry(parent, textvariable=None, width=30, **kwargs):
    return tk.Entry(
        parent,
        textvariable=textvariable,
        width=width,
        bg=UI_ENTRY_BG,
        fg=UI_FG,
        insertbackground=UI_FG,
        disabledbackground="#2f2f2f",
        disabledforeground=UI_MUTED_FG,
        highlightthickness=1,
        highlightbackground="#555555",
        relief=tk.SOLID,
        **kwargs,
    )


def tk_button(parent, text="", command=None, state=None, **kwargs):
    if state is None:
        state = tk.NORMAL if HAS_TK else "normal"
    return tk.Button(
        parent,
        text=text,
        command=command,
        state=state,
        bg=UI_BUTTON_BG,
        fg=UI_FG,
        activebackground=UI_ACTIVE_BG,
        activeforeground=UI_FG,
        disabledforeground="#777777",
        relief=tk.RAISED,
        padx=10,
        pady=3,
        **kwargs,
    )


def tk_checkbutton(parent, text="", variable=None, **kwargs):
    return tk.Checkbutton(
        parent,
        text=text,
        variable=variable,
        bg=UI_BG,
        fg=UI_FG,
        activebackground=UI_BG,
        activeforeground=UI_FG,
        selectcolor="#3d7be0",
        **kwargs,
    )


def tk_option_menu(parent, variable, values, width=12):
    menu = tk.OptionMenu(parent, variable, *values)
    menu.configure(
        width=width,
        bg=UI_ENTRY_BG,
        fg=UI_FG,
        activebackground=UI_ACTIVE_BG,
        activeforeground=UI_FG,
        highlightthickness=1,
        highlightbackground="#555555",
        relief=tk.SOLID,
    )
    menu["menu"].configure(bg=UI_ENTRY_BG, fg=UI_FG, activebackground=UI_ACTIVE_BG, activeforeground=UI_FG)
    return menu


def _apply_browser_stealth(tab, log_callback=None):
    """Best-effort anti-automation patches after tab is ready."""
    if tab is None:
        return
    js = r"""
try {
  Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
} catch (e) {}
try {
  if (!window.chrome) { window.chrome = { runtime: {} }; }
} catch (e) {}
try {
  Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
} catch (e) {}
try {
  Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
} catch (e) {}
"""
    try:
        tab.run_js(js)
    except Exception as exc:
        if log_callback:
            log_callback(f"[Debug] stealth script injection failed: {exc}")


def start_browser(log_callback=None, use_proxy=True):
    global browser, page, browser_proxy_bridge, browser_started_with_proxy
    last_exc = None
    proxy_enabled = bool(use_proxy and get_configured_proxy())
    if sys.platform != "win32":
        # Bring up Xvfb early so headed mode can work
        _ensure_xvfb(log_callback=log_callback)
    for attempt in range(1, 5):
        bridge = None
        # After 2 headed failures, force headless fallback so registration can continue
        force_hl = None
        if sys.platform != "win32" and attempt >= 3:
            force_hl = True
            if log_callback and attempt == 3:
                log_callback("[!] headed mode failed repeatedly, falling back to headless=new retry")
        try:
            browser_proxy, bridge = prepare_browser_proxy(use_proxy=use_proxy, log_callback=log_callback)
            browser = Chromium(
                create_browser_options(browser_proxy=browser_proxy, force_headless=force_hl)
            )
            browser_proxy_bridge = bridge
            browser_started_with_proxy = bool(browser_proxy)
            tabs = browser.get_tabs()
            page = tabs[-1] if tabs else browser.new_tab()
            _apply_browser_stealth(page, log_callback=log_callback)
            if log_callback and getattr(browser, "user_data_path", None):
                log_callback(f"[Debug] current browser profile directory: {browser.user_data_path}")
            if log_callback:
                if sys.platform != "win32":
                    hl = force_hl if force_hl is not None else _linux_should_headless()
                    log_callback(
                        f"[*] browser display mode: {'headless' if hl else 'headed (Xvfb/DISPLAY)'} "
                        f"DISPLAY={os.environ.get('DISPLAY') or '(empty)'} "
                        f"Xsocket={'ok' if _linux_display_socket_ok() else 'missing'}"
                    )
                if get_configured_proxy():
                    mode = "proxy" if browser_started_with_proxy else "direct"
                    log_callback(f"[*] browser network mode: {mode}")
                    meta = config.get("_last_proxy_exit") if isinstance(config, dict) else None
                    if isinstance(meta, dict) and meta.get("exit_ip"):
                        log_callback(
                            f"[*] exit residential note: {meta.get('exit_ip')} "
                            f"({meta.get('exit_org') or '?'}) "
                            f"res={meta.get('isResidential')} fraud={meta.get('fraudScore')} "
                            f"| entry gateway only={meta.get('gateway')}"
                        )
            if log_callback and attempt > 1:
                log_callback(f"[*] browser started on attempt {attempt} successfully")
            return browser, page
        except Exception as exc:
            last_exc = exc
            if bridge is not None:
                try:
                    bridge.stop()
                except Exception:
                    pass
            if log_callback:
                mode = "proxy" if proxy_enabled else "direct"
                log_callback(f"[Debug] browser {mode} start failed (attempt {attempt}/4 ): {exc}")
            try:
                if browser is not None:
                    browser.quit(del_data=True)
            except Exception:
                pass
            browser = None
            page = None
            browser_proxy_bridge = None
            browser_started_with_proxy = False
            if sys.platform != "win32" and attempt == 1:
                _ensure_xvfb(log_callback=log_callback)
            time.sleep(min(1.5 * attempt, 4))
    raise Exception(f"browser start failed, retried 4 times: {last_exc}")


def stop_browser():
    global browser, page, browser_started_with_proxy
    if browser is not None:
        try:
            browser.quit(del_data=True)
        except Exception:
            pass
    stop_browser_proxy_bridge()
    browser = None
    page = None
    browser_started_with_proxy = False


def shutdown_browser():
    """Alias for hybrid/token_harvester (grok_reg API)."""
    stop_browser()


def _get_browser():
    """Alias for hybrid/token_harvester."""
    global browser
    return browser


def _get_page():
    """Alias for hybrid/token_harvester; refresh tab if needed."""
    global page, browser
    if browser is None:
        return None
    if page is None:
        try:
            return refresh_active_page()
        except Exception:
            return None
    return page


def restart_browser(log_callback=None, use_proxy=True):
    stop_browser()
    return start_browser(log_callback=log_callback, use_proxy=use_proxy)


def cleanup_runtime_memory(log_callback=None, reason="periodic cleanup"):
    if log_callback:
        log_callback(f"[*] {reason}: closing browser and cleaning up memory")
    stop_browser()
    collected = gc.collect()
    if log_callback:
        log_callback(f"[*] Python GC collected objects: {collected}")


def refresh_active_page():
    global browser, page
    if browser is None:
        restart_browser()
    try:
        tabs = browser.get_tabs()
        if tabs:
            page = tabs[-1]
        else:
            page = browser.new_tab()
    except Exception:
        restart_browser()
    return page


def click_email_signup_button(timeout=10, log_callback=None, cancel_callback=None):
    global page
    deadline = time.time() + timeout
    while time.time() < deadline:
        raise_if_cancelled(cancel_callback)
        if log_callback:
            log_callback("[Debug] trying to find the 'Register with mail' button...")

        clicked = page.run_js(r"""
function isVisible(node) {
    if (!node) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}
function nodeText(node) {
    return [
        node.innerText,
        node.textContent,
        node.getAttribute('aria-label'),
        node.getAttribute('title'),
        node.getAttribute('href'),
    ].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
}
function scoreEntry(node) {
    const compact = nodeText(node).replace(/\s+/g, '');
    const lower = compact.toLowerCase();
    if (compact.includes('使用邮箱注册')) return 100;
    if (lower.includes('signupwithemail')) return 95;
    if (lower.includes('continuewithemail')) return 90;
    if (lower.includes('email') && (lower.includes('sign') || lower.includes('continue') || lower.includes('use') || lower.includes('with'))) return 80;
    if (lower === 'email' || lower.includes('邮箱')) return 70;
    return 0;
}
const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]'))
    .filter((node) => isVisible(node) && !node.disabled && node.getAttribute('aria-disabled') !== 'true')
    .map((node) => ({ node, score: scoreEntry(node), text: nodeText(node) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score);
const target = candidates[0]?.node || null;
if (!target) {
    return false;
}
target.click();
return candidates[0].text || true;
        """)

        if clicked:
            if log_callback:
                detail = f": {clicked}" if isinstance(clicked, str) else ""
                log_callback(f"[*] clicked the 'Register with mail' button{detail}")
            sleep_with_cancel(2, cancel_callback)
            return True

        if log_callback:
            current_url = page.url if page else "none"
            log_callback(f"[Debug] current URL: {current_url}")

        sleep_with_cancel(1, cancel_callback)

    if log_callback:
        page_html = page.html[:500] if page else "no page"
        log_callback(f"[Debug] page content snippet: {page_html}")

    raise Exception("'Register with mail' button not found")


def page_is_cloudflare_challenge(page_obj=None):
    """Detect Cloudflare interstitial / attention page."""
    p = page_obj or page
    if p is None:
        return False
    try:
        title = str(getattr(p, "title", "") or "")
        url = str(getattr(p, "url", "") or "")
        html = ""
        try:
            html = str(p.html or "")[:4000]
        except Exception:
            html = ""
        blob = f"{title}\n{url}\n{html}".lower()
        markers = (
            "attention required",
            "just a moment",
            "cf-browser-verification",
            "cf-challenge",
            "cf-turnstile",
            "checking your browser",
            "enable javascript and cookies",
            "cloudflare",
            "blocked due to abusive traffic",
            "sorry, you have been blocked",
        )
        # real signup pages also load on cloudflare-backed domains; require strong signal
        strong = (
            "attention required" in blob
            or "just a moment" in blob
            or "cf-browser-verification" in blob
            or "checking your browser" in blob
            or "blocked due to abusive traffic" in blob
            or "sorry, you have been blocked" in blob
            or ("cloudflare" in title.lower() and "sign" not in title.lower())
        )
        return strong
    except Exception:
        return False


def wait_cloudflare_passthrough(timeout=45, log_callback=None, cancel_callback=None):
    """Wait for CF challenge page to clear (JS challenge may auto-pass)."""
    deadline = time.time() + timeout
    reported = False
    while time.time() < deadline:
        raise_if_cancelled(cancel_callback)
        refresh_active_page()
        if not page_is_cloudflare_challenge(page):
            if reported and log_callback:
                log_callback("[*] Cloudflare challenge passed")
            return True
        if log_callback and not reported:
            meta = config.get("_last_proxy_exit") if isinstance(config, dict) else None
            if isinstance(meta, dict) and meta.get("exit_ip"):
                log_callback(
                    f"[!] Cloudflare challenge page detected (exit={meta.get('exit_ip')} "
                    f"{meta.get('exit_org') or ''} , not the entry gateway)，waiting for auto release..."
                )
            else:
                log_callback("[!] Cloudflare challenge page detected，waiting for auto release...")
            if sys.platform != "win32" and _linux_should_headless():
                log_callback(
                    "[!] headless browser, CF pass rate is low; consider Xvfb + GROK_REGISTER_HEADLESS=0"
                )
            reported = True
        # try click common verify buttons if present
        try:
            page.run_js(
                """
const btn = Array.from(document.querySelectorAll('button, input[type=button], input[type=submit], a'))
  .find(n => /verify|继续|human|确认|i am human/i.test((n.innerText||n.value||'')));
if (btn) btn.click();
"""
            )
        except Exception:
            pass
        sleep_with_cancel(2, cancel_callback)
    return not page_is_cloudflare_challenge(page)


def refresh_cliproxy_and_restart_browser(log_callback=None):
    """Fetch a new Cliproxy IP and restart browser with it."""
    mode = str(config.get("proxy_mode", "") or "").strip().lower()
    if mode in ("cliproxy_white", "cliproxy", "white_api", "api"):
        try:
            apply_resolved_proxy_to_config(log_callback=log_callback, fetch_live=True)
        except Exception as exc:
            if log_callback:
                log_callback(f"[!] failed to change Cliproxy IP: {exc}")
    restart_browser(log_callback=log_callback, use_proxy=True)


def open_signup_page(log_callback=None, cancel_callback=None):
    global browser, page
    raise_if_cancelled(cancel_callback)
    if browser is None:
        start_browser(log_callback=log_callback)
        if log_callback:
            log_callback("[*] Browser started")

    def _open_with_current_browser():
        global page
        try:
            page = browser.get_tab(0)
            page.get(SIGNUP_URL)
        except Exception as e:
            if log_callback:
                log_callback(f"[Debug] error opening URL: {e}")
            page = browser.new_tab(SIGNUP_URL)
        try:
            page.wait.doc_loaded()
        except Exception:
            pass
        sleep_with_cancel(2, cancel_callback)

    max_proxy_rounds = 4
    last_err = None
    for round_i in range(1, max_proxy_rounds + 1):
        raise_if_cancelled(cancel_callback)
        try:
            _open_with_current_browser()
        except Exception as e:
            last_err = e
            if browser_started_with_proxy and get_configured_proxy():
                if log_callback:
                    log_callback(f"[!] browser proxy failed to reach registration page, changing IP/retrying ({round_i}/{max_proxy_rounds}): {e}")
                refresh_cliproxy_and_restart_browser(log_callback=log_callback)
                continue
            raise

        if browser_started_with_proxy and page_has_proxy_error(page):
            if log_callback:
                log_callback("[!] browser page shows proxy error, changing proxy and retrying")
            refresh_cliproxy_and_restart_browser(log_callback=log_callback)
            continue

        if log_callback:
            log_callback(f"[*] current URL: {page.url}")

        # Cloudflare challenge: wait then rotate proxy if still blocked
        if page_is_cloudflare_challenge(page):
            ok = wait_cloudflare_passthrough(
                timeout=50, log_callback=log_callback, cancel_callback=cancel_callback
            )
            if not ok:
                if log_callback:
                    log_callback(
                        f"[!] Cloudflare still blocking (round {round_i}/{max_proxy_rounds}), changing proxy IP and retrying"
                    )
                refresh_cliproxy_and_restart_browser(log_callback=log_callback)
                continue

        try:
            click_email_signup_button(
                timeout=15,
                log_callback=log_callback,
                cancel_callback=cancel_callback,
            )
            return
        except Exception as e:
            last_err = e
            # If still CF or button missing, rotate and retry
            if page_is_cloudflare_challenge(page) or "not found" in str(e):
                if log_callback:
                    log_callback(
                        f"[!] registration page not ready: {e}; changing proxy and retrying ({round_i}/{max_proxy_rounds})"
                    )
                refresh_cliproxy_and_restart_browser(log_callback=log_callback)
                continue
            raise

    # last resort: try direct once if proxy kept failing
    if get_configured_proxy():
        if log_callback:
            log_callback("[!] proxy failed repeatedly, finally trying direct connection")
        restart_browser(log_callback=log_callback, use_proxy=False)
        _open_with_current_browser()
        wait_cloudflare_passthrough(
            timeout=40, log_callback=log_callback, cancel_callback=cancel_callback
        )
        click_email_signup_button(
            timeout=15, log_callback=log_callback, cancel_callback=cancel_callback
        )
        return

    if last_err:
        raise last_err
    raise Exception("Failed to open registration page")


def has_profile_form(log_callback=None):
    refresh_active_page()
    try:
        return bool(
            page.run_js(
                """
const givenInput = document.querySelector('input[data-testid="givenName"], input[name="givenName"], input[autocomplete="given-name"]');
const familyInput = document.querySelector('input[data-testid="familyName"], input[name="familyName"], input[autocomplete="family-name"]');
const passwordInput = document.querySelector('input[data-testid="password"], input[name="password"], input[type="password"]');
return !!(givenInput && familyInput && passwordInput);
            """
            )
        )
    except Exception:
        return False


def fill_email_and_submit(timeout=45, log_callback=None, cancel_callback=None):
    raise_if_cancelled(cancel_callback)
    email, dev_token = get_email_and_token()
    if not email or not dev_token:
        raise Exception("Failed to get mailbox")
    if log_callback:
        log_callback(f"[*] mailbox created: {email}")
    deadline = time.time() + timeout
    last_diag_time = 0
    last_reclick_time = 0
    last_snapshot = None
    while time.time() < deadline:
        raise_if_cancelled(cancel_callback)
        filled = page.run_js(
            """
const email = arguments[0];
function isVisible(node) {
    if (!node) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}
function textOf(node) {
    return [
        node.innerText,
        node.textContent,
        node.getAttribute('aria-label'),
        node.getAttribute('title'),
        node.getAttribute('placeholder'),
        node.getAttribute('data-testid'),
        node.getAttribute('name'),
        node.getAttribute('id'),
        node.getAttribute('autocomplete'),
    ].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
}
function describeInput(node) {
    return [
        `type=${node.getAttribute('type') || ''}`,
        `name=${node.getAttribute('name') || ''}`,
        `id=${node.getAttribute('id') || ''}`,
        `placeholder=${node.getAttribute('placeholder') || ''}`,
        `aria=${node.getAttribute('aria-label') || ''}`,
        `testid=${node.getAttribute('data-testid') || ''}`,
    ].join(' ').replace(/\s+/g, ' ').trim().slice(0, 160);
}
function describeAction(node) {
    return textOf(node).slice(0, 120);
}
function emailCandidates() {
    const direct = Array.from(document.querySelectorAll('input[data-testid="email"], input[name="email"], input[type="email"], input[autocomplete="email"], input[placeholder*="mail" i], input[aria-label*="mail" i]'));
    const all = Array.from(document.querySelectorAll('input, textarea'));
    for (const node of all) {
        const type = (node.getAttribute('type') || '').toLowerCase();
        if (['hidden', 'submit', 'button', 'checkbox', 'radio', 'file', 'search'].includes(type)) continue;
        const meta = textOf(node).toLowerCase();
        if (meta.includes('email') || meta.includes('e-mail') || meta.includes('mail') || meta.includes('邮箱') || meta.includes('电子邮件')) {
            direct.push(node);
        }
    }
    return Array.from(new Set(direct));
}
const visibleInputs = Array.from(document.querySelectorAll('input, textarea'))
    .filter((node) => isVisible(node) && !node.disabled && !node.readOnly)
    .map(describeInput)
    .slice(0, 8);
const visibleActions = Array.from(document.querySelectorAll('button, a, [role="button"]'))
    .filter((node) => isVisible(node) && !node.disabled && node.getAttribute('aria-disabled') !== 'true')
    .map(describeAction)
    .filter(Boolean)
    .slice(0, 10);
const input = emailCandidates().find((node) => isVisible(node) && !node.disabled && !node.readOnly) || null;
if (!input) {
    return {
        state: 'not-ready',
        url: location.href,
        title: document.title,
        inputs: visibleInputs,
        buttons: visibleActions,
    };
}
input.focus(); input.click();
const valueProto = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
const valueSetter = Object.getOwnPropertyDescriptor(valueProto, 'value')?.set;
const tracker = input._valueTracker;
if (tracker) tracker.setValue('');
if (valueSetter) valueSetter.call(input, email); else input.value = email;
input.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, data: email, inputType: 'insertText' }));
input.dispatchEvent(new InputEvent('input', { bubbles: true, data: email, inputType: 'insertText' }));
input.dispatchEvent(new Event('change', { bubbles: true }));
const inputType = (input.getAttribute('type') || '').toLowerCase();
const isValid = inputType !== 'email' || input.checkValidity();
if ((input.value || '').trim() !== email || !isValid) {
    return {
        state: 'fill-failed',
        value: input.value || '',
        valid: isValid,
        input: describeInput(input),
        url: location.href,
    };
}
input.blur();
return {
    state: 'filled',
    input: describeInput(input),
    url: location.href,
};
            """,
            email,
        )
        state = filled.get("state") if isinstance(filled, dict) else filled
        if isinstance(filled, dict):
            last_snapshot = filled
        if state == "not-ready":
            now = time.time()
            if now - last_reclick_time >= 3:
                reclicked = page.run_js(r"""
function isVisible(node) {
    if (!node) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}
function nodeText(node) {
    return [
        node.innerText,
        node.textContent,
        node.getAttribute('aria-label'),
        node.getAttribute('title'),
        node.getAttribute('href'),
    ].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
}
function scoreEntry(node) {
    const compact = nodeText(node).replace(/\s+/g, '');
    const lower = compact.toLowerCase();
    if (compact.includes('使用邮箱注册')) return 100;
    if (lower.includes('signupwithemail')) return 95;
    if (lower.includes('continuewithemail')) return 90;
    if (lower.includes('email') && (lower.includes('sign') || lower.includes('continue') || lower.includes('use') || lower.includes('with'))) return 80;
    if (lower === 'email' || lower.includes('邮箱')) return 70;
    return 0;
}
const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]'))
    .filter((node) => isVisible(node) && !node.disabled && node.getAttribute('aria-disabled') !== 'true')
    .map((node) => ({ node, score: scoreEntry(node), text: nodeText(node) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score);
if (!candidates.length) return false;
candidates[0].node.click();
return candidates[0].text || true;
                """)
                last_reclick_time = now
                if reclicked and log_callback:
                    detail = f": {reclicked}" if isinstance(reclicked, str) else ""
                    log_callback(f"[Debug] mail input didn't appear, re-triggered mail registration entry{detail}")
            if log_callback and now - last_diag_time >= 5:
                last_diag_time = now
                inputs = " | ".join((filled or {}).get("inputs", [])[:6]) if isinstance(filled, dict) else ""
                buttons = " | ".join((filled or {}).get("buttons", [])[:8]) if isinstance(filled, dict) else ""
                url = (filled or {}).get("url", page.url if page else "") if isinstance(filled, dict) else (page.url if page else "")
                log_callback(f"[Debug] waiting for mail input: url={url}; inputs={inputs or 'none'}; buttons={buttons or 'none'}")
            sleep_with_cancel(0.5, cancel_callback)
            continue
        if state != "filled":
            if log_callback:
                log_callback(f"[Debug] mail input appeared but write failed: {filled}")
            sleep_with_cancel(0.5, cancel_callback)
            continue
        sleep_with_cancel(0.8, cancel_callback)
        clicked = page.run_js(
            r"""
function isVisible(node) {
    if (!node) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}
function textOf(node) {
    return [
        node.innerText,
        node.textContent,
        node.getAttribute('aria-label'),
        node.getAttribute('title'),
        node.getAttribute('placeholder'),
        node.getAttribute('data-testid'),
        node.getAttribute('name'),
        node.getAttribute('id'),
        node.getAttribute('autocomplete'),
    ].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
}
function emailCandidates() {
    const direct = Array.from(document.querySelectorAll('input[data-testid="email"], input[name="email"], input[type="email"], input[autocomplete="email"], input[placeholder*="mail" i], input[aria-label*="mail" i]'));
    const all = Array.from(document.querySelectorAll('input, textarea'));
    for (const node of all) {
        const type = (node.getAttribute('type') || '').toLowerCase();
        if (['hidden', 'submit', 'button', 'checkbox', 'radio', 'file', 'search'].includes(type)) continue;
        const meta = textOf(node).toLowerCase();
        if (meta.includes('email') || meta.includes('e-mail') || meta.includes('mail') || meta.includes('邮箱') || meta.includes('电子邮件')) {
            direct.push(node);
        }
    }
    return Array.from(new Set(direct));
}
const input = emailCandidates().find((node) => isVisible(node) && !node.disabled && !node.readOnly) || null;
if (!input || !(input.value || '').trim()) return false;
const inputType = (input.getAttribute('type') || '').toLowerCase();
if (inputType === 'email' && !input.checkValidity()) return false;
const buttons = Array.from(document.querySelectorAll('button[type="submit"], button, [role="button"], input[type="submit"]'))
    .filter((node) => isVisible(node) && !node.disabled && node.getAttribute('aria-disabled') !== 'true');
const submitButton = buttons.find((node) => {
    const text = textOf(node).replace(/\s+/g, '');
    const lower = text.toLowerCase();
    return (
        text === '注册' ||
        text.includes('注册') ||
        text.includes('继续') ||
        text.includes('下一步') ||
        text.includes('确认') ||
        lower.includes('signup') ||
        lower.includes('sign up') ||
        lower.includes('continue') ||
        lower.includes('next') ||
        lower.includes('createaccount') ||
        lower.includes('submit')
    );
});
if (submitButton) {
    submitButton.click();
    return textOf(submitButton) || true;
}
const form = input.closest('form');
if (form) {
    if (form.requestSubmit) form.requestSubmit();
    else form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    return 'form-submit';
}
input.focus();
input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true, cancelable: true }));
input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', bubbles: true, cancelable: true }));
return 'enter';
            """
        )
        if clicked:
            if log_callback:
                detail = f" ({clicked})" if isinstance(clicked, str) else ""
                log_callback(f"[*] mail filled and submitted: {email}{detail}")
            return email, dev_token
        sleep_with_cancel(0.5, cancel_callback)
    if last_snapshot:
        inputs = " | ".join(last_snapshot.get("inputs", [])[:6])
        buttons = " | ".join(last_snapshot.get("buttons", [])[:8])
        url = last_snapshot.get("url", page.url if page else "")
        raise Exception(
            f"mail input or register button not found, last page: url={url}; inputs={inputs or 'none'}; buttons={buttons or 'none'}"
        )
    raise Exception("mail input or register button not found")


def fill_code_and_submit(email, dev_token, timeout=180, log_callback=None, cancel_callback=None):
    def _resend_code():
        page.run_js(
            r"""
const nodes = Array.from(document.querySelectorAll('button, a, [role="button"]'));
const target = nodes.find((node) => {
  const t = (node.innerText || node.textContent || '').replace(/\s+/g, '').toLowerCase();
  return t.includes('重新发送') || t.includes('resend') || t.includes('再次发送');
});
if (target && !target.disabled) { target.click(); return true; }
return false;
            """
        )

    code = get_oai_code(
        dev_token,
        email,
        log_callback=log_callback,
        cancel_callback=cancel_callback,
        resend_callback=_resend_code,
    )
    if not code:
        raise Exception("Failed to fetch verification code")
    clean_code = str(code).replace("-", "").strip()
    deadline = time.time() + timeout

    while time.time() < deadline:
        raise_if_cancelled(cancel_callback)
        filled = page.run_js(
            """
const code = String(arguments[0] || '').trim();
if (!code) return 'empty-code';

function isVisible(node) {
    if (!node) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

function setInputValue(input, value) {
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
    const tracker = input._valueTracker;
    if (tracker) tracker.setValue('');
    if (nativeSetter) nativeSetter.call(input, value);
    else input.value = value;
    input.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, data: value, inputType: 'insertText' }));
    input.dispatchEvent(new InputEvent('input', { bubbles: true, data: value, inputType: 'insertText' }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
}

const aggregate = Array.from(document.querySelectorAll(
  'input[data-input-otp=\"true\"], input[name=\"code\"], input[autocomplete=\"one-time-code\"], input[inputmode=\"numeric\"], input[inputmode=\"text\"]'
)).find((node) => isVisible(node) && !node.disabled && !node.readOnly && Number(node.maxLength || 6) > 1);

if (aggregate) {
    aggregate.focus();
    aggregate.click();
    setInputValue(aggregate, code);
    return String(aggregate.value || '').replace(/\\s+/g, '') ? 'filled-aggregate' : 'aggregate-failed';
}

const otpBoxes = Array.from(document.querySelectorAll('input')).filter((node) => {
    if (!isVisible(node) || node.disabled || node.readOnly) return false;
    const maxLength = Number(node.maxLength || 0);
    const ac = String(node.autocomplete || '').toLowerCase();
    return maxLength === 1 || ac === 'one-time-code';
});

if (otpBoxes.length >= code.length) {
    for (let i = 0; i < code.length; i += 1) {
        const ch = code[i] || '';
        const box = otpBoxes[i];
        box.focus();
        box.click();
        setInputValue(box, ch);
        box.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: ch }));
        box.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ch }));
    }
    const merged = otpBoxes.slice(0, code.length).map((x) => String(x.value || '').trim()).join('');
    return merged.length ? 'filled-boxes' : 'boxes-failed';
}

return 'not-ready';
            """,
            clean_code,
        )

        if filled == "not-ready":
            sleep_with_cancel(0.5, cancel_callback)
            continue
        if "failed" in str(filled):
            if log_callback:
                log_callback(f"[Debug] failed to fill verification code: {filled}")
            sleep_with_cancel(0.5, cancel_callback)
            continue

        clicked = page.run_js(
            r"""
function isVisible(node) {
    if (!node) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

const buttons = Array.from(document.querySelectorAll('button[type=\"submit\"], button')).filter((node) => {
    return isVisible(node) && !node.disabled && node.getAttribute('aria-disabled') !== 'true';
});

const btn = buttons.find((node) => {
    const t = (node.innerText || node.textContent || '').replace(/\\s+/g, '').toLowerCase();
    return (
        t.includes('确认邮箱') ||
        t.includes('继续') ||
        t.includes('下一步') ||
        t.includes('confirm') ||
        t.includes('continue') ||
        t.includes('next')
    );
});

if (!btn) return 'no-button';
btn.focus();
btn.click();
return 'clicked';
            """
        )

        if clicked == "clicked" or clicked == "no-button":
            if log_callback:
                log_callback(f"[*] verification code filled and submitted: {code}")
            sleep_with_cancel(1.5, cancel_callback)
            return code

        sleep_with_cancel(0.5, cancel_callback)

    raise Exception("verification code obtained, but auto-fill/submit failed")


def getTurnstileToken(log_callback=None, cancel_callback=None):
    global page
    if page is None:
        raise Exception("page not ready, cannot run Turnstile")

    try:
        page.run_js(
            "try { if (window.turnstile && typeof turnstile.reset === 'function') turnstile.reset(); } catch(e) {}"
        )
    except Exception:
        pass

    for _ in range(0, 20):
        raise_if_cancelled(cancel_callback)
        try:
            token = page.run_js(
                """
try {
  const byInput = String((document.querySelector('input[name="cf-turnstile-response"]') || {}).value || '').trim();
  if (byInput) return byInput;
  if (window.turnstile && typeof turnstile.getResponse === 'function') {
    return String(turnstile.getResponse() || '').trim();
  }
  return '';
} catch(e) { return ''; }
                """
            )
            token = str(token or "").strip()
            if len(token) >= 80:
                if log_callback:
                    log_callback(f"[*] Turnstile passed, token length={len(token)}")
                return token

            challenge_input = page.ele("@name=cf-turnstile-response")
            if challenge_input:
                wrapper = challenge_input.parent()
                iframe = None
                try:
                    iframe = wrapper.shadow_root.ele("tag:iframe")
                except Exception:
                    iframe = None
                if iframe:
                    try:
                        iframe.run_js(
                            """
window.dtp = 1;
function getRandomInt(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
let sx = getRandomInt(800, 1200);
let sy = getRandomInt(400, 700);
Object.defineProperty(MouseEvent.prototype, 'screenX', { value: sx });
Object.defineProperty(MouseEvent.prototype, 'screenY', { value: sy });
                            """
                        )
                    except Exception:
                        pass
                    try:
                        body_sr = iframe.ele("tag:body").shadow_root
                        btn = body_sr.ele("tag:input")
                        if btn:
                            btn.click()
                    except Exception:
                        pass
            else:
                # fallback: try to trigger the visible Turnstile container
                page.run_js(
                    """
const nodes = Array.from(document.querySelectorAll('div,span,iframe')).filter((n) => {
  const txt = (n.className || '') + ' ' + (n.id || '') + ' ' + (n.getAttribute?.('src') || '');
  return String(txt).toLowerCase().includes('turnstile');
});
if (nodes.length && typeof nodes[0].click === 'function') nodes[0].click();
                    """
                )
        except Exception:
            pass
        sleep_with_cancel(1, cancel_callback)

    raise Exception("Turnstile token fetch failed")


def build_profile():
    given_name_pool = [
        # Indonesia
        "Andi", "Budi", "Dimas", "Fajar", "Hendra", "Rizky", "Agus", "Yusuf",
        "Bayu", "Rafi", "Dani", "Fikri", "Arif", "Reza", "Ilham", "Farhan",
        "Putra", "Rio", "Teguh", "Wahyu",
        # Arab
        "Ahmad", "Muhammad", "Ali", "Omar", "Hassan", "Hussein", "Khalid", "Zaid",
        "Yahya", "Ibrahim", "Abdullah", "Amir", "Tariq", "Nabil", "Salman",
        "Hamza", "Bilal", "Karim", "Faisal", "Ayman",
        # Tionghoa
        "Wei", "Ming", "Jian", "Jun", "Tao", "Chen", "Bo", "Kai",
        "Hao", "Xin", "Yong", "Lei", "Tian", "Yuan", "Zhen",
        "Jie", "Bin", "Qiang", "Peng", "Hong",
        # Inggris / Barat
        "James", "John", "Michael", "William", "David", "Joseph", "Daniel", "Matthew",
        "Andrew", "Christopher", "Thomas", "Ryan", "Lucas", "Noah", "Liam",
        "Henry", "Jack", "Benjamin", "Samuel", "Oliver",
    ]
    family_name_pool = [
        # Indonesia
        "Saputra", "Pratama", "Nugroho", "Wijaya", "Santoso", "Setiawan", "Kurniawan",
        "Permana", "Hidayat", "Firmansyah", "Ramadhan", "Hakim", "Gunawan", "Siregar",
        "Nasution", "Harahap", "Simanjuntak", "Situmorang", "Manurung", "Sinaga",
        # Arab
        "Alam", "Rahman", "Hakim", "Karim", "Haddad", "Nasser", "Salim", "Farouk",
        "Mansour", "Hamdan", "Mahmoud", "Aziz", "Qureshi", "Ansari", "Khan",
        "Siddiqi", "Rashid", "Bashir", "Jabbar", "Malik",
        # Tionghoa
        "Chen", "Lin", "Wang", "Zhang", "Liu", "Yang", "Huang", "Zhao",
        "Wu", "Zhou", "Xu", "Sun", "Guo", "He", "Tang",
        "Qin", "Shi", "Fang", "Peng", "Gao",
        # Inggris / Barat
        "Smith", "Johnson", "Brown", "Taylor", "Anderson", "Thomas", "Jackson",
        "White", "Harris", "Martin", "Thompson", "Walker", "Young", "Allen",
        "King", "Wright", "Scott", "Green", "Baker", "Hall",
    ]
    # Optional user override via config (comma-separated); empty = use defaults above
    custom_given = str(config.get("profile_given_names", "") or "").strip()
    custom_family = str(config.get("profile_family_names", "") or "").strip()
    if custom_given:
        custom = [x.strip() for x in custom_given.split(",") if x.strip()]
        if custom:
            given_name_pool = custom
    if custom_family:
        custom = [x.strip() for x in custom_family.split(",") if x.strip()]
        if custom:
            family_name_pool = custom
    given_name = random.choice(given_name_pool)
    family_name = random.choice(family_name_pool)
    password = "N" + secrets.token_hex(4) + "!a7#" + secrets.token_urlsafe(6)
    return given_name, family_name, password


def fill_profile_and_submit(timeout=120, log_callback=None, cancel_callback=None):
    given_name, family_name, password = build_profile()
    deadline = time.time() + timeout
    form_filled_once = False
    wait_cf_since = None
    last_cf_retry_at = 0.0

    while time.time() < deadline:
        raise_if_cancelled(cancel_callback)
        if not form_filled_once:
            filled = page.run_js(
                """
const givenName = arguments[0];
const familyName = arguments[1];
const password = arguments[2];

function isVisible(node) {
    if (!node) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

function pickInput(selector) {
    return Array.from(document.querySelectorAll(selector)).find((node) => {
        return isVisible(node) && !node.disabled && !node.readOnly;
    }) || null;
}

function setInputValue(input, value) {
    if (!input) return false;
    input.focus();
    input.click();
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
    const tracker = input._valueTracker;
    if (tracker) tracker.setValue('');
    if (nativeSetter) nativeSetter.call(input, value);
    else input.value = value;
    input.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, data: value, inputType: 'insertText' }));
    input.dispatchEvent(new InputEvent('input', { bubbles: true, data: value, inputType: 'insertText' }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.blur();
    return String(input.value || '').trim() === String(value || '').trim();
}

const givenInput = pickInput('input[data-testid="givenName"], input[name="givenName"], input[autocomplete="given-name"], input[aria-label*="名"]');
const familyInput = pickInput('input[data-testid="familyName"], input[name="familyName"], input[autocomplete="family-name"], input[aria-label*="姓"]');
const passwordInput = pickInput('input[data-testid="password"], input[name="password"], input[type="password"], input[autocomplete="new-password"]');

if (!givenInput || !familyInput || !passwordInput) return 'not-ready';

const ok1 = setInputValue(givenInput, givenName);
const ok2 = setInputValue(familyInput, familyName);
const ok3 = setInputValue(passwordInput, password);

if (!ok1 || !ok2 || !ok3) return 'fill-failed';

const buttons = Array.from(document.querySelectorAll('button[type="submit"], button, [role="button"], input[type="submit"]')).filter((node) => {
    return isVisible(node) && !node.disabled && node.getAttribute('aria-disabled') !== 'true';
});
const submitBtn = buttons.find((node) => {
    const t = (node.innerText || node.textContent || '').replace(/\\s+/g, '').toLowerCase();
    return t.includes('完成注册') || t.includes('创建账户') || t.includes('signup') || t.includes('createaccount');
});

// must wait for Cloudflare verification to pass before submitting
const cfInput = document.querySelector('input[name="cf-turnstile-response"]');
const cfPresent = !!cfInput
  || !!document.querySelector('iframe[src*="turnstile"], div.cf-turnstile, [data-sitekey], script[src*="turnstile"]');
if (cfPresent) {
    const token = String((cfInput && cfInput.value) || '').trim();
    const solvedByToken = token.length >= 80;
    if (!solvedByToken) return 'wait-cloudflare:' + token.length;
}

if (submitBtn) {
    return 'ready-to-submit';
}
return 'filled-no-submit';
            """,
                given_name,
                family_name,
                password,
            )

            if isinstance(filled, str) and filled.startswith("wait-cloudflare"):
                form_filled_once = True
                if log_callback:
                    token_len = filled.split(":", 1)[1] if ":" in filled else "0"
                    log_callback(f"[*] profile filled, waiting for Cloudflare human verification... current token length={token_len}")
                if token_len == "0":
                    pause_seconds = random.uniform(1, 3)
                    if log_callback:
                        log_callback(f"[*] Cloudflare token empty, pausing {pause_seconds:.1f}s before checking again")
                    sleep_with_cancel(pause_seconds, cancel_callback)
                now = time.time()
                if wait_cf_since is None:
                    wait_cf_since = now
                # auto-reuse Turnstile component when stuck
                if now - wait_cf_since >= 12 and now - last_cf_retry_at >= 8:
                    if log_callback:
                        log_callback("[*] Cloudflare verification stuck, starting second Turnstile reuse...")
                    try:
                        token = getTurnstileToken(log_callback=log_callback, cancel_callback=cancel_callback)
                        if token:
                            synced = page.run_js(
                                """
const token = String(arguments[0] || '').trim();
const cfInput = document.querySelector('input[name="cf-turnstile-response"]');
if (!cfInput || !token) return false;
const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
if (nativeSetter) nativeSetter.call(cfInput, token);
else cfInput.value = token;
cfInput.dispatchEvent(new Event('input', { bubbles: true }));
cfInput.dispatchEvent(new Event('change', { bubbles: true }));
return String(cfInput.value || '').trim().length;
                                """,
                                token,
                            )
                            if log_callback:
                                log_callback(f"[*] Turnstile reuse completed, backfilled length={synced}")
                    except Exception as cf_exc:
                        if log_callback:
                            log_callback(f"[Debug] Turnstile reuse failed: {cf_exc}")
                    last_cf_retry_at = now
                sleep_with_cancel(0.8, cancel_callback)
                continue

            if filled in ("ready-to-submit", "filled-no-submit"):
                form_filled_once = True
            elif filled == "fill-failed" and log_callback:
                log_callback("[Debug] profile input failed, retrying...")
                sleep_with_cancel(0.5, cancel_callback)
                continue
            elif filled == "not-ready":
                sleep_with_cancel(0.5, cancel_callback)
                continue

        submit_state = page.run_js(
            r"""
function isVisible(node) {
    if (!node) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

const cfInput = document.querySelector('input[name="cf-turnstile-response"]');
const cfPresent = !!cfInput
  || !!document.querySelector('iframe[src*="turnstile"], div.cf-turnstile, [data-sitekey], script[src*="turnstile"]');
if (cfPresent) {
    const token = String((cfInput && cfInput.value) || '').trim();
    const solvedByToken = token.length >= 80;
    if (!solvedByToken) return 'wait-cloudflare:' + token.length;
}

function buttonText(node) {
    return [
        node.innerText,
        node.textContent,
        node.getAttribute('value'),
        node.getAttribute('aria-label'),
        node.getAttribute('title'),
    ].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
}
const buttons = Array.from(document.querySelectorAll('button[type="submit"], button, [role="button"], input[type="submit"]')).filter((node) => {
    return isVisible(node) && !node.disabled && node.getAttribute('aria-disabled') !== 'true';
});
const submitBtn = buttons.find((node) => {
    const t = buttonText(node).replace(/\s+/g, '').toLowerCase();
    return t.includes('完成注册') || t.includes('创建账户') || t.includes('signup') || t.includes('createaccount');
});
if (!submitBtn) {
    const visibleTexts = buttons.map(buttonText).filter(Boolean).slice(0, 8).join(' | ');
    return 'no-submit-button:' + visibleTexts;
}
submitBtn.focus();
submitBtn.click();
return 'submitted';
            """
        )

        if isinstance(submit_state, str) and submit_state.startswith("wait-cloudflare"):
            if log_callback:
                token_len = submit_state.split(":", 1)[1] if ":" in submit_state else "0"
                log_callback(f"[*] waiting for Cloudflare human verification before submitting... current token length={token_len}")
            now = time.time()
            if wait_cf_since is None:
                wait_cf_since = now
            if now - wait_cf_since >= 12 and now - last_cf_retry_at >= 8:
                if log_callback:
                    log_callback("[*] still stuck before submit, reusing Turnstile again...")
                try:
                    token = getTurnstileToken(log_callback=log_callback, cancel_callback=cancel_callback)
                    if token:
                        synced = page.run_js(
                            """
const token = String(arguments[0] || '').trim();
const cfInput = document.querySelector('input[name="cf-turnstile-response"]');
if (!cfInput || !token) return false;
const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
if (nativeSetter) nativeSetter.call(cfInput, token);
else cfInput.value = token;
cfInput.dispatchEvent(new Event('input', { bubbles: true }));
cfInput.dispatchEvent(new Event('change', { bubbles: true }));
return String(cfInput.value || '').trim().length;
                            """,
                            token,
                        )
                        if log_callback:
                            log_callback(f"[*] Turnstile reuse completed, backfilled length={synced}")
                except Exception as cf_exc:
                    if log_callback:
                        log_callback(f"[Debug] Turnstile reuse failed: {cf_exc}")
                last_cf_retry_at = now
            sleep_with_cancel(0.8, cancel_callback)
            continue

        if submit_state == "submitted":
            if log_callback:
                log_callback(f"[*] profile filled and submitted: {given_name} {family_name}")
            return {"given_name": given_name, "family_name": family_name, "password": password}
        wait_cf_since = None
        if isinstance(submit_state, str) and submit_state.startswith("no-submit-button") and log_callback:
            visible_buttons = submit_state.split(":", 1)[1] if ":" in submit_state else ""
            suffix = f" visible buttons: {visible_buttons}" if visible_buttons else ""
            log_callback(f"[Debug] submit button not found, continuing to wait for page to settle...{suffix}")

        sleep_with_cancel(0.5, cancel_callback)

    raise Exception("final registration page profile fill failed")


def wait_for_sso_cookie(timeout=120, log_callback=None, cancel_callback=None):
    deadline = time.time() + timeout
    last_seen_names = set()
    last_submit_retry = 0.0
    last_cf_retry_at = 0.0
    final_no_submit_state = ""
    final_no_submit_since = None
    final_no_submit_timeout = 25

    while time.time() < deadline:
        raise_if_cancelled(cancel_callback)
        try:
            refresh_active_page()
            if page is None:
                sleep_with_cancel(1, cancel_callback)
                continue

            # when still on the "complete signup" page, if Cloudflare passed, periodically retry clicking submit
            now = time.time()
            if now - last_submit_retry >= 2.5:
                retried = page.run_js(
                    r"""
function isVisible(node) {
    if (!node) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}
const titleHit = !!Array.from(document.querySelectorAll('h1,h2,div,span')).find((el) => {
    const t = (el.textContent || '').replace(/\s+/g, '');
    const lower = t.toLowerCase();
    return t.includes('完成注册') || lower.includes('completeyoursignup') || lower.includes('completesignup');
});
if (!titleHit) return 'not-final-page';

const cfInput = document.querySelector('input[name="cf-turnstile-response"]');
const cfPresent = !!cfInput
  || !!document.querySelector('iframe[src*="turnstile"], div.cf-turnstile, [data-sitekey], script[src*="turnstile"]');
if (cfPresent) {
    const token = String((cfInput && cfInput.value) || '').trim();
    const solved = token.length >= 80;
    if (!solved) return 'final-page-wait-cf:' + token.length;
}

function buttonText(node) {
    return [
        node.innerText,
        node.textContent,
        node.getAttribute('value'),
        node.getAttribute('aria-label'),
        node.getAttribute('title'),
    ].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
}
const buttons = Array.from(document.querySelectorAll('button[type="submit"], button, [role="button"], input[type="submit"]')).filter((node) => {
    return isVisible(node) && !node.disabled && node.getAttribute('aria-disabled') !== 'true';
});
const submitBtn = buttons.find((node) => {
    const t = buttonText(node).replace(/\s+/g, '').toLowerCase();
    return t.includes('完成注册') || t.includes('创建账户') || t.includes('signup') || t.includes('createaccount');
});
if (!submitBtn) {
    const visibleTexts = buttons.map(buttonText).filter(Boolean).slice(0, 8).join(' | ');
    return 'final-page-no-submit:' + visibleTexts;
}
submitBtn.focus();
submitBtn.click();
return 'final-page-clicked-submit';
                    """
                )
                last_submit_retry = now
                if log_callback and (retried == "final-page-clicked-submit" or (isinstance(retried, str) and retried.startswith("final-page-no-submit"))):
                    log_callback(f"[Debug] final page status: {retried}")
                if isinstance(retried, str) and retried.startswith("final-page-no-submit"):
                    if retried != final_no_submit_state:
                        final_no_submit_state = retried
                        final_no_submit_since = now
                    elif final_no_submit_since and now - final_no_submit_since >= final_no_submit_timeout:
                        raise AccountRetryNeeded(
                            f"final registration page state {final_no_submit_timeout}s without change and no submit button, retrying current account: {retried}"
                        )
                else:
                    final_no_submit_state = ""
                    final_no_submit_since = None
                if log_callback and isinstance(retried, str) and retried.startswith("final-page-wait-cf"):
                    token_len = retried.split(":", 1)[1] if ":" in retried else "0"
                    log_callback(f"[Debug] final page status: final-page-wait-cf, token length={token_len}")
                    if now - last_cf_retry_at >= 10:
                        if log_callback:
                            log_callback("[*] final page Cloudflare stuck, auto-reusing Turnstile...")
                        try:
                            token = getTurnstileToken(log_callback=log_callback, cancel_callback=cancel_callback)
                            if token:
                                synced = page.run_js(
                                    """
const token = String(arguments[0] || '').trim();
const cfInput = document.querySelector('input[name="cf-turnstile-response"]');
if (!cfInput || !token) return false;
const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
if (nativeSetter) nativeSetter.call(cfInput, token);
else cfInput.value = token;
cfInput.dispatchEvent(new Event('input', { bubbles: true }));
cfInput.dispatchEvent(new Event('change', { bubbles: true }));
return String(cfInput.value || '').trim().length;
                                    """,
                                    token,
                                )
                                if log_callback:
                                    log_callback(f"[*] final page Turnstile reuse completed, backfilled length={synced}")
                        except Exception as cf_exc:
                            if log_callback:
                                log_callback(f"[Debug] final page Turnstile reuse failed: {cf_exc}")
                        last_cf_retry_at = now

            cookies = page.cookies(all_domains=True, all_info=True) or []
            for item in cookies:
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip()
                    value = str(item.get("value", "")).strip()
                else:
                    name = str(getattr(item, "name", "")).strip()
                    value = str(getattr(item, "value", "")).strip()

                if name:
                    last_seen_names.add(name)

                if name == "sso" and value:
                    if log_callback:
                        log_callback("[*] obtained sso cookie")
                    return value
        except PageDisconnectedError:
            refresh_active_page()
        except AccountRetryNeeded:
            raise
        except Exception:
            pass

        sleep_with_cancel(1, cancel_callback)

    raise Exception(
        f"Timed out waiting for sso cookie. Cookies seen: {sorted(last_seen_names)}"
    )


class GrokRegisterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Grok Registrar")
        self.root.geometry("1120x900")
        self.root.minsize(960, 700)
        self.is_running = False
        self.batch_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.results = []
        self.stop_requested = False
        self.ui_queue = queue.Queue()
        self.accounts_output_file = ""
        self.setup_ui()

    def setup_ui(self):
        load_config()
        main_frame = tk.Frame(self.root, bg=UI_BG, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(3, weight=1)

        config_frame = tk.LabelFrame(
            main_frame,
            text="Config",
            bg=UI_PANEL_BG,
            fg=UI_FG,
            padx=10,
            pady=10,
            relief=tk.GROOVE,
            borderwidth=1,
        )
        config_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        config_frame.grid_columnconfigure(1, weight=1, minsize=260)
        config_frame.grid_columnconfigure(3, weight=1, minsize=260)

        def add_label(row, column, text):
            tk_label(config_frame, text=text, bg=UI_PANEL_BG).grid(
                row=row,
                column=column,
                sticky=tk.W,
                padx=(0, 6),
                pady=3,
            )

        def add_field(widget, row, column, columnspan=1, sticky=tk.EW):
            widget.grid(
                row=row,
                column=column,
                columnspan=columnspan,
                sticky=sticky,
                padx=(0, 14),
                pady=3,
            )

        add_label(0, 0, "Mail provider:")
        self.email_provider_var = tk.StringVar(value=config.get("email_provider", "litensi"))
        self.email_provider_combo = tk_option_menu(config_frame, self.email_provider_var, ["litensi", "cloudflare"], width=12)
        add_field(self.email_provider_combo, 0, 1, sticky=tk.W)

        add_label(0, 2, "Register count:")
        self.count_var = tk.StringVar(value=str(config.get("register_count", 1)))
        self.count_spinbox = tk.Spinbox(
            config_frame,
            from_=1,
            to=2500,
            width=8,
            textvariable=self.count_var,
            bg=UI_ENTRY_BG,
            fg=UI_FG,
            insertbackground=UI_FG,
            buttonbackground=UI_BUTTON_BG,
            disabledbackground="#2f2f2f",
            disabledforeground=UI_MUTED_FG,
            relief=tk.SOLID,
        )
        add_field(self.count_spinbox, 0, 3, sticky=tk.W)

        add_label(1, 0, "Register options:")
        self.nsfw_var = tk.BooleanVar(value=config.get("enable_nsfw", True))
        self.nsfw_check = tk_checkbutton(config_frame, text="Enable NSFW after registration", variable=self.nsfw_var)
        add_field(self.nsfw_check, 1, 1, sticky=tk.W)

        add_label(1, 2, "Proxy (optional):")
        self.proxy_var = tk.StringVar(value=config.get("proxy", ""))
        self.proxy_entry = tk_entry(config_frame, textvariable=self.proxy_var, width=34)
        add_field(self.proxy_entry, 1, 3)

        add_label(2, 2, "Cloudflare auth mode:")
        self.cloudflare_auth_mode_var = tk.StringVar(value=config.get("cloudflare_auth_mode", "none"))
        self.cloudflare_auth_mode_combo = tk_option_menu(
            config_frame, self.cloudflare_auth_mode_var, ["query-key", "bearer", "x-api-key", "x-admin-auth", "none"], width=12
        )
        add_field(self.cloudflare_auth_mode_combo, 2, 3, sticky=tk.W)

        add_label(3, 0, "Cloudflare API Base:")
        self.cloudflare_api_base_var = tk.StringVar(value=config.get("cloudflare_api_base", ""))
        self.cloudflare_api_base_entry = tk_entry(config_frame, textvariable=self.cloudflare_api_base_var, width=72)
        add_field(self.cloudflare_api_base_entry, 3, 1, columnspan=3)

        add_label(4, 0, "Cloudflare API Key:")
        self.cloudflare_api_key_var = tk.StringVar(value=config.get("cloudflare_api_key", ""))
        self.cloudflare_api_key_entry = tk_entry(config_frame, textvariable=self.cloudflare_api_key_var, width=34)
        add_field(self.cloudflare_api_key_entry, 4, 1)

        add_label(4, 2, "CF paths:")
        self.cloudflare_paths_var = tk.StringVar(
            value=",".join(
                [
                    config.get("cloudflare_path_domains", "/api/domains"),
                    config.get("cloudflare_path_accounts", "/api/new_address"),
                    config.get("cloudflare_path_token", "/api/token"),
                    config.get("cloudflare_path_messages", "/api/mails"),
                ]
            )
        )
        self.cloudflare_paths_entry = tk_entry(config_frame, textvariable=self.cloudflare_paths_var, width=34)
        add_field(self.cloudflare_paths_entry, 4, 3)

        add_label(10, 0, "Litensi API ID:")
        self.litensi_api_id_var = tk.StringVar(value=config.get("litensi_api_id", ""))
        self.litensi_api_id_entry = tk_entry(config_frame, textvariable=self.litensi_api_id_var, width=34)
        add_field(self.litensi_api_id_entry, 10, 1)

        add_label(10, 2, "Litensi API Key:")
        self.litensi_api_key_var = tk.StringVar(value=config.get("litensi_api_key", ""))
        self.litensi_api_key_entry = tk_entry(config_frame, textvariable=self.litensi_api_key_var, width=34)
        add_field(self.litensi_api_key_entry, 10, 3)

        add_label(11, 0, "Litensi zone:")
        self.litensi_zone_var = tk.StringVar(value=config.get("litensi_zone", ""))
        self.litensi_zone_entry = tk_entry(config_frame, textvariable=self.litensi_zone_var, width=34)
        add_field(self.litensi_zone_entry, 11, 1)

        add_label(11, 2, "Litensi site:")
        self.litensi_site_var = tk.StringVar(value=config.get("litensi_site", ""))
        self.litensi_site_entry = tk_entry(config_frame, textvariable=self.litensi_site_var, width=34)
        add_field(self.litensi_site_entry, 11, 3)

        self.litensi_prices_btn = tk_button(config_frame, text="Check Litensi prices", command=self.check_litensi_prices)
        add_field(self.litensi_prices_btn, 12, 1, sticky=tk.W)

        add_label(13, 0, "9Router push:")

        self.nine_router_enabled_var = tk.BooleanVar(value=bool(config.get("nine_router_enabled", False)))
        self.nine_router_enabled_check = tk_checkbutton(config_frame, text="Enabled", variable=self.nine_router_enabled_var)
        add_field(self.nine_router_enabled_check, 13, 1, sticky=tk.W)

        add_label(13, 2, "9Router base:")
        self.nine_router_base_var = tk.StringVar(value=config.get("nine_router_base", ""))
        self.nine_router_base_entry = tk_entry(config_frame, textvariable=self.nine_router_base_var, width=34)
        add_field(self.nine_router_base_entry, 13, 3)

        add_label(14, 0, "9Router password:")
        self.nine_router_password_var = tk.StringVar(value=config.get("nine_router_password", ""))
        self.nine_router_password_entry = tk_entry(config_frame, textvariable=self.nine_router_password_var, width=34)
        add_field(self.nine_router_password_entry, 14, 1)

        self.nine_router_test_btn = tk_button(config_frame, text="Test 9Router connection", command=self.test_nine_router)
        add_field(self.nine_router_test_btn, 14, 3, sticky=tk.W)

        btn_frame = tk.Frame(main_frame, bg=UI_BG)
        btn_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 6))
        self.start_btn = tk_button(btn_frame, text="Start", command=self.start_registration)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = tk_button(btn_frame, text="Stop", command=self.stop_registration, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.clear_btn = tk_button(btn_frame, text="Clear Log", command=self.clear_log)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        status_frame = tk.Frame(main_frame, bg=UI_BG)
        status_frame.grid(row=2, column=0, sticky=tk.EW, pady=(0, 6))
        self.status_var = tk.StringVar(value="Ready")
        tk_label(status_frame, text="Status: ").pack(side=tk.LEFT)
        self.status_label = tk.Label(status_frame, textvariable=self.status_var, bg=UI_BG, fg="green")
        self.status_label.pack(side=tk.LEFT)
        self.stats_var = tk.StringVar(value="OK: 0 | Fail: 0")
        tk.Label(status_frame, textvariable=self.stats_var, bg=UI_BG, fg=UI_FG).pack(side=tk.RIGHT)
        log_frame = tk.LabelFrame(
            main_frame,
            text="Log",
            bg=UI_PANEL_BG,
            fg=UI_FG,
            padx=5,
            pady=5,
            relief=tk.GROOVE,
            borderwidth=1,
        )
        log_frame.grid(row=3, column=0, sticky=tk.NSEW)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=18,
            width=60,
            bg="#111111",
            fg="#f5f5f5",
            insertbackground="#f5f5f5",
            selectbackground="#345a8a",
            selectforeground="#ffffff",
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground="#555555",
        )
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW)
        self.log("[*] GUI ready, config loaded")
        self.log(f"[*] Current mail provider: {self.email_provider_var.get()} | Register count: {self.count_var.get()}")

    def log(self, message):
        timestamp = now_beijing("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        print(line, flush=True)
        self.log_text.insert(tk.END, f"{line}\n")
        self.log_text.see(tk.END)

    def clear_log(self):
        self.log_text.delete(1.0, tk.END)

    def check_litensi_prices(self):
        api_id = self.litensi_api_id_var.get().strip()
        api_key = self.litensi_api_key_var.get().strip()
        site = self.litensi_site_var.get().strip()
        self.log(f"[*] Checking Litensi prices for site: {site or '(empty)'}")
        try:
            prices = litensi_get_prices(api_id=api_id, api_key=api_key, site=site)
        except Exception as exc:
            self.log(f"[!] Litensi prices check failed: {exc}")
            return
        in_stock = [p for p in prices if p.get("stock", 0) > 0]
        if not in_stock:
            self.log("[!] No Litensi zones in stock for this site")
            return
        in_stock.sort(key=lambda p: p.get("price", 0))
        for p in in_stock[:20]:
            self.log(f"[*] zone={p.get('zone')} price={p.get('price')} stock={p.get('stock')}")
        try:
            pick = litensi_pick_zone(api_id, api_key, site)
        except Exception as exc:
            self.log(f"[!] Litensi pick failed: {exc}")
            return
        self.litensi_zone_var.set(pick)
        self.log(f"[+] Auto-selected in-stock zone: {pick}")

    def test_nine_router(self):
        config["nine_router_base"] = self.nine_router_base_var.get().strip()
        config["nine_router_password"] = self.nine_router_password_var.get().strip()
        self.log(f"[*] Testing 9router connection: {config['nine_router_base'] or '(empty)'}")
        ok, msg = test_nine_router_connection(log_callback=self.log)
        self.log(f"{'[+]' if ok else '[!]'} 9router: {msg}")

    def update_stats(self):
        self.stats_var.set(f"OK: {self.success_count} | Fail: {self.fail_count}")

    def _set_running_ui(self, running):
        self.is_running = running
        self.start_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if running else tk.DISABLED)
        self.status_var.set("Running..." if running else "Ready")
        self.status_label.config(foreground="blue" if running else "green")

    def should_stop(self):
        return self.stop_requested or not self.is_running

    def start_registration(self):
        if self.is_running:
            self.log("[!] A task is already running")
            return

        config["email_provider"] = self.email_provider_var.get().strip() or "litensi"
        config["enable_nsfw"] = bool(self.nsfw_var.get())
        config["proxy"] = self.proxy_var.get().strip()
        config["cloudflare_api_base"] = self.cloudflare_api_base_var.get().strip()
        config["cloudflare_api_key"] = self.cloudflare_api_key_var.get().strip()
        config["cloudflare_auth_mode"] = self.cloudflare_auth_mode_var.get().strip() or "none"
        config["litensi_api_id"] = self.litensi_api_id_var.get().strip()
        config["litensi_api_key"] = self.litensi_api_key_var.get().strip()
        config["litensi_zone"] = self.litensi_zone_var.get().strip()
        config["litensi_site"] = self.litensi_site_var.get().strip()
        config["nine_router_enabled"] = bool(self.nine_router_enabled_var.get())
        config["nine_router_base"] = self.nine_router_base_var.get().strip()
        config["nine_router_password"] = self.nine_router_password_var.get().strip()
        raw_paths = [x.strip() for x in self.cloudflare_paths_var.get().split(",") if x.strip()]
        if len(raw_paths) >= 4:
            config["cloudflare_path_domains"] = raw_paths[0] if raw_paths[0].startswith("/") else ("/" + raw_paths[0])
            config["cloudflare_path_accounts"] = raw_paths[1] if raw_paths[1].startswith("/") else ("/" + raw_paths[1])
            config["cloudflare_path_token"] = raw_paths[2] if raw_paths[2].startswith("/") else ("/" + raw_paths[2])
            config["cloudflare_path_messages"] = raw_paths[3] if raw_paths[3].startswith("/") else ("/" + raw_paths[3])
        save_config()
        if config["email_provider"] == "cloudflare" and not config["cloudflare_api_base"]:
            self.log("[!] Cloudflare mode requires filling in Cloudflare API Base")
            return
        if config["email_provider"] == "litensi" and not (config["litensi_api_id"] and config["litensi_api_key"]):
            self.log("[!] Litensi mode requires filling in API ID and API Key")
            return
        try:
            count = int(self.count_var.get())
        except Exception:
            self.log("[!] Invalid register count")
            return
        config["register_count"] = count
        save_config()
        self.stop_requested = False
        self.success_count = 0
        self.fail_count = 0
        self.results = []
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.accounts_output_file = os.path.join(
            os.path.dirname(__file__), f"accounts_{now}.txt"
        )
        self.update_stats()
        self._set_running_ui(True)
        self.log(f"[*] Config saved, starting. Target count: {count}")
        self.log(f"[*] Successful accounts will be saved to: {self.accounts_output_file}")
        threading.Thread(
            target=self.run_registration,
            args=(count,),
            daemon=True,
        ).start()

    def stop_registration(self):
        self.stop_requested = True
        self.log("[!] User stopped registration")

    def run_registration(self, count):
        try:
            start_browser(log_callback=self.log)
            self.log("[*] Browser started")
            i = 0
            retry_count_for_slot = 0
            max_slot_retry = 3
            while i < count:
                if self.should_stop():
                    break
                self.log(f"--- Starting account {i + 1}/{count} ---")
                try:
                    email = ""
                    dev_token = ""
                    code = ""
                    mail_ok = False
                    max_mail_retry = 3
                    for mail_try in range(1, max_mail_retry + 1):
                        self.log(f"[*] 1. Open registration page (try {mail_try}/{max_mail_retry})")
                        open_signup_page(
                            log_callback=self.log, cancel_callback=self.should_stop
                        )
                        self.log("[*] 2. Create mail address and submit")
                        email, dev_token = fill_email_and_submit(
                            log_callback=self.log, cancel_callback=self.should_stop
                        )
                        self.log(f"[*] Mail: {email}")
                        self.log("[Debug] Mail credential acquired (value hidden)")
                        try:
                            with open(
                                os.path.join(os.path.dirname(__file__), "mail_credentials.txt"),
                                "a",
                                encoding="utf-8",
                            ) as f:
                                f.write(f"{email}\t{dev_token}\n")
                        except Exception:
                            pass
                        self.log("[*] 3. Fetch verification code")
                        try:
                            code = fill_code_and_submit(
                                email,
                                dev_token,
                                log_callback=self.log,
                                cancel_callback=self.should_stop,
                            )
                            mail_ok = True
                            break
                        except Exception as mail_exc:
                            msg = str(mail_exc)
                            if (("verification code" in msg.lower())) and mail_try < max_mail_retry:
                                self.log(f"[!] No code received for this mailbox, switching to a new mailbox and retrying: {msg}")
                                restart_browser(log_callback=self.log)
                                sleep_with_cancel(1, self.should_stop)
                                continue
                            raise

                    if not mail_ok:
                        raise Exception("Verification code stage failed, max retries reached")
                    self.log(f"[*] verification code: {code}")
                    self.log("[*] 4. Fill profile")
                    profile = fill_profile_and_submit(
                        log_callback=self.log, cancel_callback=self.should_stop
                    )
                    self.log(f"[*] Profile filled: {profile.get('given_name')} {profile.get('family_name')}")
                    self.log("[*] 5. Wait for sso cookie")
                    sso = wait_for_sso_cookie(
                        log_callback=self.log, cancel_callback=self.should_stop
                    )
                    self.results.append({"email": email, "sso": sso, "profile": profile})
                    try:
                        line = f"{email}----{profile.get('password','')}----{sso}\n"
                        with open(self.accounts_output_file, "a", encoding="utf-8") as f:
                            f.write(line)
                    except Exception as file_exc:
                        self.log(f"[Debug] Failed to save account file: {file_exc}")
                    # NSFW / CPA: background by default, doesn't block next account (functionality still runs)
                    schedule_post_registration(
                        email,
                        str(profile.get("password") or ""),
                        sso,
                        page=page,
                        log_callback=self.log,
                    )
                    self.success_count += 1
                    retry_count_for_slot = 0
                    i += 1
                    self.log(f"[+] Registration success: {email}")
                    if (
                        self.success_count > 0
                        and self.success_count % MEMORY_CLEANUP_INTERVAL == 0
                        and i < count
                    ):
                        cleanup_runtime_memory(
                            log_callback=self.log,
                            reason=f"registered {self.success_count} accounts, running periodic cleanup",
                        )
                except RegistrationCancelled:
                    self.log("[!] Registration stopped by user")
                    break
                except AccountRetryNeeded as exc:
                    retry_count_for_slot += 1
                    if retry_count_for_slot <= max_slot_retry:
                        self.log(
                            f"[!] Current account flow stuck, retrying {retry_count_for_slot}/{max_slot_retry}: {exc}"
                        )
                    else:
                        self.fail_count += 1
                        self.log(
                            f"[-] Current account reached max retries, skipping: {exc}"
                        )
                        retry_count_for_slot = 0
                        i += 1
                except Exception as exc:
                    self.fail_count += 1
                    retry_count_for_slot = 0
                    i += 1
                    self.log(f"[-] Registration failed: {exc}")
                finally:
                    self.update_stats()
                    if self.should_stop():
                        break
                    if browser is None:
                        start_browser(log_callback=self.log)
                    else:
                        restart_browser(log_callback=self.log)
                    sleep_with_cancel(1, self.should_stop)
        except Exception as exc:
            self.log(f"[!] Task exception: {exc}")
        finally:
            # wait for background CPA/NSFW to finish before closing the browser process env
            wait_post_success_queue(timeout=300, log_callback=self.log)
            stop_browser()
            self._set_running_ui(False)
            self.log("[*] Task finished")


class CliStopController:
    def __init__(self):
        self.stop_requested = False

    def should_stop(self):
        return self.stop_requested

    def stop(self):
        self.stop_requested = True


def cli_log(message):
    timestamp = now_beijing("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def run_registration_job(count, log_callback=None, controller=None):
    """Non-interactive registration loop for CLI and Web.

    Returns dict: success, fail, accounts_file, stopped.
    """
    log = log_callback or cli_log
    if controller is None:
        controller = CliStopController()

    reg_mode = str(config.get("register_mode") or "browser").strip().lower()
    if reg_mode in ("hybrid", "protocol_hybrid", "mixed"):
        log(f"[*] Register mode: hybrid (protocol + short browser)")
        try:
            from hybrid_register import run_hybrid_registration_job

            return run_hybrid_registration_job(
                count, log_callback=log, controller=controller
            )
        except Exception as hybrid_exc:
            log(f"[!] Hybrid mode start failed, falling back to full browser: {hybrid_exc}")

    success_count = 0
    fail_count = 0
    retry_count_for_slot = 0
    max_slot_retry = 3
    accounts_output_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"accounts_{now_beijing('%Y%m%d_%H%M%S')}.txt",
    )
    log(f"[*] Task started, target count: {count}")
    log(f"[*] Register mode: browser (full browser)")
    log(f"[*] Successful accounts will be saved to: {accounts_output_file}")
    mode = str(config.get("proxy_mode", "direct") or "direct")
    try:
        resolved_proxy = apply_resolved_proxy_to_config(log_callback=log, fetch_live=True)
    except Exception as proxy_exc:
        log(f"[!] Failed to fetch/resolve proxy: {proxy_exc}")
        raise
    if resolved_proxy:
        # mask password in log
        safe = resolved_proxy
        try:
            parsed = urllib.parse.urlparse(resolved_proxy)
            if parsed.password:
                safe = resolved_proxy.replace(":" + parsed.password + "@", ":****@")
        except Exception:
            pass
        log(f"[*] Proxy mode: {mode} | {safe}")
        if mode in ("whitelist", "group", "proxy_group"):
            log(
                f"[*] proxy group: country={config.get('proxy_country','')} "
                f" delimiter={config.get('proxy_delimiter','-')!r} "
                f" duration={config.get('proxy_duration','120')}min"
            )
        if mode in ("cliproxy_white", "cliproxy", "white_api", "api"):
            log(
                f"[*] Cliproxy whitelist: region={config.get('proxy_country','US')} "
                f"time={config.get('proxy_duration','10')}m"
            )
    else:
        log(f"[*] Proxy mode: {mode or 'direct'} (direct)")
    try:
        start_browser(log_callback=log)
        log("[*] Browser started")
        i = 0
        while i < count:
            if controller.should_stop():
                break
            log(f"--- Starting account {i + 1}/{count} ---")
            try:
                email = ""
                dev_token = ""
                code = ""
                mail_ok = False
                max_mail_retry = 3
                for mail_try in range(1, max_mail_retry + 1):
                    log(f"[*] 1. Open registration page (try {mail_try}/{max_mail_retry})")
                    open_signup_page(
                        log_callback=log, cancel_callback=controller.should_stop
                    )
                    log("[*] 2. Create mail address and submit")
                    email, dev_token = fill_email_and_submit(
                        log_callback=log, cancel_callback=controller.should_stop
                    )
                    log(f"[*] Mail: {email}")
                    log("[Debug] Mail credential acquired (value hidden)")
                    try:
                        with open(
                            os.path.join(
                                os.path.dirname(os.path.abspath(__file__)),
                                "mail_credentials.txt",
                            ),
                            "a",
                            encoding="utf-8",
                        ) as f:
                            f.write(f"{email}\t{dev_token}\n")
                    except Exception:
                        pass
                    log("[*] 3. Fetch verification code")
                    try:
                        code = fill_code_and_submit(
                            email,
                            dev_token,
                            log_callback=log,
                            cancel_callback=controller.should_stop,
                        )
                        mail_ok = True
                        break
                    except Exception as mail_exc:
                        msg = str(mail_exc)
                        if (("verification code" in msg.lower())) and mail_try < max_mail_retry:
                            log(f"[!] No code received for this mailbox, switching to a new mailbox and retrying: {msg}")
                            restart_browser(log_callback=log)
                            sleep_with_cancel(1, controller.should_stop)
                            continue
                        raise

                if not mail_ok:
                    raise Exception("Verification code stage failed, max retries reached")
                log(f"[*] verification code: {code}")
                log("[*] 4. Fill profile")
                profile = fill_profile_and_submit(
                    log_callback=log, cancel_callback=controller.should_stop
                )
                log(f"[*] Profile filled: {profile.get('given_name')} {profile.get('family_name')}")
                log("[*] 5. Wait for sso cookie")
                sso = wait_for_sso_cookie(
                    log_callback=log, cancel_callback=controller.should_stop
                )
                try:
                    line = f"{email}----{profile.get('password','')}----{sso}\n"
                    with open(accounts_output_file, "a", encoding="utf-8") as f:
                        f.write(line)
                except Exception as file_exc:
                    log(f"[Debug] Failed to save account file: {file_exc}")
                # NSFW / CPA: background write by default, functionality kept, doesn't block next account
                global page
                schedule_post_registration(
                    email,
                    str(profile.get("password") or ""),
                    sso,
                    page=page,
                    log_callback=log,
                )
                success_count += 1
                retry_count_for_slot = 0
                i += 1
                log(f"[+] Registration success: {email}")
                log(f"[*] Current stats: OK {success_count} | Fail {fail_count}")
                if success_count > 0 and success_count % MEMORY_CLEANUP_INTERVAL == 0 and i < count:
                    cleanup_runtime_memory(
                        log_callback=log,
                        reason=f"registered {success_count} accounts, running periodic cleanup",
                    )
            except RegistrationCancelled:
                log("[!] Registration stopped")
                break
            except AccountRetryNeeded as exc:
                retry_count_for_slot += 1
                if retry_count_for_slot <= max_slot_retry:
                    log(
                        f"[!] Current account flow stuck, retrying {retry_count_for_slot}/{max_slot_retry}: {exc}"
                    )
                else:
                    fail_count += 1
                    retry_count_for_slot = 0
                    i += 1
                    log(f"[-] Current account reached max retries, skipping: {exc}")
            except Exception as exc:
                fail_count += 1
                retry_count_for_slot = 0
                i += 1
                log(f"[-] Registration failed: {exc}")
            finally:
                if controller.should_stop():
                    break
                if browser is None:
                    start_browser(log_callback=log)
                else:
                    restart_browser(log_callback=log)
                sleep_with_cancel(1, controller.should_stop)
    except KeyboardInterrupt:
        controller.stop()
        log("[!] Received Ctrl+C, stopping and cleaning up")
    except Exception as exc:
        log(f"[!] Task exception: {exc}")
    finally:
        # finish background pool/CPA/NSFW before closing browser (independent of page)
        wait_post_success_queue(timeout=300, log_callback=log)
        cleanup_runtime_memory(log_callback=log, reason="Task finished")
        log(f"[*] Task finished. OK {success_count} | Fail {fail_count}")
    return {
        "success": success_count,
        "fail": fail_count,
        "accounts_file": accounts_output_file,
        "stopped": bool(controller.should_stop()),
    }


def run_registration_cli(count):
    return run_registration_job(count, log_callback=cli_log, controller=CliStopController())


def _cli_menu_status(state):
    if state["running"]:
        return "RUNNING"
    if state["result"]:
        return "STOPPED" if state["result"].get("stopped") else "READY"
    return "READY"


def _configure_cli_readline():
    """Map common terminal delete sequences for input() prompts."""
    try:
        import readline

        # GNU readline (Linux) and libedit (macOS) use different commands.
        for binding in (
            '"\\e[3~": delete-char',
            'bind -s "\\e[3~": ed-delete-next-char',
        ):
            try:
                readline.parse_and_bind(binding)
            except Exception:
                pass
    except (ImportError, OSError):
        pass


def _cli_print_menu(state):
    load_config()
    status = _cli_menu_status(state)
    count = int(config.get("register_count", 1) or 1)
    provider = str(config.get("email_provider") or "-")
    mode = str(config.get("register_mode") or "browser")
    print("\n" + "=" * 58)
    print("GROK REGISTRATION - TERMINAL CONTROL")
    print("=" * 58)
    print(f"Status   : [{status}]")
    print(f"Provider : {provider}")
    print(f"Mode     : {mode}")
    print(f"Jumlah   : {count}")
    if state["result"]:
        result = state["result"]
        print(f"Hasil    : OK {result.get('success', 0)} | Gagal {result.get('fail', 0)}")
    print("-" * 58)
    print("1. Mulai registrasi")
    print("2. Hentikan registrasi")
    print("3. Lihat status")
    print("4. Muat ulang konfigurasi")
    print("0. Keluar")
    print("-" * 58)


def _cli_start_job(state):
    if state["running"]:
        print("[!] Job sedang berjalan.")
        return
    if not _cli_config_wizard():
        return
    _cli_launch_job(state)


def _cli_launch_job(state):
    try:
        count = int(input("Jumlah akun yang dibuat [config: %s]: " % config.get("register_count", 1)).strip() or config.get("register_count", 1))
    except (ValueError, EOFError):
        print("[!] Jumlah akun tidak valid.")
        return
    if count < 1:
        print("[!] Jumlah akun minimal 1.")
        return
    config["register_count"] = count
    _cli_print_summary(count)
    try:
        confirm = input("Ketik 'start' untuk memulai: ").strip().lower()
    except EOFError:
        return
    if confirm != "start":
        print("[!] Dibatalkan. Tidak ada job yang dimulai.")
        return
    save_config()
    controller = CliStopController()
    state["controller"] = controller
    state["result"] = None
    state["running"] = True

    def worker():
        try:
            state["result"] = run_registration_job(
                count, log_callback=cli_log, controller=controller
            )
        except Exception as exc:
            cli_log(f"[!] Job exception: {exc}")
            state["result"] = {"success": 0, "fail": 0, "stopped": True}
        finally:
            state["running"] = False

    state["thread"] = threading.Thread(target=worker, daemon=True)
    state["thread"].start()
    print(f"[+] Job dimulai untuk {count} akun.")


def _cli_input(label, current="", secret=False, required=False):
    prompt = f"{label} [{current}]: " if current and not secret else f"{label}: "
    try:
        value = getpass.getpass(prompt) if secret else input(prompt)
    except (EOFError, KeyboardInterrupt):
        return None
    value = value.strip()
    if not value:
        value = str(current or "").strip()
    if required and not value:
        print(f"[!] {label} wajib diisi.")
        return None
    return value


def _cli_choose(label, options, current):
    print(f"\n{label}")
    for number, (value, title) in enumerate(options, 1):
        marker = "*" if value == current else " "
        print(f"{number}. [{marker}] {title}")
    try:
        raw = input(f"Pilih [{current}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not raw:
        return current
    try:
        return options[int(raw) - 1][0]
    except (ValueError, IndexError):
        print("[!] Pilihan tidak valid.")
        return None


def _cli_test_provider():
    provider = str(config.get("email_provider") or "").lower()
    try:
        if provider == "litensi":
            prices = litensi_get_prices()
            in_stock = [p for p in prices if float(p.get("stock") or 0) > 0]
            print(f"[+] Litensi online, {len(in_stock)} zone tersedia.")
            if in_stock and not str(config.get("litensi_zone") or "").strip():
                in_stock.sort(key=lambda item: float(item.get("price") or 0))
                config["litensi_zone"] = str(in_stock[0].get("zone") or "")
                print(f"[*] Zone otomatis: {config['litensi_zone']}")
            return bool(in_stock)
        if provider == "cloudflare":
            domains = cloudflare_get_domains(get_cloudflare_api_base())
            print(f"[+] Cloudflare email API online, {len(domains)} domain ditemukan.")
            return True
    except Exception as exc:
        print(f"[!] Tes {provider} gagal: {exc}")
        return False
    print("[!] Provider email tidak dikenali.")
    return False


def _cli_config_wizard():
    print("\n--- 1. Sumber email ---")
    provider = _cli_choose(
        "Pilih mail source",
        [("cloudflare", "Cloudflare Temp Email"), ("litensi", "Litensi Mail")],
        str(config.get("email_provider") or "cloudflare"),
    )
    if not provider:
        return False
    config["email_provider"] = provider
    if provider == "cloudflare":
        base = _cli_input("Cloudflare API base", config.get("cloudflare_api_base", ""), required=True)
        if base is None:
            return False
        config["cloudflare_api_base"] = base
        auth_mode = _cli_choose(
            "Cloudflare auth mode",
            [("none", "Anonymous"), ("bearer", "Bearer"), ("x-api-key", "X-API-Key"), ("x-admin-auth", "X-Admin-Auth")],
            str(config.get("cloudflare_auth_mode") or "none"),
        )
        if auth_mode is None:
            return False
        config["cloudflare_auth_mode"] = auth_mode
        key = _cli_input("Cloudflare API key", config.get("cloudflare_api_key", ""))
        if key is None:
            return False
        config["cloudflare_api_key"] = key
        domains = _cli_input("Domain email (opsional, pisahkan koma)", config.get("defaultDomains", ""))
        if domains is None:
            return False
        config["defaultDomains"] = domains
    else:
        for key, label in (
            ("litensi_api_id", "Litensi API ID"),
            ("litensi_api_key", "Litensi API key"),
            ("litensi_site", "Litensi site"),
        ):
            value = _cli_input(label, config.get(key, ""), secret=key.endswith("key"), required=True)
            if value is None:
                return False
            config[key] = value
        zone = _cli_input("Litensi zone (kosong = otomatis)", config.get("litensi_zone", ""))
        if zone is None:
            return False
        config["litensi_zone"] = zone
    if not _cli_test_provider():
        print("[!] Perbaiki konfigurasi provider sebelum melanjutkan.")
        return False

    print("\n--- 2. Mode registrasi ---")
    mode = _cli_choose(
        "Pilih mode",
        [("browser", "Browser penuh"), ("hybrid", "Hybrid protokol + browser")],
        str(config.get("register_mode") or "browser"),
    )
    if not mode:
        return False
    config["register_mode"] = mode

    print("\n--- 3. Push minted ke 9router ---")
    enabled = _cli_choose(
        "Aktifkan push minted ke 9router?",
        [(True, "Ya"), (False, "Tidak")],
        bool(config.get("nine_router_enabled", False)),
    )
    if enabled is None:
        return False
    config["nine_router_enabled"] = enabled
    if enabled:
        base = _cli_input("9router base URL", config.get("nine_router_base", ""), required=True)
        if base is None:
            return False
        config["nine_router_base"] = base.rstrip("/")
        push_mode = _cli_choose(
            "9router push mode",
            [("device", "Device flow (persisten)"), ("token", "Token/API key")],
            str(config.get("nine_router_push_mode") or "device"),
        )
        if push_mode is None:
            return False
        config["nine_router_push_mode"] = push_mode
        password = _cli_input("9router password (kosong jika tanpa auth)", config.get("nine_router_password", ""), secret=True)
        if password is None:
            return False
        config["nine_router_password"] = password
        print("[*] Menguji 9router... harus HTTP 200 untuk melanjutkan.")
        ok, message = test_nine_router_connection(log_callback=cli_log)
        print(("[+] " if ok else "[!] ") + message)
        if not ok or "HTTP 200" not in message:
            print("[!] 9router belum lolos tes HTTP 200.")
            return False
    return True


def _cli_validate_loaded_config():
    """Validate config.json before allowing a job to start."""
    print("\n[*] Memvalidasi konfigurasi yang dimuat...")
    provider = str(config.get("email_provider") or "").strip().lower()
    if provider not in ("cloudflare", "litensi"):
        print(f"[!] Mail source tidak valid: {provider or '(kosong)'}")
        return False
    if not _cli_test_provider():
        return False
    if config.get("nine_router_enabled", False):
        base = str(config.get("nine_router_base") or "").strip()
        if not base:
            print("[!] 9router aktif tetapi base URL kosong.")
            return False
        print("[*] Menguji 9router... harus HTTP 200 untuk melanjutkan.")
        ok, message = test_nine_router_connection(log_callback=cli_log)
        print(("[+] " if ok else "[!] ") + message)
        if not ok or "HTTP 200" not in message:
            print("[!] Status konfigurasi belum OK: 9router tidak HTTP 200.")
            return False
    print("[+] Status konfigurasi: OK")
    return True


def _cli_print_summary(count):
    print("\n" + "=" * 58)
    print("RINGKASAN KONFIGURASI")
    print("=" * 58)
    print(f"Mail source : {config.get('email_provider')}")
    if config.get("email_provider") == "litensi":
        print(f"Litensi     : site={config.get('litensi_site')} | zone={config.get('litensi_zone') or 'auto'}")
    else:
        print(f"Cloudflare  : {config.get('cloudflare_api_base')}")
    print(f"Mode        : {config.get('register_mode')}")
    print(f"9router     : {'aktif' if config.get('nine_router_enabled') else 'nonaktif'}")
    if config.get("nine_router_enabled"):
        print(f"9router URL : {config.get('nine_router_base')}")
        print(f"Push mode   : {config.get('nine_router_push_mode')}")
    print(f"Jumlah akun : {count}")
    print("=" * 58)


def _cli_stop_job(state):
    if not state["running"] or state["controller"] is None:
        print("[!] Tidak ada job yang sedang berjalan.")
        return
    state["controller"].stop()
    print("[*] Permintaan berhenti dikirim. Menunggu langkah aktif selesai...")


def _cli_show_status(state):
    status = _cli_menu_status(state)
    print(f"\nStatus: [{status}]")
    if state["running"]:
        print("Job masih berjalan. Log proses tampil di terminal.")
    elif state["result"]:
        result = state["result"]
        print(f"Selesai: OK {result.get('success', 0)} | Gagal {result.get('fail', 0)}")
        if result.get("accounts_file"):
            print(f"File akun: {result['accounts_file']}")
    else:
        print("Belum ada job yang dijalankan.")


def main_cli():
    print("[!] CLI dinonaktifkan. Jalankan aplikasi melalui Web console:")
    print("    python -m uvicorn web.server:app --host 127.0.0.1 --port 8092 --workers 1")
    return 1


def main():
    print("[!] Desktop/CLI entry point dinonaktifkan. Gunakan Web console:")
    print("    python -m uvicorn web.server:app --host 127.0.0.1 --port 8092 --workers 1")


if __name__ == "__main__":
    main()
