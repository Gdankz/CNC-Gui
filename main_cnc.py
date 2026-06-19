import sys
import serial
import time
import re
import os
import datetime
import openpyxl
from openpyxl.drawing.image import Image as ExcelImage

import matplotlib

matplotlib.use('qtagg')

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QProgressBar, QMessageBox, QFileDialog, QDialog, QFrame,
                             QSizePolicy, QGridLayout)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QPixmap, QColor

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ==========================================
# KONFIGURASI PORT
# ==========================================
PORT_GRBL = 'COM12'
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

    def wait_grbl_ok(self):
        while self.is_running:
            try:
                response = self.grbl.readline().decode(errors="ignore").strip()
                if response.lower() == "ok": return True
                if "error" in response.lower(): return False
            except:
                pass

    def baca_sensor(self):
        if self.sensor.in_waiting:
            raw = self.sensor.readline().decode(errors="ignore").strip()
            if raw.startswith("#") and raw.endswith(";"):
                return raw[1:-1]
        return None

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
                self.status_update.emit("Menunggu PCB Terpasang...")
                self.progress_update.emit(10)

                lsb_ok = False
                while self.is_running and not lsb_ok:
                    data = self.baca_sensor()
                    if data == "LSBON":
                        lsb_ok = True
                    time.sleep(0.1)

                if not self.is_running: return

                self.status_update.emit("Inisialisasi GRBL...")
                self.grbl.write(b"\r\n\r\n")
                time.sleep(2)
                self.grbl.flushInput()
                self.sensor.reset_input_buffer()

                self.kirim("$X");
                self.kirim("G21");
                self.kirim("G91")

                self.status_update.emit("Mencari Limit Switch X, Y, Z...")
                self.progress_update.emit(30)
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

                    data = self.baca_sensor()
                    if data == "LIMX":
                        limx = True
                        self.grbl.write(b'\x18');
                        time.sleep(1)
                        self.kirim("$X");
                        self.kirim("G21");
                        self.kirim("G91")
                    elif data == "LIMY":
                        limy = True
                        self.grbl.write(b'\x18');
                        time.sleep(1)
                        self.kirim("$X");
                        self.kirim("G21");
                        self.kirim("G91")
                    elif data == "LIMZ":
                        limz = True
                        self.grbl.write(b'\x18');
                        time.sleep(1)
                        self.kirim("$X");
                        self.kirim("G21");
                        self.kirim("G91")

                    if limx and limy and limz:
                        self.grbl.write(b'\x18');
                        time.sleep(1)
                        self.kirim("$X");
                        self.kirim("G21");
                        self.kirim("G91")
                        self.sensor.reset_input_buffer()
                        time.sleep(0.2)
                        break

                if not self.is_running: return

                self.status_update.emit("Geser X 37mm...")
                self.progress_update.emit(50)
                self.kirim("G91");
                self.kirim("G1 X37 F300")
                self.wait_grbl_ok()
                self.kirim("G92 X0");
                self.wait_grbl_ok()

                self.status_update.emit("Geser Y 118mm...")
                self.progress_update.emit(70)
                self.kirim("G91");
                self.kirim("G1 Y118 F300")
                self.wait_grbl_ok()
                self.kirim("G92 Y0");
                self.wait_grbl_ok()

                self.status_update.emit("Menyesuaikan Home Z (PCB Sentuh)...")
                self.progress_update.emit(85)
                self.sensor.reset_input_buffer()
                while self.is_running:
                    self.kirim("G1 Z-2 F300")
                    data = self.baca_sensor()
                    if data == "PCBON":
                        self.grbl.write(b'\x18');
                        time.sleep(1)
                        self.kirim("$X");
                        self.kirim("G21");
                        self.kirim("G91")
                        self.kirim("G92 Z0");
                        self.kirim("G1 Z0 F300")
                        time.sleep(0.5)
                        self.sensor.reset_input_buffer()
                        time.sleep(0.3)
                        break

                if not self.is_running: return
                self.status_update.emit("Kalibrasi Selesai! Tekan Tombol START di panel mesin.")
                self.progress_update.emit(95)

                self.kirim("$X");
                self.kirim("G21");
                self.kirim("G90");
                self.kirim("G17");
                self.kirim("G94")
                self.kirim("G92 X0 Y0 Z0");
                self.wait_grbl_ok()

                while self.is_running:
                    data = self.baca_sensor()
                    if data == "START_ON":
                        break
                    time.sleep(0.1)

                self.status_update.emit("START Ditekan! Mesin Siap Beroperasi.")
                self.progress_update.emit(100)

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
# JENDELA BARU: PLOT WINDOW
# ==========================================
class PlotWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visual Jalur PCB Real-Time")
        self.resize(550, 500)
        self.setStyleSheet("background-color: #cccccc;")
        layout = QVBoxLayout(self)

        self.fig = Figure(figsize=(5, 5), facecolor='#cccccc')
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)

        self.x_data, self.y_data = [], []
        self.setup_plot()

        layout.addWidget(self.canvas)

    def setup_plot(self):
        self.ax.clear()
        self.ax.set_title("Visual Jalur PCB", fontsize=12, fontweight='bold')
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.ax.set_facecolor('#e6e6e6')
        self.line, = self.ax.plot([], [], 'b-', linewidth=2)
        self.point, = self.ax.plot([], [], 'ro')
        self.x_data.clear()
        self.y_data.clear()
        self.canvas.draw()

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
# JENDELA BARU: EMERGENCY POPUP
# ==========================================
class EmergencyPopup(QDialog):
    def __init__(self, pesan_error="Mesin terdeteksi arus berlebih/kabel putus.", parent=None):
        super().__init__(parent)
        self.setWindowTitle("PERHATIAN!!")
        self.setFixedSize(450, 350)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.CustomizeWindowHint)
        self.setStyleSheet("background-color: #cccccc; border: 2px solid black;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(10)

        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_logo.setStyleSheet("border: none;")
        pix_logo = QPixmap("logo listrik.png").scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation)
        self.lbl_logo.setPixmap(pix_logo)
        layout.addWidget(self.lbl_logo)

        lbl_title = QLabel("EMERGENCY!!")
        lbl_title.setFont(QFont("Times New Roman", 20, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: red; border: none;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_subtitle = QLabel("SEGERA MATIKAN MESIN!!")
        lbl_subtitle.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        lbl_subtitle.setStyleSheet("color: black; border: none;")
        lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_subtitle)

        frame_text = QFrame()
        frame_text.setStyleSheet("background-color: white; border: 1px solid black; border-radius: 2px;")
        frame_layout = QVBoxLayout(frame_text)

        text_report = f"<b>{pesan_error}</b><br><br>Klik OK untuk melakukan<br><b>KALIBRASI ULANG.</b>"
        self.lbl_report = QLabel(text_report)
        self.lbl_report.setFont(QFont("Arial", 10))
        self.lbl_report.setStyleSheet("color: black; border: none;")
        self.lbl_report.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_report.setWordWrap(True)
        frame_layout.addWidget(self.lbl_report)

        layout.addWidget(frame_text)
        layout.addSpacing(10)

        self.btn_ok = QPushButton("OK")
        self.btn_ok.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.btn_ok.setStyleSheet("""
            QPushButton { background-color: #2d862d; color: white; border: 2px solid black; padding: 10px; min-width: 100px; }
            QPushButton:hover { background-color: #246b24; }
            QPushButton:pressed { background-color: #1a4d1a; }
        """)
        self.btn_ok.clicked.connect(self.accept)
        layout.addWidget(self.btn_ok, alignment=Qt.AlignmentFlag.AlignCenter)


# ==========================================
# 1. THREAD GRBL
# ==========================================
class GRBLWorker(QThread):
    progress_update = pyqtSignal(int)
    status_update = pyqtSignal(str)
    sim_position_update = pyqtSignal(float, float)

    def __init__(self, grbl_serial, sensor_serial, mock_mode):
        super().__init__()
        self.gcode_lines = []
        self.is_running = False
        self.grbl_serial = grbl_serial
        self.sensor_serial = sensor_serial
        self.mock_mode = mock_mode
        self.cur_x = 0.0
        self.cur_y = 0.0
        self.z_ketika_turun = False

    def load_file(self, filepath):
        with open(filepath, 'r') as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith('(')]

        homing_sequence = ["G21", "G90", "G00 Z3.000", "G00 X0 Y0", "G00 Z0.000"]
        self.gcode_lines = homing_sequence + lines

    def run(self):
        self.is_running = True
        self.status_update.emit('<i>On Progress</i>')
        total_lines = len(self.gcode_lines) if self.gcode_lines else 100

        for i, line in enumerate(self.gcode_lines):
            if not self.is_running:
                break
            print(f">> {line}")

            if not self.mock_mode and "Z" in line.upper():
                try:
                    for p in line.upper().split():
                        if p.startswith("Z"):
                            nilai_z = float(p[1:])
                            if nilai_z < 0 and not self.z_ketika_turun:
                                self.sensor_serial.write(b"#Z_TURUN;\n")
                                print("KIRIM #Z_TURUN;")
                                self.z_ketika_turun = True
                            elif nilai_z >= 0 and self.z_ketika_turun:
                                self.sensor_serial.write(b"#Z_NAIK;\n")
                                print("KIRIM #Z_NAIK;")
                                self.z_ketika_turun = False
                except:
                    pass

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
                        if res.lower() == "ok":
                            break
                        elif "error" in res.lower():
                            break
                except Exception as e:
                    print(f"Error Serial GRBL: {e}")

            persentase = int(((i + 1) / total_lines) * 100)
            self.progress_update.emit(persentase)

        if self.is_running:
            if not self.mock_mode:
                try:
                    self.sensor_serial.write(b"#MILLING_SELESAI;\n")
                except:
                    pass
            self.status_update.emit("<i>Done</i>")

    def stop(self):
        self.is_running = False


# ==========================================
# 2. THREAD SENSOR
# ==========================================
class SensorWorker(QThread):
    encoder_update = pyqtSignal(float, float)
    emergency_trigger = pyqtSignal(str)
    feed_override_update = pyqtSignal(str)

    def __init__(self, sensor_serial, mock_mode):
        super().__init__()
        self.is_running = True
        self.sensor_serial = sensor_serial
        self.mock_mode = mock_mode

    def run(self):
        while self.is_running:
            if not self.mock_mode:
                if self.sensor_serial.in_waiting:
                    raw = self.sensor_serial.readline().decode('utf-8', errors='ignore').strip()
                    if raw.startswith("#") and raw.endswith(";"):
                        data = raw[1:-1]

                        if data.startswith("POS,"):
                            try:
                                _, tx, ty = data.split(',')
                                self.encoder_update.emit(float(tx), float(ty))
                            except:
                                pass

                        elif data in ["F_LOW", "F_MED", "F_HIGH"]:
                            self.feed_override_update.emit(data)

                        elif data == "LSBOFF":
                            self.emergency_trigger.emit("Bracket PCB Terlepas!")
                        elif data == "LSC_OFF":
                            self.emergency_trigger.emit("Casing Akrilik Terbuka!")
                        elif data == "STOP_ON":
                            self.emergency_trigger.emit("Tombol STOP Ditekan Secara Fisik!")

                    self.sensor_serial.write(b"ACK\n")
            else:
                time.sleep(0.5)

    def stop(self):
        self.is_running = False


# ==========================================
# 3. MAIN GUI
# ==========================================
class CNCApp(QMainWindow):
    request_recalibration = pyqtSignal()

    def __init__(self, grbl_serial, sensor_serial, is_mock):
        super().__init__()
        self.setWindowTitle("Sistem Pengawasan dan Keamanan Mesin CNC 3 Axis")
        self.setGeometry(100, 100, 650, 600)
        self.setStyleSheet("background-color: #cccccc;")

        self.need_calibration = False
        self.waktu_mulai = None
        self.waktu_selesai = None
        self.grbl_serial_ref = grbl_serial

        self.plot_window = PlotWindow()

        self.setup_ui()
        self.start_threads(grbl_serial, sensor_serial, is_mock)

    def start_threads(self, grbl_serial, sensor_serial, is_mock):
        self.grbl_thread = GRBLWorker(grbl_serial, sensor_serial, is_mock)
        self.sensor_thread = SensorWorker(sensor_serial, is_mock)

        self.grbl_thread.progress_update.connect(self.update_progress)
        self.grbl_thread.status_update.connect(self.update_status)

        if is_mock:
            self.grbl_thread.sim_position_update.connect(self.plot_window.update_plot_data)
        else:
            self.sensor_thread.encoder_update.connect(self.plot_window.update_plot_data)

        self.sensor_thread.emergency_trigger.connect(self.trigger_emergency)
        self.sensor_thread.feed_override_update.connect(self.update_spindle_gui)
        self.sensor_thread.start()

    def create_line(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("border: 1px solid black;")
        return line

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        grid = QGridLayout(main_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        # 1. HEADER
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #d9d9d9; border-bottom: 2px solid black;")
        h_layout = QVBoxLayout(header_frame)
        lbl_h = QLabel("🪶 Jendela GUI Sistem Pengawasan dan Keamanan Mesin CNC 3 Axis untuk Milling PCB")
        lbl_h.setFont(QFont("Arial", 10))
        h_layout.addWidget(lbl_h)
        grid.addWidget(header_frame, 0, 0, 1, 2)

        # 2. HEADER PANEL
        header2_frame = QFrame()
        header2_frame.setStyleSheet("background-color: #cccccc; border-bottom: 2px solid black;")
        h2_layout = QVBoxLayout(header2_frame)
        lbl_panel = QLabel("PANEL PENGAWASAN DAN KEAMANAN")
        lbl_panel.setFont(QFont("Arial", 14, QFont.Weight.Normal))
        lbl_panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h2_layout.addWidget(lbl_panel)
        grid.addWidget(header2_frame, 1, 0, 1, 2)

        # 3. PANEL KIRI
        left_panel = QFrame()
        left_panel.setFixedWidth(200)
        left_panel.setStyleSheet("background-color: #a6a6a6; border-right: 2px solid black;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 20, 10, 20)

        lbl_indikator = QLabel("INDIKATOR")
        lbl_indikator.setFont(QFont("Arial", 12))
        lbl_indikator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_indikator.setStyleSheet("border: none;")
        left_layout.addWidget(lbl_indikator)

        self.pix_hijau_off = QPixmap("OFF.png").scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation)
        self.pix_hijau_on = QPixmap("ON.png").scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation)
        self.pix_merah_off = QPixmap("OFF-M.png").scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                                         Qt.TransformationMode.SmoothTransformation)
        self.pix_merah_on = QPixmap("ON-M.png").scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation)
        self.pix_fan = QPixmap("balingbaling.png").scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio,
                                                          Qt.TransformationMode.SmoothTransformation)

        def add_lamp(layout, pix, text):
            lbl = QLabel();
            lbl.setPixmap(pix);
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter);
            lbl.setStyleSheet("border: none;")
            layout.addWidget(lbl)
            txt = QLabel(text);
            txt.setAlignment(Qt.AlignmentFlag.AlignCenter);
            txt.setFont(QFont("Arial", 9));
            txt.setStyleSheet("border: none;")
            layout.addWidget(txt)
            layout.addSpacing(10)
            return lbl

        self.lamp_start = add_lamp(left_layout, self.pix_hijau_off, "Mulai \"START\"")
        self.lamp_stop = add_lamp(left_layout, self.pix_merah_off, "BERHENTI \"STOP\"")
        self.lamp_emergency = add_lamp(left_layout, self.pix_merah_off, "EMERGENCY")

        self.btn_emergency_sim = QPushButton(self.lamp_emergency)
        self.btn_emergency_sim.setStyleSheet("background-color: transparent;")
        self.btn_emergency_sim.resize(80, 80)
        self.btn_emergency_sim.clicked.connect(self.simulate_emergency_click)
        left_layout.addStretch()
        grid.addWidget(left_panel, 2, 0)

        # 4. PANEL KANAN UTAMA
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #cccccc;")
        r_layout = QVBoxLayout(right_panel)
        r_layout.setContentsMargins(20, 15, 20, 20)

        lbl_prog = QLabel("<i>PROGRESS BAR</i>")
        lbl_prog.setFont(QFont("Arial", 12))
        lbl_prog.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r_layout.addWidget(lbl_prog)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(25)
        self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid gray; background-color: #b3b3b3; text-align: center; color: black; font-size: 12px; }
            QProgressBar::chunk { background-color: #1aa31a; margin: 0px; }
        """)
        r_layout.addWidget(self.progress_bar)
        r_layout.addSpacing(20)

        self.lbl_status = QLabel("STATUS MESIN : <i>Off Condition</i>")
        self.lbl_status.setFont(QFont("Arial", 16))
        r_layout.addWidget(self.lbl_status)
        r_layout.addSpacing(20)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_vbox = QVBoxLayout()
        btn_style = """
            QPushButton { background-color: #a0a0a0; border: none; padding: 10px; font-size: 11px; min-width: 150px; }
            QPushButton:hover { background-color: #8c8c8c; }
            QPushButton:pressed { background-color: #737373; }
        """
        btn_load = QPushButton("Jendela Jalur PCB")
        btn_load.setStyleSheet(btn_style)
        btn_load.clicked.connect(self.load_and_start)

        self.btn_excel = QPushButton("Simpan Data .xs")
        self.btn_excel.setStyleSheet(btn_style)
        self.btn_excel.clicked.connect(self.save_to_excel)

        btn_vbox.addWidget(btn_load)
        btn_vbox.addSpacing(10)
        btn_vbox.addWidget(self.btn_excel)
        btn_layout.addLayout(btn_vbox)
        r_layout.addLayout(btn_layout)

        r_layout.addSpacing(15)
        r_layout.addWidget(self.create_line())
        r_layout.addSpacing(15)

        lbl_spindle = QLabel("STATUS KECEPATAN SPINDLE")
        lbl_spindle.setFont(QFont("Arial", 14))
        lbl_spindle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r_layout.addWidget(lbl_spindle)

        spindle_hbox = QHBoxLayout()
        spindle_hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spindle_hbox.setSpacing(40)
        r_layout.addLayout(spindle_hbox)

        def create_fan_widget(text):
            vbox = QVBoxLayout()
            vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.setSpacing(0)
            vbox.setContentsMargins(0, 0, 0, 0)
            fan = QLabel()
            fan.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fan.setPixmap(self.pix_fan)
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(QFont("Arial", 10))
            lbl.setStyleSheet("background-color: grey; color: black; padding: 3px 15px;")
            vbox.addWidget(fan)
            vbox.addWidget(lbl)
            return vbox, lbl

        fan_rendah_layout, self.lbl_rendah = create_fan_widget("RENDAH")
        fan_sedang_layout, self.lbl_sedang = create_fan_widget("SEDANG")
        fan_tinggi_layout, self.lbl_tinggi = create_fan_widget("TINGGI")

        spindle_hbox.addLayout(fan_rendah_layout)
        spindle_hbox.addLayout(fan_sedang_layout)
        spindle_hbox.addLayout(fan_tinggi_layout)
        r_layout.addStretch()
        grid.addWidget(right_panel, 2, 1)

    def update_spindle_gui(self, mode):
        self.lbl_rendah.setStyleSheet("background-color: grey; color: black; padding: 3px 15px;")
        self.lbl_sedang.setStyleSheet("background-color: grey; color: black; padding: 3px 15px;")
        self.lbl_tinggi.setStyleSheet("background-color: grey; color: white; padding: 3px 15px;")

        try:
            if mode == "F_LOW":
                self.lbl_rendah.setStyleSheet("background-color: #00FF00; color: black; padding: 3px 15px;")
                if not self.grbl_thread.mock_mode:
                    self.grbl_serial_ref.write(bytes([0x90]))
                    time.sleep(0.05)
                    for _ in range(5): self.grbl_serial_ref.write(bytes([0x92]))
            elif mode == "F_MED":
                self.lbl_sedang.setStyleSheet("background-color: yellow; color: black; padding: 3px 15px;")
                if not self.grbl_thread.mock_mode:
                    self.grbl_serial_ref.write(bytes([0x90]))
                    time.sleep(0.05)
                    for _ in range(5): self.grbl_serial_ref.write(bytes([0x91]))
            elif mode == "F_HIGH":
                self.lbl_tinggi.setStyleSheet("background-color: red; color: white; padding: 3px 15px;")
                if not self.grbl_thread.mock_mode:
                    self.grbl_serial_ref.write(bytes([0x90]))
        except:
            pass

    def load_and_start(self):
        if self.need_calibration:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Kalibrasi Dibutuhkan")
            msg.setText(
                "Mesin telah menyelesaikan milling sebelumnya.\nAnda harus melakukan kalibrasi ulang sebelum memuat file G-Code baru.")

            btn_kal = msg.addButton("Kalibrasi Sekarang", QMessageBox.ButtonRole.ActionRole)
            btn_batal = msg.addButton("Batal", QMessageBox.ButtonRole.RejectRole)

            msg.exec()

            if msg.clickedButton() == btn_kal:
                self.request_recalibration.emit()
            return

        filepath, _ = QFileDialog.getOpenFileName(self, "Pilih File G-Code", "", "Text Files (*.txt);;All Files (*)")
        if filepath:
            if not self.grbl_thread.isRunning():
                old_mock = self.grbl_thread.mock_mode
                old_grbl = self.grbl_thread.grbl_serial
                old_sensor = self.sensor_thread.sensor_serial
                self.grbl_thread = GRBLWorker(old_grbl, old_sensor, old_mock)
                self.grbl_thread.progress_update.connect(self.update_progress)
                self.grbl_thread.status_update.connect(self.update_status)

                if old_mock:
                    self.grbl_thread.sim_position_update.connect(self.plot_window.update_plot_data)

            self.grbl_thread.load_file(filepath)

            self.plot_window.setup_plot()
            self.plot_window.show()

            self.lamp_start.setPixmap(self.pix_hijau_on)
            self.lamp_stop.setPixmap(self.pix_merah_off)
            self.lamp_emergency.setPixmap(self.pix_merah_off)
            self.progress_bar.setValue(0)

            self.waktu_mulai = datetime.datetime.now()
            self.waktu_selesai = None

            if not self.grbl_thread.mock_mode:
                try:
                    self.sensor_thread.sensor_serial.write(b"#SPINDLE_ON;\n")
                except:
                    pass

            self.grbl_thread.start()

    def update_progress(self, val):
        self.progress_bar.setValue(val)

    def update_status(self, status):
        self.lbl_status.setText(f"STATUS MESIN : {status}")
        self.lbl_status.setStyleSheet("color: black;")

        if "Done" in status:
            self.waktu_selesai = datetime.datetime.now()
            self.lamp_start.setPixmap(self.pix_hijau_off)

            self.need_calibration = True

            if not self.grbl_thread.mock_mode:
                try:
                    self.sensor_thread.sensor_serial.write(b"#SPINDLE_OFF;\n")
                except:
                    pass

            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("Proses Selesai")
            msg.setText(
                "Proses milling telah selesai (Done).\n\nKlik 'Kalibrasi' jika Anda ingin langsung mereset mesin sekarang.\nKlik 'OK' jika Anda ingin menyimpan data (.xlsx) terlebih dahulu.")

            btn_kal = msg.addButton("Kalibrasi", QMessageBox.ButtonRole.ActionRole)
            btn_ok = msg.addButton("OK", QMessageBox.ButtonRole.ActionRole)

            msg.exec()

            if msg.clickedButton() == btn_kal:
                self.request_recalibration.emit()

    def stop_machine(self):
        self.grbl_thread.stop()
        self.waktu_selesai = datetime.datetime.now()

        if not self.grbl_thread.mock_mode:
            try:
                self.sensor_thread.sensor_serial.write(b"#SPINDLE_OFF;\n")
                self.grbl_thread.grbl_serial.write(b"!")
                time.sleep(0.1)
                self.grbl_thread.grbl_serial.write(b"\x18")
                time.sleep(0.5)
                self.grbl_thread.grbl_serial.write(b"$X\n")
            except:
                pass

        self.lamp_stop.setPixmap(self.pix_merah_on)
        self.lamp_start.setPixmap(self.pix_hijau_off)
        self.lamp_emergency.setPixmap(self.pix_merah_off)
        self.lbl_status.setText("STATUS MESIN : <i>Berhenti (Titik Awal Disimpan)</i>")
        self.lbl_status.setStyleSheet("color: black;")

    def simulate_emergency_click(self):
        self.trigger_emergency("Simulasi GUI Tombol Emergency")

    def trigger_emergency(self, alasan):
        self.grbl_thread.stop()
        self.waktu_selesai = datetime.datetime.now()

        self.lbl_status.setText("STATUS MESIN : <i>Emergency</i>")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold;")

        self.lamp_emergency.setPixmap(self.pix_merah_on)
        self.lamp_start.setPixmap(self.pix_hijau_off)
        self.lamp_stop.setPixmap(self.pix_merah_off)

        if not self.grbl_thread.mock_mode:
            try:
                self.sensor_thread.sensor_serial.write(b"#SPINDLE_OFF;\n")
                self.grbl_thread.grbl_serial.write(b"!")
                time.sleep(0.1)
                self.grbl_thread.grbl_serial.write(b"\x18")
                time.sleep(0.5)
                self.grbl_thread.grbl_serial.write(b"$X\n")
            except:
                pass

        self.plot_window.hide()
        self.grbl_thread.wait()

        popup = EmergencyPopup(pesan_error=alasan, parent=self)
        if popup.exec() == QDialog.DialogCode.Accepted:
            self.request_recalibration.emit()

    def save_to_excel(self):
        if not self.waktu_mulai:
            QMessageBox.warning(self, "Peringatan",
                                "Mesin belum pernah dijalankan!\nSilakan lakukan proses milling terlebih dahulu.")
            return

        # --- TAMBAHAN LOGIKA BARU MENCEGAH SAVE SAAT RUNNING ---
        if self.waktu_mulai and not self.waktu_selesai:
            QMessageBox.warning(self, "Peringatan",
                                "Mesin sedang beroperasi!\nHarap tunggu hingga proses milling selesai (Done) atau dihentikan untuk menyimpan data.")
            return
        # -------------------------------------------------------

        filepath, _ = QFileDialog.getSaveFileName(self, "Simpan Laporan", "Laporan_Milling_CNC.xlsx",
                                                  "Excel Files (*.xlsx)")
        if not filepath: return

        try:
            waktu_akhir = self.waktu_selesai if self.waktu_selesai else datetime.datetime.now()
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Laporan CNC"

            ws['A1'] = "LAPORAN PENGAWASAN MESIN CNC 3 AXIS"
            ws['A1'].font = openpyxl.styles.Font(bold=True, size=14)
            ws['A3'] = "Waktu Mulai:";
            ws['B3'] = self.waktu_mulai.strftime("%d %B %Y, %H:%M:%S")
            ws['A4'] = "Waktu Selesai:";
            ws['B4'] = waktu_akhir.strftime("%d %B %Y, %H:%M:%S")
            ws['A6'] = "Visualisasi Jalur PCB:"

            temp_img_path = "temp_plot_cnc.png"
            self.plot_window.fig.savefig(temp_img_path, dpi=150, bbox_inches='tight')

            img = ExcelImage(temp_img_path)
            ws.add_image(img, 'A7')
            wb.save(filepath)

            if os.path.exists(temp_img_path): os.remove(temp_img_path)
            QMessageBox.information(self, "Berhasil", f"Laporan berhasil disimpan ke:\n{filepath}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal menyimpan file Excel:\n{e}")

    def closeEvent(self, event):
        self.plot_window.close()
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
        continue_program = True

        while continue_program:
            cal_dialog = CalibrationDialog()
            if cal_dialog.exec() == QDialog.DialogCode.Accepted:
                window = CNCApp(cal_dialog.grbl_serial, cal_dialog.sensor_serial, cal_dialog.is_mock)
                restart_requested = [False]


                def handle_recalc_request():
                    restart_requested[0] = True
                    window.close()


                window.request_recalibration.connect(handle_recalc_request)
                window.show()
                app.exec()

                if restart_requested[0]:
                    if hasattr(window, 'plot_window'): window.plot_window.close()
                    del window
                    continue
                else:
                    continue_program = False
                    break

            else:
                continue_program = False
                break

    except Exception as e:
        print(f"GAGAL MEMULAI APLIKASI: {e}")