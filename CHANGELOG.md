# Changelog

## 0.3.0-beta.1

Checkpoint pengembangan Multitek Service untuk AI customer service, context percakapan, media customer, versioning, deployment, dan rollback.

### Added

- Hybrid AI dengan Gemini sebagai primary.
- Groq sebagai fallback.
- Pemahaman Bahasa Indonesia.
- Pemahaman Bahasa Jawa ngoko.
- Pemahaman Bahasa Jawa krama.
- Dukungan typo dan singkatan.
- Machine quantity fact guard.
- Context sementara setelah pertanyaan harga.
- Greeting fast path tanpa AI.
- Share Location flow.
- Konfirmasi lokasi.
- Customer photo intake.
- Customer video intake.
- Attachment persistence ke database.
- Mapping attachment ke service order item.
- Media lookup untuk matching.
- Forwarding foto ke mekanik.
- Forwarding video ke mekanik.
- Asia/Jakarta untuk nomor order.
- File VERSION.
- app/version.py.
- Runtime version pada health endpoint.
- Runtime Git commit support.
- Command mekanik-version.
- Deployment berbasis Git.
- Deployment berdasarkan tag.
- Deployment latest tag.
- Deployment branch main.
- Backup database sebelum deployment.
- Preflight sebelum deployment.
- Automatic application rollback.
- Manual rollback.
- Deployment state tracking.
- Manual Book.
- Deployment Guide.
- Versioning Guide.
- Rollback Guide.
- Development checkpoint documentation.

### Verified

- API berjalan sehat.
- Runtime version 0.3.0-beta.1.
- Source version 0.3.0-beta.1.
- Customer price context tersimpan.
- Mesin dan keluhan dapat dipertahankan dari pertanyaan harga.
- Foto customer berhasil tersimpan.
- Attachment berhasil masuk tabel attachments.
- Matching helper berhasil membaca attachment customer.
- Order number menggunakan tanggal Asia/Jakarta.
- Syntax deploy script valid.
- Syntax rollback script valid.
- Syntax version script valid.
- Syntax backup script valid.
- Syntax preflight script valid.

### Example Verified Order

Order:

MTK-260917-0002

Machine:

Mesin Jarum 1 Juki

Complaint:

Sering loncat

Attachment:

CUSTOMER_MACHINE_PHOTO

Media type:

image

### Pending Verification

Belum diverifikasi live secara penuh:

- foto customer benar-benar sampai ke WhatsApp mekanik;
- video customer benar-benar sampai ke WhatsApp mekanik;
- video attachment end-to-end;
- rollback live dari GitHub release;
- deploy live dari GitHub tag pertama.

### Next Development Priority

Prioritas pertama:

LIVE TEST FOTO + VIDEO CUSTOMER KE MEKANIK.

Setelah media forwarding dinyatakan stabil:

PERSISTENT CONVERSATION MEMORY

Target memory:

recent messages
+ active state
+ customer profile
+ machine history
+ previous orders
+ conversation summary

### Architecture Principle

AI digunakan untuk memahami percakapan.

Data transaksi tetap authoritative di backend dan PostgreSQL.

AI tidak boleh menjadi sumber kebenaran untuk:

- harga
- pembayaran
- order status
- assigned technician
- settlement
- booking fee
- financial transaction

### Deployment Commands

Check version:

mekanik-version

Deploy release:

mekanik-deploy v0.3.0-beta.1

Deploy latest tag:

mekanik-deploy latest

Deploy main:

mekanik-deploy main

Rollback:

mekanik-rollback

Rollback version:

mekanik-rollback v0.3.0-beta.1

### Important Safety Notes

Jangan commit:

.env
API key
password
token
customer media
database dump
backup database

Jangan gunakan:

docker compose down -v

pada production tanpa memahami dampaknya.

Jangan force push release tag.

