# 03 · Saklar Konfigurasi

File utama: `config.json`（disalin dari `config.example.json`）。

## Registrasi

| Field | Keterangan |
|------|------|
| `register_mode` | `browser` \| `hybrid` |

## Push 9router (opsional)

| Field | Keterangan |
|------|------|
| `nine_router_enabled` | push akun sukses ke 9router |
| `nine_router_base` | alamat 9router, mis. `http://host:20128` |
| `nine_router_password` | password dashboard 9router (default `123456` / env `INITIAL_PASSWORD`). Kosongkan jika `Require Login` di Settings 9router di-off |
| `nine_router_push_mode` | `device` (default) = alur device-flow `grok-cli` (simpan refresh token, koneksi awet) · `token` = push API-key `xai` (non-persisten, ±6 jam) |

Mode **`device`**: 9router membuat device code untuk `grok-cli`, tool men-approve consent dengan SSO hasil registrasi, lalu 9router menyimpan token OAuth + refresh → koneksi muncul di dashboard **Providers → Grok CLI** dan hidup terus (refresh otomatis). Mode **`token`**: fallback lama via `POST /api/providers` provider `xai` — koneksi tersimpan di Providers → xAI tapi tanpa refresh token.

Auth dashboard: jika 9router di-set **Require Login = off**, cukup `nine_router_base` — password boleh kosong. Jika **Require Login = on**, isi `nine_router_password`; tool login ke `/api/auth/login` lalu kirim cookie `auth_token`.

## CPA / OIDC

| Field | Keterangan |
|------|------|
| `cpa_export_enabled` | apakah mint setelah registrasi |
| `cpa_auth_dir` | default `./cpa_auths` |
| `cpa_prefer_protocol` | utamakan SSO HTTP device-flow |
| `cpa_protocol_only` | hanya protokol, gagal tidak fallback browser |
| `cpa_mint_gap_sec` | interval mint, cegah 429 |
| `cpa_proxy` | proxy khusus mint; kosong pakai proxy registrasi |
| `cpa_copy_to_hotload` / `cpa_hotload_dir` | salin ke direktori hot-load CLIProxy |

## Proxy

Registrasi pakai `proxy_mode` / `proxy`; mint bisa pakai `cpa_proxy` terpisah.
