# Panduan Lengkap Editing Multitek Service Melalui GitHub

**Project:** Multitek Service / `mekanik-bot`  
**Repository:** `multitek-indo/mekanik-bot`  
**Branch utama:** `main`  
**Versi checkpoint saat panduan dibuat:** `0.3.0-beta.1`

---

## 1. Tujuan Panduan

Panduan ini digunakan ketika Anda ingin mengembangkan Multitek Service langsung melalui GitHub tanpa harus mengedit source satu per satu lewat terminal VPS.

Alur yang direkomendasikan:

```text
EDIT DI GITHUB
      ↓
COMMIT / MERGE KE main
      ↓
VPS: mekanik-dev pull
      ↓
VPS: mekanik-deploy main
      ↓
TEST WHATSAPP
      ↓
JIKA SUDAH BAGUS
      ↓
VPS: mekanik-dev release VERSI_BARU "keterangan"
      ↓
VPS: mekanik-deploy vVERSI_BARU
```

GitHub menjadi **source of truth** untuk source code. VPS menjadi tempat menjalankan aplikasi production/test.

---

## 2. File Mana yang Harus Diedit?

Folder utama source adalah:

```text
app/
```

| Tujuan perubahan | File utama |
|---|---|
| Pemahaman AI, intent, typo, Jawa, ekstraksi data | `app/ai.py` |
| Alur percakapan customer | `app/customer.py` |
| Routing pesan masuk | `app/router.py` |
| Matching customer ke mekanik | `app/matching.py` |
| Alur/perintah mekanik | `app/mechanic.py` |
| Command owner/admin | `app/owner.py` |
| Pembuatan dan status order | `app/orders.py` |
| Harga jasa | `app/pricing.py` |
| Foto/video/attachment | `app/media.py` |
| Kirim pesan WhatsApp | `app/wa.py` |
| State percakapan sementara | `app/state.py` |
| Konfigurasi aplikasi | `app/config.py` |
| Struktur database awal | `app/schema.sql` |
| API utama / health endpoint | `app/main.py` |
| Background worker | `app/worker.py` |
| Nomor versi aplikasi | `VERSION` |
| Dokumentasi command | `docs/COMMANDS.md` |
| Dokumentasi flow | `docs/FLOW.md` |
| Catatan versi | `CHANGELOG.md` |

---

## 3. File yang Paling Sering Diedit

Untuk pengembangan chatbot, biasanya fokus pada:

```text
app/
├── ai.py
├── customer.py
├── router.py
├── matching.py
├── mechanic.py
├── owner.py
├── orders.py
├── pricing.py
├── media.py
└── state.py
```

Tidak perlu mengubah semua file sekaligus. Edit hanya file yang berkaitan dengan fitur yang sedang dikerjakan.

---

## 4. Tentang `.env`

File `.env` **memang tidak ada di GitHub**.

Itu disengaja karena `.env` berisi data rahasia seperti API key, database password, GoWA password, webhook secret, dan token.

Yang tersedia di GitHub adalah:

```text
.env.example
```

Struktur yang benar:

```text
GitHub
├── .env.example
├── app/
├── docs/
└── source code

VPS
├── .env          ← rahasia
├── source code
└── runtime/data
```

### Jika menambah setting baru

Misalnya ingin menambahkan:

```text
MEMORY_ENABLED=true
MEMORY_MAX_MESSAGES=20
```

Di GitHub edit:

```text
.env.example
app/config.py
```

Jika berupa secret, gunakan placeholder:

```text
NEW_API_KEY=ISI_NEW_API_KEY
```

Setelah source ditarik ke VPS, baru isi nilai sebenarnya pada:

```text
/home/mekanik/mekanik-bot/.env
```

Jangan pernah memasukkan API key/password asli ke GitHub.

---

## 5. Cara Edit File Langsung dari Website GitHub

### Langkah 1 — Buka repository

Buka repository:

```text
multitek-indo/mekanik-bot
```

Pastikan branch yang dilihat adalah:

```text
main
```

### Langkah 2 — Buka file

Contoh ingin mengubah AI:

```text
app/ai.py
```

Klik:

```text
app
→ ai.py
```

### Langkah 3 — Klik Edit

Klik ikon pensil / **Edit this file**.

### Langkah 4 — Lakukan perubahan

Edit source sesuai kebutuhan.

Jangan menghapus bagian lain jika tidak diperlukan.

### Langkah 5 — Commit perubahan

Klik:

```text
Commit changes...
```

Gunakan pesan commit yang jelas.

Contoh:

```text
fix: improve Javanese customer understanding
```

atau:

```text
feat: add customer conversation memory
```

---

## 6. Cara Paling Aman: Gunakan Branch

Untuk perubahan kecil Anda boleh commit langsung ke `main`.

Untuk fitur baru/perubahan besar, lebih aman menggunakan branch.

Contoh:

```text
dev-ai-memory
dev-media-forwarding
dev-matching
dev-customer-flow
fix-price-context
```

Workflow:

```text
main
 │
 └── dev-ai-memory
        │
        ├── edit source
        ├── commit
        ├── review
        └── Pull Request
               ↓
             main
```

Setelah branch selesai:

```text
Create Pull Request
→ Merge Pull Request
```

Setelah merge, perubahan masuk ke `main`.

---

## 7. Setelah Edit di GitHub: Ambil ke VPS

Masuk VPS, lalu:

```bash
cd /home/mekanik/mekanik-bot
mekanik-dev pull
```

Perintah tersebut mengambil perubahan dari `origin/main`.

Jika Anda menggunakan branch development, merge branch ke `main` terlebih dahulu.

---

## 8. Jalankan Source Terbaru untuk Testing

Setelah:

```bash
mekanik-dev pull
```

jalankan:

```bash
mekanik-deploy main
```

Kemudian cek:

```bash
mekanik-version
docker compose ps
curl http://127.0.0.1:8080/health
```

Setelah itu lakukan test melalui WhatsApp.

---

## 9. Contoh: Edit Balasan Customer

File utama:

```text
app/customer.py
```

Workflow:

```text
GitHub
→ app
→ customer.py
→ Edit
→ Commit
```

Contoh commit:

```text
fix: improve customer service flow
```

Di VPS:

```bash
mekanik-dev pull
mekanik-deploy main
```

Test WhatsApp.

Jika hasil belum bagus:

```text
Edit GitHub lagi
→ commit lagi
→ mekanik-dev pull
→ mekanik-deploy main
→ test lagi
```

Belum perlu membuat versi baru selama masih tahap development/testing.

---

## 10. Contoh: Membuat AI Lebih Pintar

Jika ingin bot memahami pesan seperti:

```text
mas mesinku kok ngono meneh
jarume ra gelem mudun
aku butuh wong ndandani
iki mesinku loro mas
```

Edit terutama:

```text
app/ai.py
app/customer.py
```

Pembagian tugas:

```text
ai.py
↓
memahami maksud customer

customer.py
↓
menentukan tindakan berikutnya
```

Contoh commit:

```text
feat: improve Indonesian and Javanese intent understanding
```

Testing:

```bash
mekanik-dev pull
mekanik-deploy main
```

---

## 11. Contoh: Mengubah Matching Mekanik

Jika ingin mekanik terdekat, skill tertinggi, radius dinamis, atau media customer ikut dikirim, edit:

```text
app/matching.py
```

Jika ada perubahan pengiriman WhatsApp:

```text
app/wa.py
```

Jika berkaitan dengan attachment:

```text
app/media.py
```

Contoh commit:

```text
feat: improve technician matching priority
```

---

## 12. Contoh: Mengubah Harga

Edit:

```text
app/pricing.py
```

Jika harga berasal dari database, jangan hardcode semua harga tanpa memahami sumber datanya.

Contoh commit:

```text
feat: improve service pricing calculation
```

---

## 13. Contoh: Mengembangkan Foto/Video Customer

File terkait:

```text
app/customer.py
app/media.py
app/matching.py
app/wa.py
```

Flow:

```text
customer.py
↓
meminta media

media.py
↓
menyimpan media

database attachments
↓
matching.py
↓
memilih media

wa.py
↓
mengirim ke mekanik
```

Untuk project saat ini, live test yang masih perlu dilakukan adalah:

```text
foto customer → sampai ke WhatsApp mekanik
video customer → sampai ke WhatsApp mekanik
```

---

## 14. Contoh: Menambah Persistent Conversation Memory

Kemungkinan file:

```text
app/ai.py
app/customer.py
app/state.py
app/db.py
app/schema.sql
```

Sebaiknya tambahkan modul baru:

```text
app/memory.py
```

Arsitektur target:

```text
recent messages
+
current conversation state
+
customer profile
+
machine history
+
previous orders
+
conversation summary
```

AI tidak boleh menjadi sumber kebenaran untuk harga, payment, order status, assigned technician, settlement, atau booking fee. Data tersebut tetap berasal dari backend/PostgreSQL.

---

## 15. Kapan Membuat Versi Baru?

Saat masih mencoba fitur:

```bash
mekanik-dev pull
mekanik-deploy main
```

Jika fitur sudah selesai dan sudah diuji, baru buat release baru.

Contoh:

```text
Versi aktif: 0.3.0-beta.1
Versi berikut: 0.3.0-beta.2
```

---

## 16. Cara Membuat Versi Berikutnya

Misalnya perubahan sudah selesai dan akan dibuat:

```text
v0.3.0-beta.2
```

Di VPS:

```bash
mekanik-dev release 0.3.0-beta.2 "perbaikan media forwarding"
```

Command tersebut menangani:

```text
update VERSION
git add
safety check
commit
push main
create tag
push tag
```

Kemudian deploy:

```bash
mekanik-deploy v0.3.0-beta.2
```

Cek:

```bash
mekanik-version
```

---

## 17. Contoh Siklus Development Lengkap

Misalnya Anda ingin membuat memory customer.

### A. Edit GitHub

Buat branch:

```text
dev-ai-memory
```

Edit:

```text
app/ai.py
app/customer.py
app/state.py
app/db.py
app/schema.sql
app/memory.py
```

Commit beberapa kali sesuai kebutuhan.

Setelah selesai:

```text
Pull Request
→ Merge ke main
```

### B. Ambil ke VPS

```bash
mekanik-dev pull
```

### C. Test source terbaru

```bash
mekanik-deploy main
mekanik-version
```

Test WhatsApp.

### D. Jika ada bug

Kembali ke GitHub, edit lagi, commit lagi, lalu:

```bash
mekanik-dev pull
mekanik-deploy main
```

### E. Buat release

Jika stabil:

```bash
mekanik-dev release 0.3.0-beta.2 "persistent conversation memory"
```

### F. Deploy release

```bash
mekanik-deploy v0.3.0-beta.2
```

### G. Verifikasi

```bash
mekanik-version
```

Target:

```text
Source version = Runtime API
Source commit  = Runtime commit
Deploy ref     = v0.3.0-beta.2
```

---

## 18. Perbedaan Command Utama

### `mekanik-dev pull`

Untuk perubahan dari GitHub ke VPS:

```bash
mekanik-dev pull
```

```text
GitHub → VPS
```

### `mekanik-dev save`

Jika Anda mengedit source langsung di VPS dan ingin menyimpannya ke GitHub:

```bash
mekanik-dev save "perbaikan chatbot"
```

```text
VPS → GitHub
```

Jika workflow utama Anda edit melalui GitHub, command ini jarang diperlukan.

### `mekanik-dev release`

Untuk membuat versi resmi baru:

```bash
mekanik-dev release 0.3.0-beta.2 "media forwarding verified"
```

### `mekanik-deploy main`

Untuk testing development terbaru:

```bash
mekanik-deploy main
```

### `mekanik-deploy vX.X.X`

Untuk menjalankan release tertentu:

```bash
mekanik-deploy v0.3.0-beta.2
```

---

## 19. Jika Release Baru Bermasalah

Rollback:

```bash
mekanik-rollback
```

atau:

```bash
mekanik-rollback v0.3.0-beta.1
```

Cek:

```bash
mekanik-version
```

Rollback aplikasi tidak otomatis mengembalikan database.

---

## 20. Mengecek Versi Aktif

Gunakan:

```bash
mekanik-version
```

Contoh:

```text
Source version : 0.3.0-beta.1
Source commit  : 3a3573f
Runtime API    : 0.3.0-beta.1
Runtime commit : 3a3573f28bf0
Deploy ref     : v0.3.0-beta.1
Status         : SOURCE = RUNTIME
```

Kondisi ideal:

```text
SOURCE = RUNTIME
```

---

## 21. Command Harian yang Perlu Diingat

Jika edit melalui GitHub:

```bash
mekanik-dev pull
mekanik-deploy main
mekanik-version
```

Setelah testing selesai:

```bash
mekanik-dev release 0.3.0-beta.2 "keterangan perubahan"
mekanik-deploy v0.3.0-beta.2
```

Jika bermasalah:

```bash
mekanik-rollback
```

---

## 22. Workflow Singkat yang Direkomendasikan

```text
1. Edit source di GitHub
2. Commit / merge ke main
3. VPS: mekanik-dev pull
4. VPS: mekanik-deploy main
5. Test WhatsApp
6. Jika belum bagus → edit GitHub lagi
7. Jika sudah bagus → mekanik-dev release VERSI_BARU
8. mekanik-deploy vVERSI_BARU
9. mekanik-version
```

---

## 23. Penomoran Versi

Contoh urutan:

```text
0.3.0-beta.1
0.3.0-beta.2
0.3.0-beta.3
0.3.0-rc.1
0.3.0
0.3.1
0.4.0
1.0.0
```

Panduan sederhana:

```text
beta berikutnya:
0.3.0-beta.1 → 0.3.0-beta.2

bugfix:
0.3.0 → 0.3.1

fitur baru:
0.3.1 → 0.4.0

milestone production utama:
0.x → 1.0.0
```

---

## 24. Aturan Penting Saat Edit di GitHub

Jangan upload:

```text
.env
database dump
backups/
data/media/
API key
password
token
customer photo
customer video
```

Jangan masukkan secret ke `.env.example`.

Gunakan placeholder:

```text
GEMINI_API_KEY=ISI_GEMINI_API_KEY
GROQ_API_KEY=ISI_GROQ_API_KEY
```

Jangan gunakan:

```bash
git push --force
```

untuk release production.

Jangan mengubah tag release lama. Jika ada perubahan, buat tag baru.

---

## 25. Cheat Sheet

### Edit di GitHub → VPS

```bash
mekanik-dev pull
mekanik-deploy main
mekanik-version
```

### Edit di VPS → GitHub

```bash
mekanik-dev save "keterangan"
```

### Release baru

```bash
mekanik-dev release 0.3.0-beta.2 "keterangan release"
mekanik-deploy v0.3.0-beta.2
```

### Rollback

```bash
mekanik-rollback
```

### Cek versi

```bash
mekanik-version
```

### Cek container

```bash
docker compose ps
```

### Cek API

```bash
curl http://127.0.0.1:8080/health
```

### Log

```bash
docker compose logs --tail=200 api
docker compose logs --tail=200 worker
docker compose logs --tail=200 gowa
```

---

## 26. Rekomendasi Workflow untuk Project Ini

```text
GITHUB
│
├── Edit source
├── Commit
└── Merge ke main
     │
     ▼
VPS
│
├── mekanik-dev pull
├── mekanik-deploy main
└── Test WhatsApp
     │
     ├── BELUM BAGUS
     │      ↓
     │   Edit GitHub lagi
     │
     └── SUDAH BAGUS
            ↓
       mekanik-dev release
            ↓
       mekanik-deploy tag
```

---

## 27. Checklist Sebelum Release

Sebelum menjalankan `mekanik-dev release` pastikan:

- fitur sudah dites;
- chatbot masih merespons;
- API sehat;
- worker sehat;
- GoWA sehat;
- database tidak di-reset;
- tidak ada secret di source;
- tidak ada media customer di Git;
- nomor versi baru benar;
- perubahan penting sudah dicatat.

Cek:

```bash
mekanik-dev status
```

---

## 28. Contoh Praktis Versi Berikutnya

Versi aktif:

```text
v0.3.0-beta.1
```

Misalnya Anda mengembangkan:

```text
live media forwarding
+
conversation memory tahap awal
```

Setelah edit dan merge di GitHub:

```bash
mekanik-dev pull
mekanik-deploy main
```

Test WhatsApp.

Jika sudah stabil:

```bash
mekanik-dev release 0.3.0-beta.2 "media forwarding dan memory tahap awal"
mekanik-deploy v0.3.0-beta.2
mekanik-version
```

Jika bermasalah:

```bash
mekanik-rollback v0.3.0-beta.1
```

---

## 29. Ringkasan Paling Sederhana

Untuk development melalui GitHub, ingat empat tahap:

```text
EDIT
↓
PULL
↓
TEST
↓
RELEASE
```

Praktiknya:

```text
Edit GitHub
↓
mekanik-dev pull
↓
mekanik-deploy main
↓
Test WhatsApp
↓
mekanik-dev release VERSI_BARU
↓
mekanik-deploy vVERSI_BARU
```

File `.env`, database, backup, dan media customer tetap berada di VPS dan tidak perlu dimasukkan ke GitHub.

---

# 30. Peta Struktur Repository GitHub

Bagian ini adalah **peta utama repository**. Gunakan bagian ini ketika Anda bertanya:

> "Kalau saya ingin mengubah fitur tertentu, saya harus edit file yang mana?"

Struktur repository saat ini:

```text
mekanik-bot/
├── app/
│   ├── __init__.py
│   ├── ai.py
│   ├── config.py
│   ├── customer.py
│   ├── db.py
│   ├── finance.py
│   ├── location.py
│   ├── main.py
│   ├── matching.py
│   ├── mechanic.py
│   ├── media.py
│   ├── onboarding.py
│   ├── orders.py
│   ├── owner.py
│   ├── pricing.py
│   ├── router.py
│   ├── schema.sql
│   ├── security.py
│   ├── skills.py
│   ├── state.py
│   ├── types.py
│   ├── version.py
│   ├── wa.py
│   └── worker.py
│
├── data/
│   └── .gitkeep
│
├── docs/
│   ├── COMMANDS.md
│   ├── DEPLOYMENT.md
│   ├── FLOW.md
│   ├── INSTALLATION.md
│   ├── MANUAL_BOOK.md
│   ├── MECHANIC_SKILL_MATRIX.md
│   ├── Multitek_Service_GitHub_Development_Guide.md
│   ├── NEXT_STEPS.md
│   ├── PRICING.md
│   ├── ROLLBACK.md
│   └── VERSIONING.md
│
├── scripts/
│   ├── add_technician.sh
│   ├── backup.sh
│   ├── bootstrap_ubuntu.sh
│   ├── deploy.sh
│   ├── dev.sh
│   ├── gowa_create_device.sh
│   ├── gowa_login.sh
│   ├── gowa_status.sh
│   ├── health.sh
│   ├── preflight.sh
│   ├── rollback.sh
│   └── version.sh
│
├── tests/
│   ├── conftest.py
│   ├── test_ai_fallback.py
│   ├── test_customer_parsing.py
│   ├── test_location.py
│   ├── test_pricing.py
│   └── test_skills.py
│
├── .dockerignore
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── Dockerfile
├── README.md
├── RELEASE_NOTES.md
├── TEST_REPORT.txt
├── VERSION
├── docker-compose.yml
└── requirements.txt
```

---

# 31. Fungsi Folder `app/`

Folder:

```text
app/
```

adalah **inti aplikasi**.

Sebagian besar fitur chatbot, order, mekanik, AI, WhatsApp, harga, media, dan database dikendalikan dari folder ini.

Jika Anda ingin mengubah perilaku bot, biasanya Anda akan bekerja di sini.

---

## 31.1 `app/ai.py`

### Fungsi

Mengatur kecerdasan pemahaman bahasa customer.

Digunakan untuk:

- memahami maksud pesan;
- menentukan intent;
- memahami typo;
- memahami singkatan;
- memahami Bahasa Jawa;
- mengambil nama/jenis mesin;
- mengambil keluhan;
- mengambil jumlah mesin;
- membaca konteks percakapan;
- menentukan confidence;
- memilih local parser / Gemini / Groq.

### Edit file ini jika ingin:

- bot lebih pintar memahami bahasa;
- menambah kosakata Jawa;
- menambah typo;
- menambah intent baru;
- memperbaiki salah interpretasi customer;
- memperbaiki ekstraksi mesin/keluhan/jumlah;
- mengubah aturan fallback AI.

### Contoh

Customer menulis:

```text
mas mesinku juki ra iso mlaku
```

Jika bot tidak memahami bahwa:

```text
merk = Juki
keluhan = tidak bisa berjalan
```

maka file utama yang perlu diperiksa:

```text
app/ai.py
```

### Tingkat risiko

```text
SEDANG
```

Kesalahan di sini biasanya membuat bot salah memahami pesan, tetapi tidak langsung merusak database.

---

## 31.2 `app/customer.py`

### Fungsi

Mengatur **alur percakapan customer**.

Contoh flow:

```text
customer chat
↓
identifikasi mesin
↓
identifikasi keluhan
↓
jumlah unit
↓
lokasi
↓
foto/video
↓
landmark
↓
buat order
↓
matching
```

### Edit file ini jika ingin:

- mengubah urutan pertanyaan;
- mengubah teks balasan bot;
- menambah pertanyaan baru;
- menghapus langkah tertentu;
- mengubah kapan bot meminta lokasi;
- mengubah kapan bot meminta foto/video;
- membuat customer dapat skip langkah tertentu;
- memperbaiki alur yang berhenti di state tertentu;
- mengubah behavior setelah customer bertanya harga.

### Contoh

Ingin mengubah:

```text
Kirim foto mesin terlebih dahulu.
```

menjadi:

```text
Jika berkenan, kirim foto atau video kerusakan agar mekanik dapat melakukan pengecekan awal.
```

Cari di:

```text
app/customer.py
```

### Tingkat risiko

```text
SEDANG - TINGGI
```

Karena file ini berhubungan langsung dengan state percakapan dan pembuatan order.

---

## 31.3 `app/router.py`

### Fungsi

Menentukan **pesan masuk harus diarahkan ke modul mana**.

Secara konsep:

```text
pesan WhatsApp masuk
↓
router.py
↓
customer / mechanic / owner / onboarding
```

File ini juga menangani filter pesan seperti:

- pesan dari bot sendiri;
- duplicate message;
- menentukan jenis pengguna;
- routing command.

### Edit jika ingin:

- menambah tipe user baru;
- mengubah routing;
- memperbaiki pesan yang masuk ke handler yang salah;
- menambah command global;
- memperbaiki duplicate response.

### Jangan edit hanya untuk:

- mengganti kalimat balasan customer;
- mengganti harga;
- mengganti AI prompt.

### Tingkat risiko

```text
TINGGI
```

Bug di router dapat membuat seluruh pesan WhatsApp tidak diproses atau diproses ganda.

---

## 31.4 `app/matching.py`

### Fungsi

Mengatur proses pencarian dan penawaran pekerjaan ke mekanik.

Secara konsep:

```text
order customer
↓
cari mekanik sesuai skill
↓
cek availability
↓
cek lokasi/radius
↓
buat job offer
↓
kirim ke mekanik
```

### Edit jika ingin:

- mekanik terdekat diprioritaskan;
- mekanik dengan skill tertentu diprioritaskan;
- radius pencarian diubah;
- membuat batch penawaran;
- mengubah teks job offer;
- mengirim foto/video customer;
- mengatur mekanik mana yang menerima job;
- memperbaiki kasus tidak ada mekanik ditemukan.

### Contoh

Ingin membuat prioritas:

```text
1. skill cocok
2. mekanik online
3. jarak paling dekat
4. rating tertinggi
```

File utama:

```text
app/matching.py
```

### Tingkat risiko

```text
TINGGI
```

Karena perubahan bisa menyebabkan job dikirim ke mekanik yang salah atau terkirim berulang.

---

## 31.5 `app/mechanic.py`

### Fungsi

Mengatur perilaku chatbot ketika pengguna adalah mekanik.

### Edit jika ingin:

- menambah command mekanik;
- mengubah respon ONLINE/OFFLINE;
- membuat command JOB SAYA;
- mengatur penerimaan job;
- mengatur penolakan job;
- mengatur update status pekerjaan;
- mengubah pesan untuk mekanik.

### Contoh

Ingin menambah:

```text
STATUS SAYA
```

untuk mekanik.

Periksa:

```text
app/mechanic.py
```

### Tingkat risiko

```text
SEDANG
```

---

## 31.6 `app/onboarding.py`

### Fungsi

Mengatur proses pendaftaran/onboarding mekanik.

### Edit jika ingin:

- mengubah flow pendaftaran;
- menambah pertanyaan onboarding;
- mengubah data yang wajib dikumpulkan;
- mengubah proses skill assessment;
- memperbaiki pendaftaran mekanik baru.

### Contoh

Ingin menambah pertanyaan:

```text
Berapa tahun pengalaman Anda?
```

Kemungkinan besar edit:

```text
app/onboarding.py
```

dan mungkin:

```text
app/schema.sql
```

jika perlu menyimpan field baru.

### Tingkat risiko

```text
SEDANG
```

---

## 31.7 `app/orders.py`

### Fungsi

Mengatur service order.

Termasuk:

- membuat nomor order;
- membuat order;
- membuat item order;
- update status;
- membaca order;
- menyimpan informasi order.

### Edit jika ingin:

- mengubah nomor order;
- menambah status baru;
- menambah field order;
- mengubah proses pembuatan order;
- mengubah business rule order.

### Contoh

Format sekarang:

```text
MTK-YYMMDD-NNNN
```

Jika ingin format lain, periksa:

```text
app/orders.py
```

### Tingkat risiko

```text
TINGGI
```

Order adalah data transaksi utama.

---

## 31.8 `app/pricing.py`

### Fungsi

Mengatur logic harga jasa.

### Edit jika ingin:

- mengubah cara menghitung harga;
- mengubah jawaban pertanyaan harga;
- menambah kategori harga;
- menambah rule berdasarkan jenis mesin;
- menambah rule berdasarkan jumlah unit.

### Perhatian

Jika harga sebenarnya disimpan pada tabel database:

```text
service_price_matrix
```

jangan memindahkan semuanya menjadi hardcode tanpa alasan.

### Tingkat risiko

```text
TINGGI
```

Karena harga berhubungan dengan transaksi.

---

## 31.9 `app/media.py`

### Fungsi

Mengatur file media customer.

Termasuk:

- foto;
- video;
- document;
- audio;
- video note;
- download media;
- penyimpanan local file;
- validasi real media file.

### Edit jika ingin:

- menambah tipe media;
- mengubah folder penyimpanan;
- memperbaiki download foto/video;
- mengubah validasi media;
- membatasi ukuran/jenis file.

### Tingkat risiko

```text
SEDANG
```

---

## 31.10 `app/wa.py`

### Fungsi

Merupakan interface aplikasi dengan GoWA / WhatsApp.

Menangani antara lain:

- send text;
- send image;
- send file;
- send location;
- autentikasi GoWA;
- normalisasi nomor.

### Edit jika:

- WhatsApp gagal mengirim;
- endpoint GoWA berubah;
- payload GoWA berubah;
- ingin menambah jenis pengiriman WhatsApp baru.

### Jangan edit hanya karena:

```text
teks balasan customer salah
```

Teks biasanya berasal dari customer.py/mechanic.py/owner.py.

### Tingkat risiko

```text
TINGGI
```

Kesalahan dapat menghentikan seluruh outbound WhatsApp.

---

## 31.11 `app/state.py`

### Fungsi

Mengelola state percakapan sementara.

Contoh:

```text
cust_price_context
cust_media
menunggu lokasi
menunggu jumlah
menunggu landmark
```

### Edit jika ingin:

- menambah state percakapan;
- mengubah expiration;
- menyimpan payload state;
- memperbaiki context yang hilang;
- mengubah flow multi-step.

### Contoh

Customer sedang berada pada:

```text
cust_media
```

Jika ingin menambah state:

```text
cust_confirm_order
```

maka kemungkinan Anda perlu mengubah:

```text
app/state.py
app/customer.py
```

### Tingkat risiko

```text
TINGGI
```

Bug state dapat membuat customer terjebak pada flow tertentu.

---

## 31.12 `app/db.py`

### Fungsi

Menyediakan koneksi dan helper database PostgreSQL.

### Edit jika:

- cara koneksi database berubah;
- connection pooling berubah;
- perlu helper database umum.

### Jangan edit untuk:

- sekadar menambah text balasan;
- menambah keyword AI.

### Tingkat risiko

```text
SANGAT TINGGI
```

Bug dapat memengaruhi seluruh aplikasi.

---

## 31.13 `app/schema.sql`

### Fungsi

Mendefinisikan struktur database awal.

Contoh objek:

```text
customers
technicians
service_orders
service_order_items
attachments
conversation_states
payments
settlements
```

### Edit jika ingin:

- membuat tabel baru;
- menambah field;
- membuat index;
- menambah constraint.

### Penting

Pada database production yang sudah berjalan:

```text
EDIT schema.sql ≠ otomatis mengubah database production
```

Untuk perubahan database production sebaiknya dibuat migration yang aman.

Jangan reset database hanya untuk menerapkan schema baru.

### Tingkat risiko

```text
SANGAT TINGGI
```

---

## 31.14 `app/config.py`

### Fungsi

Membaca konfigurasi dari environment.

Contoh:

```text
database URL
GoWA
AI provider
API keys
owner settings
threshold
```

### Edit jika:

- menambah environment variable;
- menambah setting aplikasi;
- mengubah default configuration.

Jika membuat setting baru, biasanya edit juga:

```text
.env.example
```

### Tingkat risiko

```text
SEDANG
```

---

## 31.15 `app/finance.py`

### Fungsi

Berhubungan dengan logic keuangan, pembayaran, atau settlement yang digunakan aplikasi.

### Edit jika:

- business rule pembayaran berubah;
- settlement berubah;
- logic finance perlu ditambah.

### Tingkat risiko

```text
SANGAT TINGGI
```

Jangan mengubah finance tanpa test yang jelas.

---

## 31.16 `app/location.py`

### Fungsi

Helper lokasi/geografis.

Dapat digunakan untuk:

- jarak;
- latitude/longitude;
- perhitungan lokasi;
- validasi data lokasi.

### Edit jika:

- radius salah;
- kalkulasi jarak salah;
- format lokasi perlu diubah.

### Tingkat risiko

```text
SEDANG
```

---

## 31.17 `app/owner.py`

### Fungsi

Mengatur command dan fitur yang khusus digunakan owner/admin.

### Edit jika:

- menambah command owner;
- mengubah approval mekanik;
- menambah laporan owner;
- menambah command administrasi.

### Tingkat risiko

```text
SEDANG - TINGGI
```

---

## 31.18 `app/security.py`

### Fungsi

Berisi fungsi terkait keamanan/authentication yang digunakan aplikasi.

### Edit jika:

- mekanisme authentication berubah;
- token verification berubah;
- signature/webhook security berubah.

### Tingkat risiko

```text
SANGAT TINGGI
```

Jangan edit untuk kebutuhan chatbot biasa.

---

## 31.19 `app/skills.py`

### Fungsi

Mendefinisikan skill/kategori kemampuan mekanik.

### Edit jika:

- menambah jenis skill;
- mengubah kode skill;
- mengubah mapping skill mesin.

### Contoh

Ingin menambah:

```text
BARTACK
BUTTONHOLE
LASER_CUTTER
```

periksa:

```text
app/skills.py
```

dan hubungan database/skill matrix.

### Tingkat risiko

```text
SEDANG
```

---

## 31.20 `app/types.py`

### Fungsi

Mendefinisikan struktur/type data internal aplikasi.

Contoh dapat berupa:

```text
IncomingMessage
structured payload
data models
```

### Edit jika:

- format object internal berubah;
- webhook membawa field baru;
- modul lain memerlukan property baru.

### Tingkat risiko

```text
TINGGI
```

Karena banyak modul dapat bergantung pada type yang sama.

---

## 31.21 `app/main.py`

### Fungsi

Entry point FastAPI.

Menangani antara lain:

- membuat aplikasi FastAPI;
- health endpoint;
- endpoint webhook;
- startup utama API.

### Edit jika:

- menambah endpoint API;
- mengubah health endpoint;
- menambah middleware;
- mengubah webhook API.

### Jangan edit untuk:

- mengubah percakapan customer;
- menambah harga.

### Tingkat risiko

```text
TINGGI
```

---

## 31.22 `app/worker.py`

### Fungsi

Menjalankan pekerjaan background/worker.

### Edit jika:

- menambah background processing;
- mengubah interval/polling worker;
- menambah task asynchronous background.

### Tingkat risiko

```text
TINGGI
```

---

## 31.23 `app/version.py`

### Fungsi

Membaca file:

```text
VERSION
```

dan menyediakan nomor versi kepada aplikasi.

### Biasanya tidak perlu diedit

Untuk mengganti versi:

```text
jangan edit version.py
```

Gunakan release workflow:

```bash
mekanik-dev release 0.3.0-beta.2 "keterangan"
```

### Tingkat risiko

```text
RENDAH
```

tetapi jarang perlu disentuh.

---

## 31.24 `app/__init__.py`

### Fungsi

Menandai folder `app` sebagai Python package.

Biasanya:

```text
TIDAK PERLU DIEDIT
```

kecuali ada kebutuhan Python package khusus.

---

# 32. Fungsi Folder `scripts/`

Folder:

```text
scripts/
```

berisi **alat operasional server dan deployment**.

Untuk development fitur chatbot biasa, Anda hampir tidak perlu mengubah folder ini.

---

## 32.1 `scripts/dev.sh`

### Fungsi

Command sederhana:

```bash
mekanik-dev
```

Digunakan untuk:

```text
status
pull
save
release
```

### Jangan edit kecuali

Anda ingin mengubah workflow GitHub/development itu sendiri.

---

## 32.2 `scripts/deploy.sh`

### Fungsi

Command:

```bash
mekanik-deploy
```

Menangani:

```text
fetch GitHub
backup database
checkout version
preflight
build
restart API + worker
health check
automatic rollback
```

### Jangan edit untuk fitur chatbot

Ini adalah script deployment production.

### Tingkat risiko

```text
SANGAT TINGGI
```

---

## 32.3 `scripts/rollback.sh`

### Fungsi

Command:

```bash
mekanik-rollback
```

Digunakan untuk mengembalikan aplikasi ke versi sebelumnya.

---

## 32.4 `scripts/version.sh`

### Fungsi

Command:

```bash
mekanik-version
```

Menampilkan:

```text
source version
source commit
runtime version
runtime commit
deploy ref
container status
```

---

## 32.5 `scripts/backup.sh`

### Fungsi

Backup PostgreSQL sebelum deployment.

Jangan diubah tanpa alasan kuat.

---

## 32.6 `scripts/preflight.sh`

### Fungsi

Memastikan kondisi server/source aman sebelum deployment.

Memeriksa antara lain:

```text
Docker
Compose
.env
environment variables
Python syntax
```

---

## 32.7 `scripts/health.sh`

### Fungsi

Mengecek apakah aplikasi sehat setelah start/deploy.

---

## 32.8 `scripts/add_technician.sh`

### Fungsi

Utility untuk menambahkan mekanik melalui command line.

Edit jika format onboarding/manual insertion mekanik berubah.

---

## 32.9 `scripts/gowa_*`

File:

```text
gowa_create_device.sh
gowa_login.sh
gowa_status.sh
```

Digunakan untuk administrasi koneksi GoWA/WhatsApp.

Untuk perubahan percakapan bot:

```text
JANGAN edit file ini.
```

---

## 32.10 `scripts/bootstrap_ubuntu.sh`

### Fungsi

Digunakan untuk persiapan environment/server Ubuntu.

Biasanya hanya digunakan saat instalasi awal.

---

# 33. Fungsi Folder `tests/`

Folder:

```text
tests/
```

digunakan untuk test otomatis.

Ini bukan aplikasi production langsung, tetapi sangat penting untuk mencegah bug.

---

## 33.1 `tests/conftest.py`

Setup/configuration untuk test.

Biasanya berisi environment dummy dan fixture.

---

## 33.2 `tests/test_ai_fallback.py`

Test fallback AI.

Edit jika logic provider/fallback AI berubah.

---

## 33.3 `tests/test_customer_parsing.py`

Test parsing pesan customer.

Jika Anda mengubah:

```text
app/ai.py
app/customer.py
```

idealnya test di file ini juga diperbarui.

---

## 33.4 `tests/test_location.py`

Test fungsi lokasi.

Edit jika:

```text
app/location.py
```

berubah.

---

## 33.5 `tests/test_pricing.py`

Test logic pricing.

Edit jika:

```text
app/pricing.py
```

berubah.

---

## 33.6 `tests/test_skills.py`

Test skill matrix/mapping.

Edit jika:

```text
app/skills.py
```

berubah.

---

# 34. Fungsi Folder `docs/`

Folder:

```text
docs/
```

berisi dokumentasi.

Perubahan file di folder ini **tidak mengubah behavior chatbot**.

---

## `docs/COMMANDS.md`

Daftar command customer/mekanik/owner.

Edit jika command baru ditambahkan.

---

## `docs/FLOW.md`

Dokumentasi alur sistem.

Edit jika flow aplikasi berubah.

---

## `docs/PRICING.md`

Dokumentasi harga/pricing.

Edit jika policy harga berubah.

---

## `docs/MECHANIC_SKILL_MATRIX.md`

Dokumentasi skill mekanik.

Edit jika kategori/skill mekanik berubah.

---

## `docs/INSTALLATION.md`

Panduan instalasi.

Edit jika cara install berubah.

---

## `docs/DEPLOYMENT.md`

Panduan deployment.

Edit jika cara deploy berubah.

---

## `docs/VERSIONING.md`

Panduan versioning/release.

Edit jika aturan versi berubah.

---

## `docs/ROLLBACK.md`

Panduan rollback.

Edit jika prosedur rollback berubah.

---

## `docs/NEXT_STEPS.md`

Checkpoint development.

**Sangat penting untuk diperbarui setiap kali berhenti development.**

Isi:

```text
apa yang sudah selesai
apa yang sudah diuji
apa yang belum diuji
prioritas development berikutnya
```

---

## `docs/MANUAL_BOOK.md`

Manual umum sistem.

Edit jika ada perubahan besar pada fungsi/flow.

---

# 35. Fungsi File di Root Repository

---

## `.env.example`

Template environment variable.

### Edit jika

Anda menambah config baru.

Contoh:

```text
MEMORY_ENABLED=true
MEMORY_MAX_MESSAGES=20
NEW_API_KEY=ISI_NEW_API_KEY
```

### Jangan

Masukkan secret sebenarnya.

---

## `.gitignore`

Menentukan file yang **tidak boleh masuk GitHub**.

Contoh:

```text
.env
backups/
data/media/
__pycache__/
```

### Edit jika

Ada file runtime/sensitif baru yang harus di-ignore.

---

## `.dockerignore`

Menentukan file yang tidak perlu dikirim ke Docker build context.

Edit hanya jika struktur build Docker berubah.

---

## `Dockerfile`

Menjelaskan cara membangun image API/worker.

### Edit jika

- Python base image berubah;
- dependency build berubah;
- file yang dicopy berubah;
- startup image berubah.

### Tingkat risiko

```text
TINGGI
```

---

## `docker-compose.yml`

Mendefinisikan service:

```text
db
api
gowa
worker
```

### Edit jika

- menambah service;
- port berubah;
- volume berubah;
- environment container berubah;
- image berubah.

### Tingkat risiko

```text
SANGAT TINGGI
```

Jangan edit untuk perubahan chatbot biasa.

---

## `requirements.txt`

Daftar dependency Python.

### Edit jika

Anda menambahkan library Python baru.

Contoh:

```text
httpx
pydantic
psycopg
```

Setelah berubah, image perlu rebuild/deploy.

---

## `VERSION`

Nomor versi source.

Contoh:

```text
0.3.0-beta.1
```

Untuk workflow normal, gunakan:

```bash
mekanik-dev release 0.3.0-beta.2 "keterangan"
```

daripada mengubahnya manual.

---

## `CHANGELOG.md`

Riwayat perubahan setiap versi.

Idealnya update setiap release.

---

## `RELEASE_NOTES.md`

Ringkasan release/milestone.

Dapat digunakan untuk penjelasan perubahan besar.

---

## `TEST_REPORT.txt`

Catatan hasil testing.

Boleh diperbarui setelah test penting.

---

## `README.md`

Halaman pertama repository.

Berisi overview project dan quick start.

Edit jika ingin memperbarui dokumentasi umum project.

---

# 36. Peta Cepat: Saya Ingin Mengubah Apa?

Gunakan tabel ini sebelum mulai edit.

| Saya ingin... | Edit utama | Mungkin terkait |
|---|---|---|
| Bot lebih pintar | `app/ai.py` | `customer.py` |
| Bot memahami Jawa | `app/ai.py` | tests |
| Bot memahami typo | `app/ai.py` | tests |
| Mengubah kalimat customer | `app/customer.py` | - |
| Mengubah urutan pertanyaan | `app/customer.py` | `state.py` |
| Tambah state conversation | `app/state.py` | `customer.py` |
| Menambah memory AI | `app/memory.py` baru | `ai.py`, `customer.py`, `db.py` |
| Mengubah matching mekanik | `app/matching.py` | `location.py`, `skills.py` |
| Mengubah radius mekanik | `app/matching.py` | `location.py` |
| Mengubah skill mekanik | `app/skills.py` | DB / docs |
| Mengubah command mekanik | `app/mechanic.py` | `router.py` |
| Mengubah registrasi mekanik | `app/onboarding.py` | DB |
| Mengubah command owner | `app/owner.py` | `router.py` |
| Mengubah pembuatan order | `app/orders.py` | `customer.py` |
| Mengubah status order | `app/orders.py` | mechanic/owner |
| Mengubah harga | `app/pricing.py` | DB |
| Mengubah foto/video | `app/media.py` | `customer.py`, `matching.py` |
| Foto/video ke mekanik | `app/matching.py` | `media.py`, `wa.py` |
| WhatsApp tidak terkirim | `app/wa.py` | GoWA |
| Pesan masuk salah routing | `app/router.py` | handlers |
| Menambah endpoint API | `app/main.py` | - |
| Menambah background task | `app/worker.py` | DB/API |
| Menambah config | `app/config.py` | `.env.example`, VPS `.env` |
| Menambah tabel database | migration/schema | `db.py` |
| Menambah library Python | `requirements.txt` | Docker rebuild |
| Mengubah Docker | `Dockerfile` | compose |
| Mengubah service/port | `docker-compose.yml` | `.env` |
| Update dokumentasi | `docs/*` | README |
| Membuat versi baru | jangan edit manual | `mekanik-dev release` |

---

# 37. Peta Berdasarkan Masalah

## Masalah: "Bot salah memahami kalimat customer"

Periksa:

```text
1. app/ai.py
2. tests/test_customer_parsing.py
```

Jika AI sudah benar tetapi respon berikutnya salah:

```text
3. app/customer.py
```

---

## Masalah: "Bot mengulang balasan dua kali"

Periksa:

```text
app/router.py
app/main.py
processed_messages/idempotency
```

Jangan langsung mengubah AI.

---

## Masalah: "Bot lupa data yang baru saja diberikan"

Periksa:

```text
app/state.py
app/customer.py
```

Jika ingin memory jangka panjang:

```text
buat app/memory.py
+ database
```

---

## Masalah: "Harga salah"

Periksa:

```text
app/pricing.py
service_price_matrix di database
```

Jangan mengubah `ai.py` jika sumber harga seharusnya database.

---

## Masalah: "Order tidak terbentuk"

Periksa:

```text
app/customer.py
app/orders.py
app/state.py
```

Lalu log API.

---

## Masalah: "Mekanik tidak menerima job"

Periksa:

```text
app/matching.py
app/mechanic.py
app/wa.py
```

Kemudian cek:

```text
mekanik active?
mekanik available?
skill sesuai?
lokasi/radius sesuai?
```

---

## Masalah: "Foto/video tidak terkirim"

Periksa urutan:

```text
app/media.py
↓
attachments database
↓
app/matching.py
↓
app/wa.py
↓
GoWA
```

---

## Masalah: "Pesan WhatsApp tidak masuk ke bot"

Periksa:

```text
GoWA
↓
app/main.py webhook
↓
app/router.py
```

Bukan `customer.py` terlebih dahulu.

---

## Masalah: "API tidak hidup"

Periksa:

```text
app/main.py
app/config.py
database connection
Docker
```

Gunakan:

```bash
docker compose logs --tail=200 api
```

---

# 38. Tingkat Risiko File

## Relatif aman untuk development rutin

```text
docs/*
README.md
CHANGELOG.md
app/ai.py
app/customer.py
app/mechanic.py
app/owner.py
app/skills.py
tests/*
```

Tetap harus test setelah perubahan.

## Perlu hati-hati

```text
app/state.py
app/media.py
app/location.py
app/config.py
app/onboarding.py
app/types.py
```

## Risiko tinggi

```text
app/router.py
app/matching.py
app/orders.py
app/pricing.py
app/wa.py
app/main.py
app/worker.py
```

## Risiko sangat tinggi

```text
app/db.py
app/schema.sql
app/security.py
app/finance.py
Dockerfile
docker-compose.yml
scripts/deploy.sh
scripts/rollback.sh
scripts/backup.sh
```

Sebelum mengubah file risiko tinggi:

```text
1. pahami efeknya
2. edit di branch
3. test
4. deploy main
5. jangan langsung release
```

---

# 39. Aturan: Satu Fitur, Edit File Sesedikit Mungkin

Contoh yang kurang baik:

```text
ingin mengubah greeting
↓
edit ai.py
edit router.py
edit db.py
edit wa.py
edit customer.py
```

Padahal kemungkinan cukup:

```text
app/customer.py
```

Prinsip:

```text
Cari pemilik fungsi
↓
ubah file utama
↓
ubah file terkait hanya jika benar-benar diperlukan
```

Ini membuat debugging dan rollback jauh lebih mudah.

---

# 40. Panduan Sebelum Klik Edit di GitHub

Sebelum edit, jawab tiga pertanyaan:

### 1. Apa yang ingin diubah?

Contoh:

```text
bot tidak memahami bahasa Jawa
```

### 2. Bagian sistem mana yang bertanggung jawab?

Jawab:

```text
AI/NLU
```

### 3. File pemilik fungsi?

Jawab:

```text
app/ai.py
```

Baru mulai edit.

Contoh lain:

```text
Masalah:
foto customer tidak sampai ke mekanik

Komponen:
media forwarding

File:
app/matching.py
app/media.py
app/wa.py
```

---

# 41. Template Permintaan Editing untuk ChatGPT

Jika Anda ingin meminta ChatGPT membantu mengedit GitHub, gunakan format berikut:

```text
Project: Multitek Service

Tujuan:
Saya ingin bot dapat mengingat percakapan customer.

Versi sekarang:
0.3.0-beta.1

File yang saya duga terkait:
app/ai.py
app/customer.py
app/state.py

Yang saya inginkan:
- simpan 20 pesan terakhir
- buat summary conversation
- jangan ubah logic harga
- jangan ubah payment
- jangan reset database

Tolong jelaskan:
1. file mana yang perlu diedit
2. fungsi mana yang perlu diubah
3. file baru apa yang perlu dibuat
4. risiko perubahan
5. cara test
6. versi berikutnya
```

Dengan format tersebut, perubahan akan lebih terarah.

---

# 42. Contoh Memilih File dengan Benar

### Kasus A

Keinginan:

```text
Saya ingin greeting "Halo" menjadi lebih ramah.
```

Edit:

```text
app/customer.py
```

Tidak perlu edit:

```text
ai.py
db.py
matching.py
```

---

### Kasus B

Keinginan:

```text
Saya ingin bot memahami "mesinku loro".
```

Edit:

```text
app/ai.py
```

Test:

```text
tests/test_customer_parsing.py
```

---

### Kasus C

Keinginan:

```text
Saya ingin mekanik menerima foto kerusakan.
```

Periksa:

```text
app/matching.py
app/media.py
app/wa.py
```

---

### Kasus D

Keinginan:

```text
Saya ingin menambah kolom rating mekanik.
```

Perlu desain:

```text
database migration
app/db.py bila perlu
app/matching.py jika rating memengaruhi ranking
app/mechanic.py/owner.py bila rating dikelola melalui chat
```

Jangan sekadar edit `schema.sql` lalu menganggap database production otomatis berubah.

---

### Kasus E

Keinginan:

```text
Saya ingin menambah Gemini model baru.
```

Periksa:

```text
app/config.py
app/ai.py
.env.example
```

Nilai API key asli tetap di:

```text
VPS .env
```

---

# 43. Workflow Ideal Saat Edit File Risiko Tinggi

Buat branch GitHub, contoh:

```text
fix-matching-v2
```

Edit.

Commit.

Merge ke `main` setelah review.

Di VPS:

```bash
mekanik-dev pull
mekanik-deploy main
mekanik-version
```

Lakukan test.

Jika stabil:

```bash
mekanik-dev release 0.3.0-beta.2 "matching v2"
mekanik-deploy v0.3.0-beta.2
```

Jika gagal:

```bash
mekanik-rollback
```

---

# 44. Ringkasan Peta Utama

Ingat pembagian paling sederhana:

```text
AI & bahasa
→ ai.py

Percakapan customer
→ customer.py

Routing
→ router.py

Mekanik
→ mechanic.py

Pendaftaran mekanik
→ onboarding.py

Matching
→ matching.py

Order
→ orders.py

Harga
→ pricing.py

Media
→ media.py

WhatsApp
→ wa.py

State
→ state.py

Database
→ db.py / migration

Owner
→ owner.py

Config
→ config.py

API
→ main.py

Background
→ worker.py

Deployment
→ scripts/

Dokumentasi
→ docs/

Test
→ tests/
```

Jika ragu, **jangan mulai dari `router.py`, `db.py`, `Dockerfile`, atau `docker-compose.yml`**.

Mulai dari file pemilik fungsi yang ingin diubah.

---

# 45. Memahami Hubungan `.env.example`, `.env`, `pull`, dan `deploy`

Bagian ini sangat penting karena sering menimbulkan kebingungan saat development melalui GitHub.

## 45.1 Konsep paling sederhana

```text
.env.example
=
TEMPLATE konfigurasi yang disimpan di GitHub

.env
=
NILAI konfigurasi asli yang hanya disimpan di VPS
```

GitHub menyimpan:

```text
.env.example
app/config.py
app/ai.py
app/customer.py
...
```

VPS menyimpan:

```text
.env
source code hasil GitHub
database
media
backup
container runtime
```

File `.env` sengaja tidak masuk GitHub karena berisi data sensitif.

---

## 45.2 Apa yang terjadi saat `.env.example` diedit di GitHub?

Contoh di GitHub:

```text
PAYMENT_BANK_ACCOUNT=ISI_NOMOR_REKENING
GEMINI_API_KEY=ISI_GEMINI_API_KEY
```

Setelah Anda menjalankan:

```bash
mekanik-dev pull
```

yang berubah di VPS adalah:

```text
.env.example
```

Sedangkan:

```text
.env
```

tetap memakai nilai yang sudah tersimpan di VPS.

Jadi:

```text
GitHub .env.example
        ↓ pull
VPS .env.example berubah

VPS .env
tetap
tidak ditimpa
```

---

## 45.3 Apakah `.env.example` otomatis mengisi `.env`?

Tidak.

Contoh:

GitHub:

```text
.env.example
PAYMENT_BANK_ACCOUNT=ISI_NOMOR_REKENING
```

VPS:

```text
.env
PAYMENT_BANK_ACCOUNT=1234567890
```

Setelah:

```bash
mekanik-dev pull
```

hasilnya tetap:

```text
.env.example = ISI_NOMOR_REKENING
.env         = 1234567890
```

Aplikasi production tetap memakai nilai dari `.env` VPS.

---

# 46. Contoh: Mengganti Nomor Rekening yang Sudah Ada

Jika setting berikut sudah tersedia:

```text
PAYMENT_BANK_ACCOUNT
```

dan Anda hanya ingin mengganti nomor rekening, Anda tidak perlu mengubah GitHub.

Masuk VPS:

```bash
cd /home/mekanik/mekanik-bot
nano .env
```

Cari:

```text
PAYMENT_BANK_ACCOUNT=nomor_lama
```

ubah:

```text
PAYMENT_BANK_ACCOUNT=nomor_baru
```

Simpan.

Karena source code tidak berubah, biasanya tidak perlu build ulang image.

Tetapi container perlu dibuat ulang agar environment baru dibaca:

```bash
docker compose up -d --force-recreate api worker
```

Cek:

```bash
docker compose ps
curl http://127.0.0.1:8080/health
```

---

# 47. Contoh: Menambah Rekening Baru, Bukan Sekadar Mengganti Nomor

Misalnya aplikasi sekarang hanya mengenal:

```text
PAYMENT_BANK_ACCOUNT
```

Anda ingin menambah rekening kedua:

```text
PAYMENT_BANK_ACCOUNT_2
```

Ini adalah **perubahan struktur konfigurasi**.

Maka langkahnya berbeda.

## GitHub

Edit:

```text
.env.example
app/config.py
```

Contoh `.env.example`:

```text
PAYMENT_BANK_ACCOUNT=ISI_REKENING_UTAMA
PAYMENT_BANK_ACCOUNT_2=ISI_REKENING_KEDUA
```

Di `app/config.py`, aplikasi harus mengenali setting baru tersebut.

Jika rekening kedua akan ditampilkan ke customer, file lain yang mungkin ikut berubah:

```text
app/customer.py
app/finance.py
app/pricing.py
```

tergantung fungsi sebenarnya.

## VPS

Setelah GitHub di-commit:

```bash
mekanik-dev pull
```

Lalu edit:

```bash
nano /home/mekanik/mekanik-bot/.env
```

Isi:

```text
PAYMENT_BANK_ACCOUNT=1234567890
PAYMENT_BANK_ACCOUNT_2=0987654321
```

Kemudian:

```bash
mekanik-deploy main
```

Test.

Jika sudah benar:

```bash
mekanik-dev release 0.3.0-beta.2 "tambah rekening kedua"
mekanik-deploy v0.3.0-beta.2
```

---

# 48. Mengapa `.env.example` Tetap Penting?

Walaupun aplikasi production tidak memakai `.env.example` sebagai nilai runtime, file ini tetap penting.

Fungsinya:

```text
1. dokumentasi daftar environment variable
2. template instalasi server baru
3. memberi tahu developer setting apa yang diperlukan
4. membantu preflight/config review
5. mencegah secret asli masuk GitHub
```

Jadi konsepnya:

```text
.env.example
=
NAMA dan CONTOH konfigurasi

.env
=
NILAI ASLI konfigurasi production
```

---

# 49. Apa yang Terjadi Jika `ai.py` Diedit di GitHub?

Misalnya Anda mengedit:

```text
app/ai.py
```

dan commit ke GitHub.

Lalu di VPS:

```bash
mekanik-dev pull
```

Pada tahap ini:

```text
GitHub source = BARU
VPS source    = BARU
Docker runtime = MASIH SOURCE LAMA
```

Mengapa?

Karena aplikasi berjalan di dalam Docker image yang sudah dibangun sebelumnya.

Source baru pada filesystem VPS belum otomatis dipakai container yang sedang berjalan.

Jadi:

```text
git pull
≠
langsung mengubah aplikasi yang sedang berjalan
```

---

# 50. Kapan Source Baru Mulai Aktif?

Setelah:

```bash
mekanik-deploy main
```

Secara konsep:

```text
source baru
↓
build image API + worker
↓
recreate API + worker
↓
health check
↓
source baru aktif
```

Database dan GoWA tidak perlu dibuild ulang untuk perubahan Python biasa.

---

# 51. Apakah `mekanik-dev pull` Mengganggu Aplikasi yang Sedang Berjalan?

Pada arsitektur sekarang:

```text
mekanik-dev pull
```

hanya mengubah source repository di VPS.

Container API/worker yang sedang berjalan tetap menggunakan image lama.

Jadi pull sendiri pada umumnya tidak mengganggu bot yang aktif.

Namun source filesystem VPS sudah menjadi source baru, sedangkan runtime masih source lama.

Kondisi ini normal sementara.

Cek dengan:

```bash
mekanik-version
```

---

# 52. Apakah `mekanik-deploy main` Mengganggu Aplikasi?

Saat deployment:

```text
API + worker
```

akan dibuild dan direcreate.

Kemungkinan ada jeda singkat saat container lama diganti container baru.

Yang tetap berjalan:

```text
PostgreSQL
GoWA
```

untuk perubahan source Python normal.

Setelah start, health check memastikan API kembali sehat.

---

# 53. Perbedaan `pull`, `deploy`, dan `release`

## `mekanik-dev pull`

Tujuan:

```text
GitHub → source VPS
```

Tidak otomatis mengaktifkan source baru di container.

---

## `mekanik-deploy main`

Tujuan:

```text
source main terbaru → Docker runtime
```

Digunakan untuk testing development.

---

## `mekanik-dev release`

Tujuan:

```text
membuat versi resmi/tag baru
```

Contoh:

```bash
mekanik-dev release 0.3.0-beta.2 "peningkatan AI"
```

---

## `mekanik-deploy v0.3.0-beta.2`

Tujuan:

```text
menjalankan release tertentu
```

---

# 54. Contoh Workflow AI yang Aman

Misalnya Anda ingin memperbaiki:

```text
app/ai.py
```

## GitHub

Edit:

```text
app/ai.py
```

Commit:

```text
feat: improve Indonesian and Javanese understanding
```

## VPS

Tarik source:

```bash
mekanik-dev pull
```

Cek source/runtime:

```bash
mekanik-version
```

Aktifkan untuk testing:

```bash
mekanik-deploy main
```

Test WhatsApp.

Jika masih salah:

```text
Edit GitHub lagi
↓
commit
↓
mekanik-dev pull
↓
mekanik-deploy main
↓
test lagi
```

Jika sudah stabil:

```bash
mekanik-dev release 0.3.0-beta.2 "peningkatan kecerdasan AI"
mekanik-deploy v0.3.0-beta.2
```

---

# 55. Kemungkinan Masalah: Setting Baru Ada di `.env.example`, Tetapi Tidak Bekerja

Contoh Anda menambahkan:

```text
MEMORY_ENABLED=true
```

ke:

```text
.env.example
```

tetapi aplikasi tidak berubah.

Kemungkinan penyebab:

```text
app/config.py
```

belum membaca setting tersebut.

Artinya:

```text
.env.example
sendiri
tidak membuat fitur baru.
```

Urutannya harus:

```text
.env.example
+
config.py
+
source yang menggunakan setting tersebut
+
.env VPS
```

---

# 56. Kemungkinan Masalah: Setting Sudah Ada di `.env`, Tetapi Container Masih Memakai Nilai Lama

Penyebab paling umum:

container belum direcreate.

Solusi untuk perubahan environment saja:

```bash
docker compose up -d --force-recreate api worker
```

Untuk perubahan source sekaligus:

```bash
mekanik-deploy main
```

---

# 57. Kemungkinan Masalah: Nama Variable Salah

Contoh source membaca:

```text
PAYMENT_BANK_ACCOUNT
```

tetapi `.env` berisi:

```text
PAYMENT_BANK_ACOUNT
```

satu huruf kurang.

Akibatnya aplikasi dapat memakai:

```text
blank
default value
atau gagal preflight/start
```

Selalu samakan nama variable antara:

```text
.env.example
.env VPS
app/config.py
docker-compose.yml jika digunakan
```

---

# 58. Kemungkinan Masalah: Variable Ada di `.env`, Tetapi Tidak Diteruskan ke Container

Ini dapat terjadi bila:

```text
docker-compose.yml
```

tidak menggunakan variable tersebut, atau aplikasi tidak membaca environment tersebut.

Periksa alur:

```text
.env
↓
docker-compose.yml
↓
container environment
↓
app/config.py
↓
kode aplikasi
```

Tidak semua variable harus ditulis satu per satu di compose jika compose memakai `env_file`, tetapi konsep alurnya tetap sama.

---

# 59. Kemungkinan Masalah: `.env.example` Berisi Secret Asli

Ini berbahaya.

Contoh yang salah:

```text
GEMINI_API_KEY=AIza........
```

Yang benar:

```text
GEMINI_API_KEY=ISI_GEMINI_API_KEY
```

Jika secret sudah telanjur masuk GitHub:

```text
anggap secret sudah bocor
↓
rotate/ganti secret
↓
hapus dari source
↓
jangan hanya menghapus commit terbaru
```

---

# 60. Kemungkinan Masalah: Edit `ai.py` Menghasilkan Syntax Error

Contoh:

```text
kurang tanda kurung
indent salah
quote tidak ditutup
```

Akibat:

```text
build/preflight gagal
atau API gagal start
```

Sebelum release, source perlu lolos:

```bash
python3 -m py_compile app/*.py
```

Script deployment Anda juga memiliki preflight.

---

# 61. Kemungkinan Masalah: AI Source Valid, Tetapi Behavior Salah

Contoh:

```text
syntax benar
API sehat
tetapi AI salah memahami customer
```

Ini bukan deployment error.

Ini adalah logic/regression error.

Solusi:

```text
perbaiki ai.py/customer.py
tambahkan test
deploy main
uji WhatsApp
```

Jangan mengubah database untuk masalah seperti ini.

---

# 62. Kemungkinan Masalah: Menambah Library Baru

Misalnya Anda menulis di `ai.py`:

```python
import some_new_library
```

tetapi lupa menambah:

```text
requirements.txt
```

Akibat:

```text
ModuleNotFoundError
```

Langkah benar:

```text
1. edit source
2. update requirements.txt
3. commit
4. pull
5. deploy main
```

Docker build akan memasang dependency baru.

---

# 63. Kemungkinan Masalah: Mengubah Database Schema

Misalnya ingin menambah:

```text
customer_memory
```

Jangan hanya edit:

```text
app/schema.sql
```

lalu berharap database production berubah.

Database production sudah mempunyai data.

Yang dibutuhkan:

```text
migration
```

Contoh prinsip:

```text
ALTER TABLE ...
CREATE TABLE IF NOT EXISTS ...
CREATE INDEX ...
```

dengan backup sebelumnya.

Jangan:

```text
drop database
reinitialize database
docker compose down -v
```

untuk menerapkan perubahan schema.

---

# 64. Kemungkinan Masalah: GitHub Sudah Diedit, Tetapi `pull` Ditolak

Kemungkinan:

```text
ada perubahan lokal di VPS
```

Cek:

```bash
git status
```

Sistem `mekanik-dev pull` sengaja menolak jika ada perubahan lokal agar file tidak tertimpa.

Solusi:

```text
tentukan apakah perubahan lokal:
- perlu disimpan ke GitHub
- perlu dibuang
- perlu dibandingkan
```

Jangan langsung:

```bash
git reset --hard
```

jika belum tahu isi perubahan lokal.

---

# 65. Kemungkinan Masalah: GitHub dan VPS Berada di Branch Berbeda

Deployment release sering meninggalkan Git pada kondisi:

```text
detached/tag
```

Ini normal untuk production release.

Ketika:

```bash
mekanik-dev pull
```

script development akan mencoba kembali ke:

```text
main
```

sebelum menarik update.

Jangan panik jika:

```bash
git branch --show-current
```

kosong setelah deploy tag.

Cek:

```bash
mekanik-version
```

---

# 66. Kemungkinan Masalah: Source VPS Baru Tetapi Runtime Masih Lama

Ini terjadi setelah:

```bash
mekanik-dev pull
```

tetapi sebelum:

```bash
mekanik-deploy main
```

Ini bukan error.

Kondisi:

```text
source = baru
runtime = lama
```

Gunakan:

```bash
mekanik-version
```

untuk membedakan source dan runtime.

---

# 67. Kemungkinan Masalah: Deploy Gagal

Kemungkinan penyebab:

```text
syntax error
dependency gagal install
config baru belum ada di .env
database tidak aktif
health endpoint gagal
source incompatible
```

Periksa:

```bash
docker compose logs --tail=200 api
docker compose logs --tail=200 worker
mekanik-version
```

Jangan reset database.

---

# 68. Catatan Penting Tentang Rollback Otomatis Saat Ini

Ada satu skenario yang perlu dipahami pada workflow sekarang:

```text
release lama sedang berjalan
↓
mekanik-dev pull
↓
working tree berpindah ke commit main baru
↓
mekanik-deploy main
```

Pada desain deployment saat ini, `deploy.sh` menggunakan commit source yang sedang checkout sebagai `CURRENT_COMMIT`.

Jika source sudah berpindah ke commit baru sebelum deploy, maka pada beberapa kondisi kegagalan build/deploy:

```text
CURRENT_COMMIT
```

bisa sama dengan target baru.

Artinya rollback otomatis **tidak selalu identik dengan "kembali ke runtime release yang sebelumnya sedang berjalan"**.

Karena itu, sampai mekanisme rollback ini diperbaiki, untuk recovery yang paling jelas gunakan tag release yang diketahui stabil:

```bash
mekanik-rollback v0.3.0-beta.1
```

atau deploy ulang tag stabil:

```bash
mekanik-deploy v0.3.0-beta.1
```

### Rekomendasi improvement berikutnya

Ubah deployment agar rollback mengambil:

```text
/home/mekanik/.mekanik-bot-deploy/current_commit
```

sebagai sumber versi runtime sebelumnya, bukan hanya:

```text
git rev-parse HEAD
```

Ini akan membuat automatic rollback lebih akurat.

---

# 69. Kemungkinan Masalah: Perubahan Config Baru Membuat Preflight Gagal

Jika Anda menambah variable baru dan menjadikannya wajib, preflight dapat gagal karena `.env` VPS belum mempunyai variable tersebut.

Flow aman:

```text
1. edit GitHub
2. commit
3. pull ke VPS
4. tambah value baru di .env VPS
5. baru deploy main
```

Jangan deploy dulu jika config wajib belum diisi.

---

# 70. Kemungkinan Masalah: Mengganti Password Database di `.env`

Mengubah:

```text
POSTGRES_PASSWORD
```

di `.env` saja **tidak otomatis mengganti password role PostgreSQL yang sudah ada**.

Ini berbeda dengan variable aplikasi biasa.

Untuk database yang sudah diinisialisasi, password user database tersimpan di PostgreSQL.

Jadi:

```text
ubah .env saja
≠
ubah password PostgreSQL existing user
```

Perubahan seperti ini harus dilakukan dengan prosedur database yang benar.

---

# 71. Kemungkinan Masalah: Mengubah GOWA Password atau Device Setting

Setting GoWA dapat memengaruhi:

```text
auth API
device ID
webhook
outbound WhatsApp
```

Jangan mengubah konfigurasi tersebut hanya dari `.env.example`.

Pastikan nilai di VPS sesuai dengan service GoWA yang sedang berjalan.

Kesalahan dapat membuat:

```text
pesan masuk ada
tetapi outbound gagal
```

atau sebaliknya.

---

# 72. Kemungkinan Masalah: Mengubah Nomor Owner

Jika hanya mengganti:

```text
OWNER_WA_NUMBER
```

dan source sudah mendukung variable tersebut:

```text
cukup ubah .env VPS
```

lalu recreate container yang membaca config.

Tidak perlu commit nomor owner asli ke GitHub.

---

# 73. Kemungkinan Masalah: Mengubah Harga di `.env`, Padahal Harga Berasal dari Database

Jangan asumsi semua setting bisnis berasal dari `.env`.

Project Anda mempunyai data harga/business data di database.

Jika harga berasal dari:

```text
service_price_matrix
```

maka mengubah `.env` tidak akan mengubah harga tersebut.

Sebelum edit, tentukan sumber kebenaran:

```text
.env?
Python?
PostgreSQL?
```

---

# 74. Menentukan Sumber Kebenaran Sebelum Edit

Gunakan prinsip ini:

```text
SECRET / SERVER CONFIG
→ .env VPS

DAFTAR CONFIG YANG DIBUTUHKAN
→ .env.example

LOGIC PROGRAM
→ app/*.py

DATA TRANSAKSI
→ PostgreSQL

MEDIA CUSTOMER
→ data/media + attachments database

VERSI SOURCE
→ GitHub + VERSION + Git tag

RUNTIME
→ Docker containers
```

Ini adalah salah satu konsep terpenting untuk development project ini.

---

# 75. Decision Tree: Saya Harus Edit Di Mana?

## Saya ingin mengganti nilai rahasia/config yang sudah ada

Contoh:

```text
nomor rekening
API key
owner number
token
```

Edit:

```text
VPS .env
```

Tidak perlu GitHub.

---

## Saya ingin menambah jenis setting baru

Edit:

```text
.env.example
app/config.py
source yang menggunakan setting
```

Lalu isi nilai sebenarnya di:

```text
VPS .env
```

---

## Saya ingin mengubah logic chatbot

Edit:

```text
GitHub app/*.py
```

Lalu:

```bash
mekanik-dev pull
mekanik-deploy main
```

---

## Saya ingin mengubah data transaksi

Jangan edit GitHub terlebih dahulu.

Tentukan apakah data berada di:

```text
PostgreSQL
```

Contoh:

```text
harga
order
payment
technician data
```

---

## Saya ingin mengubah Docker/service

Edit:

```text
Dockerfile
docker-compose.yml
```

Hanya jika memang perubahan infrastructure.

---

# 76. Tabel Skenario Development

| Keinginan | GitHub | VPS `.env` | Database | Perlu Deploy |
|---|---:|---:|---:|---:|
| Ganti nomor rekening existing | Tidak | Ya | Tidak | Recreate |
| Ganti Gemini API key | Tidak | Ya | Tidak | Recreate |
| Ganti owner WA number | Tidak | Ya | Tidak | Recreate |
| Tambah config baru | Ya | Ya | Mungkin | Ya |
| Ubah AI behavior | Ya | Tidak | Tidak | Ya |
| Ubah greeting | Ya | Tidak | Tidak | Ya |
| Ubah matching | Ya | Tidak | Mungkin | Ya |
| Ubah harga dari DB | Tidak/Mungkin | Tidak | Ya | Tergantung |
| Tambah tabel | Ya | Mungkin | Ya | Ya |
| Tambah library | Ya | Tidak | Tidak | Ya |
| Update dokumentasi | Ya | Tidak | Tidak | Tidak |
| Ganti runtime secret | Tidak | Ya | Tidak | Recreate |
| Ganti DB password existing | Mungkin | Ya | Ya | Prosedur khusus |

---

# 77. Workflow Aman Sebelum dan Sesudah Edit

Sebelum edit:

```bash
mekanik-version
```

Catat versi stabil.

Edit di GitHub.

Commit.

Di VPS:

```bash
mekanik-dev pull
```

Jika ada config baru:

```bash
nano .env
```

Kemudian:

```bash
mekanik-deploy main
```

Test.

Jika stabil:

```bash
mekanik-dev release 0.3.0-beta.2 "keterangan"
mekanik-deploy v0.3.0-beta.2
```

Jika bermasalah:

```bash
mekanik-deploy v0.3.0-beta.1
```

atau tag stabil terakhir.

---

# 78. Checklist Saat Menambah Environment Variable Baru

Contoh variable baru:

```text
MEMORY_ENABLED
```

Checklist:

```text
[ ] Tambah ke .env.example
[ ] Tambah pembacaan di app/config.py
[ ] Source benar-benar memakai variable tersebut
[ ] Isi nilai di VPS .env
[ ] Pastikan nama variable sama persis
[ ] Pull source
[ ] Deploy main
[ ] Cek logs
[ ] Test fitur
[ ] Baru release
```

---

# 79. Checklist Saat Mengedit `ai.py`

```text
[ ] Edit di branch/main GitHub
[ ] Jangan masukkan secret
[ ] Jangan mengubah pricing/payment tanpa alasan
[ ] Commit perubahan
[ ] mekanik-dev pull
[ ] mekanik-deploy main
[ ] cek API
[ ] test Bahasa Indonesia
[ ] test typo
[ ] test Bahasa Jawa
[ ] test jumlah mesin
[ ] test cancel
[ ] test model number
[ ] jika stabil baru release
```

---

# 80. Prinsip Akhir yang Harus Diingat

```text
GitHub
=
source code

.env VPS
=
secret dan nilai konfigurasi server

PostgreSQL
=
data transaksi

Docker
=
aplikasi yang benar-benar sedang berjalan
```

Karena itu:

```text
edit GitHub
tidak otomatis
mengubah runtime
```

dan:

```text
edit .env.example
tidak otomatis
mengubah .env
```

serta:

```text
edit .env
tidak selalu
berarti business data berubah
```

Selalu tentukan terlebih dahulu:

```text
SOURCE OF TRUTH-NYA DI MANA?
```

baru lakukan editing.
