# STM32G431CBU (UFQFPN48) — pin map hiện tại

Tài liệu này mô tả **đúng theo source firmware và `motor_controller.ioc` hiện
tại**. Mọi thay đổi pin phải được cập nhật đồng thời trong CubeMX, code driver
và sơ đồ dây thực tế.

## Các chân đang được firmware sử dụng

| Chân | Chức năng | Căn cứ |
|---|---|---|
| PA0 | M1_STEP | GPIO output trong `main.c` |
| PA1 | M1_DIR | GPIO output trong `main.c` |
| PA2 | M2_STEP | GPIO output trong `main.c` |
| PA3 | M2_DIR | GPIO output trong `main.c` |
| PA4 | IMU RST tùy chọn | Chỉ dùng khi bật `BNO08X_USE_HW_RST=1` |
| PA5 | IMU INT tùy chọn | Chỉ dùng khi bật `BNO08X_USE_INT_PIN=1` |
| PA11 | USB_DM | USB CDC |
| PA12 | USB_DP | USB CDC |
| PA13 | SWDIO | Debug, không dùng cho thiết bị khác |
| PA14 | SWCLK | Debug, không dùng cho thiết bị khác |
| PB6 | IMU SCL | I2C bit-bang trong `bno08x.c` |
| PB7 | IMU SDA | I2C bit-bang trong `bno08x.c` |
| PB0 | SR04T SONAR1 TRIG | J_SONAR1 pin 2, GPIO output |
| PB1 | SR04T SONAR1 ECHO | J_SONAR1 pin 3, EXTI1 input |
| PB11 | SR04T SONAR2 TRIG | J_SONAR2 pin 2, GPIO output |
| PB12 | SR04T SONAR2 ECHO | J_SONAR2 pin 3, EXTI15_10 input |

## ST-LINK / SWD

```text
ST-LINK SWDIO  -> STM32 PA13 (SWDIO)
ST-LINK SWCLK  -> STM32 PA14 (SWCLK)
ST-LINK GND    -> STM32 GND
ST-LINK VTref  -> STM32 3V3 (mức tham chiếu, không phải nguồn 5V)
ST-LINK NRST   -> STM32 NRST (khuyến nghị, có thể bỏ qua nếu board không đưa ra)
```

USB nối vào cổng USB CDC của board chỉ dùng cho giao tiếp firmware/ROS, không
thay thế được dây SWD. ST-LINK phải được USB attach vào đúng hệ điều hành đang
chạy CubeIDE; nếu CubeIDE chạy trên Windows thì không để VMware giữ ST-LINK cho
Ubuntu guest. Kiểm tra bằng `STM32_Programmer_CLI -l` trước khi bấm Run/Debug.

## IMU BNO08x

```text
BNO08x SCL -> PB6
BNO08x SDA -> PB7
BNO08x ADD -> GND       # địa chỉ 7-bit 0x4A
BNO08x CS  -> 3V3       # chọn chế độ I2C
BNO08x RST -> 3V3       # hiện không dùng reset GPIO
BNO08x INT -> bỏ trống  # hiện driver đang polling
```

Driver không dùng `HAL_I2C`, `I2C_HandleTypeDef` hay `MX_I2C1_Init`. Nó tự tạo
START/STOP/ACK bằng GPIO open-drain và đọc `GPIOB->IDR`. Vì vậy đây là I2C
bit-bang, có hỗ trợ chờ clock stretching của BNO08x (timeout 25 ms).

## Các chân chưa được cấu hình trong firmware hiện tại

| Nhóm | Trạng thái |
|---|---|
| PB8/PB9 | Chưa dùng. Không được ghi là I2C1 trong tài liệu hiện tại. Có thể dành cho CAN sau khi cấu hình CubeMX và driver CAN. |
| I2C1/I2C2/I2C3 | Chưa có peripheral nào được khởi tạo trong `main.c`; các giá trị clock I2C còn lại trong `.ioc` không có nghĩa là I2C đang chạy. |
| CAN/FDCAN | Chưa có cấu hình và driver trong firmware hiện tại. |
| PA6, PA7, PA8, PA9, PA10, PA15, PB2–PB5, PB8–PB10, PC4, PC6, PC10–PC15, PF0–PF1 | Đang để dành; phải kiểm tra alternate function trong CubeMX trước khi dùng. |

## Lưu ý phần cứng

- BNO08x dùng bus I2C open-drain; cần pull-up phù hợp lên 3.3V.
- Không nối PB6/PB7 đồng thời vào một peripheral I2C khác nếu chưa kiểm tra địa
  chỉ và tải bus.
- Echo của SR04T có thể là 5V. Sơ đồ hiện tại nối trực tiếp vào PB1/PB12, nên phải xác nhận module đang chạy mức echo 3.3V hoặc thêm chia áp/level shifter trước khi cấp nguồn và flash firmware.
- 74HCT245 phải cấp 5V nếu dùng để nâng mức tín hiệu STEP/DIR; `OE#` phải được
  kéo đúng mức để output hoạt động.
- PB8/PB9 không được tự nhận là CAN chỉ vì tài liệu cũ từng đề xuất như vậy.
