# Keterangan Adaptasi Email Sekali Pakai

Registrator mengambil email = **buat alamat** + **polling kode verifikasi**.  
`email_provider` menentukan API mana yang digunakan; **browser / hybrid berbagi** pintu masuk yang sama (`get_email_and_token` / terima email).

---

## Yang Sudah Didukung Proyek Ini

| `email_provider` | Item konfigurasi | Keterangan |
|------------------|--------|------|
| `cloudflare` | `cloudflare_api_base`, opsional `cloudflare_api_key` / `cloudflare_auth_mode` | Worker kompatibel [Cloudflare Temp Email](https://github.com/dreamhunter2333/cloudflare_temp_email) (path dapat dikonfigurasi) |
| `litensi` | `litensi_api_id`, `litensi_api_key` | [Litensi Mail](https://litensi.id)：pesan akun + polling kode verifikasi |

Zona Litensi otomatis memilih zona stok termurah. Jika `litensi_zone` diisi, nilai itu dipakai langsung dan mengesampingkan pemilihan otomatis.

Tab Web console: Cloudflare / Litensi.

### Contoh Litensi

```json
"email_provider": "litensi",
"litensi_api_id": "your-id",
"litensi_api_key": "your-key",
"litensi_site": "x.ai"
```

### Contoh Cloudflare

```json
"email_provider": "cloudflare",
"cloudflare_api_base": "https://your-worker.example.com",
"cloudflare_auth_mode": "none",
"cloudflare_api_key": ""
```

Path default: `/api/domains`、`/api/new_address`、`/api/token`、`/api/mails`（dapat diubah di konfigurasi）。

---

## Referensi Adaptasi (stack email registrasi chatgpt2api)

Repo ini **saat ini belum sepenuhnya mengimplementasikan** tipe berikut; daftar ini berasal dari **daftar type dan pengalaman operasional** registrator ChatGPT lokal  
`chatgpt2api`（`services/register/mail_provider.py`），untuk memudahkan ekstensi atau pembandingan konfigurasi.

### Type yang sudah diimplementasikan pihak lain

| type（chatgpt2api） | Ringkasan kemampuan | Hubungan dengan proyek ini |
|---------------------|----------|----------------|
| `cloudflare_temp_email` | email sekali pakai CF Worker | ≈ `cloudflare` proyek ini |
| `yyds_mail` | YYDS buat akun + terima email | ≈ `yyds` proyek ini (sudah tidak diimplementasikan, referensi) |
| `gptmail` | GPTMail（kuota / public key dll.） | belum terhubung, bisa jadi referensi ekstensi |
| `moemail` | MoeMail | belum terhubung |
| `cloudmail_gen` | pembuatan mirip CloudMail | belum terhubung |
| `tempmail_lol` | Tempmail.lol | belum terhubung |
| `ddg_mail` | email alias DuckDuckGo | belum terhubung |
| `inbucket` | Inbucket self-hosted | belum terhubung |
| `outlook_token` | Outlook/Hotmail **OAuth refresh_token** baca email | belum terhubung; bisa jadi referensi modul terpisah |

### Poin operasional yang bisa dipelajari (saat mengimplementasikan provider baru)

| Pengalaman | Keterangan |
|------|------|
| **Daftar hitam domain YYDS** | domain yang timeout ambil kode masuk daftar hitam, hindari terus menginjak domain mati; bisa dipersist ke `yyds_domain_blacklist.json` |
| **Daftar putih YYDS** | domain sukses dicatat ke daftar putih, diutamakan |
| **Kumpulan token Outlook** | state machine `used` / `in_use` / `token_invalid` akun, cegah berebut email yang sama secara konkuren |
| **Alias Outlook** | `user+tag@outlook.com` terhubung dengan pemakaian akun utama |
| **Pisah proxy terima email** | proxy registrasi dan proxy "API tarik email" bisa dipisah（`mail_fetch_proxy`），hindari API email keluar lewat jalur yang salah |
| **Parsing OTP** | regex multi-jalur subject + HTML + plaintext; template email Grok/xAI mungkin berbeda dari OpenAI, saat ekstensi perlu tambah keyword |
| **Modul Outlook terpisah** | `outlook_mail_fetcher.py`：Graph / IMAP + XOAUTH2 + proxy, bisa disalin lalu dimodifikasi untuk dipasang di `email_provider=outlook` |

Keterangan khusus Outlook lihat di repo chatgpt2api: `outlook_mail_fetcher_README.md`（Graph + `Mail.Read` + `offline_access`）。

---

## Antarmuka yang Disarankan Saat Mengekstensi Email Baru

Selaraskan dengan cabang yang ada saja (secara konsep):

1. **create**：mengembalikan `(email_address, mail_token_or_session)`
2. **poll_code(email, token, timeout)**：tunggu sampai kode verifikasi xAI muncul atau timeout
3. Tambahkan satu item di `get_email_provider()` / tab Web / `config.example.json`

Ekstraksi kode verifikasi harus mencakup template email xAI (jangan hanya menyalin keyword OpenAI).

---

## Pintu Masuk Konfigurasi

| Lokasi | Fungsi |
|------|------|
| `config.json` → `email_provider` | backend saat ini |
| Web「Sumber Email」 | ganti Cloudflare / Litensi |
| `config.example.json` | template field |

browser dan hybrid **tidak perlu** memilih mode lagi untuk email.
