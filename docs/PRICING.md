# Pricing Model MVP

## Booking / perjalanan awal

Default `.env`:

| Jarak | Booking |
|---|---:|
| 0-5 km | Rp20.000 |
| >5-10 km | Rp30.000 |
| >10-20 km | Rp40.000 |
| >20-30 km | Rp50.000 |
| >30 km | Manual owner |

Nilai ini sengaja rendah untuk tahap awal. Ubah melalui `.env` sesuai biaya BBM dan kondisi lapangan.

## Tarif service

Tarif service ditentukan oleh dua dimensi:

1. kategori mesin/skill;
2. tingkat kesulitan: RINGAN, SEDANG, BERAT, atau KHUSUS/quotation.

Semua tarif jasa pada database **dimulai dari 0** karena Multitek belum menetapkan nominal aktual. Nilai 0 berarti belum ditetapkan dan mekanik dapat mengusulkan jasa setelah diagnosis.

Owner mengisi matrix dari WhatsApp:

```text
SET TARIF 1 INSPEKSI 30000
SET TARIF 1 RINGAN 75000
SET TARIF 1 SEDANG 125000
SET TARIF 1 BERAT 200000
```

Nomor 1-18 mengikuti Skill Matrix.

## Booking sebagai kredit jasa

Contoh booking Rp30.000, jasa final Rp100.000, part Rp0:

```text
jasa            100.000
booking credit  -30.000
sisa             70.000
```

Jika jasa hanya Rp20.000 sedangkan booking Rp30.000, tidak ada tambahan jasa.

## Spare part

Spare part tidak dikurangi booking; spare part selalu ditambahkan ke tagihan akhir jika customer menyetujuinya.

## Mesin tambahan

Satu booking berlaku untuk satu kunjungan/lokasi. Mekanik boleh mengajukan biaya pengecekan untuk mesin tambahan, tetapi customer harus menyetujui melalui sistem sebelum mesin tambahan diperiksa.
