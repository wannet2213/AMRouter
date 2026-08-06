# grok-regkit

Toolkit Python untuk otomasi registrasi akun xAI/Grok melalui browser Chromium.
Proyek ini dijalankan melalui Web console.
Mode `hybrid` menggabungkan protokol dengan browser singkat untuk mengambil token
yang diperlukan.

> **Penting:** Proyek ini hanya untuk riset, pengujian, dan pembelajaran pribadi.
> Patuhi Terms of Service situs target dan hukum yang berlaku. Otomasi dapat
> menyebabkan akun atau IP dibatasi. Lihat [`NOTICE.md`](./NOTICE.md).

## Daftar Isi

- [Fitur](#fitur)
- [Cara Kerja](#cara-kerja)
- [Persyaratan](#persyaratan)
- [Instalasi](#instalasi)
- [Konfigurasi](#konfigurasi)
- [Menjalankan Web console](#menjalankan-web-console)
- [VPS Tanpa Chrome UI](#vps-tanpa-chrome-ui)
- [Output](#output)
- [Update](#update)
- [Stop dan Hapus](#stop-dan-hapus)
- [Troubleshooting](#troubleshooting)
- [Keamanan](#keamanan)
- [Dokumentasi](#dokumentasi)
- [Lisensi](#lisensi)

## Fitur

| Fitur              | Keterangan                                                                            |
| ------------------ | ------------------------------------------------------------------------------------- |
| Registrasi browser | Chromium digunakan sepanjang proses registrasi                                        |
| Registrasi hybrid  | Protokol digunakan untuk sebagian proses, browser tetap digunakan untuk token singkat |
| Email verifikasi   | Cloudflare Temp Email atau Litensi Mail                                               |
| SSO                | Menyimpan hasil dalam format `email----password----sso`                               |
| CPA/OIDC           | Opsional menghasilkan `cpa_auths/xai-*.json`                                          |
| Web console        | Panel FastAPI untuk menjalankan dan memantau job                                      |
| Web console        | Satu-satunya antarmuka untuk konfigurasi dan registrasi                               |

## Cara Kerja

```text
Email provider
      |
      v
accounts.x.ai melalui Chromium
      |
      v
SSO -> accounts_*.txt
      |
      v
CPA/OIDC opsional -> cpa_auths/xai-*.json
```

SSO dan OIDC adalah artefak yang berbeda. File SSO tidak otomatis dapat dipakai
sebagai kredensial CLIProxyAPI. Lihat [`docs/sso-cpa/`](./docs/sso-cpa/).

Mode registrasi diatur melalui `register_mode`:

| Nilai     | Keterangan                                                              |
| --------- | ----------------------------------------------------------------------- |
| `browser` | Browser digunakan sepanjang alur; biasanya paling kompatibel            |
| `hybrid`  | Protokol menangani sebagian alur; browser digunakan untuk token singkat |

## Persyaratan

- Python 3.9 atau lebih baru; Python 3.11/3.12 disarankan
- Google Chrome atau Chromium
- Akses jaringan ke `accounts.x.ai` dan email provider yang digunakan
- Proxy jika diperlukan oleh jaringan atau konfigurasi akun
- Linux VPS: `xvfb` disarankan agar Chromium berjalan tanpa desktop

Dependensi Python dikunci di [`requirements.txt`](./requirements.txt). Direktori
`deploy/` dan CLIProxyAPI tidak diperlukan untuk registrasi inti.

## Instalasi

### Linux/macOS

```bash
git clone <URL_REPOSITORY> grok-regkit-mibp
cd grok-regkit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp config.example.json config.json
```

Pasang Chrome/Chromium sesuai sistem operasi. Pada Debian/Ubuntu VPS:

```bash
sudo apt update
sudo apt install -y chromium xvfb
```

Nama paket Chromium dapat berbeda pada distro lain. Pastikan executable
`chromium`, `chromium-browser`, atau `google-chrome` tersedia di `PATH`.

### Windows

```powershell
git clone <URL_REPOSITORY> grok-regkit
cd grok-regkit
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy config.example.json config.json
```

Jika PowerShell menolak aktivasi, jalankan Python dari virtual environment
secara langsung, atau gunakan Command Prompt dengan `.venv\Scripts\activate.bat`.

### macOS dengan zsh

Karakter `?`, `*`, dan beberapa karakter wildcard lain diproses oleh zsh.
Contoh `zsh: no matches found: projek?` berarti shell menganggap `projek?`
sebagai pola file, bukan teks biasa. Gunakan tanda kutip:

```bash
printf '%s\n' 'projek?'
```

Untuk perintah instalasi di atas, gunakan path sebenarnya seperti `cd
grok-regkit`, tanpa tanda `?` di belakangnya.

## Konfigurasi

Salin [`config.example.json`](./config.example.json) menjadi `config.json`,
kemudian isi nilai sesuai layanan yang digunakan. File `config.json` tidak boleh
dimasukkan ke Git.

### Pengaturan utama

| Field                 | Nilai/contoh             | Keterangan                      |
| --------------------- | ------------------------ | ------------------------------- |
| `email_provider`      | `cloudflare` / `litensi` | Provider email verifikasi       |
| `register_mode`       | `browser` / `hybrid`     | Mode registrasi                 |
| `register_count`      | `1`                      | Jumlah akun pada satu job       |
| `proxy_mode`          | `direct`                 | Mode proxy registrasi           |
| `proxy`               | URL proxy                | Proxy jika diperlukan           |
| `cpa_export_enabled`  | `true`/`false`           | Aktifkan ekspor OIDC            |
| `cpa_auth_dir`        | `./cpa_auths`            | Folder output OIDC              |
| `cpa_prefer_protocol` | `true`/`false`           | Dahulukan mint melalui protokol |

### Cloudflare Temp Email

```json
{
  "email_provider": "cloudflare",
  "cloudflare_api_base": "https://your-worker.example.com",
  "cloudflare_auth_mode": "none",
  "cloudflare_api_key": "",
  "defaultDomains": "mail.example.com"
}
```

Path API dan mode autentikasi tambahan tersedia di
[`docs/mail-providers.md`](./docs/mail-providers.md).

### Litensi Mail

```json
{
  "email_provider": "litensi",
  "litensi_api_id": "your-id",
  "litensi_api_key": "your-key"
}
```

Jangan menaruh API key, password, token, cookie, atau hasil registrasi di dalam
source code atau repository publik.

## Menjalankan Web console

Aktifkan virtual environment setiap kali membuka shell baru:

```bash
source .venv/bin/activate
```

```bash
python -m uvicorn web.server:app --host 127.0.0.1 --port 8092 --workers 1
```

Buka `http://127.0.0.1:8092`. Pada VPS, akses melalui SSH tunnel atau reverse
proxy. Web console membaca `GROK_REGISTER_HOST`, `GROK_REGISTER_PORT`, dan
`GROK_REGISTER_ACCESS_PASSWORD` dari environment.

Contoh password akses:

```bash
export GROK_REGISTER_ACCESS_PASSWORD='ganti-dengan-password-kuat'
python -m uvicorn web.server:app --host 127.0.0.1 --port 8092 --workers 1
```

Registrasi hanya dijalankan melalui Web console. Entry point CLI dan GUI desktop
dinonaktifkan untuk mencegah konfigurasi terpisah atau error input terminal.

### Backfill OIDC

Untuk membuat OIDC dari akun yang sudah tersimpan:

```bash
python scripts/backfill_cpa_xai_from_accounts.py
```

Lihat opsi lengkap:

```bash
python scripts/backfill_cpa_xai_from_accounts.py --help
```

## Menjalankan di macOS

Pada macOS, gunakan mode headed agar Chromium dapat melewati browser challenge
Cloudflare/Turnstile dengan lebih baik. Chrome dapat terlihat di desktop.

```bash
unset GROK_REGISTER_HEADLESS
python -m uvicorn web.server:app --host 127.0.0.1 --port 8092 --workers 1
```

Alternatif eksplisit:

```bash
export GROK_REGISTER_HEADLESS=0
python -m uvicorn web.server:app --host 127.0.0.1 --port 8092 --workers 1
```

## VPS Tanpa Chrome UI

Pada Linux VPS tanpa desktop, gunakan **Xvfb**. Xvfb menyediakan display virtual
sehingga Chrome tetap berjalan dalam mode headed, tetapi tidak menampilkan UI
pada layar fisik VPS.

### Xvfb, disarankan

Xvfb menyediakan display virtual. Chrome tetap berjalan dalam mode headed,
tetapi tidak menampilkan UI pada layar fisik VPS.

```bash
sudo apt update
sudo apt install -y chromium xvfb
export GROK_REGISTER_HEADLESS=0
Xvfb :99 -screen 0 1280x900x24 >/tmp/grok-regkit-xvfb.log 2>&1 &
export DISPLAY=:99
python -m uvicorn web.server:app --host 127.0.0.1 --port 8092 --workers 1
```

Jalankan `uvicorn` setelah `DISPLAY` tersedia.
Kode registrator juga mencoba menyalakan Xvfb otomatis pada Linux ketika tidak
menemukan display. Xvfb umumnya lebih kompatibel dengan Cloudflare/Turnstile
daripada pure headless.

### Pure headless

Mode pure headless tersedia, tetapi **tidak disarankan** untuk alur yang
melewati Cloudflare/Turnstile. Cloudflare dapat menahan browser challenge dan
registrasi tidak akan lanjut.

```bash
export GROK_REGISTER_HEADLESS=1
python -m uvicorn web.server:app --host 127.0.0.1 --port 8092 --workers 1
```

Gunakan mode ini hanya jika target tidak memerlukan browser challenge
interaktif. Jika muncul log berikut, ganti ke Xvfb:

```text
headless browser, CF pass rate is low
Cloudflare challenge page detected
```

Jangan mengaktifkan `GROK_REGISTER_HEADLESS=1` bersamaan dengan Xvfb. Untuk VPS
yang membutuhkan kompatibilitas Cloudflare, gunakan:

```bash
export GROK_REGISTER_HEADLESS=0
export DISPLAY=:99
```

## Output

| Path                    | Isi                                             |
| ----------------------- | ----------------------------------------------- |
| `accounts_*.txt`        | Email, password, dan SSO dengan pemisah `----`  |
| `accounts_hybrid_*.txt` | Output akun dari mode hybrid bila digunakan     |
| `mail_credentials.txt`  | Kredensial mailbox runtime; rahasiakan file ini |
| `cpa_auths/xai-*.json`  | Kredensial OIDC untuk CLIProxyAPI               |
| `.chrome-data/`         | Data runtime Chromium                           |

## Update

Simpan atau backup konfigurasi dan hasil penting terlebih dahulu. Kemudian:

```bash
cd grok-regkit
source .venv/bin/activate
git status --short
git pull --ff-only
python -m pip install -r requirements.txt
```

Jika `git pull --ff-only` berhenti karena ada perubahan lokal, jangan hapus
perubahan tersebut secara paksa. Simpan atau review perubahan dengan `git diff`,
lalu selesaikan sesuai kebutuhan.

Setelah update, jalankan kembali proses menggunakan perintah pada bagian
[Menjalankan Web console](#menjalankan-web-console). Proses yang sedang berjalan tidak otomatis
direstart oleh `git pull`.

## Stop dan Hapus

### Menghentikan proses

- Web console: hentikan proses `uvicorn` dengan `Ctrl+C` pada terminalnya.
- Xvfb: cari PID lalu hentikan prosesnya jika tidak lagi digunakan.

```bash
ps aux | grep '[X]vfb :99'
kill <PID_XVFB>
```

Jangan membunuh proses berdasarkan tebakan PID. Periksa dahulu command line
proses yang ditampilkan.

### Menghapus data runtime saja

Perintah berikut menghapus cache browser dan output sensitif. Pastikan file
tersebut sudah tidak dibutuhkan:

```bash
rm -rf .chrome-data cpa_auths/*.json accounts_*.txt mail_credentials.txt
```

### Menghapus instalasi proyek

Hentikan semua proses proyek, keluar dari direktori proyek, lalu hapus folder
proyek jika memang ingin menghapus seluruh source dan virtual environment:

```bash
cd ..
rm -rf grok-regkit
```

Sesuaikan `grok-regkit` dengan nama folder sebenarnya. `rm -rf` bersifat
permanen; pastikan path dengan `pwd` dan `ls` sebelum menjalankannya.

## Troubleshooting

### `zsh: no matches found`

zsh menemukan wildcard yang tidak cocok dengan nama file. Periksa typo dan
gunakan quote untuk teks yang memang mengandung wildcard, misalnya
`'projek?'`. Jangan menambahkan `?` ke nama direktori kecuali itu memang bagian
dari namanya.

### `No Tkinter in this environment`

Gunakan Web console di server. Tkinter tidak diperlukan.

### Browser tidak dapat dimulai

Periksa Chromium dan display:

```bash
command -v chromium || command -v chromium-browser || command -v google-chrome
echo "$DISPLAY"
```

Di VPS, pasang Xvfb atau gunakan `GROK_REGISTER_HEADLESS=1`.

### Cloudflare/Turnstile gagal

Gunakan Xvfb dengan `GROK_REGISTER_HEADLESS=0`, pastikan waktu sistem benar,
dan gunakan koneksi/proxy yang stabil. Pure headless dapat menurunkan tingkat
keberhasilan pada proteksi browser.

### Web console tidak bisa dibuka dari komputer lain

Default server hanya listen pada `127.0.0.1`. Gunakan SSH tunnel atau reverse
proxy yang aman. Hindari membuka port aplikasi langsung ke internet tanpa
autentikasi dan TLS.

## Keamanan

File berikut berisi data sensitif dan sudah diabaikan oleh `.gitignore`:

- `config.json`
- `mail_credentials.txt`
- `accounts_*.txt`
- `cpa_auths/*.json`
- `*.key`, `*.pem`, dan file secret

Periksa status Git sebelum commit:

```bash
git status --short --ignored
git diff --cached --name-only
```

Jika credential pernah terlanjur dibagikan, segera rotasi atau hapus credential
tersebut. Menambahkan file ke `.gitignore` tidak menghapusnya dari history Git.

## CLIProxyAPI dan Reverse Proxy

Integrasi CPA bersifat opsional dan tidak diperlukan untuk menjalankan
registrasi. Setelah `cpa_auths/xai-*.json` tersedia, lihat:

- [`deploy/setup-cliproxyapi.md`](./deploy/setup-cliproxyapi.md) untuk checklist CPA
- [`docs/reverse-proxy.md`](./docs/reverse-proxy.md) untuk Nginx dan gateway
- [`deploy/README.md`](./deploy/README.md) untuk daftar file deployment

Jangan menyamakan SSO, file OIDC, upstream API key, dan key `cpa_xxx`; semuanya
memiliki fungsi dan tingkat akses yang berbeda.

## Struktur Direktori

```text
grok-regkit/
├── grok_register_ttk.py       # engine registrasi browser
├── hybrid_register.py         # mode registrasi hybrid
├── browser/                   # browser/token helper
├── protocol/                  # protokol dan sesi
├── cpa_xai/                   # mint OIDC
├── web/                       # Web console FastAPI
├── scripts/                   # utilitas backfill/export
├── deploy/                    # gateway dan template reverse proxy opsional
├── docs/                      # dokumentasi tambahan
├── config.example.json        # template konfigurasi
└── requirements.txt           # dependency Python
```

## Dokumentasi

| Dokumen                                              | Isi                           |
| ---------------------------------------------------- | ----------------------------- |
| [`docs/pengenalan.md`](./docs/pengenalan.md)         | Penjelasan fitur dan mode     |
| [`docs/mail-providers.md`](./docs/mail-providers.md) | Provider email dan path API   |
| [`docs/sso-cpa/`](./docs/sso-cpa/)                   | Perbedaan SSO dan OIDC        |
| [`docs/reverse-proxy.md`](./docs/reverse-proxy.md)   | Reverse proxy dan CPA gateway |
| [`LOCAL_RUN.md`](./LOCAL_RUN.md)                     | Menjalankan secara lokal      |
| [`SECURITY.md`](./SECURITY.md)                       | Panduan keamanan              |
| [`NOTICE.md`](./NOTICE.md)                           | Batasan penggunaan            |

## Lisensi

Proyek ini menggunakan [MIT License](./LICENSE).

Proyek ini tidak memiliki hubungan resmi dengan xAI atau Grok. Penggunaan
otomasi, proxy, email provider, dan kredensial akun menjadi tanggung jawab
pengguna.
