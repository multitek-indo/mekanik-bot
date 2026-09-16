# Instalasi Multitek Service MVP v0.2.0 di VPS Ubuntu 24.04

Panduan ini mengasumsikan Ubuntu Server 24.04 baru selesai di-install.

## 1. Update Ubuntu

Login sebagai root:

```bash
ssh root@IP_VPS
apt update && apt upgrade -y
apt install -y sudo git curl nano unzip openssl
```

## 2. Buat user aplikasi

```bash
adduser multitek
usermod -aG sudo multitek
```

Salin public key SSH Anda ke `/home/multitek/.ssh/authorized_keys` bila menggunakan key login, lalu login ulang:

```bash
ssh multitek@IP_VPS
```

## 3. Repository GitHub private

Di GitHub buat repository private, contoh:

```text
multitek-service
```

### Dari PC development

Extract source ke folder project, lalu:

```bash
git init
git branch -M main
git add .
git status
git commit -m "Initial Multitek Service MVP v0.2.0"
git remote add origin git@github.com:USERNAME/multitek-service.git
git push -u origin main
```

Pastikan `.env`, `data/`, `backups/`, database dump, dan session WhatsApp tidak masuk commit.

### Deploy key VPS

Pada VPS sebagai `multitek`:

```bash
ssh-keygen -t ed25519 -C "multitek-service-production"
cat ~/.ssh/id_ed25519.pub
```

Copy public key tersebut ke GitHub repository:

```text
Settings -> Deploy keys -> Add deploy key
```

Gunakan read-only; tidak perlu mengaktifkan write access.

Test:

```bash
ssh -T git@github.com
```

## 4. Clone project

```bash
sudo mkdir -p /opt/multitek-service
sudo chown multitek:multitek /opt/multitek-service
git clone git@github.com:USERNAME/multitek-service.git /opt/multitek-service
cd /opt/multitek-service
```

## 5. Install Docker + firewall

```bash
chmod +x scripts/*.sh
sudo ./scripts/bootstrap_ubuntu.sh
```

Script memasang Docker Engine + Compose plugin dan mengaktifkan UFW dengan hanya SSH terbuka. API dan GOWA hanya bind ke `127.0.0.1`.

Logout/login sekali agar group Docker aktif:

```bash
exit
ssh multitek@IP_VPS
```

Test:

```bash
docker ps
docker compose version
```

## 6. Konfigurasi `.env`

```bash
cd /opt/multitek-service
cp .env.example .env
nano .env
```

Buat secret hex agar aman saat di-source shell:

```bash
openssl rand -hex 32
```

Isi minimal:

```env
POSTGRES_PASSWORD=<hex-random>
DATABASE_URL=postgresql://multitek:<PASSWORD_SAMA>@db:5432/multitek_service
OWNER_WA_NUMBER=628xxxxxxxxxx
OWNER_API_TOKEN=<hex-random>
GOWA_BASIC_AUTH_PASSWORD=<hex-random>
GOWA_WEBHOOK_SECRET=<hex-random>
PAYMENT_BANK_NAME=BCA
PAYMENT_BANK_ACCOUNT=xxxxxxxxxx
PAYMENT_BANK_HOLDER="MULTITEK INDONESIA"
```

`POSTGRES_PASSWORD` dan password di `DATABASE_URL` harus sama.

### AI customer service

Tanpa AI, router fallback tetap bisa mendeteksi keyword dasar. Untuk respons/intake yang lebih natural, aktifkan provider OpenAI-compatible:

```env
AI_ENABLED=true
AI_BASE_URL=https://api.groq.com/openai/v1
AI_API_KEY=<api-key>
AI_MODEL=openai/gpt-oss-20b
```

AI hanya mengklasifikasikan maksud dan mengekstrak draft; pembayaran, status, harga, matching, serta database tetap divalidasi backend.

### QRIS

Simpan QRIS statis Anda:

```bash
mkdir -p data
# upload/copy QRIS ke:
data/qris.png
```

Path container tetap:

```env
QRIS_IMAGE_PATH=/app/data/qris.png
```

Lindungi `.env`:

```bash
chmod 600 .env
git check-ignore .env
```

## 7. Preflight

```bash
cd /opt/multitek-service
./scripts/preflight.sh
```

Target:

```text
PREFLIGHT OK
```

## 8. Start stack

```bash
docker compose pull
docker compose up -d --build
```

Cek:

```bash
docker compose ps
./scripts/health.sh
```

Container utama:

```text
db
api
worker
gowa
```

## 9. Buat GOWA device slot

```bash
./scripts/gowa_create_device.sh
```

Device ID harus sama dengan:

```env
GOWA_DEVICE_ID=multitek-main
```

## 10. Pair WhatsApp

Cara paling aman: UI GOWA tetap hanya di localhost VPS.

Dari PC:

```bash
ssh -L 3000:127.0.0.1:3000 multitek@IP_VPS
```

Buka browser:

```text
http://127.0.0.1:3000
```

Login dengan `GOWA_BASIC_AUTH_USER` dan `GOWA_BASIC_AUTH_PASSWORD`, pilih device `multitek-main`, lalu scan QR menggunakan nomor WhatsApp pusat Multitek Service.

Alternatif untuk melihat response login dari terminal:

```bash
./scripts/gowa_login.sh
```

Status:

```bash
./scripts/gowa_status.sh
```

## 11. Test owner

Dari nomor yang sama dengan `OWNER_WA_NUMBER`, kirim ke chatbot:

```text
OWNER
```

Bot harus menampilkan command owner.

## 12. Test pendaftaran mekanik

Dari nomor berbeda:

```text
DAFTAR MEKANIK
```

Ikuti:

- nama
- domisili
- Share Location basis
- radius
- pengalaman
- kendaraan
- selfie
- 18 skill
- top 3
- pertanyaan verifikasi

Owner:

```text
CALON MEKANIK
DETAIL MEKANIK MKN-...
SETUJUI MEKANIK MKN-...
```

Setelah approved, mekanik:

```text
ONLINE
```

lalu Share Location saat ini.

## 13. Isi tariff matrix

Tarif jasa sengaja 0 pada instalasi awal. Contoh pengisian:

```text
SET TARIF 1 INSPEKSI 30000
SET TARIF 1 RINGAN 75000
SET TARIF 1 SEDANG 125000
SET TARIF 1 BERAT 200000
```

Gunakan angka aktual Multitek, bukan contoh di atas, ketika production.

Lihat matrix:

```text
TARIF
```

## 14. Test customer end-to-end

Dari nomor ketiga, customer cukup menulis natural:

```text
Mas, mesin obras saya suara kasar dan benangnya sering putus. Bisa dibantu?
```

Ikuti intake sampai Share Location. Setelah mekanik berminat dan customer memilih, customer mendapat rekening + QRIS, mengirim screenshot pembayaran, lalu owner memverifikasi:

```text
KONFIRMASI BAYAR MTK-...
```

Customer mengonfirmasi lokasi final:

```text
LOKASI BENAR MTK-...
```

Mekanik:

```text
BERANGKAT MTK-...
SAMPAI MTK-...
DIAGNOSIS MTK-... 1
```

Setelah repair:

```text
SELESAI ITEM MTK-... 1
SELESAI MTK-...
```

Jika ada pelunasan, customer kirim bukti dan owner:

```text
KONFIRMASI PELUNASAN MTK-...
```

Customer:

```text
KONFIRMASI SELESAI MTK-...
```

Owner:

```text
SETUJUI SETTLEMENT MTK-...
PAYOUT MTK-...
```

## 15. Backup sebelum update

```bash
cd /opt/multitek-service
./scripts/backup.sh
```

Jangan menjalankan:

```bash
docker compose down -v
```

karena `-v` dapat menghapus volume PostgreSQL dan session WhatsApp.

## 16. Deploy update dari GitHub

Di PC:

```bash
git checkout -b feature/nama-fitur
# edit + test
git add .
git commit -m "feat: nama fitur"
git push -u origin feature/nama-fitur
```

Gabungkan ke `develop`, test, lalu ke `main`.

Di production VPS:

```bash
cd /opt/multitek-service
git status
./scripts/backup.sh
git pull --ff-only origin main
./scripts/deploy.sh
```

Jika `git status` menunjukkan perubahan source di production, jangan pull sebelum perubahan tersebut diperiksa. Production sebaiknya tidak digunakan untuk edit source langsung.

## 17. Log troubleshooting

```bash
docker compose ps
docker compose logs --since 30m --tail 200 api
docker compose logs --since 30m --tail 200 worker
docker compose logs --since 30m --tail 200 gowa
docker compose logs --since 30m --tail 200 db
```

Health:

```bash
./scripts/health.sh
./scripts/gowa_status.sh
```
