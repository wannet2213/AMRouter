# Menjalankan di Mesin Lokal

```bash
cd grok-regkit
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json
```

Edit `config.json`:

1. Email: `email_provider` + kunci Cloudflare/Litensi dll.
2. Proxy: `proxy_mode` / `proxy`
3. Mode: `register_mode` = `browser` atau `hybrid`
4. CPA: default `cpa_export_enabled=true`, hasil di `cpa_auths/`

Menjalankan:

```bash
# Web
uvicorn web.server:app --host 127.0.0.1 --port 8092

# CLI (tetap akan memulai Chromium)
python grok_register_ttk.py --cli
```

Variabel lingkungan opsional (akses Web):

```text
GROK_REGISTER_ACCESS_PASSWORD=   # kata sandi akses Web, kosong = tanpa autentikasi
```

Backfill OIDC untuk akun lama:

```bash
python scripts/backfill_cpa_xai_from_accounts.py
```

Keterangan kredensial: [docs/sso-cpa/](./docs/sso-cpa/).
