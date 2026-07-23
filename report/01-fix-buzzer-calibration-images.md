# Report: Perbaikan 3 Masalah CNC GUI

**Branch:** `feature/fix-buzzer-calibration-images`
**Commit:** 3080e69

## Ringkasan

Memperbaiki 3 masalah pada `main_cnc.py` dengan menganalisis perbandingan dengan `kal2.py` (referensi non-GUI).

---

## [1] Buzzer berbunyi sebelum milling selesai

### Akar Masalah
GRBLWorker mengirim `#MILLING_SELESAI;` ke Arduino sensor segera setelah semua baris G-code dikirim dan "ok" diterima. Namun GRBL menggunakan **planner buffer** — "ok" berarti perintah sudah masuk antrian gerak, bukan berarti gerakan sudah selesai. Motor stepper masih bergerak saat buzzer sudah berbunyi.

### Perbaikan
Setelah semua G-code selesai dikirim (`for` loop selesai), GRBLWorker sekarang:
1. Mengirim `?\n` (status query) ke GRBL
2. Membaca response sampai menemukan `"Idle"` atau `"idle"` (menandakan semua gerakan selesai)
3. Timeout 30 detik untuk keamanan
4. Baru setelah itu mengirim `#MILLING_SELESAI;\n` dan `#SPINDLE_OFF;\n`

**File:** `main_cnc.py`, method `GRBLWorker.run()` (bagian akhir)

### Catatan
- `kal2.py` juga tidak menunggu Idle — punya bug yang sama. Perbaikan ini lebih baik dari referensi.
- Jika perlu test, bisa disimulasi dengan mock mode.

---

## [2] Kalibrasi selesai harus tekan START dulu

### Akar Masalah
Di `CalibrationWorker.run()` step 7, ada `while` loop yang menunggu `START_ON` dari sensor sebelum memanggil `finished_success()`. Akibatnya jendela utama tidak bisa dibuka sampai operator menekan tombol START fisik.

### Perbaikan
1. **CalibrationWorker:** Hapus seluruh section "7. Menunggu tombol START fisik". Setelah `G92 X0 Y0 Z0`, langsung emit `finished_success`.
2. **SensorWorker:** Tambah signal `start_pressed = pyqtSignal()` dan emit saat data `START_ON` diterima.
3. **CNCApp:** Tambah `self.start_event = threading.Event()`. Signal `start_pressed` terhubung ke `_on_start_pressed()` yang me-set event.
4. **GRBLWorker:** Di awal `run()`, sebelum memproses G-code, tunggu `start_event.wait()`. Setelah event ter-set, kirim `#SPINDLE_ON;\n`.
5. **load_and_start:** Hapus pengiriman `#SPINDLE_ON;\n` (pindah ke GRBLWorker), tambah `start_event.clear()` sebelum start thread.
6. **trigger_emergency & closeEvent:** Set `start_event` agar worker bisa berhenti bersih jika sedang menunggu START.

### Alur Baru
1. Kalibrasi selesai -> jendela kalibrasi tutup -> jendela utama terbuka
2. User klik "Jendela Jalur PCB" -> pilih file -> status "Tekan tombol START pada panel mesin"
3. Operator tekan START fisik -> GRBLWorker mulai milling

---

## [3] Gambar lampu & baling-baling hilang

### Akar Masalah
`QPixmap("file.png")` gagal load secara diam-diam. Jika file tidak ditemukan atau rusak, `QPixmap.isNull()` = True, dan `setPixmap(null)` menghapus gambar dari label. Tidak ada logging atau fallback.

### Perbaikan
1. **CNCApp:** Tambah method `_load_pixmap_checked(path, size, fallback_rgb)` yang:
   - Memuat QPixmap
   - Jika `isNull()`, print warning dan buat placeholder berwarna solid dengan lingkaran putih
   - Return scaled pixmap
2. **setup_ui:** Gunakan `_load_pixmap_checked()` untuk semua gambar (`OFF.png`, `ON.png`, `OFF-M.png`, `ON-M.png`, `balingbaling.png`)
3. **EmergencyPopup:** Pixmap `logo listrik.png` juga pakai fallback — jika null, tampilkan teks `[!]` merah besar

### Fallback Behavior
| Gambar         | Warna Fallback | Bentuk                |
|----------------|----------------|-----------------------|
| OFF.png        | Hijau gelap    | Lingkaran putih       |
| ON.png         | Hijau terang   | Lingkaran putih       |
| OFF-M.png      | Merah gelap    | Lingkaran putih       |
| ON-M.png       | Merah terang   | Lingkaran putih       |
| balingbaling.png| Abu-abu        | Lingkaran putih       |
| logo listrik.png| (teks)         | "[!]" merah           |

---

## Dokumentasi yang Perlu Diupdate

### `docs/developer.md`
Tambah catatan:

> **START button flow** (Fix [2]):
> - Start event (`threading.Event`) digunakan untuk sinkronisasi START antar thread
> - `SensorWorker` deteksi `START_ON` -> emit `start_pressed` signal -> `CNCApp._on_start_pressed` set event -> `GRBLWorker` terbangun
> - Saat emergency atau close, event di-set agar worker tidak stuck

> **Image loading** (Fix [3]):
> - Semua QPixmap harus melalui `_load_pixmap_checked()` untuk null-checking
> - Jika gambar tidak ditemukan, warning dicetak ke console dan fallback placeholder ditampilkan
