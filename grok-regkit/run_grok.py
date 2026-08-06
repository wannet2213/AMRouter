#!/usr/bin/env python3
"""
Grok registration wrapper for AMRouter.

Called by the AMRouter backend (/api/automation/grok) via subprocess.
Wraps grok_register_ttk.run_registration_job() with:
  - job id + state file (JSON) for status polling
  - log file (plain text) for streaming
  - stop support via a stop file
  - config override via CLI args (email provider, proxy, count, mode)

Usage:
  python run_grok.py --job-id JOBID --count N [--mode browser|hybrid]
                     [--config PATH] [--state-dir PATH]
                     [--proxy PROXY] [--email-base URL] [--email-key KEY]
"""
import argparse
import json
import os
import sys
import time
import traceback

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--mode", default="browser")
    ap.add_argument("--config", default=None)
    ap.add_argument("--state-dir", default=None)
    ap.add_argument("--proxy", default="")
    ap.add_argument("--email-base", default="")
    ap.add_argument("--email-key", default="")
    args = ap.parse_args()

    # State dir: default = cwd of the toolkit (grok-regkit dir)
    state_dir = args.state_dir or os.getcwd()
    os.makedirs(state_dir, exist_ok=True)
    state_file = os.path.join(state_dir, f"grok_{args.job_id}.state.json")
    log_file = os.path.join(state_dir, f"grok_{args.job_id}.log")

    def write_state(**updates):
        state = {"job_id": args.job_id, "updated_at": time.time()}
        state.update(updates)
        with open(state_file, "w") as f:
            json.dump(state, f)

    def log_cb(msg):
        with open(log_file, "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    # Import engine (must run from toolkit dir)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import grok_register_ttk as engine

    # Config overrides
    cfg_path = args.config or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if not os.path.exists(cfg_path):
        # create from example
        example = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.example.json")
        if os.path.exists(example):
            with open(example) as f:
                cfg = json.load(f)
            if args.proxy:
                cfg["proxy"] = args.proxy
                cfg["proxy_mode"] = "proxy" if args.proxy else "direct"
            if args.email_base:
                cfg["cloudflare_api_base"] = args.email_base
            if args.email_key:
                cfg["cloudflare_api_key"] = args.email_key
            cfg["register_mode"] = args.mode
            with open(cfg_path, "w") as f:
                json.dump(cfg, f, indent=2)
            log_cb(f"[*] config.json created from example (mode={args.mode})")
    else:
        with open(cfg_path) as f:
            cfg = json.load(f)
        if args.proxy:
            cfg["proxy"] = args.proxy
        if args.email_base:
            cfg["cloudflare_api_base"] = args.email_base
        if args.email_key:
            cfg["cloudflare_api_key"] = args.email_key
        cfg["register_mode"] = args.mode
        with open(cfg_path, "w") as f:
            json.dump(cfg, f, indent=2)

    write_state(status="starting", progress=0, success=0, fail=0, stopped=False)

    # Stop file support
    stop_file = os.path.join(state_dir, f"grok_{args.job_id}.stop")
    if os.path.exists(stop_file):
        os.remove(stop_file)

    class StopController(engine.CliStopController):
        def should_stop(self):
            return os.path.exists(stop_file) or super().should_stop()

    controller = StopController()

    try:
        engine.load_config()
        result = engine.run_registration_job(
            args.count, log_callback=log_cb, controller=controller
        )
        stopped = bool(result.get("stopped"))
        # Extract the successfully registered email from accounts file
        email = ""
        accounts_file = result.get("accounts_file") or ""
        if accounts_file and os.path.exists(accounts_file):
            try:
                with open(accounts_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and "@" in line:
                            email = line.split("----")[0].strip()
                            break
            except Exception:
                pass
        write_state(
            status="stopped" if stopped else "done",
            progress=100,
            success=int(result.get("success") or 0),
            fail=int(result.get("fail") or 0),
            stopped=stopped,
            accounts_file=accounts_file,
            email=email,
        )
        # Extract OIDC (Grok Build / grok-cli) credentials from cpa_auths/xai-<email>.json
        oidc = {}
        if email:
            auth_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                str(engine.config.get("cpa_auth_dir", "./cpa_auths") or "./cpa_auths"),
            )
            candidate = os.path.join(auth_dir, f"xai-{email}.json")
            try:
                if os.path.exists(candidate):
                    with open(candidate, encoding="utf-8") as f:
                        oidc = json.load(f)
                    log_cb(f"[*] OIDC/Grok-Build auth found for {email}")
                else:
                    # fallback: any xai-*.json written in the last 10 minutes
                    import time as _t
                    now = _t.time()
                    for fn in os.listdir(auth_dir):
                        if fn.startswith("xai-") and fn.endswith(".json"):
                            p = os.path.join(auth_dir, fn)
                            if now - os.path.getmtime(p) < 600:
                                with open(p, encoding="utf-8") as f:
                                    oidc = json.load(f)
                                log_cb(f"[*] OIDC/Grok-Build auth fallback: {fn}")
                                break
            except Exception as exc:
                log_cb(f"[!] OIDC extract failed: {exc}")
        # Append OIDC to state file
        state_file = os.path.join(state_dir, f"grok_{args.job_id}.state.json")
        try:
            if os.path.exists(state_file):
                with open(state_file, encoding="utf-8") as f:
                    st = json.load(f)
                st["oidc"] = {
                    "access_token": oidc.get("access_token") or "",
                    "refresh_token": oidc.get("refresh_token") or "",
                    "expires_in": oidc.get("expires_in") or 21600,
                    "sub": oidc.get("sub") or "",
                }
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump(st, f)
        except Exception as exc:
            log_cb(f"[!] state append failed: {exc}")
        log_cb(f"[*] done: success={result.get('success')} fail={result.get('fail')}")
        # Emit machine-readable final result on stdout for the AMRouter backend
        print(json.dumps({
            "status": "stopped" if stopped else "done",
            "success": int(result.get("success") or 0),
            "fail": int(result.get("fail") or 0),
            "accounts_file": result.get("accounts_file") or "",
            "job_id": args.job_id,
            "has_oidc": bool(oidc.get("access_token") and oidc.get("refresh_token")),
        }))
        sys.stdout.flush()
    except Exception as exc:
        write_state(status="error", error=str(exc), progress=100)
        log_cb(f"[!] error: {exc}")
        print(json.dumps({"status": "error", "error": str(exc), "job_id": args.job_id}))
        sys.stdout.flush()
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
