# 04 · Hasil dan Pemanggilan

## File

| Path | Isi |
|------|------|
| `accounts_*.txt` / `accounts_hybrid_*.txt` | `email----password----sso` |
| `cpa_auths/xai-<email>.json` | OIDC, untuk CLIProxyAPI |

## Pemanggilan (Jangan Campur Key)

| Jalur | Contoh Base | Key | Model |
|----|-----------|-----|-------|
| Kumpulan akun SSO | `https://<host>/v1` | api_key kumpulan akun | `grok-4.20-fast` dll. |
| CPA 4.5 | `https://<host>/cpa/v1` atau CPA lokal `/v1` | api-keys CPA | `grok-4.5` |

## Cek Cepat Gangguan

| Gejala | Prioritaskan cek |
|------|--------|
| Ada akun tanpa 4.5 | apakah sudah mint; apakah json masuk direktori hot-load CPA |
| mint protokol gagal | apakah SSO wrapper; cookie jar |
| mint 429 | perbesar `cpa_mint_gap_sec` |
| hybrid tanpa sso | castle / turnstile / next-action |
| probe tanpa grok-4.5 | izin gratis tidak dijamin |
