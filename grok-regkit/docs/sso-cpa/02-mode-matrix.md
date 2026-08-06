# 02 · Matriks Adaptasi Mode Registrasi

`register_mode`: `browser` | `hybrid`

## Tabel Lengkap

| Kemampuan | browser | hybrid |
|------|---------|--------|
| Jalur utama | UI Chromium sepanjang jalan | browser singkat ambil castle/turnstile + RPC protokol/Server Action |
| Menghasilkan session SSO | biasanya langsung | sering perlu materialize |
| SSO → kumpulan akun | adaptasi | adaptasi (setelah session) |
| SSO → mint protokol CPA | adaptasi | adaptasi (session + sebisa mungkin cookie jar lengkap) |
| Fallback mint browser CPA | adaptasi | adaptasi (dengan password) |
| Kecepatan / sumber daya | lambat、makan memori | lebih cepat，tetap bergantung browser lewati CF |

## Pasca-Proses (Berbagi)

```text
simpan SSO
  → opsional NSFW
  → opsional masuk kumpulan akun
  → mint CPA（prefer protocol → browser fallback）
```

## Rekomendasi

| Skenario | Mode | CPA |
|------|------|-----|
| Ingin stabil | browser | prefer protocol, izinkan fallback browser |
| Ingin cepat | hybrid | sama seperti di atas; pastikan session SSO |
| Hanya mint protokol | pilih bebas | `cpa_protocol_only=true`（wajib session SSO） |
| Peak hanya produksi akun | pilih bebas | bisa matikan `cpa_export_enabled`, backfill nanti |
