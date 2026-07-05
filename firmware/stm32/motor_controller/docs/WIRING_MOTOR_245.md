# Sơ đồ nối dây: STM32G431 → 74HCT245 → HBS57H

74HCT245 dùng làm **bộ đệm dòng / dịch mức 3.3V → 5V** (không đảo tín hiệu)
giữa STM32 (logic 3.3V) và driver bước HBS57H (logic 5V).

Driver HBS57H đấu kiểu **common-cathode** (PUL−/DIR− chung GND; tín hiệu đẩy
chân + lên mức cao). **Không dùng ENA** (để trống → driver luôn enable).

## Chân STM32 (đã cố định trong firmware)

| Chân STM32 | Nhãn | Chức năng |
|-----------|------|-----------|
| PA0 | M1_STEP | Motor TRÁI — xung bước (STEP/PUL) |
| PA1 | M1_DIR  | Motor TRÁI — chiều (DIR) |
| PA2 | M2_STEP | Motor PHẢI — xung bước |
| PA3 | M2_DIR  | Motor PHẢI — chiều |

## 74HCT245 #1 — Motor TRÁI

```
STM32              74HCT245 #1                 HBS57H Left
──────────────────────────────────────────────────────────
                   VCC (pin 20) ← 5V
                   GND (pin 10) → GND chung
                   DIR (pin 1)  ← 5V    (hướng truyền A → B)
                   OE# (pin 19) → GND   (bật output buffer)

PA0 (M1_STEP) ───→ A1 (pin 2)  ══►  B1 (pin 18) ───→ PUL+
PA1 (M1_DIR)  ───→ A2 (pin 3)  ══►  B2 (pin 17) ───→ DIR+
```

## 74HCT245 #2 — Motor PHẢI

```
STM32              74HCT245 #2                 HBS57H Right
──────────────────────────────────────────────────────────
                   VCC (pin 20) ← 5V
                   GND (pin 10) → GND chung
                   DIR (pin 1)  ← 5V
                   OE# (pin 19) → GND

PA2 (M2_STEP) ───→ A1 (pin 2)  ══►  B1 (pin 18) ───→ PUL+
PA3 (M2_DIR)  ───→ A2 (pin 3)  ══►  B2 (pin 17) ───→ DIR+
```

## Phía HBS57H (cả 2 driver) — common-cathode

```
PUL−  → GND chung
DIR−  → GND chung
ENA+  → để trống   (không dùng enable)
ENA−  → để trống
```

## Chân điều khiển của mỗi 74HCT245 (BẮT BUỘC)

| Chân 245 | Pin | Nối | Lý do |
|----------|-----|-----|-------|
| VCC | 20 | 5V | Cấp nguồn để output ra mức 5V |
| GND | 10 | GND chung | Mass |
| DIR | 1  | 5V (HIGH) | Hướng truyền A→B (STM32 phát ra driver) |
| OE# | 19 | GND (LOW) | Bật buffer; nếu HIGH thì high-Z, motor đứng im |

6 kênh thừa (A3–A8 / B3–B8) **để trống**. Có thể nối A3–A8 xuống GND để
tránh nhiễu đầu vào hở (không bắt buộc).

## LƯU Ý QUAN TRỌNG

1. **GND phải chung tất cả**: STM32 ⟷ 74HCT245 ⟷ HBS57H ⟷ nguồn 5V.
   Đây là lỗi phổ biến nhất khiến tín hiệu không tới driver.
2. **74HCT245 phải cấp 5V** (không phải 3.3V) — vì mục đích là nâng mức lên 5V.
   Đầu vào A nhận 3.3V từ STM32 (HCT nhận mức ~2V trở lên là HIGH).
3. **DIR (pin 1) của 245 ≠ DIR của motor.** Pin 1 là hướng truyền của chip
   đệm, phải = 5V. DIR motor đi qua kênh A2/B2.
4. **OE# = GND** mới có tín hiệu ra. Đây là chân hay quên.
5. HBS57H cần nguồn động lực riêng (vd 48V) cấp vào chân V+/GND động lực
   của nó — KHÁC với 5V logic. Xem datasheet HBS57H.

## Tham chiếu chân STM32 đang dùng (toàn hệ thống)

| Chân | Dùng cho |
|------|----------|
| PA0–PA3 | Motor STEP/DIR (qua 74HCT245) |
| PA11/PA12 | USB CDC |
| PA13/PA14 | SWD debug |
| PB6/PB7 | IMU BNO085 (I2C bit-bang) |
| (PC4/PF0) | Trống — dành cho CAN/cảm biến sau này |

Xem thêm `docs/PIN_MAP.md` cho pin-map tổng thể.
