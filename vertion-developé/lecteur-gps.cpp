#include <SoftwareSerial.h>
#include <TinyGPS++.h>

static const int RXPin = 4, TXPin = 3;
static const uint32_t GPSBaud = 9600;

TinyGPSPlus gps;
SoftwareSerial ss(RXPin, TXPin);

void setup() {
    Serial.begin(115200); 
    ss.begin(GPSBaud);    
    Serial.println("--- Démarrage de Trajet Tranquille (Hardware Test) ---");
}

void loop() {
    while (ss.available() > 0) {
      if (gps.encode(ss.read())) {
        displayInfo();
      }
    }
  if (millis() > 5000 && gps.charsProcessed() < 10) {
      Serial.println("Erreur : Aucun signal GPS détecté. Vérifiez le câblage.");
      while(true);
    }
}

void displayInfo() {
    if (gps.location.isValid()) {
      Serial.print("Latitude: ");
      Serial.print(gps.location.lat(), 6);
      Serial.print(" | Longitude: ");
      Serial.println(gps.location.lng(), 6);
      Serial.print("Vitesse (km/h): ");
      Serial.println(gps.speed.kmph());
    } else {
      Serial.println("En attente de fixation satellite (Sortez près d'une fenêtre)...");
    }
}