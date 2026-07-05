// INA219
#include <Wire.h>
#include <Adafruit_INA219.h>
Adafruit_INA219 ina219;

// LCD I2C 20x4
#include <LiquidCrystal_I2C.h>
LiquidCrystal_I2C lcd(0x27, 20, 4);

//PZEM 004T
#include <PZEM004Tv30.h>
#include <SoftwareSerial.h>

#if !defined(PZEM_RX_PIN) && !defined(PZEM_TX_PIN)
#define PZEM_RX_PIN 12  //nyambung ke pin TX pada pzem
#define PZEM_TX_PIN 13  //nyambung pin RX pada pzem
#endif

SoftwareSerial pzemSWSerial(PZEM_RX_PIN, PZEM_TX_PIN);
PZEM004Tv30 pzem(pzemSWSerial);

//LIMIT SWITCH
int limitx = 5;     //Pin Limit Switch X untuk kalibrasi
int limity = 7;     //Pin Limit Switch Y untuk kalibrasi
int limitz = 8;     //Pin Limit Switch Z untuk kalibrasi (Z naik)
int pcb = 10;       //Pin menyentuh PCB untuk kalibrasi (Z turun)
int ls_casing = 4;  //Pin Limit Switch Casing Akrilik

int buzzerEMG = 11;  //Pin Buzzer Tower Lamp
int vaccum = 6;      //Pin Relay Vaccum

unsigned long waktuLCD = 0;
unsigned long waktuTunda = 0;
// int sensor = 7;

//SPINDLE
int pwmPin = 9;  //PWM Spindle
int sel1 = 2;    //Selektor Rendah
int sel2 = 3;    //Selektor Tinggi
int dutyON = 0;
int dutyOFF = 0;

// FLAG
bool limx_state = false;
bool limy_state = false;
bool limz_state = false;
bool pcb_kena_state = false;
bool statusBuzzer = false;
bool lsc_state = false;

// STRING KOMUNIKASI DATA
String data = "";
String last_mode = "";

// INA219
void tcaSelect(uint8_t channel) {
  if (channel > 7) return;

  Wire.beginTransmission(0x70);
  Wire.write(1 << channel);
  Wire.endTransmission();
}

void setup() {
  Wire.begin();
  tcaSelect(2);
  if (ina219.begin()) {
    Serial.println("INA219 CH2 OK");
  }

  tcaSelect(3);
  if (ina219.begin()) {
    Serial.println("INA219 CH3 OK");
  }

  tcaSelect(4);
  if (ina219.begin()) {
    Serial.println("INA219 CH4 OK");
  }

  lcd.init();
  lcd.backlight();
  Serial.begin(9600);        //debug
  pzemSWSerial.begin(9600);  //PZEM Software Serial begin di 9600
  while (!Serial) {
    delay(1);
  }
  delay(2000);
  pinMode(limitx, INPUT_PULLUP);
  pinMode(limity, INPUT_PULLUP);
  pinMode(limitz, INPUT_PULLUP);
  pinMode(pcb, INPUT_PULLUP);
  pinMode(ls_casing, INPUT);
  pinMode(buzzerEMG, OUTPUT);
  pinMode(vaccum, OUTPUT);
  //SPINDLE
  pinMode(sel1, INPUT_PULLUP);
  pinMode(sel2, INPUT_PULLUP);
  pinMode(pwmPin, OUTPUT);
}

//Moving Average Arus Z
float bacaArusZ() {
  float totalZ = 0;
  tcaSelect(4);

  for (int i = 0; i < 20; i++) {
    totalZ += ina219.getCurrent_mA();
    delay(1);
  }

  return totalZ / 20.0;
}

// Moving Average Arus X
float bacaArusX() {
  float totalX = 0;
  tcaSelect(2);

  for (int i = 0; i < 20; i++) {
    totalX += ina219.getCurrent_mA();
    delay(1);
  }

  return totalX / 20.0;
}

// Moving Average Arus Y
float bacaArusY() {
  float totalY = 0;
  tcaSelect(3);

  for (int i = 0; i < 20; i++) {
    totalY += ina219.getCurrent_mA();
    delay(1);
  }

  return totalY / 20.0;
}

void loop() {
  // PROGRAM INA219 DAN PZEM-004T
  float Daya = pzem.power();
  float ArusZ = bacaArusZ();
  float ArusX = bacaArusX();
  float ArusY = bacaArusY();

  if (millis() - waktuLCD >= 300) {
    waktuLCD = millis();
    lcd.setCursor(0, 0);  //(kolom, baris)
    lcd.print("P: ");
    lcd.print(Daya);
    lcd.setCursor(7, 0);
    lcd.print("W");
    lcd.setCursor(8, 0);
    lcd.print("|");

    lcd.setCursor(0, 1);
    lcd.print("X:    mA");
    lcd.setCursor(3, 1);
    lcd.print(ArusX, 0);
    lcd.setCursor(8, 1);
    lcd.print("|");

    lcd.setCursor(0, 2);
    lcd.print("Y:    mA");
    lcd.setCursor(3, 2);
    lcd.print(ArusY, 0);

    lcd.setCursor(0, 3);
    lcd.print("Z:    mA");
    lcd.setCursor(3, 3);
    lcd.print(ArusZ, 0);
  }

  int Arus_Max = 1000;  //Arus Maksimal = 1000mA
  if (ArusX >= Arus_Max) {
    if (millis() - waktuTunda >= 500) {
      waktuTunda = millis();
      statusBuzzer = !statusBuzzer;
      if (statusBuzzer) {
        digitalWrite(buzzerEMG, LOW);  //BUZZER NYALA
      } else {
        digitalWrite(buzzerEMG, HIGH);  //BUZZER MATI
      }
    }
  }
  if (ArusY >= Arus_Max) {
    if (millis() - waktuTunda >= 500) {
      waktuTunda = millis();
      statusBuzzer = !statusBuzzer;
      if (statusBuzzer) {
        digitalWrite(buzzerEMG, LOW);  //BUZZER NYALA
      } else {
        digitalWrite(buzzerEMG, HIGH);  //BUZZER MATI
      }
    }
  }
  if (ArusZ >= Arus_Max) {
    if (millis() - waktuTunda >= 500) {
      waktuTunda = millis();
      statusBuzzer = !statusBuzzer;
      if (statusBuzzer) {
        digitalWrite(buzzerEMG, LOW);  //BUZZER NYALA
      } else {
        digitalWrite(buzzerEMG, HIGH);  //BUZZER MATI
      }
    }
  }

  else {
    digitalWrite(buzzerEMG, HIGH);
    statusBuzzer = false;
    waktuTunda = millis();
  }

  // PROGRAM SELEKTOR KECEPATAN DAN PUTARAN SPINDLE
  String current_mode = "";
  int sel_low = digitalRead(sel1);   // put your main code here, to run repeatedly:
  int sel_high = digitalRead(sel2);  // put your main code here, to run repeatedly:
  if (sel_low == LOW) {              //selektor memilih rendah
    dutyON = 64;                     //60 4000rpm target 1000
    current_mode = "#F_LOW;";
    lcd.setCursor(9, 0);
    lcd.print("F  : LOW   ");
    lcd.setCursor(9, 1);
    lcd.print("RPM: 3400 ");
  } else if (sel_high == LOW) {  //selektor memilih tinggi
    dutyON = 255;                //255 udah oke
    current_mode = "#F_HIGH;";
    lcd.setCursor(9, 0);
    lcd.print("F  : HIGH  ");
    lcd.setCursor(9, 1);
    lcd.print("RPM: 10080");
  } else {  //selektor memilih sedang
    dutyON = 128;
    current_mode = "#F_MED;";
    lcd.setCursor(9, 0);
    lcd.print("F  : MEDIUM");
    lcd.setCursor(9, 1);
    lcd.print("RPM: 6700 ");
  }
  if (current_mode != last_mode) {
    sendData(current_mode);
    last_mode = current_mode;
  }  // analogWrite(pwmPin, duty);

  // PROGRAM MENERIMA DATA DARI PC/PYTHON
  if (Serial.available()) {
    data = Serial.readStringUntil('\n');
    data.trim();
    if (data == "#SPINDLE_ON;") { //MENERIMA DATA DARI PC/PYTHON
      analogWrite(pwmPin, dutyON);
      Serial.println("ACK");
      digitalWrite(vaccum, HIGH);
    }
    if (data == "#SPINDLE_OFF;") { //MENERIMA DATA DARI PC/PYTHON
      analogWrite(pwmPin, dutyOFF);
      Serial.println("ACK");
      digitalWrite(vaccum, LOW);
    }
  }

  // PROGRAM KALIBRASI
  int limx = digitalRead(limitx);
  int limy = digitalRead(limity);
  int limz = digitalRead(limitz);
  int pcb_kena = digitalRead(pcb);
  int casing_kena = digitalRead(ls_casing);
  if (limx == LOW) {
    if (!limx_state) {
      sendData("#LIMX;");
      limx_state = true;
    }
  } else {
    limx_state = false;
  }

  if (limy == LOW) {
    if (!limy_state) {
      sendData("#LIMY;");
      limy_state = true;
    }
  } else {
    limy_state = false;
  }

  if (limz == LOW) {
    if (!limz_state) {
      sendData("#LIMZ;");
      limz_state = true;
    }
  } else {
    limz_state = false;
  }


  if (pcb_kena == 1) {
    if (!pcb_kena_state) {
      sendData("#PCBON;");
      pcb_kena_state = true;
    }
  } else {
    pcb_kena_state = false;
  }
  delay(20);

  if (casing_kena == 0) {
    if (!lsc_state) {
      sendData("#LSC_ON;");
      lsc_state = true;
    }
  } else {
    if (lsc_state) {

      sendData("#LSC_OFF;");
      lsc_state = false;
    }
  }
}

// KIRIM DATA KE ARDUINO 3
bool sendData(String msg) {
  int retry = 3;

  while (retry--) {
    Serial.println(msg);

    unsigned long startTime = millis();
    while (millis() - startTime < 100) {
      if (Serial.available()) {
        String resp = Serial.readStringUntil('\n');
        resp.trim();
        if (resp == "ACK") {
          return true;
        }
      }
    }
  }
  return false;
}