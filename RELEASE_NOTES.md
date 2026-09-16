# Release Notes — v0.2.0

## Perubahan utama dari baseline v0.1.x

- customer dapat berbicara natural; `SERVIS` hanya shortcut;
- AI customer service opsional dengan fallback deterministik;
- Share Location customer dan mekanik;
- lokasi customer dikonfirmasi sebelum matching dan sebelum keberangkatan;
- service order mendukung banyak mesin;
- pendaftaran mekanik mewajibkan selfie;
- skill matrix 18 bidang + top skill + pertanyaan verifikasi;
- approval mekanik disederhanakan menjadi approve/reject owner;
- mekanik ONLINE/OFFLINE dan current location;
- matching Top 3 dan offer window 10 menit;
- customer memilih mekanik dari profil tanpa kontak person;
- booking/travel fee murah berdasarkan jarak;
- QRIS/transfer dengan konfirmasi pembayaran manual owner;
- booking menjadi credit terhadap jasa sukses;
- tariff matrix jenis mesin x tingkat kesulitan;
- mesin tambahan di lapangan memerlukan approval customer;
- diagnosis/quotation per machine item;
- unrepairable mewajibkan diagnosis + foto + video;
- customer dapat menyetujui hasil unrepairable atau membuka dispute;
- owner menjadi final approval settlement;
- GOWA multi-device menggunakan device ID terkonfigurasi;
- webhook HMAC verification, deduplication dan background processing;
- health/preflight/backup/deploy scripts.

## Catatan kompatibilitas

v0.2.0 dirancang sebagai fresh-install MVP. Tidak ada migration path otomatis dari schema v0.1.x.
