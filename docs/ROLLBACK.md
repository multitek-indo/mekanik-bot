# Multitek Service - Rollback Guide

## 1. Tujuan

Rollback digunakan untuk mengembalikan aplikasi ke versi sebelumnya ketika release baru mengalami masalah.

Rollback aplikasi tidak otomatis mengembalikan database.

Prinsip:

aplikasi rollback
!=
database rollback

Hal ini sengaja dilakukan agar transaksi terbaru di database tidak hilang.

## 2. Rollback Otomatis Saat Deploy

Jika deployment baru gagal pada tahap:

- build
- startup
- health check
- version validation

scripts/deploy.sh mencoba rollback otomatis.

Flow:

release baru gagal
-> checkout commit sebelumnya
-> build API + worker versi sebelumnya
-> restart API + worker
-> health check

Database dan GoWA tidak dihapus.

## 3. Rollback Manual ke Deployment Sebelumnya

Gunakan:

mekanik-rollback

Script akan membaca:

/home/mekanik/.mekanik-bot-deploy/previous_commit

Kemudian melakukan deployment commit tersebut.

## 4. Rollback ke Versi Tertentu

Contoh:

mekanik-rollback v0.3.0-beta.1

Versi dapat berupa Git tag.

Contoh lain:

mekanik-rollback v0.3.0-beta.2

## 5. Rollback ke Commit Tertentu

Jika mengetahui Git commit:

mekanik-rollback COMMIT_HASH

Contoh:

mekanik-rollback a751801

Sebaiknya gunakan Git tag bila tersedia karena lebih mudah dilacak.

## 6. Backup Database

Sebelum deployment, scripts/deploy.sh menjalankan:

scripts/backup.sh

Backup tersimpan pada:

backups/

Format:

multitek-service-TIMESTAMP.dump

Checksum:

multitek-service-TIMESTAMP.dump.sha256

## 7. Melihat Backup

Gunakan:

ls -lh backups/

Untuk melihat backup terbaru:

ls -lht backups/ | head

## 8. Database Tidak Direstore Otomatis

Rollback aplikasi tidak menjalankan restore PostgreSQL otomatis.

Alasannya:

- data transaksi baru mungkin sudah masuk
- restore otomatis dapat menghapus data terbaru
- perubahan schema perlu dianalisis terlebih dahulu
- restore database adalah tindakan berisiko tinggi

Jika pada masa depan ada migration database besar, migration harus mempunyai strategi forward dan rollback sendiri.

## 9. Deployment State

Lokasi:

/home/mekanik/.mekanik-bot-deploy

File:

current_commit
previous_commit
current_ref
history.log

Untuk melihat:

ls -lah /home/mekanik/.mekanik-bot-deploy

## 10. Melihat Riwayat Deployment

Gunakan:

cat /home/mekanik/.mekanik-bot-deploy/history.log

Atau:

tail -n 20 /home/mekanik/.mekanik-bot-deploy/history.log

## 11. Cek Versi Sebelum Rollback

Gunakan:

mekanik-version

Catat:

- Source version
- Source commit
- Runtime API
- Runtime commit
- Deploy ref
- Deploy commit

Ini penting agar diketahui kondisi sebelum rollback.

## 12. Cek Kondisi Setelah Rollback

Setelah rollback:

mekanik-version

Kemudian:

docker compose ps

Cek health:

curl http://127.0.0.1:8080/health

## 13. Jika API Tidak Sehat

Periksa:

docker compose logs --tail=200 api

Periksa worker:

docker compose logs --tail=200 worker

Periksa container:

docker compose ps

## 14. Jika WhatsApp Bermasalah

Periksa GoWA:

docker compose logs --tail=200 gowa

GoWA biasanya tidak perlu direstart hanya karena rollback source Python.

## 15. Jika Rollback Otomatis Juga Gagal

Jangan reset database.

Periksa terlebih dahulu:

git status

git log --oneline --decorate -10

docker compose ps

docker compose logs --tail=200 api worker

Periksa health:

curl http://127.0.0.1:8080/health

## 16. Mengecek Commit yang Sedang Aktif

Gunakan:

mekanik-version

Atau source:

git rev-parse HEAD

Short commit:

git rev-parse --short HEAD

## 17. Mengecek Tag pada Commit

Gunakan:

git tag --points-at HEAD

Atau:

git describe --tags --always

## 18. Rollback Production yang Disarankan

Contoh kondisi:

versi aktif:
v0.3.0-beta.2

versi tersebut bermasalah.

Rollback:

mekanik-rollback v0.3.0-beta.1

Setelah selesai:

mekanik-version

Pastikan:

Runtime API menunjukkan versi lama.

Jika runtime commit sudah tersedia, pastikan commit runtime juga sesuai.

## 19. Jangan Gunakan Cara Berbahaya

Hindari:

docker compose down -v

karena dapat menghapus volume.

Hindari:

git reset --hard

jika masih ada perubahan source penting yang belum tersimpan.

Hindari restore database tanpa memastikan backup yang benar.

Hindari menghapus folder data secara manual.

## 20. Prinsip Recovery

Urutan troubleshooting yang disarankan:

1. cek mekanik-version
2. cek docker compose ps
3. cek health API
4. cek logs
5. rollback aplikasi
6. verifikasi kembali
7. baru analisis database jika memang masalah berasal dari database

Jangan menjadikan reset database sebagai solusi pertama.

