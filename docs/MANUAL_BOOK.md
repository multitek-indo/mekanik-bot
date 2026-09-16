# Multitek Service - Manual Book

## 1. Fungsi Sistem

Multitek Service adalah sistem WhatsApp untuk menghubungkan customer yang membutuhkan perbaikan mesin dengan mekanik yang sesuai.

Komponen utama:

- WhatsApp / GoWA
- FastAPI
- PostgreSQL
- Worker
- Gemini sebagai AI primary
- Groq sebagai AI fallback
- Sistem matching mekanik
- Penyimpanan foto/video customer
- Sistem deployment dan versioning Git

## 2. Prinsip Sistem

AI digunakan untuk memahami bahasa manusia, typo, singkatan, Bahasa Indonesia dan Bahasa Jawa.

Data transaksi tidak ditentukan oleh AI.

Data berikut tetap dikendalikan backend dan database:

- order
- harga
- pembayaran
- status
- settlement
- attachment
- mekanik
- riwayat service

## 3. Flow Customer

Alur service:

Customer chat
-> bot memahami jenis mesin dan keluhan
-> menentukan jumlah mesin
-> meminta Share Location
-> customer mengonfirmasi lokasi
-> customer mengirim foto/video
-> customer memberikan patokan
-> order dibuat
-> sistem mencari mekanik
-> mekanik menerima penawaran job

Customer dapat membatalkan proses dengan:

BATAL

## 4. Bahasa yang Didukung

Bot dirancang memahami:

- Bahasa Indonesia formal
- Bahasa Indonesia santai
- typo
- singkatan
- Bahasa Jawa ngoko
- Bahasa Jawa krama
- campuran Indonesia dan Jawa

Contoh:

butuh mekanik mas
mung siji
loro unit
mesinku juki ra gelem mlaku
mboten wonten patokane

## 5. Pertanyaan Harga

Customer boleh bertanya harga terlebih dahulu.

Contoh:

mesin jarum 1 juki sering loncat, kira-kira berapa ya?

Sistem dapat menyimpan sementara informasi mesin dan keluhan.

Jika kemudian customer berkata:

yawes mas kirim mekanik ke tempatku

bot dapat melanjutkan proses menggunakan konteks mesin sebelumnya.

## 6. Foto dan Video Customer

Setelah lokasi dikonfirmasi, customer dapat mengirim:

- foto mesin
- beberapa foto
- video kerusakan
- video suara atau gerakan abnormal

Jika selesai, customer mengetik:

SELESAI

Jika tidak mempunyai dokumentasi:

LEWATI

Attachment disimpan dengan purpose:

CUSTOMER_MACHINE_PHOTO
CUSTOMER_MACHINE_VIDEO
## 7. Nomor Service

Format nomor service:

MTK-YYMMDD-NNNN

Contoh:

MTK-260917-0002

Tanggal menggunakan zona waktu Asia/Jakarta.

## 8. Mekanik

Pendaftaran mekanik dimulai dengan:

DAFTAR MEKANIK

Mekanik yang dapat menerima job harus memenuhi antara lain:

- aktif
- available
- memiliki lokasi
- berada dalam radius pelayanan
- memiliki skill yang sesuai

Referensi command mekanik lengkap:

docs/COMMANDS.md

## 9. Owner / Admin

Owner memiliki command khusus untuk administrasi order, mekanik dan pembayaran.

Referensi:

docs/COMMANDS.md

## 10. Mengecek Kondisi Server

Status container:

docker compose ps

Health API:

curl http://127.0.0.1:8080/health

Log API:

docker compose logs --tail=100 api

Log worker:

docker compose logs --tail=100 worker

Log GoWA:

docker compose logs --tail=100 gowa

## 11. Mengecek Versi

Gunakan:

mekanik-version

Informasi yang ditampilkan meliputi:

- source version
- Git tag / describe
- source commit
- Git branch
- runtime API version
- runtime commit
- deployment ref
- deployment commit
- status container

## 12. Deployment

Deploy tag tertentu:

mekanik-deploy v0.3.0-beta.1

Deploy tag terbaru:

mekanik-deploy latest

Deploy branch main:

mekanik-deploy main

Untuk production lebih disarankan menggunakan tag versi.

## 13. Rollback

Rollback ke deployment sebelumnya:

mekanik-rollback

Rollback ke versi tertentu:

mekanik-rollback v0.3.0-beta.1

Rollback aplikasi tidak otomatis mengembalikan database.

## 14. Backup Database

Sebelum deployment, database dibackup.

Script:

scripts/backup.sh

Backup tersimpan di folder:

backups/

Jangan menghapus backup sebelum memastikan versi baru stabil.

## 15. File Rahasia dan Runtime

Jangan dimasukkan ke GitHub:

.env
password
API key
token
database dump
backup database
foto/video customer
file runtime

File .env.example boleh masuk GitHub selama hanya berisi placeholder.

## 16. Larangan Penting

Jangan menjalankan:

docker compose down -v

pada production kecuali benar-benar memahami dampaknya karena opsi -v dapat menghapus volume database.

Jangan melakukan:

git push --force

ke branch production tanpa alasan yang jelas.

Jangan mengedit source production secara permanen tanpa menyimpan perubahannya ke GitHub.

## 17. Dokumen Project

Dokumentasi utama:

README.md
docs/MANUAL_BOOK.md
docs/COMMANDS.md
docs/FLOW.md
docs/INSTALLATION.md
docs/DEPLOYMENT.md
docs/VERSIONING.md
docs/ROLLBACK.md
docs/NEXT_STEPS.md
CHANGELOG.md
VERSION

## 18. Versi Saat Ini

Checkpoint saat manual ini dibuat:

0.3.0-beta.1

Status penting:

- customer photo sudah berhasil disimpan ke database
- matching sudah berhasil membaca attachment customer
- forwarding foto/video ke mekanik sudah diimplementasikan
- live test foto dan video sampai ke WhatsApp mekanik belum dilakukan
