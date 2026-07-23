import serial
import time
import threading
import sys

#PORT
grbl = serial.Serial('COM12', 115200, timeout=1)
sensor = serial.Serial('COM9', 115200, timeout=1)
GCODE_FILE = 'mbohrauruskeselanjirfak.txt'

time.sleep(2)

lock = threading.Lock()

last_sensor_data = None
machine_state = "IDLE"      # RUN / STOP / HOME
line_index = 0
home_requested = False
lsb_on = False #flag untuk limit switch bracket
lsc_on = False #flag untuk limit siwtch casing
kalibrasi_selesai = False #Flag untuk menandai kalibrasi selesai atau belum
z_ketika_turun = False #flag untuk menandai sumbu Z sedang turun atau naik

# ← TAMBAH VARIABEL UNTUK SIMPAN ZERO POSITION
zero_position = {"X": 0, "Y": 0, "Z": 0}
is_calibrated = False
#home_offset = {"X": 0, "Y":0, "Z":0}

#INIT GRBL
with lock:
    grbl.write(b"\r\n\r\n")
    time.sleep(2)
with lock:
    grbl.flushInput()

with lock:
    grbl.reset_input_buffer()
    grbl.reset_output_buffer()

sensor.reset_input_buffer()

#MEMBACA SENSOR
def read_sensor_data(raw):
    if raw.startswith("#") and raw.endswith(";"):
        return raw[1:-1]
    return None

#KIRIM KE GRBL
def kirim(cmd):
    print(">>", cmd)

    with lock:
        grbl.write((cmd + '\n').encode())
        grbl.flush()
    
#WAIT OK
def wait_grbl_ok():
    while True:

        with lock:
            response = grbl.readline().decode(errors="ignore").strip()

        if response != "":
            print("<<", response)

        if response.lower() == "ok":
            return "OK"

        if "error" in response.lower():
            return "ERROR"

        if "alarm" in response.lower():
            return "ALARM"

def init_grbl():

    kirim("$X")
    wait_grbl_ok()

    kirim("G21")
    wait_grbl_ok()

    kirim("G90")
    wait_grbl_ok()

    kirim("G17")
    wait_grbl_ok()

    kirim("G94")
    wait_grbl_ok()

#FEED OVERRIDE FUNCTION
current_feed = 100
last_mode = None

def set_feed(target):
    global current_feed

    with lock:
        grbl.write(bytes([0x90]))  # reset 100%
    time.sleep(0.05)

    if target > 100:
        steps = (target - 100) // 10
        for _ in range(steps):
            with lock:
                grbl.write(bytes([0x91]))
            time.sleep(0.02)

    elif target < 100:
        steps = (100 - target) // 10
        for _ in range(steps):
            with lock:
                grbl.write(bytes([0x92]))
            time.sleep(0.02)

    current_feed = target
    print(f"[FEED OVERRIDE] {current_feed}%")


#MEMBACA FEEDRATE DARI ARDUINO 2
def handle_extra_command(data):
    global last_mode
    if data == last_mode:
        return
    last_mode = data
    # ===== MODE DARI ARDUINO =====
    if data == "F_LOW":
        print("F_LOW")
        set_feed(50)

    elif data == "F_MED":
        print("F_MED")
        set_feed(150)

    elif data == "F_HIGH":
        print("F_HIGH")
        set_feed(100)
        
# ← FUNGSI BARU UNTUK RESTORE HOMING
def restore_homing():
    global home_offset

    cmd = (
        f"G92 "
        f"X{home_offset['X']} "
        f"Y{home_offset['Y']} "
        f"Z{home_offset['Z']}"
    )

    kirim(cmd)
    wait_grbl_ok()

#SPINDLE
def spindle_on():
    print("SPINDLE ON")
    sensor.write(b"#SPINDLE_ON;\n") #Kirim perintah menyalakan spindle ke Arduino 2
    time.sleep(3)

def spindle_off():
    print("SPINDLE OFF")
    sensor.write(b"#SPINDLE_OFF;\n")#Kirim perintah mematikan spindle ke arduino 2
    time.sleep(1)

#Menghentikan Program dengan tombol Stop    
def check_stop():
    global machine_state, zero_position, is_calibrated
    if machine_state=="STOP":
        print("MILLING DIHENTIKAN")
        spindle_off()
        with lock:
            grbl.write(b'!')     # Feed hold
        time.sleep(0.2)

        with lock:
            grbl.write(b'\x18')
        time.sleep(1)
        grbl.close()
        sensor.close()
        print("Program berhenti/selesai")
        sys.exit()
    return False

def save_home_offset():
    global home_offset
    kirim("$#")

    while True:

        line = grbl.readline().decode(errors="ignore").strip()

        if line:
            print("<<", line)

        if line.startswith("[G92:"):

            data = line.replace("[G92:", "").replace("]", "")
            x, y, z = map(float, data.split(","))

            home_offset["X"] = x
            home_offset["Y"] = y
            home_offset["Z"] = z

            print("HOME OFFSET:", home_offset)

        if line.lower() == "ok":
            break
    
#THREAD SENSOR
def tombol_kontrol():
    
    global lsb_on, lsc_on
    global machine_state

    while True:
        if sensor.in_waiting:

            raw=sensor.readline().decode(
                errors="ignore" 
            ).strip()

            data=read_sensor_data(raw)

            if data:

                print("SENSOR:",data)
                if data=="LSBON": #Limit Switch Bracket terpasang
                    lsb_on = True
                    print("LSB AKTIF")
                elif data=="LSBOFF": #Limit Switch Bracket terlepas
                    lsb_on = False
                    print("LSB TIDAK AKTIF")
                elif data=="LSC_ON": #Limit Switch Casing terpasang
                    lsc_on = True
                    print("LSC_ON")
                elif data=="LSC_OFF":#Limit Switch Casing terlepas
                    lsc_on = False
                    print("LSC_OFF")
                elif data=="STOP_ON":#Tombol Stop ditekan
                    if machine_state=="START":
                        machine_state="STOP"
                        print("STOP DITEKAN")

                elif data=="START_ON": #Tombol Start ditekan
                    if kalibrasi_selesai and not lsc_on:
                        print("Casing terbuka - Start ditolak")
                        continue
                    #if machine_state=="START":
                    machine_state="START"
                    print("START DITEKAN")

                else:
                    global last_sensor_data
                    last_sensor_data=data

                sensor.write(b"ACK\n")

        time.sleep(0.01)

#Menghentikan proses milling/kalibrasi yang sedang dikerjakan
#saat terjadi PCB terlepas atau Casing terbuka 
def emg_limit():
    print ("PROGRAM DIHENTIKAN")
    spindle_off()
    with lock:
        grbl.write(b'!') #feed hold
    time.sleep(0.2)
    with lock:
        grbl.write(b'\x18') #reset grbl
    time.sleep(1)
    grbl.close()
    sensor.close()
    sys.exit()

#Cek Kondisi Bracket
def check_lsb():
    if not lsb_on:
        print("ERROR : PCB Lepas")
        emg_limit()

#Cek Kondisi Casing
def check_lsc():
    if not lsc_on:
        print("Casing terbuka")
        emg_limit()
threading.Thread(target=tombol_kontrol, daemon=True).start()

print("MENUNGGU PCB TERPASANG")
while not lsb_on:
    time.sleep(0.1)
print("PCB SUDAH TERPASANG")
print("MULAI KALIBRASI")

# ====== SETUP ======
kirim("$X")
wait_grbl_ok()

kirim("G21")
wait_grbl_ok()

kirim("G91")
wait_grbl_ok()

#PROSES KALIBRASI
limx = False
limy = False
limz = False

limx = False
limy = False
limz = False

while True:
    check_lsb()
    move_cmd = "G1"
    if not limx:
        move_cmd += "X-2"
    if not limy:
        move_cmd += "Y-2"   # gerak ke arah limit
    if not limz :
        move_cmd+= "Z2"
        
    move_cmd += "F300"
    if move_cmd != "G1 F300":
        kirim(move_cmd)
    time.sleep(0.05)
    
    data =  last_sensor_data
    last_sensor_data = None
    if data == "LIMX":            
        limx = True
        print("X LIMIT KETEMU")
        grbl.write(b'\x18')   # RESET TOTAL
        time.sleep(1)

        kirim("$X")
        kirim("G21")
        kirim("G91")    

    if data == "LIMY":
        limy = True
        print ("Y LIMIT KETEMU")
        grbl.write(b'\x18')   # RESET TOTAL
        time.sleep(1)

        kirim("$X")
        kirim("G21")
        kirim("G91")

    if data == "LIMZ":
        limz = True
        print("Z LIMIT KETEMU")
        grbl.write(b'\x18')
        time.sleep(1)

        kirim("$X")
        kirim("G21")
        kirim("G91")
            
    if limx and limy and limz:
        print("🔥 LIMIT X Y Z KETEMU!")

        # RESET GRBL
        grbl.write(b'\x18')
        time.sleep(1)

        kirim("$X")
        kirim("G21")
        kirim("G91")
        sensor.reset_input_buffer()
        time.sleep(0.2)
        break
    else:
        continue
    break

#HOME X
while True:
    check_lsb()
    print("GESER X 37mm")
    kirim("G91")
    kirim("G1 X37 F300")
    wait_grbl_ok()
    kirim("G92 X0")
    wait_grbl_ok()
    print("X HOME DITEMUKAN")
    time.sleep(0.2)
    break

#HOME Y
while True :
    check_lsb()
    print("GESER Y 123mm")
    kirim("G91")
    kirim("G1 Y118 F300")
    wait_grbl_ok()
    kirim("G92 Y0")
    wait_grbl_ok()
    print("Y HOME DITEMUKAN")
    time.sleep(0.3)
    break

#HOME Z
while True:
    check_lsb()
    kirim("G1 Z-2 F300")
    ketemu_z = False
    data = last_sensor_data
    last_sensor_data = None
    
    if data == "PCBON":
        ketemu_z = True
        print("🔥 Z HOME DITEMUKAN!")

            # ===== RESET GRBL =====
        grbl.write(b'\x18')
        time.sleep(1)

            # ===== INIT ULANG =====
        kirim("$X")
        kirim("G21")
        kirim("G91")

            # ===== SET Z HOME ===== 
        kirim("G92 Z0")
        kirim("G1 Z0 F300")
        time.sleep(0.5)

        #kirim("?")
        sensor.reset_input_buffer()
        time.sleep(0.3)
        break
    
# ====== SET HOME ======
kirim("$X")
wait_grbl_ok()

kirim("G21")
wait_grbl_ok()

kirim("G90")
wait_grbl_ok()

kirim("G17")
wait_grbl_ok()

kirim("G94")
wait_grbl_ok()

kirim("G92 X0 Y0 Z0")
wait_grbl_ok()

home_offset = {"X":0, "Y":0, "Z":0}

kirim("$#")

while True:

    line = grbl.readline().decode(errors="ignore").strip()

    if line.startswith("[G92:"):

        data = line[5:-1]

        x, y, z = map(float, data.split(","))

        home_offset["X"] = x
        home_offset["Y"] = y
        home_offset["Z"] = z

        print("HOME OFFSET:", home_offset)

    if line == "ok":
        break
    
kirim("$#")

while True:
    line = grbl.readline().decode(errors="ignore").strip()

    if line:
        print("DEBUG:", line)

    if line.lower() == "ok":
        break
    
# ← SIMPAN ZERO KE VARIABLE
zero_position = {"X": 0, "Y": 0, "Z": 0}
is_calibrated = True

print(f"✓ ZERO POSITION DISIMPAN: {zero_position}")
print("✓ SISTEM SIAP - KALIBRASI SELESAI")
kalibrasi_selesai = True


kirim("?")
time.sleep(0.2)

while grbl.in_waiting:
    print("STATUS:", grbl.readline().decode(errors="ignore").strip())
    
machine_state = "IDLE"    
print("MENUNGGU START")

while machine_state!="START":
    time.sleep(0.1)

#MEMBACA G-CODE DARI FILE .txt   
with open(GCODE_FILE) as f:
    lines = [l.strip() for l in f if l.strip() and not l.startswith("(")]
    spindle_on()
    
buffer_size = 10      # jumlah line di buffer
line_index = 0
pending = 0

print("Start streaming...")
    
while True:
    check_lsb()
    check_lsc()
    #global z_ketika_turun
    if check_stop():
        break
    
    # isi buffer
    if machine_state=="START":
        while pending < buffer_size and line_index < len(lines):
            
            cmd = lines[line_index]
            #deteksi perubahan Z dari g-code
            #Arduino akan mengirimkan nilai Rotary X dan Y
            #setelah start ditekan/Z turun
            if "Z" in cmd.upper():
                try:
                    for p in cmd.upper().split():
                        if p.startswith("Z"):
                            nilai_z = float(p[1:])

                            #z turun
                            if nilai_z < 0 and not z_ketika_turun:
                                sensor.write(b"#Z_TURUN;\n")
                                print("KIRIM #Z_TURUN;")
                                z_ketika_turun = True

                            #z naik
                            elif nilai_z >= 0 and z_ketika_turun:
                                sensor.write(b"#Z_NAIK;\n")
                                print("KIRIM #Z_NAIK;")
                                z_ketika_turun = False
                except:
                    pass
                
            grbl.write((cmd + "\n").encode())
            print(">>", cmd)

            line_index += 1
            pending += 1   

        # baca respon GRBL
        while grbl.in_waiting:
            response = grbl.readline().decode().strip()
            if response:
                print("<<", response)
                if response.lower() == "ok":
                    if pending > 0:
                        pending -= 1
        
        #selesai
        if line_index >= len(lines):
            spindle_off()
            sensor.write(b"#MILLING_SELESAI;\n")
            print("Kirim Milling Selesai")
            break
        time.sleep(0.001)
grbl.close()
sensor.close()
print("DONE")
