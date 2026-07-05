# STM32G431CBU (UFQFPN48) — Pin Map tổng thể

> Bản nháp đề xuất. **PHẢI xác nhận lại trong STM32CubeMX** trước khi đấu dây,
> vì gói UFQFPN48 giới hạn alternate-function của một số chân (bài học: PB6
> KHÔNG ra được I2C1_SCL trên chip này).

## 1. Đang dùng (đã cố định trong .ioc)

| Chân | Chức năng | Ghi chú |
|------|-----------|---------|
| PA0  | M1_STEP (GPIO out) | Motor trái — STEP |
| PA1  | M1_DIR  (GPIO out) | Motor trái — DIR |
| PA2  | M2_STEP (GPIO out) | Motor phải — STEP |
| PA3  | M2_DIR  (GPIO out) | Motor phải — DIR |
| PA11 | USB_DM | USB CDC (debug) |
| PA12 | USB_DP | USB CDC (debug) |
| PA13 | SWDIO | Debug — KHÔNG đụng |
| PA14 | SWCLK | Debug — KHÔNG đụng |
| PB8  | I2C1_SCL | IMU BNO085 + bus I2C dùng chung |
| PB9  | I2C1_SDA | IMU BNO085 + bus I2C dùng chung |
| PA8  | IMU INT (GPIO in) | BNO085 ngắt (tùy chọn) |

IMU **không dùng RST cứng** — reset bằng lệnh phần mềm qua I2C. Tiết kiệm 1 chân.

## 2. Xung đột cần giải quyết: USB + CAN

FDCAN1 trên G431 chỉ có 2 cặp chân khả dĩ:
- **PA11 / PA12** → TRÙNG USB.
- **PB8 / PB9** → TRÙNG I2C1 (IMU).

Vì muốn giữ **cả USB (debug) lẫn CAN (chạy thật)**, phải dời I2C để
nhường PB8/PB9 cho CAN:

**Phương án đề xuất:**
- USB: giữ PA11/PA12.
- CAN (FDCAN1): **PB8=FDCAN1_RX, PB9=FDCAN1_TX**.
- I2C1 (IMU): dời sang cặp khác — ứng viên cần verify trong CubeMX:
  - `PA15 / PB7`  (I2C1: SCL=PA15? cần kiểm tra) — hoặc
  - `PC4 / PB7`, hoặc dùng **I2C2/I2C3** trên cặp chân còn trống.

> TODO: mở CubeMX, thử gán I2C lên cặp chân còn trống, ghi lại cặp hợp lệ.

## 3. Cần thêm (theo sơ đồ khối hệ thống)

| Ngoại vi | Số chân | Gợi ý |
|----------|---------|-------|
| CAN (FDCAN1) | 2 (TX/RX) | PB8/PB9 (sau khi dời I2C) |
| 4× SR04T siêu âm | 5–8 | Trig chung (1) + 4 Echo (input-capture timer), hoặc riêng |
| 2× RD03 radar | 2–4 | UART (LPUART1 / USART). Mỗi con 1 UART nếu cần song công |
| E-Stop input | 1 | GPIO in, có pull-up, đọc trạng thái NC |
| Contactor coil ctrl | 1 | GPIO out (5V qua mạch đệm) |

## 4. Chân còn trống (UFQFPN48) để phân bổ

Sau khi trừ các chân trên, còn lại (cần verify từng cái trong CubeMX):
PA4, PA5, PA6, PA7, PA9, PA10, PA15, PB0, PB1, PB2, PB3, PB4, PB5, PB6, PB7,
PB10, PB11, PC4, PC6, PC10, PC11, PC13, PC14, PC15, PF0, PF1.

(PA9 vừa được giải phóng do bỏ RST của IMU.)

## 5. Lưu ý quan trọng

- **Echo của SR04T là 5V** — STM32 chỉ chịu 3.3V (đa số chân 5V-tolerant
  nhưng KHÔNG phải tất cả). Cần **chia áp** hoặc dùng chân 5V-tolerant.
- **PB8 kiêm BOOT0** — nếu dùng PB8, để ý mức lúc power-on.
- I2C là bus dùng chung: thêm cảm biến I2C khác KHÔNG tốn thêm chân.
- Mọi gán chân cuối cùng phải khớp giữa CubeMX (.ioc) và phần cứng thật.
