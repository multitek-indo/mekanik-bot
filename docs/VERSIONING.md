# Multitek Service - Versioning Guide

## 1. Tujuan

Versioning digunakan agar setiap perubahan Multitek Service mempunyai identitas yang jelas dan dapat:

- diketahui versi yang sedang berjalan
- dibandingkan dengan source GitHub
- di-deploy ulang
- di-rollback
- dilacak commit-nya
- dilanjutkan development-nya tanpa kehilangan checkpoint

GitHub menjadi source of truth.

## 2. Format Versi

Multitek Service menggunakan Semantic Versioning.

Format dasar:

MAJOR.MINOR.PATCH

Contoh:

0.3.0
0.3.1
0.4.0
1.0.0

## 3. Pre-release

Untuk versi yang masih dalam tahap pengujian digunakan suffix seperti:

beta
rc

Contoh:

0.3.0-beta.1
0.3.0-beta.2
0.3.0-rc.1
0.3.0

Urutannya secara umum:

0.3.0-beta.1
-> 0.3.0-beta.2
-> 0.3.0-rc.1
-> 0.3.0

## 4. Git Tag

File VERSION tidak menggunakan awalan v.

Contoh isi VERSION:

0.3.0-beta.1

Git tag menggunakan awalan v:

v0.3.0-beta.1

Jadi:

VERSION:
0.3.0-beta.1

Git tag:
v0.3.0-beta.1

## 5. PATCH

PATCH digunakan untuk bugfix atau perbaikan kecil yang tidak menambah fitur besar.

Contoh:

0.3.0
-> 0.3.1

Contoh perubahan:

- memperbaiki typo bot
- memperbaiki validasi
- memperbaiki bug media
- memperbaiki error kecil
- optimasi tanpa mengubah flow besar

## 6. MINOR

MINOR digunakan ketika ada fitur baru.

Contoh:

0.3.1
-> 0.4.0

Contoh perubahan:

- persistent conversation memory
- fitur dashboard baru
- metode matching baru
- fitur customer baru
- fitur mekanik baru

## 7. MAJOR

MAJOR digunakan untuk perubahan besar atau milestone production utama.

Contoh:

0.9.5
-> 1.0.0

Versi 1.0.0 dapat digunakan ketika sistem dianggap cukup matang untuk production stabil.

## 8. File VERSION

Versi source disimpan pada file:

VERSION

Cek:

cat VERSION

Contoh:

0.3.0-beta.1

File ini ikut masuk ke Docker image.

## 9. Runtime Version

API membaca VERSION melalui:

app/version.py

Health endpoint menampilkan versi aplikasi.

Cek:

curl http://127.0.0.1:8080/health

Contoh:

{"status":"ok","version":"0.3.0-beta.1","commit":"abc123","env":"production"}

## 10. Git Commit Runtime

Selain nomor versi, Docker image menerima commit Git saat build.

Build argument:

GIT_COMMIT

Environment container:

APP_GIT_COMMIT

Tujuannya agar kita tahu commit persis yang sedang berjalan, bukan hanya nomor versinya.

## 11. Mengecek Versi Lengkap

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
Docker status

Kondisi ideal setelah deployment:

Source version = Runtime API

dan:

Source commit = Runtime commit

## 12. Current Development Version

Checkpoint saat ini:

0.3.0-beta.1

Git tag yang akan dibuat:

v0.3.0-beta.1

Status versi ini:

- AI hybrid sudah aktif
- context percakapan sementara sudah aktif
- foto customer sudah tersimpan
- attachment sudah terbaca matching
- forwarding media sudah diimplementasikan
- forwarding foto/video ke perangkat mekanik masih perlu live test

Karena masih ada live test yang belum selesai, versi menggunakan beta.

## 13. Membuat Versi Berikutnya

Misalnya development berikutnya memperbaiki media forwarding.

Versi dapat menjadi:

0.3.0-beta.2

Ubah file:

printf '%s\n' '0.3.0-beta.2' > VERSION

Cek:

cat VERSION

## 14. Commit Release

Setelah source selesai dan sudah diuji:

git status

Kemudian:

git add -A

Commit:

git commit -m "release: v0.3.0-beta.2"

Push branch:

git push origin main

## 15. Membuat Tag

Setelah commit release berhasil:

git tag -a v0.3.0-beta.2 -m "Release v0.3.0-beta.2"

Cek:

git tag --points-at HEAD

Push tag:

git push origin v0.3.0-beta.2

## 16. Deploy Versi

Pada VPS:

mekanik-deploy v0.3.0-beta.2

Setelah selesai:

mekanik-version

Pastikan source dan runtime sesuai.

## 17. Deploy Versi Terbaru

Untuk mengambil tag versi terbaru:

mekanik-deploy latest

Namun pada production disarankan mengetahui tag yang akan dipasang secara eksplisit.

Contoh yang lebih aman:

mekanik-deploy v0.3.0-beta.2

## 18. Deploy Main

Untuk testing commit terbaru pada branch main:

mekanik-deploy main

Main sebaiknya tidak dianggap sebagai release stabil sebelum dibuat tag.

## 19. Rollback Berdasarkan Versi

Jika release baru bermasalah:

mekanik-rollback

Atau:

mekanik-rollback v0.3.0-beta.1

Dengan Git tag, rollback lebih mudah karena setiap release mempunyai checkpoint tetap.

## 20. Tag Bersifat Tetap

Tag release lama jangan dipindahkan ke commit baru.

Contoh:

v0.3.0-beta.1

harus selalu menunjuk source yang sama.

Jika ada perubahan, buat versi baru:

v0.3.0-beta.2

Jangan mengganti isi v0.3.0-beta.1.

## 21. Jangan Force Push Release

Hindari:

git push --force

terutama pada main dan release tag.

Tujuannya agar history development tetap dapat dilacak.

## 22. Workflow Development

Workflow normal:

Edit source
-> test
-> commit ke main
-> push GitHub

Jika akan membuat release:

update VERSION
-> final test
-> commit release
-> push main
-> create tag
-> push tag
-> deploy tag
-> cek mekanik-version

## 23. Contoh Release Lengkap

Misalnya versi berikutnya:

0.3.0-beta.2

Update:

printf '%s\n' '0.3.0-beta.2' > VERSION

Cek perubahan:

git status

Stage:

git add -A

Commit:

git commit -m "release: v0.3.0-beta.2"

Push:

git push origin main

Tag:

git tag -a v0.3.0-beta.2 -m "Release v0.3.0-beta.2"

Push tag:

git push origin v0.3.0-beta.2

Deploy:

mekanik-deploy v0.3.0-beta.2

Verifikasi:

mekanik-version

## 24. Prinsip Utama

GitHub menyimpan source.

VERSION menyimpan nomor release.

Git commit menyimpan identitas source persis.

Git tag menjadi checkpoint release.

Docker runtime menyimpan version dan commit.

mekanik-version membandingkan semuanya.

Dengan mekanisme ini kita dapat mengetahui dengan jelas:

versi apa yang ada di GitHub
versi apa yang ada di VPS
commit apa yang sedang berjalan
release apa yang terakhir dipasang
dan ke versi mana sistem dapat di-rollback

