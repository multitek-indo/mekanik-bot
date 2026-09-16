# Multitek Service - Deployment Guide

## 1. Tujuan

Dokumen ini menjelaskan cara memasang, memperbarui, dan menjalankan versi Multitek Service dari GitHub ke VPS.

GitHub menjadi source of truth untuk source code aplikasi.

Flow deployment:

GitHub
-> Commit
-> Tag versi
-> VPS
-> mekanik-deploy
-> backup database
-> checkout source
-> preflight
-> build
-> restart API + worker
-> health check
-> version validation

## 2. Repository

Repository:

git@github.com:multitek-indo/mekanik-bot.git

Branch utama:

main

Versi production sebaiknya menggunakan Git tag.

Contoh:

v0.3.0-beta.1
v0.3.0-beta.2
v0.3.0
v0.3.1

## 3. Lokasi Project VPS

Project berada di:

/home/mekanik/mekanik-bot

Masuk project:

cd /home/mekanik/mekanik-bot

## 4. Service Docker

Service utama:

db
api
gowa
worker

Periksa dengan:

docker compose ps

API berjalan pada:

127.0.0.1:8080

GoWA berjalan pada:

127.0.0.1:3000

## 5. Mengecek Health

Gunakan:

curl http://127.0.0.1:8080/health

Contoh hasil:

{"status":"ok","version":"0.3.0-beta.1","commit":"abc123","env":"production"}

## 6. Mengecek Versi

Gunakan:

mekanik-version

Informasi yang ditampilkan:

Source version
Git describe
Source commit
Git branch
Runtime API
Runtime commit
Deploy ref
Deploy commit
Docker container status

Kondisi ideal:

Source version = Runtime API

dan setelah deployment melalui mekanik-deploy:

Source commit = Runtime commit

## 7. Deploy Versi Tertentu

Contoh:

mekanik-deploy v0.3.0-beta.1

Script akan:

1. memastikan repository VPS bersih
2. fetch GitHub
3. fetch Git tags
4. mencari commit target
5. memastikan database aktif
6. membuat backup database
7. checkout source target
8. menjalankan preflight
9. build API dan worker
10. restart API dan worker
11. melakukan health check
12. membandingkan VERSION dengan runtime
13. menyimpan deployment state

## 8. Deploy Tag Terbaru

Gunakan:

mekanik-deploy latest

Script akan memilih Git tag versi terbaru.

Untuk production, cara ini dapat digunakan setelah release baru benar-benar sudah dites.

## 9. Deploy Branch Main

Gunakan:

mekanik-deploy main

Mode ini cocok untuk testing commit terbaru.

Untuk production lebih disarankan menggunakan tag versi karena tag memberikan titik rollback yang jelas.

## 10. Backup Database

Sebelum deployment, script menjalankan:

scripts/backup.sh

Backup disimpan pada:

backups/

Format backup:

multitek-service-TIMESTAMP.dump

Checksum:

multitek-service-TIMESTAMP.dump.sha256

Database menggunakan PostgreSQL custom dump format.

## 11. Preflight

Sebelum build, script menjalankan:

scripts/preflight.sh

Preflight memeriksa antara lain:

docker
git
openssl
docker compose
.env
konfigurasi environment
format OWNER_WA_NUMBER
QRIS
syntax Python

Jika preflight gagal, deployment dibatalkan.

## 12. Build

Deployment hanya melakukan build pada:

api
worker

Command yang digunakan secara konsep:

docker compose build api worker

Database dan GoWA tidak perlu dibuild ulang untuk perubahan source Python biasa.

## 13. Runtime Git Commit

Build menerima Git commit melalui:

GIT_COMMIT

Kemudian disimpan sebagai environment:

APP_GIT_COMMIT

Health endpoint menampilkan commit tersebut sehingga dapat diketahui source yang benar-benar berjalan.

## 14. Automatic Rollback

Jika terjadi kegagalan pada:

build
startup
health check
version validation

deployment mencoba kembali ke commit aplikasi sebelumnya.

Flow:

deploy baru gagal
-> checkout commit sebelumnya
-> build API + worker versi sebelumnya
-> restart
-> health check

Rollback otomatis hanya untuk aplikasi.

Database tidak otomatis dikembalikan.

## 15. Deployment State

State deployment berada di:

/home/mekanik/.mekanik-bot-deploy

File yang digunakan:

current_commit
previous_commit
current_ref
history.log

current_commit:

commit yang berhasil dideploy terakhir.

previous_commit:

commit sebelum deployment terakhir.

current_ref:

tag atau target deployment.

history.log:

riwayat deployment sukses.

## 16. Rollback Manual

Rollback deployment sebelumnya:

mekanik-rollback

Rollback ke versi tertentu:

mekanik-rollback v0.3.0-beta.1

Rollback ke commit tertentu:

mekanik-rollback COMMIT_HASH

## 17. Logs

API:

docker compose logs --tail=200 api

Worker:

docker compose logs --tail=200 worker

GoWA:

docker compose logs --tail=200 gowa

Realtime:

docker compose logs -f api worker gowa

## 18. Troubleshooting Dasar

Jika API tidak sehat:

docker compose ps

Kemudian:

docker compose logs --tail=200 api

Jika worker bermasalah:

docker compose logs --tail=200 worker

Jika WhatsApp bermasalah:

docker compose logs --tail=200 gowa

Jika source dan runtime berbeda:

mekanik-version

Kemudian periksa apakah container sudah dibuild ulang.

## 19. Aturan Production

Jangan melakukan deployment ketika repository VPS memiliki perubahan source lokal yang belum di-commit.

Jangan menggunakan:

git push --force

tanpa memahami dampaknya.

Jangan menggunakan:

docker compose down -v

karena dapat menghapus volume database.

Jangan menyimpan secret di GitHub.

## 20. Workflow Release yang Disarankan

Development:

edit source
-> test
-> commit ke main

Release:

ubah VERSION
-> commit
-> push main
-> buat tag
-> push tag

Production:

mekanik-deploy TAG

Contoh:

VERSION:
0.3.0-beta.2

Git tag:
v0.3.0-beta.2

Deploy:

mekanik-deploy v0.3.0-beta.2

Verifikasi:

mekanik-version
