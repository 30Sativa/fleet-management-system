/*
 * I2C Scanner cho module GY-BNO080X (BNO080/085)
 * --------------------------------------------------
 * Dung de KIEM TRA xem chip co song & ACK tren bus I2C khong.
 * Neu thay 0x4A hoac 0x4B => chip song. Neu khong thay => nghi chip chet
 * hoac sai day.
 *
 * !! CANH BAO QUAN TRONG: BNO080 chi chiu 3.3V.
 *    - Cap VIN = 3.3V (KHONG dung 5V).
 *    - Voi Arduino Uno/Nano (logic 5V) chan A4/A5 la 5V -> CO THE LAM CHET CHIP.
 *      Nen dung level shifter, hoac dung board 3.3V (vd: Arduino Pro Mini 3.3V,
 *      STM32, ESP32, ESP8266, Pi Pico...).
 *
 * Wiring (board GY-BNO080X):
 *   VIN/VCC -> 3.3V
 *   GND     -> GND
 *   SCL     -> SCL (Uno/Nano: A5)
 *   SDA     -> SDA (Uno/Nano: A4)
 *   CS      -> 3.3V   (BAT BUOC: keo cao de vao che do I2C)
 *   PS0     -> GND
 *   PS1     -> GND
 *   ADD     -> GND (=>0x4A)  hoac 3.3V (=>0x4B)  hoac de trong (mac dinh 0x4B)
 *   BOOT    -> 3.3V (qua dien tro 10k neu co; test thi noi thang cung duoc)
 *   RST     -> 3.3V (hoac de trong; co the noi GPIO de reset)
 *   INT     -> de trong cung duoc
 */
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  while (!Serial) { /* doi cong serial (Leonardo/ESP32) */ }
  delay(500);

  Wire.begin();
  Wire.setClock(100000);   // 100kHz cho an toan

  Serial.println();
  Serial.println(F("===== I2C SCANNER (BNO080X) ====="));
}

void loop() {
  byte count = 0;
  Serial.println(F("Quet bus I2C..."));

  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    byte err = Wire.endTransmission();
    if (err == 0) {
      Serial.print(F("  -> Thay thiet bi tai 0x"));
      if (addr < 16) Serial.print('0');
      Serial.print(addr, HEX);
      if (addr == 0x4A || addr == 0x4B)
        Serial.print(F("  <== DAY LA BNO080! Chip SONG."));
      Serial.println();
      count++;
    }
  }

  if (count == 0)
    Serial.println(F("  !! Khong thay thiet bi nao. Kiem tra day/nguon, hoac chip chet."));
  else
    Serial.print(F("Xong. Tong cong ")), Serial.print(count), Serial.println(F(" thiet bi."));

  Serial.println();
  delay(3000);
}
