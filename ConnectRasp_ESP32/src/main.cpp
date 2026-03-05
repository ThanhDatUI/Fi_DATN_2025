#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <HardwareSerial.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

TaskHandle_t CallTaskHandle = NULL;
portMUX_TYPE uartMux = portMUX_INITIALIZER_UNLOCKED;

const char* ssid = "DACN";
const char* password = "12345678";

const char* pi_ip_url = "https://script.google.com/macros/s/AKfycbxazIeUl2Q9zXUBUVG-kuc6q9RA7jbuqJPFwdN6oaU8IDeOWHtLo74hR4Kkd9XpcNDT/exec";
const char* scriptURL = "https://script.google.com/macros/s/AKfycbzyYU-wogDP8d2snAJm4yRgYTDyovdMoSeKtGnVtBiEgNwbn8JAIRiAcpXDDhpD2m2K/exec";

#define RELAY_PIN 15
#define SW420_PIN 25
#define SW520_PIN 26
#define SIM_TX 17
#define SIM_RX 16

LiquidCrystal_I2C lcd(0x27, 16, 2);  // LCD I2C 16x2

HardwareSerial SIM900(1);
WebServer server(80);
bool isCalling = false;
unsigned long activateStart = 0;
bool counting = false;
String pi_ip = "";
String phoneNumber = "0901284053";

void showSIMResponse() {
  portENTER_CRITICAL(&uartMux);
  while (SIM900.available()) {
    char c = SIM900.read();
    Serial.write(c);
  }
  portEXIT_CRITICAL(&uartMux);
}

bool checkNetworkReady() {
  for (int i = 0; i < 5; i++) {
    portENTER_CRITICAL(&uartMux);
    SIM900.println("AT+CREG?");
    portEXIT_CRITICAL(&uartMux);
    delay(500);
    String response = "";

    portENTER_CRITICAL(&uartMux);
    while (SIM900.available()) {
      char c = SIM900.read();
      response += c;
      Serial.write(c);
    }
    portEXIT_CRITICAL(&uartMux);

    if (response.indexOf("+CREG: 0,1") >= 0) {
      Serial.println("✅ Mạng OK (CREG: 0,1)");
      return true;
    } else {
      Serial.println("⚠️ Mạng chưa sẵn sàng, thử lại...");
      delay(2000);
    }
  }
  Serial.println("❌ Mạng không sẵn sàng sau 5 lần thử!");
  return false;
}

void notifyPiCallDone();

void callPhoneNumber() {
  if (isCalling) {
    Serial.println("🚫 Đang trong cuộc gọi, bỏ qua callPhoneNumber!");
    return;
  }

  isCalling = true;
  Serial.println("📞 Bắt đầu gọi SIM900A...");

  server.stop();
  delay(100);

  portENTER_CRITICAL(&uartMux);
  SIM900.println("ATZ");
  portEXIT_CRITICAL(&uartMux);
  delay(500);
  showSIMResponse();

  portENTER_CRITICAL(&uartMux);
  SIM900.println("ATE0");
  portEXIT_CRITICAL(&uartMux);
  delay(500);
  showSIMResponse();

  portENTER_CRITICAL(&uartMux);
  SIM900.println("AT+CSQ");
  portEXIT_CRITICAL(&uartMux);
  delay(500);
  showSIMResponse();

  portENTER_CRITICAL(&uartMux);
  SIM900.println("AT+CPIN?");
  portEXIT_CRITICAL(&uartMux);
  delay(500);
  showSIMResponse();

  portENTER_CRITICAL(&uartMux);
  SIM900.println("AT+CREG?");
  portEXIT_CRITICAL(&uartMux);
  delay(500);
  showSIMResponse();

  portENTER_CRITICAL(&uartMux);
  SIM900.println("AT+COPS?");
  portEXIT_CRITICAL(&uartMux);
  delay(1000);
  showSIMResponse();

  portENTER_CRITICAL(&uartMux);
  SIM900.println("AT+COLP=1");
  portEXIT_CRITICAL(&uartMux);
  delay(500);
  showSIMResponse();

  portENTER_CRITICAL(&uartMux);
  SIM900.println("AT+CSCS=\"GSM\"");
  portEXIT_CRITICAL(&uartMux);
  delay(500);
  showSIMResponse();

  Serial.println("⏳ Chờ mạng ổn định...");

  if (!checkNetworkReady()) {
    Serial.println("❌ Hủy cuộc gọi vì không có mạng!");
    return;
  }

  String cmd = "ATD" + phoneNumber + ";";
  delay(1000);
  portENTER_CRITICAL(&uartMux);
  SIM900.println(cmd);
  portEXIT_CRITICAL(&uartMux);

  Serial.printf("📞 Đang gọi %s ...\n", phoneNumber.c_str());

  for (int i = 0; i < 60; i++) {
    showSIMResponse();
    delay(500);
  }

  portENTER_CRITICAL(&uartMux);
  SIM900.println("ATH");
  portEXIT_CRITICAL(&uartMux);
  Serial.println("📞 Đã cúp máy.");
  delay(1000);
  showSIMResponse();
  notifyPiCallDone();

  isCalling = false;
  server.begin();
  CallTaskHandle = NULL;
  Serial.println("🌐 WebServer đã khởi động lại.");
}

void CallTask(void *parameter) {
  Serial.println("📡 Tắt WiFi để gọi SIM900A...");
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  delay(500);

  callPhoneNumber();

  Serial.println("📡 Bật lại WiFi sau khi gọi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\n✅ WiFi đã kết nối lại.");
  server.begin();

  CallTaskHandle = NULL;
  vTaskDelete(NULL);
}

void sendIPtoGoogleSheet(const String& ip) {
  HTTPClient http;
  String url = String(scriptURL) + "?ip=" + ip;
  http.begin(url);
  http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  int httpCode = http.GET();
  if (httpCode > 0) {
    Serial.printf("HTTP Response code: %d\n", httpCode);
    Serial.println(http.getString());
  } else {
    Serial.printf("Lỗi gửi IP: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

void notifyPiCallDone() {
  if (pi_ip == "") return;
  HTTPClient http;
  String url = "http://" + pi_ip + ":5000/log_call_done";
  http.begin(url);
  int httpCode = http.POST("");
  if (httpCode > 0) {
    Serial.printf("📞 Đã báo log_call_done về Pi (%d)\n", httpCode);
  } else {
    Serial.printf("❌ Lỗi gửi log_call_done: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

void handleRelay() {
  String state = server.arg("state");
  if (state == "on") {
    digitalWrite(RELAY_PIN, HIGH);
    server.send(200, "text/plain", "Relay ON");
  } else if (state == "off") {
    digitalWrite(RELAY_PIN, LOW);
    server.send(200, "text/plain", "Relay OFF");
  } else {
    server.send(400, "text/plain", "Tham số không hợp lệ. Dùng ?state=on hoặc off");
  }
}

void sendAlertToPi() {
  if (pi_ip == "") {
    Serial.println("❌ Không có IP Pi!");
    return;
  }
  HTTPClient http;
  String url = "http://" + pi_ip + ":5000/alert_sw";
  http.begin(url);
  int httpCode = http.POST("");
  if (httpCode > 0) {
    Serial.printf("📡 Gửi cảnh báo về Pi %s, Response: %d\n", pi_ip.c_str(), httpCode);
    Serial.println(http.getString());
  } else {
    Serial.printf("❌ Lỗi gửi cảnh báo: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

void checkSensors() {
  int sw420 = digitalRead(SW420_PIN);
  int sw520 = digitalRead(SW520_PIN);

  if (sw420 == LOW && sw520 == LOW) {
    if (!counting) {
      counting = true;
      activateStart = millis();
      Serial.println("⏳ Cả 2 cảm biến ON → Bắt đầu đếm 3 giây...");
    } else {
      if (millis() - activateStart >= 3000) {
        Serial.println("🚨 Cảm biến SW420 + SW520 > 3s → Gửi cảnh báo về Pi!");
        sendAlertToPi();
        counting = false;
        delay(7000);
      }
    }
  } else {
    counting = false;
  }
}

void getPiIP() {
  HTTPClient http;
  http.begin(pi_ip_url);
  http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  int httpCode = http.GET();
  if (httpCode > 0) {
    String ip = http.getString();
    ip.trim();
    Serial.printf("🌐 Pi IP mới nhất: %s\n", ip.c_str());
    pi_ip = ip;
  } else {
    Serial.printf("❌ Lỗi lấy IP Pi: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

void handleAlertMPU() {
  Serial.println("🚨 Nhận yêu cầu ALERT_MPU từ Pi → tạo Task gọi SIM900A!");
  if (isCalling) {
    Serial.println("🚫 Đang trong cuộc gọi → từ chối ALERT_MPU");
    server.send(200, "text/plain", "BUSY - Đang trong cuộc gọi SIM900A");
    return;
  }

  if (CallTaskHandle == NULL) {
    xTaskCreatePinnedToCore(CallTask, "CallTask", 4096, NULL, 1, &CallTaskHandle, 0);
    server.send(200, "text/plain", "CONFIRM_ACCIDENT");
  } else {
    server.send(200, "text/plain", "BUSY - Đang gọi SIM900A");
  }
}

void handleSetPhone() {
  String newPhone = server.arg("phone");
  if (newPhone.length() > 5) {
    phoneNumber = newPhone;
    Serial.printf("✅ Đã cập nhật số điện thoại mới: %s\n", phoneNumber.c_str());
    server.send(200, "text/plain", "Phone updated");
  } else {
    server.send(400, "text/plain", "Invalid phone number");
  }
}
void handleSendSMS() {
  String msg = server.arg("msg");
  if (msg.length() == 0) {
    server.send(400, "text/plain", "Thiếu tham số msg");
    return;
  }

  if (!checkNetworkReady()) {
    server.send(500, "text/plain", "SIM900A không có mạng!");
    return;
  }

  String cmd = "AT+CMGF=1";  // Text mode
  SIM900.println(cmd);
  delay(500);
  showSIMResponse();

  cmd = "AT+CMGS=\"" + phoneNumber + "\"";
  SIM900.println(cmd);
  delay(500);
  showSIMResponse();

  SIM900.print(msg);
  SIM900.write(26); // Ctrl+Z để gửi
  delay(1000);
  showSIMResponse();

  server.send(200, "text/plain", "SEND SMS");
}

void setup() {
  Serial.begin(9600);
  SIM900.begin(9600, SERIAL_8N1, SIM_RX, SIM_TX);

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  pinMode(SW420_PIN, INPUT_PULLUP);
  pinMode(SW520_PIN, INPUT_PULLUP);

  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("WiFi Connecting...");

  WiFi.begin(ssid, password);
  Serial.print("Đang kết nối WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\n✅ Đã kết nối WiFi");
  String ip = WiFi.localIP().toString();
  Serial.print("🌐 IP nội bộ ESP32: ");
  Serial.println(ip);

  sendIPtoGoogleSheet(ip);
  getPiIP();

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("IP:");
  lcd.print(ip);
  lcd.setCursor(0, 1);
  lcd.print("Ready to Start");
  server.on("/send_sms", handleSendSMS);
  server.on("/relay", handleRelay);
  server.on("/alert_mpu", handleAlertMPU);
  server.on("/set_phone", handleSetPhone);
  server.begin();
  Serial.println("🌐 WebServer đã sẵn sàng (port 80)");
}

unsigned long lastGetPiIP = 0;
const unsigned long getPiInterval = 2 * 60 * 5000;

void loop() {
  server.handleClient();
  checkSensors();

  if (millis() - lastGetPiIP > getPiInterval) {
    getPiIP();
    lastGetPiIP = millis();
  }

  delay(50);
}
