#define CLK    2
#define DT     3
#define SW     4

#define CLK2   5
#define DT2    6
#define SW2    7

int counter = 0; 
int currentCLK; 
int previousCLK; 

int currentSW;
int previousSW = HIGH;

int counter2 = 0; 
int currentCLK2; 
int previousCLK2; 

int currentSW2;
int previousSW2 = HIGH;

void setup()
{  
  pinMode(CLK,INPUT); 
  pinMode(DT,INPUT);
  pinMode(SW,INPUT_PULLUP);

  pinMode(CLK2,INPUT); 
  pinMode(DT2,INPUT);
  pinMode(SW2,INPUT_PULLUP);

  Serial.begin(115200);

  previousCLK = digitalRead(CLK);
  previousCLK2 = digitalRead(CLK2);
} 

void loop()
{  
  // RESET X
  currentSW = digitalRead(SW);
  if(previousSW == HIGH && currentSW == LOW)
  {
    counter = 0;
  }
  previousSW = currentSW;

  // ENCODER X
  currentCLK = digitalRead(CLK);
  if(currentCLK != previousCLK)
  {       
    if(digitalRead(DT) != currentCLK)
      counter++;
    else
      counter--;
      
    sendData();
  }
  previousCLK = currentCLK; 

  // RESET Y
  currentSW2 = digitalRead(SW2);
  if(previousSW2 == HIGH && currentSW2 == LOW)
  {
    counter2 = 0;
  }
  previousSW2 = currentSW2;

  // ENCODER Y
  currentCLK2 = digitalRead(CLK2);
  if(currentCLK2 != previousCLK2)
  {       
    if(digitalRead(DT2) != currentCLK2)
      counter2++;
    else
      counter2--;
      
    sendData();
  }
  previousCLK2 = currentCLK2; 
}

// ======================
// KIRIM DATA KE PYTHON
// ======================
void sendData()
{
  Serial.print(counter);
  Serial.print(",");
  Serial.println(counter2);
}