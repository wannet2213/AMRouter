# grok-regkit

Mengubah **registrasi akun Grok** menjadi toolkit yang bisa dijalankan: otomatis menghasilkan akun, mendapatkan **SSO**, dan dapat mengekspor **OIDC (CPA `xai-*.json`)** untuk **Grok 4.5** gratis. Dilengkapi Web console, GUI, dan CLI.

**Posisi saat ini: registrator + ekspor kredensial** · dua mode (browser / protokol hibrida) · mint CPA protokol-utama

> **SSO ≠ OIDC.** Hanya SSO tidak bisa dijadikan kredensial Build 4.5. Lihat [sso-cpa/](./sso-cpa/).

---

## Fitur Unggulan

| Kemampuan | Keterangan |
|------|------|
| **Dua mode registrasi** | `browser` sepenuhnya browser demi stabilitas · `hybrid` RPC protokol + browser singkat ambil token demi kecepatan |
| **Lewati proteksi dengan browser asli** | Chromium mengumpulkan Turnstile / castle, mendekati lingkungan halaman registrasi asli |
| **SSO ke file** | `email----password----sso` ditulis ke `accounts_*.txt`, opsional tulis ke kumpulan akun |
| **CPA / OIDC satu jalur** | setelah sukses registrasi otomatis mint → `cpa_auths/xai-*.json` → hot-load CLIProxyAPI → **grok-4.5** |
| **Mint protokol-utama** | SSO HTTP device-flow diutamakan; bisa fallback browser saat gagal; interval dapat diatur untuk hindari 429 |
| **wrapper → session** | wrapper SSO umum hybrid dapat di-materialize menjadi session yang bisa dipakai |
| **Banyak pintu masuk** | Web console · GUI · CLI · skrip backfill |
| **Batas kredensial jelas** | dokumen dan pipeline membedakan kumpulan akun (SSO) dan 4.5 (OIDC), mengurangi campur kunci |

---

## Arsitektur

```text
Email sekali pakai + proxy
        │
        ▼
  grok-regkit  (browser | hybrid)
        │
        ▼
     SSO cookie
        │
   ┌────┴────┐
   ▼         ▼
 Kumpulan akun  CPA mint (OIDC)
 Model Web  xai-*.json → CLIProxyAPI → grok-4.5
```

| Tahap | Isi |
|------|------|
| Registrasi | `accounts.x.ai` kode verifikasi email + submit profil + lewati proteksi |
| SSO | set-cookie / materialize → sesi JWT |
| OIDC | device-flow atau konfirmasi browser → auth JSON lokal (pipeline `type=xai`) |
| Pasca-proses | opsional NSFW, masuk kumpulan akun, probe CPA |

---

## Daftar Fungsi

| Fungsi | Keterangan |
|------|------|
| Registrasi browser | UI sepanjang jalan: CF → email → kode verifikasi → buat akun → ambil SSO |
| Registrasi hybrid | browser hanya ambil castle / Turnstile; CreateEmail / Verify / create_user lewat protokol |
| Email sekali pakai | **Cloudflare Temp Email** · **Litensi** (ganti `email_provider`, berlaku browser/hybrid) |
| Proxy | langsung / proxy tetap / mode bandara; CPA mint dapat `cpa_proxy` terpisah |
| Ekspor SSO | `accounts_*.txt` / `accounts_hybrid_*.txt` |
| Integrasi kumpulan akun | dorong ke 9router (`POST /api/providers`) |
| Ekspor OIDC | `cpa_auths/xai-<email>.json` |
| Mint protokol | curl_cffi + SSO, diutamakan selesai tanpa browser |
| Mint browser | fallback jika protokol gagal dan ada password |
| Backfill akun lama | `scripts/backfill_cpa_xai_from_accounts.py` |
| Web console | ubah konfigurasi, mulai, lihat progres dan log |
| GUI / CLI | jendela lokal atau batch `--cli` |

---

## Mode Registrasi

| Mode | Konfigurasi | Karakteristik |
|------|------|------|
| **browser** | `"register_mode": "browser"` | Chromium penuh, proteksi dan status halaman lengkap, cocok untuk sehari-hari |
| **hybrid** | `"register_mode": "hybrid"` | browser singkat ambil token + protokol kirim permintaan bisnis, biasanya lebih cepat; SSO perlu diperhatikan konversi ke session |

Keduanya setelah sukses berbagi pasca-proses: simpan → (opsional) masuk kumpulan akun → (opsional) mint CPA.

### Seberapa Cepat Mode Hybrid?

Tidak ada angka tetap "N kali lebih cepat" — total waktu satu akun terutama ditentukan oleh **melewati proteksi, menerima kode verifikasi, kualitas proxy**, dan bagian yang tidak terkait mode hampir sama di keduanya.

Yang dihemat hybrid adalah bagian **klik halaman, isi form, tunggu perpindahan UI**:

| Tahap | browser | hybrid |
|------|---------|--------|
| Buka halaman registrasi / lewati CF | browser sepanjang jalan | browser tetap perlu dibuka (ambil token) |
| Submit email, kode verifikasi, buat akun | operasi halaman, banyak langkah, banyak tunggu | RPC protokol / Server Action, lebih singkat |
| Turnstile / castle | selesai di dalam halaman | browser ambil singkat, sisi bisnis membawa token |
| Pemakaian browser | menempel sepanjang siklus hidup akun | jendela lebih pendek, selesai ambil bisa langsung ditutup |

Perkiraan pengalaman (lingkungan normal, sekali sukses):

- **Browser penuh**: per akun umumnya lebih lama, langkah UI banyak, memori tinggi
- **Hybrid**: bagian bisnis jelas lebih pendek; total waktu sering berkurang (dalam banyak kasus sekitar **hemat 20%–40% wall-clock time**, selisih mengecil saat proteksi lambat)
- **Saat proteksi/email sangat lambat**: kedua mode tertahan, keunggulan hybrid terutama jadi "lebih sedikit klik halaman, lebih sedikit pakai browser"

Pasca-proses mint CPA sama untuk keduanya, tidak masuk hitungan "siapa lebih cepat".

### Kenapa Tidak Default "Protokol Murni"?

Protokol murni = semua permintaan registrasi via HTTP, Turnstile pakai **platform solver captcha** (seperti YesCaptcha createTask) untuk tukar token, bukan buka Chrome lokal.

Kami **default tidak pakai jalur ini**, terutama karena:

1. **Solver berbayar**
   Tiap akun, kadang tiap langkah, harus beli token; biaya batch membengkak; proyek ini mengutamakan **Chromium lokal lewati proteksi, tidak wajib bayar solver**.

2. **Perlu ikat akun pihak ketiga dan kuota**
   Kunci solver, saldo, antrean, kegagalan penyedia menjadi titik tunggal baru; jalur hybrid/browser hanya bergantung Chrome + proxy Anda sendiri.

3. **CF / risk control tidak hanya satu gerbang Turnstile**
   HTTP murni mengandalkan sidik jari TLS + token solver; saat ada blokir keras, butuh `cf_clearance` atau lingkungan halaman, jalur browser biasanya lebih tahan. Protokol murni bisa sangat cepat saat "solver sukses", tetapi saat gagal seluruh batch lebih mudah tumbang.

4. **Hybrid sudah memakan sebagian besar "kecepatan protokol"**
   Bisnis via protokol, proteksi via browser — **sedikit lebih cepat, dan tanpa bayar solver per akun**. Ini kompromi biaya dan tingkat sukses.

5. **Protokol murni bisa jadi opsi di masa depan, bukan satu-satunya default**
   Jika Anda punya solver sendiri, mengejar konkurensi ekstrem dan server lebih ringan, bisa tambah plugin `protocol` / YesCaptcha; jalur default tetap "nol biaya solver, akselerasi hybrid".

Ringkasnya: **hybrid = pakai protokol hemat waktu, pakai browser lokal hemat biaya solver; protokol murni = mungkin lebih cepat dan lebih ringan, tapi biaya solver per akun dan ketergantungan pihak ketiga adalah pintu keras.**

---

## Keterangan Kredensial

| Kredensial | Bentuk | Kegunaan |
|------|------|------|
| **SSO** | Cookie `sso` | kumpulan akun / model reverse proxy Web (mis. 4.20、4.3) |
| **OIDC** | `access_token` + `refresh_token` | CLIProxyAPI → **grok-4.5** |

```text
SSO  ──► kumpulan akun ──► Model Web
SSO  ──► mint ──► xai-*.json ──► CPA ──► 4.5
```

Saat memanggil jangan mencampur: Base kumpulan akun + Key kumpulan akun ≠ Base CPA + Key CPA.

---

## Mulai Cepat

```bash
cd grok-regkit
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
cp config.example.json config.json
# Edit: API email, proxy, register_mode, saklar CPA
```

### Web (disarankan)

```bash
# Linux tanpa desktop: export DISPLAY=:99  (Xvfb)
uvicorn web.server:app --host 127.0.0.1 --port 8092 --workers 1
```

Buka di browser: `http://127.0.0.1:8092`

### GUI / CLI

```bash
python grok_register_ttk.py
python grok_register_ttk.py --cli
```

### Konfigurasi Umum

| Field | Keterangan |
|------|------|
| `register_mode` | `browser` \| `hybrid` |
| `email_provider` | `cloudflare` \| `litensi` |
| `cloudflare_*` / `litensi_api_id` / `litensi_api_key` | kunci email terkait (lihat di bawah) |
| `proxy` / `proxy_mode` | proxy registrasi |
| `cpa_export_enabled` | apakah mint OIDC setelah registrasi |
| `cpa_prefer_protocol` | mint protokol diutamakan |
| `cpa_auth_dir` | default `./cpa_auths` |
| `cpa_mint_gap_sec` | interval mint, cegah rate-limit |

Field lengkap lihat [sso-cpa/03-config.md](./sso-cpa/03-config.md) dan `config.example.json`.

### Backend Email

| `email_provider` | Item konfigurasi | Keterangan |
|------------------|--------|------|
| `cloudflare` | `cloudflare_api_base`, opsional `cloudflare_api_key` / `cloudflare_auth_mode` | Worker kompatibel Cloudflare Temp Email |
| `litensi` | `litensi_api_id`, `litensi_api_key`, opsional `litensi_zone` / `litensi_site` | Litensi Mail (buat akun + polling kode verifikasi) |

Pilihan zona otomatis: zona stok termurah, atau `litensi_zone` yang diisi langsung dipakai.

browser / hybrid berbagi logika email yang sama. Web console punya dua tab terkait.

Keterangan lebih detail, serta referensi adaptasi terhadap stack email registrasi **chatgpt2api** (GPTMail / Outlook token / MoeMail / daftar hitam domain dll.), lihat:

→ [mail-providers.md](./mail-providers.md)

---

## Hasil

| Path | Isi |
|------|------|
| `accounts_*.txt` | akun sukses browser: `email----password----sso` |
| `accounts_hybrid_*.txt` | akun sukses hybrid |
| `cpa_auths/xai-<email>.json` | OIDC, untuk CLIProxyAPI |

File sensitif sudah di `.gitignore`, jangan di-commit.

Backfill OIDC untuk akun lama:

```bash
python scripts/backfill_cpa_xai_from_accounts.py
```

---

## Kebutuhan Lingkungan

- Python 3.9+ (disarankan 3.11 / 3.12)
- Chrome / Chromium
- Dapat mengakses `accounts.x.ai`, API email; gunakan proxy sesuai kebutuhan
- Server Linux disarankan **Xvfb + Chromium bertampilan** (lewati proteksi lebih stabil)

---

## Struktur Direktori

```text
grok-regkit/
  grok_register_ttk.py     # registrasi browser + penjadwalan tugas
  hybrid_register.py       # registrasi hybrid
  browser/                 # pengumpulan token
  protocol/                # sesi protokol / gRPC-web / alat SSO
  cpa_xai/  cpa_export.py  # OIDC mint dan tulis
  web/                     # konsol FastAPI
  scripts/                 # backfill dll.
  docs/sso-cpa/            # keterangan kredensial dan mode
  config.example.json
```

---

## Dokumentasi

| Dokumen | Isi |
|------|------|
| [sso-cpa/](./sso-cpa/) | SSO / OIDC, matriks mode, konfigurasi dan hasil |
| [mail-providers.md](./mail-providers.md) | email yang didukung + referensi adaptasi chatgpt2api |
| [../LOCAL_RUN.md](../LOCAL_RUN.md) | detail menjalankan lokal |
| [../OPEN_SOURCE.md](../OPEN_SOURCE.md) | pemeliharaan snapshot open source |
| [../SECURITY.md](../SECURITY.md) | kunci dan keamanan |
| [../NOTICE.md](../NOTICE.md) | batasan penggunaan |

---

## Keamanan dan Disclaimer

- Jangan commit `config.json`, file akun, `xai-*.json`, kunci proxy asli ke Git
- Web disarankan bind `127.0.0.1`; untuk akses jarak jauh setel kata sandi akses
- Kredensial yang diekspor setara kunci, simpan dengan baik
- **Hanya untuk riset, pengujian dan pembelajaran pribadi**; patuhi ketentuan layanan situs target dan hukum setempat
- Proyek ini **tidak ada hubungan resmi** dengan xAI / Grok; penyalahgunaan dapat menyebabkan akun atau IP diblokir, tanggung jawab sendiri

Lisensi: [MIT](../LICENSE) · Ketentuan: [NOTICE.md](../NOTICE.md)
