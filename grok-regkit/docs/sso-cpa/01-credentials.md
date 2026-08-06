# 01 · Kredensial dan Hilir

## Dua Kredensial

| Tipe | Bentuk | Kegunaan |
|------|------|------|
| **SSO** | Cookie `sso` / `sso-rw` | reverse proxy Web kumpulan akun (4.20 / 4.3 dll.) |
| **OIDC** | `access_token` + `refresh_token`（`xai-*.json`） | CLIProxyAPI → grok-4.5 |

### Subtipe SSO

| Tipe | Karakteristik | Kumpulan akun | Mint CPA protokol |
|------|------|------|----------------|
| **session SSO** | JWT lebih pendek, bukan wrapper set-cookie | cocok | cocok |
| **wrapper SSO** | payload berisi `config.success_url`, sering sangat panjang | tidak stabil | perlu materialize dulu |

Registrasi protokol hybrid sering pertama kali mendapatkan wrapper; ubah ke session dulu sebelum simpan / masuk kumpulan akun / mint.

## Hilir

| Hilir | Mengonsumsi apa | Model |
|------|--------|------|
| Kumpulan akun (9router / gateway lain) | SSO | model jalur Web |
| CLIProxyAPI (CPA) | `xai-*.json` | grok-4.5 |

## Jangan Mencampur

- Pakai SSO sebagai Bearer CPA → salah
- Pakai kunci CPA ke kumpulan akun → salah
- Registrasi sukses ≠ 4.5 tersedia (masih perlu mint + muat CPA)
- Ekspor OIDC gratis sukses ≠ pasti bisa chat (izin upstream tidak dijamin)

Mengekspos CLIProxy / gateway kuota multi-key ke publik: lihat [docs/reverse-proxy.md](../reverse-proxy.md) dan [deploy/](../../deploy/).
