"""Selenium-backed browser wrapper exposing a Playwright-like API.

Why: OpenRouter's Cloudflare Turnstile only passes when launched with the
SYSTEM firefox-esr binary on the real X display (:0). Playwright cannot drive
the system Firefox (it requires its own build / juggler protocol, which gets
flagged). Selenium uses Marionette, which firefox-esr supports natively, so we
wrap Selenium to look like Playwright's `page` object the signup script expects.
"""
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementNotInteractableException,
)
import time
import re


_FIREFOX_ESR = "/usr/lib/firefox-esr/firefox-esr"


def _locator(sel):
    """Translate a (subset of) Playwright CSS selector to a Selenium locator."""
    sel = sel.strip()
    # text=Something
    if sel.startswith("text="):
        txt = sel[len("text="):]
        return By.XPATH, f"//*[contains(normalize-space(.), {_xpath_str(txt)})]"
    # tag:has-text('X')
    m = re.match(r"^([a-zA-Z0-9\*]+):has-text\(\s*'([^']*)'\s*\)$", sel)
    if m:
        tag, txt = m.group(1), m.group(2)
        tag = "*" if tag == "*" else tag
        return By.XPATH, f"//{tag}[contains(normalize-space(.), {_xpath_str(txt)})]"
    # [role='button']:has-text('X')
    m = re.match(r"^\[([^\]]+)\]:has-text\(\s*'([^']*)'\s*\)$", sel)
    if m:
        attr, txt = m.group(1), m.group(2)
        # attr like role='button' or aria-label*='copy' i
        am = re.match(r"^([a-zA-Z\-]+)\*?=['\"]?([^'\"]*)['\"]?$", attr.strip())
        if am:
            name, val = am.group(1), am.group(2)
            return By.XPATH, f"//*[@{name}='{val}' and contains(normalize-space(.), {_xpath_str(txt)})]"
    # a[href*='x'] etc -> fall back to CSS
    return By.CSS_SELECTOR, sel


def _xpath_str(s):
    # escape single quotes for XPath string literal
    if "'" not in s:
        return f"'{s}'"
    return "concat('" + s.replace("'", "', \"'\", '") + "')"


class Page:
    def __init__(self, driver):
        self._d = driver
        self._wait = WebDriverWait(driver, 30)

    @property
    def title(self):
        return self._d.title

    @property
    def url(self):
        return self._d.current_url

    def goto(self, url, wait_until="domcontentloaded", timeout=30000):
        self._d.get(url)
        # Selenium waits for load by default; give a small settle
        time.sleep(1)
        return self

    def set_default_timeout(self, ms):
        self._wait = WebDriverWait(self._d, max(1, ms // 1000))

    def _find(self, sel, timeout=None):
        by, val = _locator(sel)
        w = WebDriverWait(self._d, (timeout or 30000) // 1000)
        return w.until(EC.presence_of_element_located((by, val)))

    def click(self, sel, timeout=5000, force=False):
        el = self._find(sel, timeout)
        if force:
            self._d.execute_script("arguments[0].click();", el)
        else:
            try:
                el.click()
            except ElementNotInteractableException:
                self._d.execute_script("arguments[0].click();", el)
        return el

    def fill(self, sel, text, timeout=5000):
        el = self._find(sel, timeout)
        el.clear()
        el.send_keys(text)
        return el

    def type(self, sel, text, timeout=5000):
        return self.fill(sel, text, timeout)

    def evaluate(self, js, *args):
        # Playwright passes a function body string; Selenium needs a full expression.
        # Our callers pass either a `() => {...}` arrow or a plain expression.
        body = js.strip()
        if body.startswith("() =>") or body.startswith("function"):
            expr = body[body.index("=>") + 2:].strip() if "=>" in body else body[body.index("{") if "{" in body else 0:]
            if expr.startswith("{"):
                expr = "(function() " + expr + ")()"
            else:
                expr = "(function(){ return (" + expr + "); })()"
            if args:
                return self._d.execute_script(expr, *args)
            return self._d.execute_script(expr)
        # already an expression
        if args:
            try:
                return self._d.execute_script("return (" + body + ")", *args)
            except Exception:
                return self._d.execute_script(body, *args)
        try:
            return self._d.execute_script("return (" + body + ")")
        except Exception:
            return self._d.execute_script(body)

    def screenshot(self, path):
        self._d.save_screenshot(path)

    def wait_for_load_state(self, state="load", timeout=30000):
        # Best-effort: just sleep a bit; Selenium already waits for load on get()
        time.sleep(min(3, timeout // 1000 if timeout else 1))
        return self

    def content(self):
        return self._d.page_source

    def quit(self):
        try:
            self._d.quit()
        except Exception:
            pass


def launch_selenium(display=":0"):
    """Launch system firefox-esr on the real X display (trusted by Cloudflare)."""
    opts = Options()
    opts.binary_location = _FIREFOX_ESR
    opts.add_argument("-new-instance")
    opts.add_argument(f"--display={display}")
    # headless would re-trigger Turnstile; we must run on the real display
    drv = webdriver.Firefox(options=opts)
    return Page(drv)
