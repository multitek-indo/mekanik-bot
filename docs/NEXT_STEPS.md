# Multitek Service - Development Checkpoint

## 1. Current Version

Versi saat checkpoint ini dibuat:

0.3.0-beta.1

Git tag yang akan digunakan:

v0.3.0-beta.1

Status:

BETA

Alasan masih beta:

forwarding foto dan video dari customer ke WhatsApp mekanik sudah diimplementasikan tetapi belum diverifikasi dengan live test lengkap.

## 2. Project Location

VPS:

/home/mekanik/mekanik-bot

GitHub repository:

git@github.com:multitek-indo/mekanik-bot.git

Branch utama:

main

## 3. Infrastructure yang Sudah Berjalan

Docker services:

db
api
gowa
worker

Database:

PostgreSQL 17

API:

FastAPI

WhatsApp gateway:

GoWA v9.3.1

API binding:

127.0.0.1:8080

GoWA binding:

127.0.0.1:3000

## 4. AI Configuration

AI aktif.

Primary:

Gemini
gemini-3.5-flash-lite

Fallback:

Groq
openai/gpt-oss-120b

Confidence threshold:

0.78

Prinsip:

AI digunakan untuk memahami bahasa manusia.

Business logic tetap deterministic.

Harga, payment, order, status dan settlement tidak boleh ditentukan bebas oleh AI.

## 5. Bahasa yang Sudah Didukung

Bot dirancang memahami:

- Bahasa Indonesia
- Bahasa Indonesia santai
- typo
- singkatan
- Bahasa Jawa ngoko
- Bahasa Jawa krama
- campuran Jawa dan Indonesia

Contoh yang sudah pernah diuji:

mesin jhkitku juki ra gelem mlaku
mung siji mas
loro unit mas
juki ddl-8700 mati total
ora dadi mas sesuk wae

## 6. Customer Flow yang Sudah Berfungsi

Flow:

customer chat
-> identifikasi mesin
-> identifikasi keluhan
-> jumlah mesin
-> lokasi
-> konfirmasi lokasi
-> foto/video
-> landmark
-> create order
-> matching

Pembatalan:

BATAL

## 7. Price Context

Jika customer bertanya:

saya punya mesin jarum 1 juki sering loncat, kira-kira biayanya berapa?

bot dapat menyimpan sementara:

Mesin Jarum 1 Juki
Sering loncat

State:

cust_price_context

Context disimpan sementara sekitar 6 jam.

Jika customer kemudian mengatakan:

yawes mas kirim mekanik ke tempatku

bot dapat melanjutkan mesin dan keluhan sebelumnya.

## 8. Greeting Optimization

Greeting sederhana tidak perlu memanggil AI.

Contoh:

HALO
HAI
HI
PAGI
SIANG
SORE
MALAM
MAS
MIN
ADMIN
PERMISI

Tujuan:

- respon lebih cepat
- menghemat quota AI
- menghindari greeting tidak sesuai waktu

## 9. Customer Media

Customer dapat mengirim:

- image
- video
- video note

Media disimpan ke:

/app/data/media/incoming/

Attachment disimpan di tabel:

attachments

Purpose:

CUSTOMER_MACHINE_PHOTO
CUSTOMER_MACHINE_VIDEO

Limit saat ini:

maksimal 6 media per mesin

maksimal 20 media per order

## 10. Media yang Sudah Terverifikasi

Order test:

MTK-260917-0002

Item:

Mesin Jarum 1 Juki

Keluhan:

Sering loncat

Attachment yang berhasil disimpan:

CUSTOMER_MACHINE_PHOTO

Media type:

image

Matching helper juga sudah berhasil membaca attachment tersebut.

Helper:

_customer_reference_media()

## 11. Media Forwarding ke Mekanik

Source forwarding sudah berada di:

app/matching.py

Mendukung:

send_image
send_file

Flow yang diharapkan:

customer attachment
-> attachments table
-> matching
-> candidate mechanic
-> job offer text
-> customer photo/video

Kegagalan mengirim media tidak boleh membatalkan job offer utama.

## 12. PRIORITAS PERTAMA SESI BERIKUTNYA

Jangan langsung membuat fitur baru.

Lakukan live verification terlebih dahulu.

Langkah:

1. cek teknisi yang aktif
2. pastikan is_active = true
3. pastikan is_available = true
4. pastikan lokasi mekanik tersedia
5. pastikan skill sesuai
6. buat order customer baru
7. gunakan Mesin Jarum 1 Juki atau mesin yang skill mekaniknya tersedia
8. kirim 1 foto
9. kirim 1 video pendek
10. selesaikan intake
11. pastikan order baru dibuat
12. pastikan job offer terkirim ke mekanik
13. pastikan foto diterima mekanik
14. pastikan video diterima mekanik
15. cek attachments database
16. cek logs API
17. cek logs GoWA
18. cek logs worker

Jika semua lulus, media forwarding dianggap VERIFIED.

## 13. Query Mekanik untuk Live Test

Periksa mekanik:

SELECT
    name,
    wa_number,
    is_active,
    is_available,
    base_lat,
    base_lon,
    service_radius_km,
    current_lat,
    current_lon,
    current_location_at
FROM technicians;

Periksa skill:

SELECT
    t.name,
    t.wa_number,
    s.skill_code,
    s.skill_name,
    s.level,
    s.verified
FROM technicians t
LEFT JOIN technician_skill_matrix s
ON s.technician_id = t.id
WHERE t.is_active = true;

## 14. Setelah Media Forwarding Lulus

Tahap development berikutnya:

PERSISTENT CONVERSATION MEMORY

Tujuan:

bot tidak hanya mengingat current state, tetapi dapat memahami history customer secara relevan.

Arsitektur target:

recent messages
+
conversation state
+
customer profile
+
machine history
+
previous orders
+
conversation summary

## 15. Rencana Conversation Memory

Kemungkinan tabel baru:

conversation_messages

Contoh field:

id
wa_number
role
content
parsed
order_id
created_at

Kemungkinan memory summary:

customer_memory

Contoh:

preferred_language
known_machines
common_problems
conversation_summary
updated_at

Detail schema harus dirancang terlebih dahulu sebelum migration.

Jangan langsung mengubah database production tanpa migration plan.

## 16. Prinsip Memory

Memory tidak boleh menggantikan database transaksi.

Contoh:

AI boleh mengingat:

customer biasa memakai mesin Juki
customer lebih sering menggunakan Bahasa Jawa
customer sebelumnya mengeluhkan loncat jahitan

Tetapi nilai berikut tetap harus berasal dari database:

harga
payment status
order status
assigned technician
settlement
invoice
booking fee

## 17. Versioning yang Sudah Dipasang

File versi:

VERSION

Saat ini:

0.3.0-beta.1

Version module:

app/version.py

Health endpoint memberikan:

version
commit
environment

Command:

mekanik-version

## 18. Deployment System

Commands:

mekanik-deploy
mekanik-rollback
mekanik-version

Deployment script:

scripts/deploy.sh

Rollback:

scripts/rollback.sh

Version check:

scripts/version.sh

Backup:

scripts/backup.sh

Preflight:

scripts/preflight.sh

## 19. Deployment Target

Deploy release:

mekanik-deploy v0.3.0-beta.1

Latest tag:

mekanik-deploy latest

Latest main:

mekanik-deploy main

Rollback:

mekanik-rollback

## 20. Deployment Safety

Sebelum deploy:

- repository harus bersih
- database harus aktif
- backup database dilakukan
- preflight harus lulus

Deployment hanya build:

api
worker

Tidak perlu reset:

db
gowa

## 21. Database Safety

JANGAN menggunakan:

docker compose down -v

JANGAN menghapus volume PostgreSQL untuk menyelesaikan bug aplikasi.

JANGAN reinitialize database yang sudah mempunyai transaksi.

Backup harus tersedia sebelum migration besar.

## 22. Git Safety

Jangan commit:

.env
API key
password
token
media customer
database dump
backup database
runtime data

Jangan force push release tag.

Tag release harus immutable.

## 23. Dokumentasi

Manual:

docs/MANUAL_BOOK.md

Deployment:

docs/DEPLOYMENT.md

Versioning:

docs/VERSIONING.md

Rollback:

docs/ROLLBACK.md

Customer / mechanic commands:

docs/COMMANDS.md

Flow:

docs/FLOW.md

Installation:

docs/INSTALLATION.md

Pricing:

docs/PRICING.md

Checkpoint:

docs/NEXT_STEPS.md

## 24. Kondisi Saat Berhenti

API sehat.

Runtime version:

0.3.0-beta.1

Source version:

0.3.0-beta.1

Runtime commit masih dapat menunjukkan:

unknown

sampai aplikasi pertama kali dideploy menggunakan mekanik-deploy dengan build argument GIT_COMMIT.

GitHub checkpoint v0.3.0-beta.1 masih harus:

- safety scan
- git add
- commit
- create tag
- push main
- push tag
- test deploy dari tag
- test rollback

## 25. Instruksi Ketika Melanjutkan

Mulai dengan:

cd /home/mekanik/mekanik-bot

mekanik-version

git status

git log --oneline --decorate -5

docker compose ps

Kemudian baca:

cat docs/NEXT_STEPS.md

Prioritas pertama:

LIVE TEST FOTO + VIDEO CUSTOMER KE MEKANIK.

Jangan melanjutkan persistent memory sebelum forwarding media sudah terbukti stabil.

