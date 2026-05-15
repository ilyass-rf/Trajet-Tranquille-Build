#include <SoftwareSerial.h>
#include <TinyGPS++.h>

// GPS sur Pins 4 (RX) et 3 (TX non utilisé)
SoftwareSerial ssGPS(4, 3);
// GSM sur Pins 8 (RX) et 9 (TX)
SoftwareSerial ssGSM(8, 9);

TinyGPSPlus gps;

const char APN[]        = "votre_apn";
const char SERVER_URL[] = "http://votre-ip-public:8000/update-location";

bool gprsOk = false;    // ✅ état de la connexion GPRS

void setup() {
  Serial.begin(115200);
  ssGPS.begin(9600);
  ssGSM.begin(9600);
  delay(3000);
  gprsOk = setupGPRS();
}

void loop() {
  // ✅ SoftwareSerial ne peut écouter qu'un port à la fois → activer GPS ici
  ssGPS.listen();

  unsigned long start = millis();
  while (millis() - start < 2000) {      // lire le GPS pendant 2 secondes max
    while (ssGPS.available() > 0) {
      gps.encode(ssGPS.read());
    }
  }

  if (gps.location.isValid() && gps.location.isUpdated()) {
    double lat   = gps.location.lat();
    double lon   = gps.location.lng();
    double speed = gps.speed.kmph();     // ✅ vitesse réelle transmise au serveur

    // ✅ Vérification basique : éviter d'envoyer 0,0 (fix GPS invalide)
    if (lat == 0.0 && lon == 0.0) {
      Serial.println("[GPS] Fix invalide (0,0), skip.");
    } else {
      if (!gprsOk) {
        Serial.println("[GPRS] Reconnexion...");
        gprsOk = setupGPRS();
      }
      if (gprsOk) {
        sendDataToServer(lat, lon, speed);
      }
    }
  } else {
    Serial.println("[GPS] En attente du fix...");
  }

  delay(500);  // envoyer toutes les 10 secondes
}

// ✅ Retourne true si la connexion GPRS est établie
bool setupGPRS() {
  bool ok = true;
  ok &= sendAT("AT+SAPBR=3,1,\"Contype\",\"GPRS\"");
  ok &= sendAT("AT+SAPBR=3,1,\"APN\",\"" + String(APN) + "\"");
  ok &= sendAT("AT+SAPBR=1,1");   // Activer le contexte GPRS
  if (ok) Serial.println("[GPRS] Connecté.");
  else    Serial.println("[GPRS] Échec connexion.");
  return ok;
}

void sendDataToServer(double lat, double lon, double speed) {
  // ✅ speed_kmh inclus dans le payload pour un ETA plus précis côté serveur
  String payload = "{\"bus_id\":\"BUS_01\","
                   "\"latitude\":"  + String(lat,   6) + ","
                   "\"longitude\":" + String(lon,   6) + ","
                   "\"speed_kmh\":" + String(speed, 1) + "}";

  // ✅ Activer le port GSM avant d'envoyer
  ssGSM.listen();

  if (!sendAT("AT+HTTPINIT"))                               return;
  if (!sendAT("AT+HTTPPARA=\"CID\",1"))                    { sendAT("AT+HTTPTERM"); return; }
  if (!sendAT("AT+HTTPPARA=\"URL\",\"" + String(SERVER_URL) + "\"")) { sendAT("AT+HTTPTERM"); return; }
  if (!sendAT("AT+HTTPPARA=\"CONTENT\",\"application/json\""))       { sendAT("AT+HTTPTERM"); return; }

  ssGSM.print("AT+HTTPDATA=");
  ssGSM.print(payload.length());
  ssGSM.println(",10000");
  delay(500);
  ssGSM.println(payload);
  delay(500);

  sendAT("AT+HTTPACTION=1");  // POST
  delay(2000);
  sendAT("AT+HTTPTERM");
  Serial.println("[HTTP] Données envoyées : " + payload);
}

// ✅ Retourne true si la réponse contient "OK"
bool sendAT(String command) {
  ssGSM.println(command);
  delay(500);
  String response = "";
  while (ssGSM.available()) {
    char c = ssGSM.read();
    response += c;
    Serial.write(c);
  }
  return response.indexOf("OK") >= 0;
}