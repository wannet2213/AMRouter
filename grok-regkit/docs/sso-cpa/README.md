# Ringkasan Adaptasi SSO / CPA

Direktori ini menjelaskan **grok-regkit** setelah registrasi sukses bagaimana menghubungkan dua jalur hilir.

```text
Registrasi (browser | hybrid)
        │
        ▼
   SSO cookie
        │
   ┌────┴────┐
   ▼         ▼
 Kumpulan akun g2a   CPA mint (OIDC)
 Model Web   xai-*.json → CLIProxyAPI → grok-4.5
```

| Dokumen | Isi |
|------|------|
| [01-credentials.md](./01-credentials.md) | SSO ≠ OIDC；session / wrapper |
| [02-mode-matrix.md](./02-mode-matrix.md) | matriks adaptasi browser / hybrid |
| [03-config.md](./03-config.md) | item konfigurasi terkait |
| [04-outputs.md](./04-outputs.md) | path hasil dan catatan pemanggilan |

## Kesimpulan 30 Detik

| Kredensial | Kegunaan | Siapa yang menghasilkan |
|------|------|--------|
| **SSO** | sesi web / kumpulan akun | alur utama registrasi (dua mode) |
| **OIDC** | 4.5 gratis | **mint kedua** setelah registrasi（protokol utama，fallback browser） |

Dua `register_mode` hanya menentukan **bagaimana mendapatkan SSO**; CPA adalah pasca-proses yang sama.
