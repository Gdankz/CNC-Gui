import tkinter as tk
from PIL import Image, ImageTk

root = tk.Tk()
root.title("Panel Lampu ON/OFF")
root.configure(bg="white")  # warna background, bisa kamu ubah

# ======== PENGATURAN DASAR ========
WIDTH, HEIGHT = 150, 150  # ukuran gambar
PADDING_Y = 15            # jarak antar komponen (biar bisa kamu ubah dengan mudah)

# ======== LOAD GAMBAR ========
# Indikator ON-HIJAU
img_hijau_off = ImageTk.PhotoImage(Image.open("OFF.png").resize((WIDTH, HEIGHT)))
img_hijau_on  = ImageTk.PhotoImage(Image.open("ON.png").resize((WIDTH, HEIGHT)))

# Indikator OFF-Merah
img_merah_off = ImageTk.PhotoImage(Image.open("OFF-M.png").resize((WIDTH, HEIGHT)))
img_merah_on  = ImageTk.PhotoImage(Image.open("ON-M.png").resize((WIDTH, HEIGHT)))

# ======== STATUS AWAL ========
is_hijau_on = False
is_merah_on = False


# ======== BAGIAN LAMPU ATAS ========
# Frame untuk ngatur posisi lampu dan tombol atas
frame_hijau = tk.Frame(root, width=WIDTH, height=HEIGHT + 50, bg="white")
frame_hijau.pack(pady=PADDING_Y)

# Label untuk menampilkan gambar lampu atas
lampu_hijau_label = tk.Label(frame_hijau, image=img_hijau_off, bg="white")
lampu_hijau_label.pack()  # posisi tengah dalam frame

# Fungsi toggle lampu atas
def toggle_hijau():
    global is_hijau_on
    is_hijau_on = not is_hijau_on
    lampu_hijau_label.config(image=img_hijau_on if is_hijau_on else img_hijau_off)
    print("Indikator ON-Hijau:", "ON" if is_hijau_on else "OFF")

# Tombol kontrol lampu atas
btn_hijau = tk.Button(frame_hijau, 
                     text="START", 
                     command=toggle_hijau,
                     font=("Arial", 12, "bold"),
                     bg="#404040", fg="white", 
                     activebackground="green", 
                     relief="raised", padx=10, pady=5)
btn_hijau.pack(pady=5)  # tombol di bawah lampu


# ======== BAGIAN LAMPU BAWAH ========
frame_merah = tk.Frame(root, width=WIDTH, height=HEIGHT + 50, bg="white")
frame_merah.pack(pady=PADDING_Y)

lampu_merah_label = tk.Label(frame_merah, image=img_merah_off, bg="white")
lampu_merah_label.pack()

def toggle_merah():
    global is_merah_on
    is_merah_on = not is_merah_on
    lampu_merah_label.config(image=img_merah_on if is_merah_on else img_merah_off)
    print("Indikator OFF-Merah:", "ON" if is_merah_on else "OFF")

btn_merah = tk.Button(frame_merah, 
                      text="STOP", 
                      command=toggle_merah,
                      font=("Arial", 12, "bold"),
                      bg="#404040", fg="white", 
                      activebackground="red", 
                      relief="raised", padx=10, pady=5)
btn_merah.pack(pady=5)


# ======== POSISI BISA DIUBAH ========
# Kamu bisa ganti .pack() jadi .place(x=?, y=?) kalau mau atur posisi manual
# Contoh:
# frame_atas.place(x=100, y=50)
# frame_bawah.place(x=100, y=400)

root.mainloop()
