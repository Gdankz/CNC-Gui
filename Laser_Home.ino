int sensor = A0;
int tcrt = A1;
int limitx = 2;
int limity = 3;
int limitz = 6;
int pcb = 7;
int pwmPin = 9;
int start = 5;

int threshold = 1;
int threshold2 = 3;
int dutyON = 42;
int dutyOFF = 0;

bool laser_state = false;
bool tcrt_state = false;
bool limx_state = false;
bool limy_state = false;
bool limz_state = false;
bool pcb_kena_state = false;
bool start_state = false;

String data = "" ;

void setup() {
  Serial.begin(115200);
  delay(2000);
  pinMode(sensor, INPUT);
  pinMode(tcrt, INPUT);
  pinMode(limitx, INPUT_PULLUP);
  pinMode(limity, INPUT_PULLUP);
  pinMode(limitz, INPUT_PULLUP);
  pinMode(pcb, INPUT_PULLUP);
  pinMode(start, INPUT_PULLUP);
  pinMode(pwmPin, OUTPUT);
}

void loop() {

  if(Serial.available()){
    data = Serial.readStringUntil('\n');
    data.trim();
    if (data == "SPINDLE_ON"){
      analogWrite(pwmPin, dutyON);
    }
    if (data == "SPINDLE_OFF"){
      analogWrite(pwmPin, dutyOFF);
    }
  }

  int val = analogRead(sensor);
  int tc = analogRead(tcrt);
  int limx = digitalRead(limitx);
  int limy = digitalRead(limity);
  int limz = digitalRead(limitz);
  int pcb_kena = digitalRead(pcb);
  int start_kena = digitalRead(start);

  // ===== PRIORITAS 1: LIMIT =====
  if (limx == LOW) {
    if (!limx_state) {
      Serial.println("LIMX");
      limx_state = true;
    }
  } else {
    limx_state = false;
  }

  if (limy == LOW) {
    if (!limy_state) {
      Serial.println("LIMY");
      limy_state = true;
    }
  } else {
    limy_state = false;
  }

  if (limz == LOW) {
    if (!limz_state) {
      Serial.println("LIMZ");
      limz_state = true;
    }
  } else {
    limz_state = false;
  }

  // ===== PRIORITAS 2: LASER =====
  if (val >= threshold && val < threshold2) {
    if (!laser_state) {
      Serial.println("LASER");
      laser_state = true;
    }
  } else {
    laser_state = false;
  }

  // ===== PRIORITAS 3: TCRT =====
  if (tc <= 100) {
    if (!tcrt_state) {
      Serial.println("TCON");
      tcrt_state = true;
    }
  } else {
    tcrt_state = false;
  }

  // ===== PRIORITAS 4: MENYENTUH PCB =====
  if (pcb_kena == LOW) {
    if (!pcb_kena_state) {
      Serial.println("PCBON");
      pcb_kena_state = true;
    }
  } else {
    pcb_kena_state = false;
  }

  if (start_kena == LOW) {
    if (!start_state) {
      Serial.println("START");
      start_state = true;
    }
  } else {
    start_state = false;
  }
  delay(20);
}