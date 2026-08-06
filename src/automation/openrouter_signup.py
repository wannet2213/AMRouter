#!/usr/bin/env python3
"""OpenRouter account auto-signup via Camoufox (anti-fingerprint) + Ammail email verification.

Flow:
  1. Open openrouter.ai, click "Sign Up"
  2. Fill email (from Ammail) + password, accept Terms, click Continue
  3. (Optional) solve any captcha via 2Captcha
  4. Poll Ammail inbox for the OpenRouter verification email → open verification link
  5. Open /keys, create a new API key, copy it
  6. Emit {"status":"success","api_key":"sk-or-v1-...","email":"..."}

Outputs JSON lines to stdout:
  {"step": "..."}
  {"status": "success", "api_key": "...", "email": "..."}
  {"status": "error", "error": "..."}
"""

import sys
import os
import json
import argparse
import time
import random
import string
import re
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

# ── Stdout JSON helpers ────────────────────────────────────────────────────────
def emit(obj):
    print(json.dumps(obj), flush=True)

def log_step(msg):
    emit({"step": msg})

def success(api_key, email):
    # Clean api_key — extract sk-or-v1-... token if wrapped in other text
    m = re.search(r'(sk-or-v1-[A-Za-z0-9_-]{20,})', api_key)
    if m:
        api_key = m.group(1)
    emit({"status": "success", "api_key": api_key, "email": email})

def die(msg):
    emit({"status": "error", "error": msg})
    sys.exit(1)

# ── Ammail helpers ─────────────────────────────────────────────────────────────
def ammail_request(base_url, api_key, path, method="GET", data=None):
    url = base_url.rstrip("/") + "/api" + path
    req = urllib.request.Request(url, method=method)
    req.add_header("X-API-Key", api_key)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    req.add_header("Accept", "application/json, */*")
    if "localhost" in base_url or "127.0.0.1" in base_url:
        req.add_header("Host", "ammail.klipers.site")
    if data:
        req.data = json.dumps(data).encode()
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def create_ammail_inbox(base_url, api_key, email):
    try:
        alias, domain = email.split("@", 1)
        ammail_request(base_url, api_key, "/inboxes", method="POST",
                       data={"alias": alias, "domain": domain})
    except Exception:
        pass  # might already exist

def wait_for_openrouter_verify_email(base_url, api_key, email, timeout=240):
    """Poll Ammail inbox for the OpenRouter verification email; return the link."""
    log_step(f"Menunggu email verifikasi OpenRouter ({email})...")
    alias = email.split("@")[0]
    deadline = time.time() + timeout
    seen_ids = set()
    while time.time() < deadline:
        try:
            data = ammail_request(base_url, api_key, f"/inboxes/{urllib.parse.quote(alias)}/messages")
            messages = data.get("messages", [])
            for msg in messages:
                msg_id = msg.get("id", "")
                subject = msg.get("subject", "")
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)
                subj_lower = subject.lower()
                from_addr = str(msg.get("from", "")).lower()
                is_or_email = (
                    "openrouter" in subj_lower
                    or "openrouter" in from_addr
                    or "verify" in subj_lower
                    or "confirm" in subj_lower
                    or "sign" in subj_lower
                    or "email" in subj_lower
                    or "welcome" in subj_lower
                )
                if is_or_email:
                    try:
                        full = ammail_request(base_url, api_key, f"/messages/{urllib.parse.quote(msg_id)}")
                        msg_body = full.get("message", full)
                        body = msg_body.get("body", msg_body.get("html", msg_body.get("text", "")))
                    except Exception:
                        body = msg.get("snippet", "")
                    # Prefer real openrouter.ai verification links; fall back to clkmail redirects
                    patterns = [
                        r'https://openrouter\.ai/[^\\s"\'<>]+verif[^\\s"\'<>]*',
                        r'https://openrouter\.ai/[^\\s"\'<>]+',
                        r'https://clkmail\.openrouter\.ai/[^\\s"\'<>]+',
                        r'https://[^\\s"\'<>]*verify[^\\s"\'<>]*',
                        r'https://[^\\s"\'<>]*confirm[^\\s"\'<>]*',
                        r'https://[^\\s"\'<>]*activation[^\\s"\'<>]*',
                    ]
                    for pat in patterns:
                        links = re.findall(pat, body or "")
                        if links:
                            link = links[0].rstrip(".")
                            log_step("Link verifikasi OpenRouter ditemukan!")
                            return link
        except Exception as e:
            log_step(f"Ammail poll error: {e}")
        time.sleep(5)
    return None

# ── 2Captcha Turnstile/captcha solver (optional) ──────────────────────────────
def solve_captcha_2captcha(api_key, page_url, sitekey, timeout=120, invisible=False):
    """Generic captcha solver via 2Captcha. Returns solution token or None."""
    if not api_key or not sitekey:
        return None
    log_step("Mengirim captcha ke 2Captcha...")
    try:
        submit = {
            "key": api_key,
            "method": "turnstile",
            "sitekey": sitekey,
            "pageurl": page_url,
            "json": 1,
        }
        if invisible:
            submit["invisible"] = 1
        encoded = urllib.parse.urlencode(submit).encode()
        req = urllib.request.Request("https://2captcha.com/in.php", data=encoded)
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        if resp.get("status") != 1:
            log_step(f"2Captcha submit error: {resp}")
            return None
        task_id = resp.get("request")
        log_step(f"2Captcha task: {task_id}")
        deadline = time.time() + timeout
        time.sleep(15)
        while time.time() < deadline:
            res_url = f"https://2captcha.com/res.php?key={api_key}&action=get&id={task_id}&json=1"
            with urllib.request.urlopen(urllib.request.Request(res_url), timeout=15) as r2:
                res = json.loads(r2.read())
            if res.get("status") == 1:
                return res.get("request")
            if res.get("request") == "CAPCHA_NOT_READY":
                time.sleep(5)
                continue
            log_step(f"2Captcha poll error: {res}")
            return None
    except Exception as e:
        log_step(f"2Captcha error: {e}")
    return None

def get_captcha_sitekey(page):
    """Try to find a captcha sitekey on the page (Turnstile / recaptcha).
    Returns the sitekey string, or the magic marker "TURNSTILE_PRESENT" when a
    Cloudflare Turnstile widget is detected but its sitekey cannot be read."""
    try:
        return page.evaluate(r"""
            () => {
                // Cloudflare Turnstile widget (explicit mode renders a .cf-turnstile div)
                const cf = document.querySelector('.cf-turnstile, [data-cf-turnstile-response], [data-sitekey]');
                if (cf && cf.getAttribute('data-sitekey')) return cf.getAttribute('data-sitekey');
                // Turnstile iframe (challenges.cloudflare.com/turnstile)
                for (const iframe of document.querySelectorAll('iframe')) {
                    const src = iframe.src || '';
                    if (src.includes('turnstile') || src.includes('challenges.cloudflare.com')) {
                        const m = src.match(/[?&]sitekey=([^&]+)/) || src.match(/[?&]k=([^&]+)/);
                        if (m) return decodeURIComponent(m[1]);
                        return 'TURNSTILE_PRESENT';
                    }
                }
                // generic recaptcha
                const el = document.querySelector('[data-sitekey]');
                if (el) return el.getAttribute('data-sitekey');
                for (const iframe of document.querySelectorAll('iframe')) {
                    const m = (iframe.src || '').match(/[?&]sitekey=([^&]+)/);
                    if (m) return decodeURIComponent(m[1]);
                }
                return null;
            }
        """)
    except Exception:
        return None

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--profiles-dir", default="profiles/openrouter")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--engine", default="camoufox", choices=["camoufox", "firefox"],
                        help="Browser engine: camoufox (anti-fingerprint) or firefox (system Firefox, best for bypassing Turnstile on a real display)")
    parser.add_argument("--pause", action="store_true",
                        help="Pause before clicking Continue so a human can solve any Turnstile/captcha manually in the GUI")
    parser.add_argument("--ammail-base-url", default="")
    parser.add_argument("--ammail-api-key", default="")
    parser.add_argument("--ammail-domain", default="")
    parser.add_argument("--2captcha-key", default="")
    parser.add_argument("--stagger-delay", type=int, default=0)
    args = parser.parse_args()

    if args.stagger_delay > 0:
        log_step(f"Stagger delay {args.stagger_delay}s...")
        time.sleep(args.stagger_delay)

    email = args.email.strip()
    password = args.password.strip()

    # Lazy import camoufox (heavy)
    try:
        from camoufox.sync_api import Camoufox
    except Exception as e:
        die(f"Camoufox tidak terinstall: {e}")

    # Ensure Ammail inbox exists (so verification email can arrive)
    if args.ammail_base_url and args.ammail_api_key:
        create_ammail_inbox(args.ammail_base_url, args.ammail_api_key, email)

    log_step("Meluncurkan browser...")
    browser = None
    pw = None
    try:
        if args.engine == "firefox":
            from sel_browser import launch_selenium
            page = launch_selenium(display=os.environ.get("DISPLAY", ":0"))
            log_step("Browser: system firefox-esr via Selenium (DISPLAY=:0, trusted)")
        else:
            _cam = Camoufox(headless=args.headless)
            browser = _cam.__enter__()
            log_step("Browser: Camoufox (anti-fingerprint)")
            page = browser.new_page()
        page.set_default_timeout(30000)

        # ── Step 1: open signup ──
        log_step("Membuka openrouter.ai...")
        page.goto("https://openrouter.ai/", wait_until="domcontentloaded")
        time.sleep(2)

        # Click "Sign Up" button (could be in nav or a dialog trigger)
        signup_clicked = False
        for sel in [
            "button:has-text('Sign Up')",
            "a:has-text('Sign Up')",
            "text=Sign Up",
        ]:
            try:
                page.click(sel, timeout=5000)
                signup_clicked = True
                break
            except Exception:
                continue
        if not signup_clicked:
            log_step("Tombol Sign Up tidak ditemukan, langsung buka /auth...")
            page.goto("https://openrouter.ai/auth", wait_until="domcontentloaded")
        time.sleep(2)

        # ── Step 2: fill the signup form ─────────────────────────────────
        log_step("Mengisi form signup...")

        def fill_field(selectors, value, label):
            for sel in selectors:
                try:
                    page.fill(sel, value, timeout=6000)
                    log_step(f"{label} diisi.")
                    return True
                except Exception:
                    continue
            return False

        ok_email = fill_field([
            "input[name='emailAddress']",
            "#emailAddress-field",
            "input[type='email']",
            "input[name='email']",
            "#email",
        ], email, "Email")
        if not ok_email:
            die("Tidak bisa menemukan field email di halaman signup.")

        ok_pass = fill_field([
            "input[name='password']",
            "#password-field",
            "input[type='password']",
            "#password",
        ], password, "Password")
        if not ok_pass:
            die("Tidak bisa menemukan field password di halaman signup.")

        # Optional first/last name fields (not required)
        fill_field([
            "input[name='firstName']", "input[name='first_name']",
            "input[autocomplete='given-name']", "#firstName",
        ], "User", "First name")
        fill_field([
            "input[name='lastName']", "input[name='last_name']",
            "input[autocomplete='family-name']", "#lastName",
        ], "Account", "Last name")

        # Accept Terms checkbox (legalAccepted)
        for sel in [
            "input[name='legalAccepted']",
            "#legalAccepted-field",
            "input[type='checkbox']",
            "[role='checkbox']",
            "label:has-text('Terms of Service') input",
        ]:
            try:
                page.click(sel, timeout=5000)
                log_step("Checkbox Terms dicentang.")
                break
            except Exception:
                continue

        # ── Step 3: verify the form is actually filled ───────────────────
        # Dump field values so we KNOW the form is populated before Continue.
        try:
            vals = page.evaluate(r"""
                () => {
                    const g = (s) => { const e = document.querySelector(s); return e ? (e.value || '') : 'NONE'; };
                    return {
                        email: g("input[type='email'], input[name='email'], #emailAddress-field, #email"),
                        pass: g("input[type='password'], input[name='password'], #password-field, #password").length,
                        terms: (() => { const c = document.querySelector("input[name='legalAccepted'], #legalAccepted-field, input[type='checkbox']"); return c ? c.checked : 'NONE'; })()
                    };
                }
            """)
            log_step(f"FORM VALUES: email={vals.get('email')} pass_len={vals.get('pass')} terms_checked={vals.get('terms')}")
        except Exception as e:
            log_step(f"Gagal dump form values: {e}")

        # ── Step 4: click Continue ONCE ──────────────────────────────────
        log_step("Klik Continue...")
        continue_clicked = False
        for sel in [
            "button:has-text('Continue')",
            "[role='dialog'] button:has-text('Continue')",
            "[role='dialog'] button[type='submit']",
            "button[type='submit']",
            "input[type='submit']",
            "text=Continue",
        ]:
            try:
                page.click(sel, timeout=8000, force=True)
                continue_clicked = True
                log_step(f"Tombol Continue diklik ({sel}).")
                break
            except Exception:
                continue
        if not continue_clicked:
            die("Tidak bisa menemukan tombol Continue.")
        time.sleep(5)

        # ── Step 4b: Turnstile appears AFTER Continue (Clerk challenge page) ──
        # Instruction: after clicking Continue, the captcha (a checkbox) appears.
        # We just need to CLICK the checkbox — no 2Captcha needed.
        log_step("Menunggu kemunculan captcha (centang) pasca-Continue...")
        turnstile_clicked = False
        for _ in range(30):  # up to ~30s
            try:
                present = page.evaluate(r"""
                    () => {
                        if (document.querySelector('.cf-turnstile, [data-cf-turnstile-response], iframe[src*="challenges.cloudflare.com/turnstile"]')) return true;
                        if (/challenges\.cloudflare\.com\/turnstile/.test(document.documentElement.outerHTML)) return true;
                        return false;
                    }
                """)
            except Exception:
                present = False
            if present:
                log_step("Captcha terdeteksi pasca-Continue. Mengklik centang...")
                # Click the Turnstile checkbox (the .cf-turnstile widget triggers it)
                for sel in [
                    ".cf-turnstile",
                    ".cf-turnstile iframe",
                    "iframe[src*='challenges.cloudflare.com/turnstile']",
                    "[data-cf-turnstile-response]",
                    "input[type='checkbox']",
                    "[role='checkbox']",
                ]:
                    try:
                        page.click(sel, timeout=5000, force=True)
                        turnstile_clicked = True
                        log_step(f"Centang captcha diklik ({sel}).")
                        break
                    except Exception:
                        continue
                if not turnstile_clicked:
                    log_step("Centang tidak bisa diklik, mencoba klik via JS...")
                    try:
                        page.evaluate(r"""
                            () => {
                                const el = document.querySelector('.cf-turnstile, [data-cf-turnstile-response], iframe[src*="challenges.cloudflare.com/turnstile"]');
                                if (el) el.click();
                            }
                        """)
                        turnstile_clicked = True
                    except Exception as e:
                        log_step(f"Gagal klik centang: {e}")
                # Wait for Turnstile to solve automatically after the click
                time.sleep(6)
                break
            time.sleep(1)
        if not turnstile_clicked:
            log_step("Captcha tidak muncul pasca-Continue (browser trusted / lolos).")

        # Verify submission: dialog should close and URL should change
        still_in_dialog = False
        try:
            still_in_dialog = page.evaluate("() => !!document.querySelector('dialog[open]')")
        except Exception:
            still_in_dialog = False
        if still_in_dialog:
            # Read any validation error shown in the dialog
            err_txt = ""
            try:
                err_txt = page.evaluate("() => document.querySelector('dialog')?.innerText || ''")
            except Exception:
                err_txt = ""
            if re.search(r"invalid|error|required|must|please|already|exists", err_txt, re.I):
                die(f"Signup ditolak: {err_txt.strip()[:200]}")
            log_step("Masih di dialog signup, menunggu redirect...")

        # Detect failed submission: OpenRouter redirects to /sign-in on auth failure
        cur_url = ""
        try:
            cur_url = page.url
        except Exception:
            cur_url = ""
        if "/sign-in" in cur_url or "?error" in cur_url or "error=" in cur_url:
            die("Signup GAGAL — OpenRouter mengalihkan ke halaman sign-in "
                "(biasanya karena Turnstile/captcha belum ter-solve atau email ditolak). "
                "Pastikan 2Captcha key benar dan email valid.")

        # DEBUG: capture post-Continue state for inspection
        try:
            page.screenshot(path="/tmp/or_after_continue.png")
            log_step(f"DEBUG URL after continue: {cur_url}")
            body_txt = page.evaluate("() => document.body.innerText.slice(0,400)") or ""
            log_step(f"DEBUG BODY after continue: {body_txt.strip()[:400]}")
        except Exception as e:
            log_step(f"DEBUG screenshot gagal: {e}")

        # ── Step 5: verify email via Ammail ──────────────────────────────
        if not (args.ammail_base_url and args.ammail_api_key):
            die("Signup mungkin berhasil tapi Ammail tidak dikonfigurasi — "
                "email verifikasi tidak bisa diterima. Setel Ammail di Settings Automation.")

        verify_link = wait_for_openrouter_verify_email(
            args.ammail_base_url, args.ammail_api_key, email
        )
        if verify_link:
            log_step(f"Membuka link verifikasi: {verify_link[:60]}...")
            try:
                page.goto(verify_link, wait_until="domcontentloaded")
                time.sleep(5)
                log_step("Verifikasi email selesai.")
            except Exception as e:
                log_step(f"Gagal buka link verifikasi: {e}")
            # Reload keys page to ensure session is established
            try:
                page.goto("https://openrouter.ai/keys", wait_until="networkidle", timeout=20000)
                time.sleep(3)
            except Exception:
                pass
        else:
            log_step("Tidak ada link verifikasi (mungkin akun langsung aktif atau verifikasi manual).")

        # ── Step 6: open API keys page & create a key ────────────────────
        log_step("Membuka halaman API keys...")
        try:
            page.goto("https://openrouter.ai/keys", wait_until="networkidle", timeout=20000)
        except Exception:
            page.goto("https://openrouter.ai/keys", wait_until="domcontentloaded")
        time.sleep(3)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        try:
            page.evaluate("() => window.scrollTo(0,0)")
        except Exception:
            pass
        time.sleep(2)

        # If redirected to login, try to log in with the same credentials
        if "login" in page.url.lower() or "auth" in page.url.lower():
            log_step("Dialihkan ke login, mencoba login...")
            fill_field([
                "input[type='email']", "input[name='email']", "#email",
            ], email, "Login email")
            fill_field([
                "input[type='password']", "input[name='password']", "#password",
            ], password, "Login password")
            for sel in ["button:has-text('Sign in')", "button:has-text('Log in')",
                        "button[type='submit']", "text=Sign in"]:
                try:
                    page.click(sel, timeout=6000)
                    break
                except Exception:
                    continue
            time.sleep(5)
            page.goto("https://openrouter.ai/keys", wait_until="domcontentloaded")
            time.sleep(5)

        # Click "Create Key" / "New Key"
        key_created = False
        for sel in [
            "button:has-text('Create Key')",
            "button:has-text('New Key')",
            "button:has-text('New API Key')",
            "button:has-text('Generate')",
            "button:has-text('Add Key')",
            "button:has-text('Create')",
            "button:has-text('+ Create')",
            "[role='button']:has-text('Key')",
            "button[type='submit']",
            "a:has-text('Create Key')",
        ]:
            try:
                page.click(sel, timeout=8000, force=True)
                key_created = True
                log_step("Dialog pembuatan key dibuka.")
                break
            except Exception:
                continue

        if not key_created:
            # Debug: dump all buttons + screenshot for inspection
            try:
                btns = page.evaluate(r"""() => Array.from(document.querySelectorAll('button, a, [role=button]')).map(b => (b.textContent||'').trim()).filter(Boolean).slice(0,40)""")
                log_step(f"Tombol di /keys: {btns}")
            except Exception as e:
                log_step(f"Gagal dump tombol: {e}")
            try:
                shot = f"/tmp/or_keys_{email.split('@')[0]}.png"
                page.screenshot(path=shot)
                log_step(f"Screenshot disimpan: {shot}")
            except Exception:
                pass
            die("Tidak bisa menemukan tombol Create Key di /keys.")

        # Fill key name if a name field appears
        fill_field([
            "input[name='name']", "input[placeholder*='name' i]",
            "input[placeholder*='Key' i]", "#name",
        ], f"9router-{int(time.time())}", "Key name")
        time.sleep(1)

        # Confirm creation
        for sel in [
            "button:has-text('Create')",
            "button:has-text('Generate')",
            "button:has-text('Confirm')",
            "button[type='submit']",
        ]:
            try:
                page.click(sel, timeout=8000)
                log_step("Konfirmasi pembuatan key...")
                break
            except Exception:
                continue
        time.sleep(4)

        # Extract the API key from the page
        log_step("Mengekstrak API key...")
        api_key = None
        # Try to read from a visible input/code element first
        try:
            api_key = page.evaluate(r"""
                () => {
                    const m = document.body.innerText.match(/sk-or-v1-[A-Za-z0-9_-]{20,}/);
                    if (m) return m[0];
                    const inp = document.querySelector('input[readonly], input[value^="sk-or-"]');
                    if (inp && inp.value) return inp.value;
                    const code = document.querySelector('code');
                    if (code && /sk-or-v1-/.test(code.textContent)) return code.textContent.trim();
                    return null;
                }
            """)
        except Exception:
            api_key = None

        # If still not found, try to copy via clipboard button then read
        if not api_key:
            for sel in ["button:has-text('Copy')", "button[aria-label*='copy' i]"]:
                try:
                    page.click(sel, timeout=5000)
                    time.sleep(1)
                    break
                except Exception:
                    continue
            # Re-read after copy attempt
            try:
                api_key = page.evaluate(r"""
                    () => {
                        const m = document.body.innerText.match(/sk-or-v1-[A-Za-z0-9_-]{20,}/);
                        return m ? m[0] : null;
                    }
                """)
            except Exception:
                api_key = None

            if not api_key:
                die("Gagal mengekstrak API key OpenRouter dari halaman /keys.")

            log_step("API key berhasil diambil.")
            success(api_key, email)

    except SystemExit:
        raise
    except Exception as e:
        die(f"Exception tak terduga: {e}")
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        try:
            if pw is not None:
                pw.stop()
        except Exception:
            pass
        try:
            if '_cam' in globals() and _cam is not None:
                _cam.__exit__(None, None, None)
        except Exception:
            pass

if __name__ == "__main__":
    main()
