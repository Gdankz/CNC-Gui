#include <SoftwareSerial.h>

SoftwareSerial linkSerial(10, 11); //10 nyambung ke 1(arduino 2), 11 nyambung ke 0(arduino 2)

int start = 5;
int stop = 6;
String data = "";
String data_py = "";

bool start_state = false;//FLAG atau STATE untuk TOMBOL START
bool stop_state = false; //FLAG atau STATE untuk TOMBOL STOP

void setup() {
  Serial.begin(115200);     // ke Python
  linkSerial.begin(9600); // dari Arduino 2
  pinMode(start, INPUT_PULLUP);
  pinMode(stop, INPUT_PULLUP);

}

void loop() {
//MENERIMA DATA DARI ARDUINO 2 SERTA MENGIRIMKAN SEMUA DATA KE PC
  while (linkSerial.available()) {
    char c = linkSerial.read();

    if (c == '\n') {
      data.trim();

      // kirim ke Python
      if (data.startsWith("#")) {
      Serial.println(data);   // kirim ke Python
      linkSerial.println("ACK"); // kirim ACK
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
  while (Serial.available()){
    char c = Serial.read();
    if (c == '\n'){
      data_py.trim();

      //validasi data yang dikirimkan python
      if(data_py.startsWith("#") && data_py.endsWith(";")){
        linkSerial.println(data_py); //kirim ke arduino 2

        unsigned long t = millis();
        while (millis() - t < 100){
          if(linkSerial.available()){
            String resp = linkSerial.readStringUntil('\n');
            resp.trim();
          if (resp == "ACK"){
            Serial.println("#ACK;");//kirim ke python
            break;
            }

          }
        }
      }
      data_py = "";
    }
    else{
      data_py += c;
      if(data_py.length() > 30 )data_py = "";
    }
  }

//PROGRAM KHUSUS ARDUINO 3   
  int start_kena = digitalRead(start);
  int stop_kena = digitalRead(stop);
  //TOMBOL START
  if (start_kena == LOW) {
    if (!start_state) {
      Serial.println("#START;");
      start_state = true;
    }
  } else {
    start_state = false;
  }
  delay(20);

  //TOMBOL STOP
  if (stop_kena == LOW) {
    if (!stop_state) {
      Serial.println("#STOP;");
      stop_state = true;
    }
  } else {
    stop_state = false;
  }
  delay(20);
}