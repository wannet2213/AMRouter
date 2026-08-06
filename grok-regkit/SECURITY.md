# Keamanan

## Jangan commit

- `config.json` / `.env` dengan kunci asli
- `accounts_*.txt`, cookie, profil Chrome
- `cpa_auths/xai-*.json` (token OIDC)
- Proxy privat, kunci API email, kunci admin kumpulan akun

## Laporkan masalah

Buka GitHub Issue **tanpa** menempel token, cookie, atau kata sandi akun.  
Redaksi email jika perlu (`a***@example.com`).

## Tips saat runtime

- Ikat Web UI ke `127.0.0.1` kecuali berada di belakang autentikasi
- Untuk akses jarak jauh, utamakan env `GROK_REGISTER_ACCESS_PASSWORD`
- Perlakukan SSO / OIDC yang diekspor sebagai rahasia
