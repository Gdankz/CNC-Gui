//Hardware Serial (pin 0 dan 1) digunakan untuk komunikasi ke PC melalui COM USB
//Software Serial digunakan untuk komunikasi data ke Arduino 2
#include <SoftwareSerial.h>
SoftwareSerial linkSerial(10, 11);  //10 nyambung ke 1(arduino 2), 11 nyambung ke 0(arduino 2)

int ind_start = 4; //Pin Indikator Start
int ind_stop = 13; //Pin Indikator Stop
int start = 2;  //Pin Tombol Start
int stop = 3;   //Pin Tombol Stop
int ls_bracket = 12; //Pin Deteksi Bracket
int BUZZER = 5;  //Pin Buzzer Pasif

String data = "";
String data_py = "";

bool start_state = false;  //FLAG atau STATE untuk TOMBOL START
bool stop_state = false;   //FLAG atau STATE untuk TOMBOL STOP
bool lsb_state = false;
bool buzzer_state = false;  //FLAG untuk BUZZER PASIF
bool z_turun = false;       //flag mendeteksi keadaan Z
bool kal_ok = false;        //flag mendeteksi kalibrasi selesai atau belum

#define CLK_X  6 //Pin CLK Rotary Sumbu X
#define DT_X  7 //Pin DT Rotary Sumbu X

#define CLK_Y  8 //Pin CLK Rotary Sumbu Y
#define DT_Y  9 //Pin DT Rotary Sumbu Y
int lastCLK_X;
int lastCLK_Y;

long posX = 0;
long posY = 0;
long lastPosX = 0;
long lastPosY = 0;


void setup() {
  Serial.begin(115200);    // Baudrate komunikasi PC
  linkSerial.begin(9600);  // Baudrate komunikasi antara Arduino 2 dan 3
  pinMode(start, INPUT_PULLUP);
  pinMode(stop, INPUT_PULLUP);
  pinMode(ls_bracket, INPUT_PULLUP);
  pinMode(ind_start, OUTPUT);
  pinMode(ind_stop, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(CLK_X, INPUT_PULLUP);
  pinMode(DT_X, INPUT_PULLUP);
  pinMode(CLK_Y, INPUT_PULLUP);
  pinMode(DT_Y, INPUT_PULLUP);
  lastCLK_X = digitalRead(CLK_X);
  lastCLK_Y = digitalRead(CLK_Y);


  //Setelah program di upload, lampu indikator stop menyala tanda mesin mati
  digitalWrite(ind_stop, HIGH);
  Serial.println("#IND_STOP_ON;");
}

// PROGRAM MENGATUR NADA BUZZER
void Play_Buzz() {
  tone(BUZZER, 2000);
  delay(150);
  tone(BUZZER, 1000);
  delay(150);
  tone(BUZZER, 2500);
  delay(150);
  noTone(BUZZER);
  delay(150);
}

// PROGRAM ROTARY SUMBU X
void Rotary_X() {
  int currentCLK = digitalRead(CLK_X);

  if (currentCLK != lastCLK_X) {

    if (digitalRead(DT_X) != currentCLK)
      posX++;
    else
      posX--;
  }

  lastCLK_X = currentCLK;
}

// PROGRAM ROTARY SUMBU Y
void Rotary_Y() {
  int currentCLK = digitalRead(CLK_Y);

  if (currentCLK != lastCLK_Y) {

    if (digitalRead(DT_Y) != currentCLK)
      posY++;
    else
      posY--;
  }

  lastCLK_Y = currentCLK;
}

void loop() {
  //MENERIMA DATA DARI ARDUINO 2 SERTA MENGIRIMKAN SEMUA DATA KE PC
  while (linkSerial.available()) {
    char c = linkSerial.read();

    if (c == '\n') {
      data.trim();

      // kirim ke Python
      if (data.startsWith("#")) {
        Serial.println(data);       // kirim ke Python
        linkSerial.println("ACK");  // kirim ACK
      }

      data = "";
    } else {
      data += c;
      if (data.length() > 30) {
        data = "";
      }
    }
  }

  //MENERIMA DATA DARI PC DAN MENGIRIMKAN KE ARDUINO 2
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      data_py.trim();

      //validasi data yang dikirimkan python
      if (data_py.startsWith("#") && data_py.endsWith(";")) {
        //PERINTAH DARI MEMBUNYIKAN BUZZER
        if (data_py == "#MILLING_SELESAI;") {
          buzzer_state = true;
        }

        //PERINTAH DARI PC UNTUK MENGIRIMKAN NILAI ROTARY ENCODER
        if (data_py == "#Z_TURUN;") {
          z_turun = true;
          Serial.println("#ZTURUN_OK;");
          posX = 0;
          posY = 0;

          lastPosX = 0;
          lastPosY = 0;
        }

        if (data_py == "#Z_NAIK;") {
          z_turun = false;
          Serial.println("#ZNAIK_OK;");
        }


        linkSerial.println(data_py);  //MENGIRIM DATA YANG DIBUTUHKAN KE ARDUINO 2
        unsigned long t = millis();
        while (millis() - t < 100) {
          if (linkSerial.available()) {
            String resp = linkSerial.readStringUntil('\n');
            resp.trim();
            if (resp == "ACK") {
              Serial.println("#ACK;");  //MENGIRIM KE PC SEBAGAI TANDA BAHWA DATA SUDAH DITERIMA ARDUINO
              break;
            }
          }
        }
      }
      data_py = "";
    } else {
      data_py += c;
      if (data_py.length() > 30) data_py = "";
    }
  }

  //PROGRAM KHUSUS ARDUINO 3
  int start_kena = digitalRead(start);
  int stop_kena = digitalRead(stop);
  int bracket_kena = digitalRead(ls_bracket);
  //TOMBOL START
  if (start_kena == LOW) {
    if (!start_state) {
      Serial.println("#START_ON;");
      start_state = true;
      digitalWrite(ind_start, HIGH);
      digitalWrite(ind_stop, LOW);
      Serial.println("#IND_START_ON;");
    }
  } else {
    start_state = false;
  }
  delay(20);

  //TOMBOL STOP
  if (stop_kena == LOW) {
    if (!stop_state) {
      Serial.println("#STOP_ON;");
      stop_state = true;
      buzzer_state = false;
      noTone(BUZZER);
      digitalWrite(ind_start, LOW);
      digitalWrite(ind_stop, HIGH);
      Serial.println("#IND_STOP_ON;");
    }
  } else {
    stop_state = false;
  }
  delay(20);

  // LIMIT SWITCH BRACKET
  if (bracket_kena == 0) {
    if (!lsb_state) {
      Serial.println("#LSBON;");
      lsb_state = true;
    }
  } else {
    Serial.println("#LSBOFF;");
    lsb_state = false;
  }
  delay(20);

  if (buzzer_state) {
    Play_Buzz();
  }

  //ROTARY ENCODER KY-040
  Rotary_X();
  Rotary_Y();
  if (z_turun) {

    if (posX != lastPosX || posY != lastPosY) {

      Serial.print("#POS,");
      Serial.print(posX);
      Serial.print(",");
      Serial.print(posY);
      Serial.println(";");

      lastPosX = posX;
      lastPosY = posY;
    }
  }
}