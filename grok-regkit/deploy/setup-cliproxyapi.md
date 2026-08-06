# CLIProxyAPI (CPA) — catatan instalasi (contoh)

Ini adalah checklist **umum**. Gunakan dokumentasi resmi CLIProxyAPI / Cliproxy untuk biner yang Anda pilih. Path di bawah hanya contoh.

## Tujuan

- Mendengarkan API kompatibel OpenAI di `127.0.0.1:8317` (atau pilihan Anda).
- Memuat file OIDC secara hot: `xai-*.json` yang dihasilkan oleh grok-regkit (`cpa_auths/`).
- Mengekspos satu kunci API **upstream** (ditulis mis. ke `API_CREDENTIALS.txt` atau konfigurasi Anda).

## Langkah (garis besar)

1. Instal CLIProxyAPI di server (Docker atau biner).
2. Arahkan **direktori auth** ke folder yang menerima `xai-*.json`
   - Salin dari `cpa_auths/` registrasi
   - Atau atur `cpa_copy_to_hotload` + `cpa_hotload_dir` registrasi ke folder tersebut.
3. Verifikasi lokal:

```bash
curl -sS http://127.0.0.1:8317/v1/models \
  -H "Authorization: Bearer YOUR_UPSTREAM_API_KEY"
```

4. Letakkan **cpa-gateway** di depan (opsional tetapi disarankan untuk kunci multi-pengguna):

```bash
export CPA_GATEWAY_ROOT=/opt/cliproxyapi   # keys.json berada di sini
export CPA_UPSTREAM=http://127.0.0.1:8317
# Letakkan upstream key ke keys.json sebagai "upstream_api_key", atau simpan di API_CREDENTIALS.txt dengan "API Key: ..."
python deploy/cpa_gateway.py serve
```

5. Nginx: lihat `nginx-cpa.snippet.conf` dan [docs/reverse-proxy.md](../docs/reverse-proxy.md).

## Pengingat Kredensial

| Artefak | Peran |
|----------|------|
| `xai-*.json` | OIDC akun agar CPA dapat memanggil Grok 4.5 |
| Kunci API upstream | Satu kunci yang diharapkan CLIProxy pada `/v1/*` |
| Kunci `cpa_xxx` | Diterbitkan oleh **cpa-gateway** untuk klien; tidak pernah sama dengan SSO |
