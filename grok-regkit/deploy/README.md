# deploy/ — pembantu reverse proxy opsional

Direktori ini **tidak** diperlukan untuk menjalankan registrasi.  
Ini adalah **referensi** untuk menempatkan CLIProxyAPI (dan opsional Web UI registrasi) di belakang Nginx dengan kuota multi-key.

**Mulai dari sini:** [docs/reverse-proxy.md](../docs/reverse-proxy.md)

| File | Tujuan |
|------|---------|
| `cpa_gateway.py` | Gateway multi-key + kuota permintaan di depan CLIProxyAPI |
| `cpa-gateway.service` | Template unit systemd |
| `nginx-cpa.snippet.conf` | Nginx `location /cpa/` |
| `nginx-register.snippet.conf` | Nginx untuk Web console `:8092` |
| `env.example` | Variabel lingkungan |
| `setup-cliproxyapi.md` | Catatan instalasi CLIProxy tingkat tinggi |

Path inti registrasi **tidak** mengimpor file-file ini.
