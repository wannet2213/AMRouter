# Catatan Pemeliharaan Open Source

Direktori ini adalah **snapshot terpilih yang telah disensor**, bukan mirror git dari repo privat `grok-register`.

## Sumber

| Pohon | Peran |
|----|------|
| `../grok-register` | Untuk privat/server (dapat berisi deploy) |
| `../grok-regkit` (direktori ini) | Paket open source untuk publik |

## Sinkronisasi dari repo privat

Jalankan di repo privat:

```bash
python scripts/export_to_regkit.py
python scripts/export_to_regkit.py --check-only
```

Skrip akan:

1. Menyalin browser / hybrid / protocol / cpa / web / scripts publik / tests sesuai daftar putih
2. Mengganti domain privat dan alamat intranet menjadi placeholder `127.0.0.1`
3. **Tidak menimpa** `README.md`、`LOCAL_RUN.md`、`config.example.json`、`docs/sso-cpa/` yang dipelihara di pohon ini

## Pemeriksaan sebelum rilis

- [ ] `export_to_regkit.py --check-only` lolos
- [ ] Tidak ada `config.json`, file akun, kunci asli
- [ ] `docs/sso-cpa` konsisten dengan kemampuan kode
- [ ] Setelah `pip install -r requirements.txt` lokal, uji smoke CLI/Web

## Yang jelas tidak termasuk

- Skrip privat `deploy/`
- Catatan percakapan operasional, domain produksi, kunci kumpulan akun asli
