import sys
import serial
import time
import re
import os
import datetime  # Tambahan untuk merekam waktu
import openpyxl  # Tambahan untuk membuat file Excel
from openpyxl.drawing.image import Image as ExcelImage  # Untuk memasukkan gambar ke Excel

import matplotlib

matplotlib.use('qtagg')

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QProgressBar, QMessageBox, QFileDialog, QDialog)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QPixmap

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ==========================================
# KONFIGURASI PORT
# ==========================================
PORT_GRBL = 'COM11'
PORT_SENSOR = 'COM9'
BAUD_RATE = 115200


# ==========================================
# 0. THREAD KALIBRASI
# ==========================================
class CalibrationWorker(QThread):
    progress_update = pyqtSignal(int)
    status_update = pyqtSignal(str)
    finished_success = pyqtSignal(object, object)
    finished_mock = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.grbl = None
        self.sensor = None
        self.is_running = True

    def kirim(self, cmd):
        print(f"> {cmd}")
        if self.grbl:
            self.grbl.write((cmd + '\n').encode())
            time.sleep(0.05)
            while self.grbl.in_waiting:
                self.grbl.readline()

    def run(self):
        self.status_update.emit("Mencari Mesin di Port Serial...")
        self.progress_update.emit(5)
        time.sleep(0.5)

        mock_mode = False
        try:
            self.grbl = serial.Serial(PORT_GRBL, BAUD_RATE, timeout=1)
            self.sensor = serial.Serial(PORT_SENSOR, BAUD_RATE, timeout=1)
        except Exception as e:
            print(f"[AUTO-SIMULASI] Mesin tidak ditemukan: {e}")
            mock_mode = True

        if not mock_mode:
            try:
                self.status_update.emit("Inisialisasi GRBL...")
                self.grbl.write(b"\r\n\r\n")
                time.sleep(2)
                self.grbl.flushInput()
                self.sensor.reset_input_buffer()

                self.kirim("$X");
                self.kirim("G21");
                self.kirim("G91")

                # FASE 1: LIMIT
                self.status_update.emit("Mencari Limit Switch X, Y, Z...")
                self.progress_update.emit(20)
                limx, limy, limz = False, False, False

                while self.is_running:
                    move_cmd = "G1 "
                    if not limx: move_cmd += "X-2 "
                    if not limy: move_cmd += "Y-2 "
                    if not limz: move_cmd += "Z2 "
                    move_cmd += "F300"

                    if move_cmd != "G1 F300":
                        self.kirim(move_cmd)
                    time.sleep(0.05)

                    while self.sensor.in_waiting:
                        data = self.sensor.readline().decode(errors='ignore').strip().upper()
                        if data == "LIMX": limx = True
                        if data == "LIMY": limy = True
                        if data == "LIMZ": limz = True

                    if limx and limy and limz:
                        self.grbl.write(b'\x18');
                        time.sleep(1)
                        self.kirim("$X");
                        self.kirim("G21");
                        self.kirim("G91")
                        break

                # FASE 2: LASER
                if not self.is_running: return
                self.status_update.emit("Menyesuaikan Home X (Laser)...")
                self.progress_update.emit(40)
                self.sensor.reset_input_buffer()
                while self.is_running:
                    self.kirim("G1 X2 F300")
                    ketemu = False
                    while self.sensor.in_waiting:
                        if self.sensor.readline().decode(errors='ignore').strip().upper() == "LASER":
                            ketemu = True
                            self.grbl.write(b'\x18');
                            time.sleep(1)
                            self.kirim("$X");
                            self.kirim("G21");
                            self.kirim("G91")
                            self.kirim("G92 X0")
                            break
                    if ketemu: break

                # FASE 3: TCRT
                if not self.is_running: return
                self.status_update.emit("Menyesuaikan Home Y (TCRT)...")
                self.progress_update.emit(60)
                self.sensor.reset_input_buffer()
                while self.is_running:
                    self.kirim("G1 Y2 F300")
                    ketemu = False
                    while self.sensor.in_waiting:
                        if self.sensor.readline().decode(errors='ignore').strip().upper() == "TCON":
                            ketemu = True
                            self.grbl.write(b'\x18');
                            time.sleep(1)
                            self.kirim("$X");
                            self.kirim("G21");
                            self.kirim("G91")
                            self.kirim("G92 Y0")
                            break
                    if ketemu: break

                # FASE 4: PCB
                if not self.is_running: return
                self.status_update.emit("Menyesuaikan Home Z (PCB Sentuh)...")
                self.progress_update.emit(80)
                self.sensor.reset_input_buffer()
                while self.is_running:
                    self.kirim("G1 Z-2 F300")
                    ketemu = False
                    while self.sensor.in_waiting:
                        if self.sensor.readline().decode(errors='ignore').strip().upper() == "PCBON":
                            ketemu = True
                            self.grbl.write(b'\x18');
                            time.sleep(1)
                            self.kirim("$X");
                            self.kirim("G21");
                            self.kirim("G91")
                            self.kirim("G92 Z0")
                            self.kirim("G1 Z3 F300")
                            break
                    if ketemu: break

                # FASE 5: START
                if not self.is_running: return
                self.status_update.emit("Kalibrasi Selesai! Tekan Tombol START di panel mesin.")
                self.progress_update.emit(95)
                self.sensor.reset_input_buffer()
                while self.is_running:
                    ketemu = False
                    while self.sensor.in_waiting:
                        if self.sensor.readline().decode(errors='ignore').strip().upper() == "START":
                            ketemu = True
                            break
                    if ketemu: break

                self.status_update.emit("START Ditekan! Mesin Siap Beroperasi.")
                self.progress_update.emit(100)

                self.grbl.write(b'\x18');
                time.sleep(1)
                self.kirim("$X");
                self.kirim("G21");
                self.kirim("G90");
                self.kirim("G17");
                self.kirim("G94")
                self.kirim("G92 X0 Y0 Z0")

                self.finished_success.emit(self.grbl, self.sensor)

            except Exception as e:
                print(f"Kalibrasi Hardware Terputus: {e}")
                self.finished_mock.emit()
        else:
            if not self.is_running: return
            self.status_update.emit("[SIMULASI] Kalibrasi berjalan...")
            self.progress_update.emit(50)
            time.sleep(2.0)
            self.status_update.emit("[SIMULASI] Selesai. Klik OK untuk masuk Panel.")
            self.progress_update.emit(100)
            self.finished_mock.emit()

    def stop(self):
        self.is_running = False


# ==========================================
# 0. JENDELA KALIBRASI (POP UP AWAL)
# ==========================================
class CalibrationDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Proses Kalibrasi Mesin CNC")
        self.setFixedSize(500, 250)
        self.setModal(True)

        self.grbl_serial = None
        self.sensor_serial = None
        self.is_mock = False

        layout = QVBoxLayout()
        title = QLabel("SISTEM KALIBRASI MESIN CNC 3 AXIS")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.lbl_status = QLabel("Memulai Sistem...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: blue; font-weight: bold;")
        layout.addWidget(self.lbl_status)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.btn_ok = QPushButton("OK - Masuk ke Panel Utama")
        self.btn_ok.setEnabled(False)
        self.btn_ok.clicked.connect(self.accept)
        layout.addWidget(self.btn_ok)

        self.btn_skip = QPushButton("Skip (Lewati Paksa)")
        self.btn_skip.clicked.connect(self.force_mock_mode)
        layout.addWidget(self.btn_skip)

        self.setLayout(layout)

        self.worker = CalibrationWorker()
        self.worker.progress_update.connect(self.progress.setValue)
        self.worker.status_update.connect(self.lbl_status.setText)
        self.worker.finished_success.connect(self.on_success)
        self.worker.finished_mock.connect(self.on_mock)
        self.worker.start()

    def on_success(self, grbl, sensor):
        self.grbl_serial = grbl
        self.sensor_serial = sensor
        self.is_mock = False
        self.btn_ok.setEnabled(True)
        self.btn_ok.setStyleSheet("background-color: #00FF00; font-weight: bold;")

    def on_mock(self):
        self.is_mock = True
        self.btn_ok.setEnabled(True)
        self.btn_ok.setStyleSheet("background-color: #00FF00; font-weight: bold;")

    def force_mock_mode(self):
        self.worker.stop()
        self.on_mock()
        self.progress.setValue(100)

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()


# ==========================================
# 1. THREAD GRBL (MAIN WINDOW)
# ==========================================
class GRBLWorker(QThread):
    progress_update = pyqtSignal(int)
    status_update = pyqtSignal(str)
    sim_position_update = pyqtSignal(float, float)

    def __init__(self, grbl_serial, mock_mode):
        super().__init__()
        self.gcode_lines = []
        self.is_running = False
        self.grbl_serial = grbl_serial
        self.mock_mode = mock_mode
        self.cur_x = 0.0
        self.cur_y = 0.0

    def load_file(self, filepath):
        with open(filepath, 'r') as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith('(')]

        homing_sequence = [
            "G21", "G90", "G00 Z3.000", "G00 X0 Y0", "G00 Z0.000"
        ]
        self.gcode_lines = homing_sequence + lines

    def run(self):
        self.is_running = True
        self.status_update.emit('On Progress')
        total_lines = len(self.gcode_lines) if self.gcode_lines else 100

        for i, line in enumerate(self.gcode_lines):
            if not self.is_running:
                break
            print(f">> {line}")

            if self.mock_mode:
                match_x = re.search(r'[Xx]\s*([-+]?\d*\.?\d+)', line)
                match_y = re.search(r'[Yy]\s*([-+]?\d*\.?\d+)', line)

                if match_x: self.cur_x = float(match_x.group(1))
                if match_y: self.cur_y = float(match_y.group(1))
                if match_x or match_y:
                    self.sim_position_update.emit(self.cur_x, self.cur_y)
                time.sleep(0.05)

            if not self.mock_mode:
                cmd = (line + '\n').encode()
                try:
                    self.grbl_serial.write(cmd)
                    while True:
                        res = self.grbl_serial.readline().decode('utf-8', errors='ignore').strip()
                        if res: print(f"<< {res}")
                        if res.lower() == 'ok':
                            break
                        elif "error" in res.lower():
                            break
                except Exception as e:
                    print(f"Error Serial GRBL: {e}")

            persentase = int(((i + 1) / total_lines) * 100)
            self.progress_update.emit(persentase)

        if self.is_running:
            self.status_update.emit("Done")

    def stop(self):
        self.is_running = False


# ==========================================
# 2. THREAD SENSOR (MAIN WINDOW)
# ==========================================
class SensorWorker(QThread):
    encoder_update = pyqtSignal(float, float)
    emergency_trigger = pyqtSignal(str)

    def __init__(self, sensor_serial, mock_mode):
        super().__init__()
        self.is_running = True
        self.sensor_serial = sensor_serial
        self.mock_mode = mock_mode

    def run(self):
        while self.is_running:
            if not self.mock_mode:
                if self.sensor_serial.in_waiting:
                    line = self.sensor_serial.readline().decode('utf-8', errors='ignore').strip()
                    if "," in line:
                        try:
                            tx, ty = map(int, line.split(','))
                            self.encoder_update.emit(float(tx), float(ty))
                        except:
                            pass
            else:
                time.sleep(0.5)

    def stop(self):
        self.is_running = False


# ==========================================
# 3. MAIN GUI (CNC APP)
# ==========================================
class CNCApp(QMainWindow):
    def __init__(self, grbl_serial, sensor_serial, is_mock):
        super().__init__()
        self.setWindowTitle("Sistem Pengawasan dan Keamanan Mesin CNC 3 Axis")
        self.setGeometry(100, 100, 1200, 700)
        self.setStyleSheet("background-color: #d9d9d9;")

        self.need_calibration = False

        # VARIABEL PEREKAM WAKTU
        self.waktu_mulai = None
        self.waktu_selesai = None

        self.setup_ui()
        self.setup_plot()
        self.start_threads(grbl_serial, sensor_serial, is_mock)

    def start_threads(self, grbl_serial, sensor_serial, is_mock):
        self.grbl_thread = GRBLWorker(grbl_serial, is_mock)
        self.sensor_thread = SensorWorker(sensor_serial, is_mock)

        self.grbl_thread.progress_update.connect(self.update_progress)
        self.grbl_thread.status_update.connect(self.update_status)

        if is_mock:
            self.grbl_thread.sim_position_update.connect(self.update_plot_data)
        else:
            self.sensor_thread.encoder_update.connect(self.update_plot_data)

        self.sensor_thread.emergency_trigger.connect(self.trigger_emergency)
        self.sensor_thread.start()

    def setup_plot(self):
        self.x_data, self.y_data = [], []
        self.ax.set_title("Real Path Encoder")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], 'b-', linewidth=2)
        self.point, = self.ax.plot([], [], 'ro')

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        self.pix_hijau_off = QPixmap("OFF.png").scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation)
        self.pix_hijau_on = QPixmap("ON.png").scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation)
        self.pix_merah_off = QPixmap("OFF-M.png").scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                                         Qt.TransformationMode.SmoothTransformation)
        self.pix_merah_on = QPixmap("ON-M.png").scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation)
        self.pix_fan = QPixmap("balingbaling.png").scaled(70, 70, Qt.AspectRatioMode.KeepAspectRatio,
                                                          Qt.TransformationMode.SmoothTransformation)

        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("INDIKATOR", alignment=Qt.AlignmentFlag.AlignCenter))

        self.lamp_start = QLabel()
        self.lamp_start.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lamp_start.setPixmap(self.pix_hijau_off)
        left_panel.addWidget(self.lamp_start)
        left_panel.addWidget(QLabel("Mulai \"START\"", alignment=Qt.AlignmentFlag.AlignCenter))

        self.lamp_stop = QLabel()
        self.lamp_stop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lamp_stop.setPixmap(self.pix_merah_off)
        left_panel.addWidget(self.lamp_stop)
        left_panel.addWidget(QLabel("BERHENTI \"STOP\"", alignment=Qt.AlignmentFlag.AlignCenter))

        self.lamp_emergency = QLabel()
        self.lamp_emergency.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lamp_emergency.setPixmap(self.pix_merah_off)
        left_panel.addWidget(self.lamp_emergency)
        left_panel.addWidget(QLabel("EMERGENCY", alignment=Qt.AlignmentFlag.AlignCenter))
        left_panel.addStretch()

        mid_panel = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #00aa00; }")

        self.lbl_status = QLabel("STATUS MESIN : Standby")
        self.lbl_status.setFont(QFont("Arial", 16, QFont.Weight.Bold))

        btn_load = QPushButton("Jendela Jalur PCB (.txt)")
        btn_load.clicked.connect(self.load_and_start)
        btn_load.setMinimumHeight(40)

        btn_stop = QPushButton("BERHENTI / STOP")
        btn_stop.clicked.connect(self.stop_machine)
        btn_stop.setMinimumHeight(40)

        # FITUR BARU: TOMBOL SIMPAN EXCEL
        self.btn_excel = QPushButton("Simpan Laporan (.xlsx)")
        self.btn_excel.clicked.connect(self.save_to_excel)
        self.btn_excel.setMinimumHeight(40)
        self.btn_excel.setStyleSheet(
            "background-color: #217346; color: white; font-weight: bold;")  # Warna hijau khas Excel

        lbl_spindle = QLabel("STATUS KECEPATAN SPINDLE", alignment=Qt.AlignmentFlag.AlignCenter)
        lbl_spindle.setFont(QFont("Arial", 12, QFont.Weight.Bold))

        spindle_layout = QHBoxLayout()
        v_rendah = QVBoxLayout()
        fan_rendah = QLabel();
        fan_rendah.setAlignment(Qt.AlignmentFlag.AlignCenter);
        fan_rendah.setPixmap(self.pix_fan)
        self.sp_rendah = QLabel("RENDAH", alignment=Qt.AlignmentFlag.AlignCenter);
        self.sp_rendah.setStyleSheet("background-color: #00FF00; font-weight: bold; padding: 5px;")
        v_rendah.addWidget(fan_rendah);
        v_rendah.addWidget(self.sp_rendah)

        v_sedang = QVBoxLayout()
        fan_sedang = QLabel();
        fan_sedang.setAlignment(Qt.AlignmentFlag.AlignCenter);
        fan_sedang.setPixmap(self.pix_fan)
        self.sp_sedang = QLabel("SEDANG", alignment=Qt.AlignmentFlag.AlignCenter);
        self.sp_sedang.setStyleSheet("background-color: yellow; font-weight: bold; padding: 5px;")
        v_sedang.addWidget(fan_sedang);
        v_sedang.addWidget(self.sp_sedang)

        v_tinggi = QVBoxLayout()
        fan_tinggi = QLabel();
        fan_tinggi.setAlignment(Qt.AlignmentFlag.AlignCenter);
        fan_tinggi.setPixmap(self.pix_fan)
        self.sp_tinggi = QLabel("TINGGI", alignment=Qt.AlignmentFlag.AlignCenter);
        self.sp_tinggi.setStyleSheet("background-color: red; color: white; font-weight: bold; padding: 5px;")
        v_tinggi.addWidget(fan_tinggi);
        v_tinggi.addWidget(self.sp_tinggi)

        spindle_layout.addLayout(v_rendah);
        spindle_layout.addLayout(v_sedang);
        spindle_layout.addLayout(v_tinggi)

        mid_panel.addWidget(QLabel("PROGRESS BAR", alignment=Qt.AlignmentFlag.AlignCenter))
        mid_panel.addWidget(self.progress_bar)
        mid_panel.addWidget(self.lbl_status)
        mid_panel.addWidget(btn_load)
        mid_panel.addWidget(btn_stop)
        mid_panel.addWidget(self.btn_excel)  # Memasukkan tombol ke layout
        mid_panel.addSpacing(20)
        mid_panel.addWidget(lbl_spindle)
        mid_panel.addLayout(spindle_layout)
        mid_panel.addStretch()

        right_panel = QVBoxLayout()
        self.fig = Figure(figsize=(5, 5))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        right_panel.addWidget(QLabel("VISUAL JALUR PCB REAL-TIME", alignment=Qt.AlignmentFlag.AlignCenter))
        right_panel.addWidget(self.canvas)

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(mid_panel, 2)
        main_layout.addLayout(right_panel, 3)

    def load_and_start(self):
        if self.need_calibration:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("Kalibrasi Diperlukan")
            msg.setText(
                "Proses milling sebelumnya telah berhasil (Done).\nMesin akan dikalibrasi ulang untuk memulai PCB baru.")
            msg.exec()

            self.sensor_thread.stop()
            self.sensor_thread.wait()

            if hasattr(self.grbl_thread, 'grbl_serial') and self.grbl_thread.grbl_serial:
                try:
                    self.grbl_thread.grbl_serial.close()
                except:
                    pass
            if hasattr(self.sensor_thread, 'sensor_serial') and self.sensor_thread.sensor_serial:
                try:
                    self.sensor_thread.sensor_serial.close()
                except:
                    pass

            cal_dialog = CalibrationDialog()
            if cal_dialog.exec() == QDialog.DialogCode.Accepted:
                self.start_threads(cal_dialog.grbl_serial, cal_dialog.sensor_serial, cal_dialog.is_mock)
                self.need_calibration = False
            else:
                return

        filepath, _ = QFileDialog.getOpenFileName(self, "Pilih File G-Code", "", "Text Files (*.txt);;All Files (*)")
        if filepath:
            if not self.grbl_thread.isRunning():
                old_mock = self.grbl_thread.mock_mode
                old_grbl = self.grbl_thread.grbl_serial

                self.grbl_thread = GRBLWorker(old_grbl, old_mock)
                self.grbl_thread.progress_update.connect(self.update_progress)
                self.grbl_thread.status_update.connect(self.update_status)

                if old_mock:
                    self.grbl_thread.sim_position_update.connect(self.update_plot_data)

            self.grbl_thread.load_file(filepath)

            # Reset Visual dan Variabel
            self.x_data.clear()
            self.y_data.clear()
            self.ax.clear()
            self.ax.set_title("Real Path Encoder")
            self.ax.grid(True)
            self.line, = self.ax.plot([], [], 'b-', linewidth=2)
            self.point, = self.ax.plot([], [], 'ro')

            self.lamp_start.setPixmap(self.pix_hijau_on)
            self.lamp_stop.setPixmap(self.pix_merah_off)
            self.progress_bar.setValue(0)

            # Catat Waktu Mulai
            self.waktu_mulai = datetime.datetime.now()
            self.waktu_selesai = None

            if not self.grbl_thread.mock_mode:
                try:
                    self.sensor_thread.sensor_serial.write(b"SPINDLE_ON\n")
                except:
                    pass

            self.grbl_thread.start()

    def update_progress(self, val):
        self.progress_bar.setValue(val)

    def update_status(self, status):
        self.lbl_status.setText(f"STATUS MESIN : {status}")
        if status == "Done":
            self.waktu_selesai = datetime.datetime.now()  # Catat Waktu Selesai
            self.lamp_start.setPixmap(self.pix_hijau_off)
            self.need_calibration = True

            if not self.grbl_thread.mock_mode:
                try:
                    self.sensor_thread.sensor_serial.write(b"SPINDLE_OFF\n")
                except:
                    pass

    def stop_machine(self):
        self.grbl_thread.stop()
        self.waktu_selesai = datetime.datetime.now()  # Catat Waktu Selesai (Dihentikan)

        if not self.grbl_thread.mock_mode:
            try:
                self.sensor_thread.sensor_serial.write(b"SPINDLE_OFF\n")
                self.grbl_thread.grbl_serial.write(b"!")
                time.sleep(0.1)
                self.grbl_thread.grbl_serial.write(b"\x18")
                time.sleep(0.5)
                self.grbl_thread.grbl_serial.write(b"$X\n")
            except:
                pass

        self.lamp_stop.setPixmap(self.pix_merah_on)
        self.lamp_start.setPixmap(self.pix_hijau_off)
        self.lbl_status.setText("STATUS MESIN : Berhenti (Titik Awal Disimpan)")

    def trigger_emergency(self, alasan):
        self.grbl_thread.stop()
        self.waktu_selesai = datetime.datetime.now()  # Catat Waktu Selesai (Emergency)

        if not self.grbl_thread.mock_mode:
            try:
                self.sensor_thread.sensor_serial.write(b"SPINDLE_OFF\n")
                self.grbl_thread.grbl_serial.write(b"!")
                time.sleep(0.1)
                self.grbl_thread.grbl_serial.write(b"\x18")
                time.sleep(0.5)
                self.grbl_thread.grbl_serial.write(b"$X\n")
            except:
                pass

        self.lamp_emergency.setPixmap(self.pix_merah_on)
        self.lbl_status.setText("STATUS MESIN : EMERGENCY")

        msg = QMessageBox()
        msg.setIconPixmap(QPixmap("logo listrik.png").scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                                             Qt.TransformationMode.SmoothTransformation))
        msg.setWindowTitle("PERHATIAN!!")
        msg.setText(
            f"EMERGENCY!!\nSEGERA MATIKAN MESIN!!\n{alasan}\n\nMesin berhenti, titik awal disimpan. Klik Buka Jendela untuk mengulang jalur.")
        msg.exec()

        self.lamp_emergency.setPixmap(self.pix_merah_off)
        self.lamp_stop.setPixmap(self.pix_merah_on)
        self.lamp_start.setPixmap(self.pix_hijau_off)

    def update_plot_data(self, tx, ty):
        if len(self.x_data) == 0 or (abs(tx - self.x_data[-1]) > 0.02 or abs(ty - self.y_data[-1]) > 0.02):
            self.x_data.append(tx)
            self.y_data.append(ty)

            self.line.set_data(self.x_data, self.y_data)
            self.point.set_data([tx], [ty])

            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw()

    # ==========================================
    # LOGIKA SIMPAN EXCEL
    # ==========================================
    def save_to_excel(self):
        if not self.waktu_mulai:
            QMessageBox.warning(self, "Peringatan",
                                "Mesin belum pernah dijalankan!\nSilakan lakukan proses milling terlebih dahulu.")
            return

        # Buka dialog save file
        filepath, _ = QFileDialog.getSaveFileName(self, "Simpan Laporan", "Laporan_Milling_CNC.xlsx",
                                                  "Excel Files (*.xlsx)")
        if not filepath:
            return

        try:
            # Ambil waktu selesai terbaru jika mesin masih berjalan saat tombol ditekan
            waktu_akhir = self.waktu_selesai if self.waktu_selesai else datetime.datetime.now()

            # Buat Workbook Baru
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Laporan CNC"

            # Tulis Teks Laporan
            ws['A1'] = "LAPORAN PENGAWASAN MESIN CNC 3 AXIS"
            ws['A1'].font = openpyxl.styles.Font(bold=True, size=14)

            ws['A3'] = "Waktu Mulai:"
            ws['B3'] = self.waktu_mulai.strftime("%d %B %Y, %H:%M:%S")

            ws['A4'] = "Waktu Selesai:"
            ws['B4'] = waktu_akhir.strftime("%d %B %Y, %H:%M:%S")

            ws['A6'] = "Visualisasi Jalur PCB:"

            # Simpan Grafik Matplotlib ke file sementara
            temp_img_path = "temp_plot_cnc.png"
            self.fig.savefig(temp_img_path, dpi=150, bbox_inches='tight')

            # Masukkan Gambar ke Excel
            img = ExcelImage(temp_img_path)
            ws.add_image(img, 'A7')

            # Simpan File Excel
            wb.save(filepath)

            # Hapus file gambar sementara agar bersih
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)

            QMessageBox.information(self, "Berhasil", f"Laporan berhasil disimpan ke:\n{filepath}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal menyimpan file Excel:\n{e}")

    def closeEvent(self, event):
        self.grbl_thread.stop()
        self.sensor_thread.stop()

        if hasattr(self.grbl_thread, 'grbl_serial') and self.grbl_thread.grbl_serial:
            try:
                self.grbl_thread.grbl_serial.close()
            except:
                pass
        if hasattr(self.sensor_thread, 'sensor_serial') and self.sensor_thread.sensor_serial:
            try:
                self.sensor_thread.sensor_serial.close()
            except:
                pass

        event.accept()


# ==========================================
# BOOT SEQUENCE
# ==========================================
if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        cal_dialog = CalibrationDialog()

        if cal_dialog.exec() == QDialog.DialogCode.Accepted:
            window = CNCApp(cal_dialog.grbl_serial, cal_dialog.sensor_serial, cal_dialog.is_mock)
            window.show()
            sys.exit(app.exec())

    except Exception as e:
        print(f"GAGAL MEMULAI APLIKASI: {e}")