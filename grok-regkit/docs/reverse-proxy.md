# Reverse Proxy dan CPA Gateway (deployment opsional)

Registrator hanya bertanggung jawab menghasilkan akun dan mint. **Menaruh 4.5 / kumpulan akun di internet** adalah urusan hilir. Direktori `deploy/` di repo ini menyediakan jalur referensi yang **dapat dibangun sendiri**, bukan syarat untuk menjalankan registrasi.

Keterangan kredensial lihat [sso-cpa/01-credentials.md](./sso-cpa/01-credentials.md).

## Arsitektur

```text
Klien (OpenAI SDK / curl)
    │  Authorization: Bearer cpa_xxx
    ▼
Nginx (TLS)  location /cpa/
    ▼
cpa-gateway :8318
    │  validasi kuota keys.json
    │  ganti dengan upstream API key CLIProxy
    ▼
CLIProxyAPI :8317
    │  hot-load xai-*.json (OIDC)
    ▼
Grok 4.5

Paralel (tidak terkait CPA):
  Registrasi → SSO → kumpulan akun / model reverse proxy Web
```

| Kredensial | Untuk di mana | Jangan |
|------|--------|------|
| Cookie SSO | kumpulan akun | jangan dijadikan Bearer CPA |
| `xai-*.json` | hanya hot-load ke CLIProxy | jangan dijadikan kunci API HTTP untuk pengguna akhir |
| `cpa_xxx` | hanya ke `/cpa/` publik | jangan dipakai ke kumpulan akun |
| Upstream key CLIProxy | hanya untuk gateway / debug lokal | jangan diekspos langsung ke semua klien |

## Yang Perlu Anda Siapkan

1. Mesin lokal atau VPS: Python 3.9+ (gateway hanya stdlib)
2. **CLIProxyAPI** yang sudah berjalan (contoh port `8317`), dan sudah memuat minimal satu `xai-*.json`
3. (Disarankan) domain + TLS + Nginx
4. `cpa_auths/xai-*.json` yang dihasilkan registrator (atau direktori hot-load)

## Langkah End-to-End

### 1. Registrasi dan mint

Lihat [README](../README.md) / [LOCAL_RUN.md](../LOCAL_RUN.md) di root repo.  
Pastikan `cpa_auths/xai-*.json` ada, lalu salin ke direktori auth CLIProxy (atau atur `cpa_hotload_dir`).

### 2. Verifikasi CLIProxy tersedia lokal

```bash
curl -sS http://127.0.0.1:8317/v1/models \
  -H "Authorization: Bearer YOUR_UPSTREAM_API_KEY"
```

### 3. Konfigurasi dan mulai cpa-gateway

```bash
cd grok-regkit
# lihat deploy/env.example
export CPA_GATEWAY_ROOT=/opt/cliproxyapi
export CPA_UPSTREAM=http://127.0.0.1:8317
export CPA_PUBLIC_BASE=https://api.example.com/cpa/v1

# Pertama kali tulis upstream key ke $CPA_GATEWAY_ROOT/keys.json:
# { "keys": {}, "upstream_api_key": "YOUR_UPSTREAM_API_KEY" }
# atau tulis di API_CREDENTIALS.txt di direktori yang sama: API Key: YOUR_UPSTREAM_API_KEY

python deploy/cpa_gateway.py serve
# mendengarkan di 0.0.0.0:8318
```

Template systemd: `deploy/cpa-gateway.service`.

### 4. Terbitkan kunci klien

```bash
python deploy/cpa_gateway.py add --name alice --quota 1000
# mencetak cpa_... dan contoh curl (base dari CPA_PUBLIC_BASE)
python deploy/cpa_gateway.py list
```

`quota=0` berarti tanpa batas. `disable` / `enable` / `set-quota` lihat `--help` skrip.

### 5. Nginx

Gabungkan `deploy/nginx-cpa.snippet.conf` ke `server` HTTPS Anda, arahkan `proxy_pass` ke gateway (Nginx host menggunakan `127.0.0.1:8318`; Nginx dalam container yang mengakses host biasanya `172.17.0.1:8318`).

Panel Web registrasi opsional: `deploy/nginx-register.snippet.conf` → `:8092`.

### 6. Panggilan klien

```bash
export BASE=https://api.example.com/cpa/v1
export KEY=cpa_YOUR_KEY

curl -sS "$BASE/models" -H "Authorization: Bearer $KEY"

curl -sS "$BASE/chat/completions" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"grok-4.5","messages":[{"role":"user","content":"hi"}]}'
```

```python
from openai import OpenAI
client = OpenAI(base_url="https://api.example.com/cpa/v1", api_key="cpa_YOUR_KEY")
print(client.chat.completions.create(
    model="grok-4.5",
    messages=[{"role": "user", "content": "hi"}],
))
```

## Perilaku Gateway

- **Multi-key + kuota permintaan**: tersimpan di `keys.json` (path ditentukan `CPA_GATEWAY_KEYS` / `CPA_GATEWAY_ROOT`).
- **Ganti kunci**: klien `cpa_xxx` → upstream `upstream_api_key` CLIProxy.
- **Stabilitas Chat**: untuk `/chat/completions` default diubah ke non-streaming lalu dibalas; jika klien meminta `stream:true`, gateway mungkin **memalsukan completion utuh sebagai SSE** (menghindari koneksi panjang terputus di CDN/Nginx). Untuk streaming upstream asli, ubah kode atau hubungkan langsung ke CLIProxy lokal.
- **Health check**: `GET /health` → `{"ok":true,"service":"cpa-gateway"}` (tanpa Bearer).

## Dengan Kumpulan Akun SSO

Kumpulan akun (mis. 9router) mengonsumsi **SSO**, modelnya jalur Web; **jangan** masukkan `cpa_xxx` atau OIDC ke kumpulan akun.  
Jalur CPA hanya melayani **OIDC → 4.5**. Lihat [sso-cpa](./sso-cpa/).

## Troubleshooting

| Gejala | Kemungkinan penyebab |
|------|----------|
| 401 invalid api key | kunci klien tidak ada di `keys.json` |
| 403 disabled | kunci di-`disable` |
| 429 quota exceeded | kuota habis, lakukan `set-quota` atau buat kunci baru |
| 503 upstream_api_key not configured | kunci asli CLIProxy belum dikonfigurasi |
| 502 upstream failed | CLIProxy belum jalan / port salah / tidak ada `xai-*.json` yang tersedia |
| models kosong atau chat gagal | mint belum sukses, akun tanpa izin 4.5, direktori hot-load salah |

## Keamanan

- Jangan commit `keys.json`, upstream key, `xai-*.json` ke git.
- Wajib TLS untuk internet publik; batasi akses admin ke `8317` (hanya lokal atau gateway).
- Implementasi referensi ini **tanpa** autentikasi UI admin; `add`/`list` bergantung pada izin shell Anda di server.
