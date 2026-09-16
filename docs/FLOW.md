# Flow Multitek Service MVP v0.2.0

## 1. Customer

```text
Customer mengirim chat natural
        |
        v
AI/deterministic classifier memahami intent
        |
        +-- pertanyaan tarif -> jawab booking + konsep tarif
        +-- pertanyaan status -> baca database
        +-- kebutuhan service -> intake
                                |
                                v
                       jumlah & data mesin
                                |
                                v
                       Share Location mesin
                                |
                                v
                       customer konfirmasi titik
                                |
                                v
                       landmark opsional
                                |
                                v
                       Service Order MTK-...
                                |
                                v
                       matching top 3 mekanik
```

`SERVIS` tetap tersedia sebagai shortcut tetapi bukan syarat.

## 2. Matching mekanik

```text
Service Order
    |
    v
kategori skill seluruh mesin
    |
    v
mekanik aktif + ONLINE
    |
    v
filter radius
    |
    v
coverage skill + level + jarak + rating
    |
    v
TOP 3 kandidat
    |
    v
penawaran bersamaan selama 10 menit
    |
    v
mekanik balas BERMINAT / TOLAK
    |
    v
customer melihat profil kandidat yang berminat
(foto, pengalaman, jarak, rating, skill; tanpa nomor WA)
    |
    v
customer PILIH MTK-... <nomor>
```

## 3. Booking dan keberangkatan

```text
Customer memilih mekanik
      |
      v
booking/biaya perjalanan dihitung dari jarak
      |
      v
rekening + QRIS Multitek dikirim
      |
      v
customer kirim screenshot bukti
      |
      v
owner menerima bukti
      |
      v
owner cek rekening secara manual
      |
      v
KONFIRMASI BAYAR MTK-...
      |
      v
customer konfirmasi lokasi final
      |
      v
LOKASI BENAR MTK-...
      |
      v
mekanik BERANGKAT -> SAMPAI
```

Booking default:

- 0-5 km: Rp20.000
- >5-10 km: Rp30.000
- >10-20 km: Rp40.000
- >20-30 km: Rp50.000
- >30 km: owner menentukan manual dengan `SET BOOKING`.

Booking adalah biaya minimum perjalanan/kunjungan sekaligus kredit terhadap jasa bila repair berhasil.

## 4. Multi-mesin

Satu `service_order` mewakili satu kunjungan/lokasi dan dapat memiliki beberapa `service_order_items`.

```text
MTK-...
  +-- item 1 Jarum 1
  +-- item 2 Obras
  +-- item 3 Bartack
  +-- item 4 Servo
```

Masing-masing item memiliki diagnosis, difficulty, inspection fee, repair fee, parts fee, dan status sendiri.

Jika di lokasi ada mesin tambahan, mekanik mengajukan:

```text
TAMBAH MESIN MTK-... jenis/model | keluhan | biaya_cek
```

Customer harus menyetujui sebelum pemeriksaan mesin tambahan.

## 5. Diagnosis, quotation, repair

```text
DIAGNOSIS MTK-... <item>
      |
      v
diagnosis tertulis
      |
      v
RINGAN / SEDANG / BERAT / KHUSUS
      |
      v
ambil service_price_matrix
atau usulan jasa jika tarif belum ditetapkan
      |
      v
spare part
      |
      v
quotation per item ke customer
      |
      +-- SETUJU -> repair -> SELESAI ITEM
      +-- TOLAK  -> inspection fee bila berlaku
```

Harga jasa tidak di-hard-code. Owner mengisi matrix menggunakan `SET TARIF`.

## 6. Tagihan akhir

Pada pekerjaan berhasil:

```text
jasa/pengecekan seluruh item
+ spare part
- booking sebagai kredit terhadap jasa
= tambahan pembayaran
```

Formula implementasi:

```text
effective_labour = max(booking_fee, labour_total)
additional_due   = max(0, labour_total - booking_fee) + parts_total
```

Jika `additional_due = 0`, customer tidak perlu membayar jasa lagi.

## 7. Tidak dapat diperbaiki

Mekanik tidak dapat menutup item hanya dengan teks.

```text
TIDAK BISA MTK-... <item>
      |
      v
wajib diagnosis/alasan teknis
      |
      v
wajib FOTO
      |
      v
wajib VIDEO analisa/pengujian
      |
      v
bukti dikirim ke customer
      |
      +-- SETUJU TIDAK BISA -> item confirmed
      +-- MASALAH -> DISPUTE, payout ditahan
```

Jika seluruh mesin dalam order dikonfirmasi tidak dapat diperbaiki, settlement booking default:

- refund customer 60%
- kompensasi mekanik 30%
- fee Multitek 10%

Owner tetap final approval dengan `SETUJUI SETTLEMENT MTK-...`.

## 8. Pendaftaran mekanik

```text
DAFTAR MEKANIK
 -> nama
 -> domisili
 -> Share Location basis
 -> radius
 -> pengalaman
 -> kendaraan
 -> selfie wajib
 -> 18 skill level 0-5
 -> pilih max 3 top skill
 -> 1 pertanyaan per top skill
 -> SUBMITTED
 -> owner SETUJUI atau TOLAK
```

Sesudah approved, mekanik mengetik `ONLINE` dan mengirim Share Location posisi saat ini untuk menerima job.
