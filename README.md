# Multitek Service MVP v0.2.0

Platform marketplace servis mesin berbasis WhatsApp untuk Multitek Indonesia. Customer dapat berbicara natural, membuat permintaan servis untuk satu atau banyak mesin, membagikan lokasi, melihat beberapa kandidat mekanik, memilih mekanik, membayar biaya perjalanan awal, menerima quotation hasil diagnosis, dan mengonfirmasi hasil pekerjaan. Mekanik mendaftar melalui WhatsApp dengan skill matrix 18 bidang dan approval sederhana oleh owner.

## Status proyek

Versi ini adalah **MVP fresh-install** untuk pengujian operasional di VPS baru. Belum dimaksudkan sebagai marketplace publik skala besar.

Yang sudah tersedia:

- identifikasi OWNER / MEKANIK / CUSTOMER berdasarkan nomor WhatsApp dan database;
- customer tidak wajib mengetik `SERVIS`; AI opsional dapat merespons chat/pertanyaan secara natural lalu mengarahkan ke flow servis;
- service order multi-mesin;
- Share Location customer dan mekanik;
- konfirmasi lokasi sebelum matching dan sebelum mekanik berangkat;
- pendaftaran mekanik + selfie wajib + 18 skill matrix + 1 pertanyaan pada maksimal 3 top skill;
- approval mekanik sederhana oleh owner;
- mekanik `ONLINE` / `OFFLINE`;
- matching Top 3 berdasarkan skill coverage, radius, jarak, rating dan histori;
- jendela minat mekanik 10 menit;
- customer memilih mekanik dari profil (foto, pengalaman, skill, jarak, rating) tanpa nomor kontak;
- booking/travel fee murah berdasarkan jarak;
- pembayaran QRIS/transfer dengan verifikasi manual owner;
- tariff matrix per jenis mesin dan tingkat kesulitan;
- diagnosis dan quotation per mesin;
- mesin tambahan di lokasi harus diajukan melalui sistem dan disetujui customer;
- booking menjadi kredit/pengurang jasa ketika repair berhasil;
- pekerjaan tidak dapat diperbaiki wajib diagnosis + foto + video analisa;
- settlement sukses / tidak dapat diperbaiki tercatat, tetapi refund dan payout masih manual;
- PostgreSQL sebagai sumber kebenaran;
- GOWA, API, worker dan PostgreSQL berjalan dengan Docker Compose;
- webhook GOWA dilindungi HMAC secret;
- API dan GOWA hanya bind localhost VPS.

## Arsitektur

```text
Customer / Mekanik / Owner
          |
       WhatsApp
          |
          v
         GOWA
          |
          v
   FastAPI / Router
          |
   +------+------+----------------+
   |             |                |
Customer Flow  Matching       Finance/Owner
   |             |                |
   +-------------+----------------+
                 |
              PostgreSQL
                 |
              Worker
        (offer timeout 10m)
```

AI **bukan** pemegang transaksi. AI hanya membantu memahami bahasa customer dan membuat respons aman. Matching, harga, pembayaran, perubahan status, settlement, dan database tetap diputuskan oleh backend deterministik.

## Tarif MVP

Booking/travel fee default yang dapat diubah lewat `.env`:

- 0-5 km: Rp20.000
- >5-10 km: Rp30.000
- >10-20 km: Rp40.000
- >20-30 km: Rp50.000
- >30 km: owner menentukan manual

Booking adalah biaya minimum perjalanan/kunjungan dan menjadi **kredit terhadap jasa** jika pekerjaan berhasil.

Tarif jasa sebenarnya **tidak diisi dengan angka asumsi**. Semua tariff matrix awal bernilai `0` sampai owner mengaturnya:

```text
SET TARIF <skill_no> <INSPEKSI|RINGAN|SEDANG|BERAT> <nominal>
```

Contoh:

```text
SET TARIF 1 RINGAN 75000
SET TARIF 1 SEDANG 125000
```

`KHUSUS` / mesin kompleks dapat memakai quotation manual.

## Struktur project

```text
app/
  ai.py
  config.py
  customer.py
  db.py
  finance.py
  location.py
  main.py
  matching.py
  mechanic.py
  media.py
  onboarding.py
  orders.py
  owner.py
  pricing.py
  router.py
  schema.sql
  security.py
  skills.py
  state.py
  types.py
  wa.py
  worker.py

docs/
  INSTALLATION.md
  FLOW.md
  COMMANDS.md
  PRICING.md
  MECHANIC_SKILL_MATRIX.md

scripts/
  bootstrap_ubuntu.sh
  preflight.sh
  deploy.sh
  health.sh
  backup.sh
  gowa_create_device.sh
  gowa_login.sh
  gowa_status.sh
  add_technician.sh

tests/
```

## Instalasi

Panduan lengkap ada di:

```text
docs/INSTALLATION.md
```

Ringkasnya setelah source berada di `/opt/multitek-service`:

```bash
cd /opt/multitek-service
chmod +x scripts/*.sh
sudo ./scripts/bootstrap_ubuntu.sh
```

Login ulang setelah Docker terpasang, lalu:

```bash
cd /opt/multitek-service
cp .env.example .env
nano .env
./scripts/preflight.sh
docker compose pull
docker compose up -d --build
./scripts/health.sh
```

Setelah stack sehat:

```bash
./scripts/gowa_create_device.sh
```

Buat SSH tunnel dari PC untuk pairing:

```bash
ssh -L 3000:127.0.0.1:3000 multitek@IP_VPS
```

Buka `http://127.0.0.1:3000`, login ke GOWA, pilih device `multitek-main`, lalu scan QR menggunakan nomor WhatsApp pusat Multitek Service.

## GitHub workflow

Gunakan repository private.

```text
feature/* -> develop -> main -> VPS production
```

VPS sebaiknya memakai **read-only deploy key**. Setelah perubahan stabil masuk `main`:

```bash
cd /opt/multitek-service
git pull origin main
./scripts/deploy.sh
```

`.env`, data runtime, backup database, dan session WhatsApp tidak boleh masuk Git.

## Dokumen penting

- `docs/FLOW.md` — flow customer, matching, pembayaran, multi-mesin, diagnosis dan unrepairable.
- `docs/COMMANDS.md` — command owner, mekanik dan customer.
- `docs/PRICING.md` — konsep booking credit, tariff matrix, tagihan akhir dan settlement.
- `docs/MECHANIC_SKILL_MATRIX.md` — 18 bidang skill dan bank pertanyaan.
- `docs/INSTALLATION.md` — instalasi VPS + GitHub + pairing WhatsApp.

## Batas MVP yang disengaja

- **Fresh install**. Paket ini tidak menyediakan migrasi otomatis dari v0.1.x.
- Pembayaran diverifikasi manual owner dari mutasi/rekening.
- Refund dan payout teknisi masih dilakukan manual; sistem hanya mencatat settlement.
- Jarak matching memakai Haversine (garis lurus), belum road routing Google Maps/Mapbox.
- Share Location menggunakan koordinat/name/address yang diberikan WhatsApp/GOWA; belum memakai API reverse-geocoding eksternal.
- AI opsional. Jika `AI_ENABLED=false`, command dan keyword dasar tetap berjalan, tetapi respons customer tidak se-natural saat AI aktif.
- Tariff matrix jasa awalnya `0`; owner harus mengisi sesuai pengalaman lapangan Multitek.
- Jika satu order berisi sebagian item sukses dan sebagian tidak dapat diperbaiki, billing dilakukan per item. Skema 60/30/10 booking hanya dipakai ketika seluruh item order berakhir tidak dapat diperbaiki dan customer menyetujui hasilnya.
- GOWA adalah integrasi WhatsApp non-resmi. Untuk komersialisasi skala besar, evaluasi migrasi ke WhatsApp Business Platform resmi.

## Pengujian paket

Pada build v0.2.0:

```text
Python compile : PASS
Unit tests     : 15 passed
Shell syntax   : PASS
```

Pengujian live Docker + PostgreSQL + pairing GOWA tetap harus dilakukan di VPS karena environment build paket ini tidak memiliki daemon Docker/WhatsApp session nyata.

## Keamanan dasar

- `.env` di-ignore Git dan sebaiknya `chmod 600`.
- buat secret dengan `openssl rand -hex 32`;
- GOWA dan API hanya bind `127.0.0.1`;
- webhook divalidasi dengan HMAC secret;
- owner dikenali dari `OWNER_WA_NUMBER`;
- kontak mekanik tidak ditampilkan ketika customer memilih kandidat;
- AI tidak boleh mengonfirmasi pembayaran atau menentukan settlement;
- jangan gunakan `docker compose down -v` pada production karena dapat menghapus volume PostgreSQL/session.
