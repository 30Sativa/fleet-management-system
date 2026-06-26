/**
 ******************************************************************************
 * @file    bno08x.h
 * @brief   Driver BNO080/085/086 (GY-BNO080X) qua I2C bit-bang.
 *
 * Vi sao bit-bang: BNO08x dung CLOCK STRETCHING phi tieu chuan tren I2C lam
 * I2C peripheral phan cung cua STM32 that bai. Bit-bang (lac GPIO bang phan
 * mem) cho duoc clock stretching -> giao tiep on dinh.
 *
 * Wiring (board GY-BNO080X) -> STM32G431:
 *   VCC -> 3V3        GND -> GND
 *   SCL -> PB6        SDA -> PB7
 *   ADD -> GND (0x4A) CS  -> VCC (BAT BUOC cao = che do I2C)
 *   RST -> PA9        INT -> PA8
 *   PS1 -> GND        PS0 -> GND
 *   BOOT-> VCC (keo cao, qua 10k neu co)
 ******************************************************************************
 */
#ifndef IMU_BNO08X_H
#define IMU_BNO08X_H

#include <stdint.h>

/* Goc Euler (do) tinh tu quaternion. */
typedef struct
{
    float yaw;     /* quay quanh truc Z (heading) */
    float pitch;   /* quay quanh truc Y */
    float roll;    /* quay quanh truc X */
} BNO08x_Euler;

/* Khoi tao GPIO/bus cho BNO08x. Goi 1 lan luc boot. */
void BNO08x_Init(void);

/* Self-test: kiem tra chip ACK + doc Product ID.
 * Tra ve 1 = chip song & giao tiep OK, 0 = that bai.
 * sw_major/sw_minor (co the NULL) nhan version firmware. */
uint8_t BNO08x_SelfTest(uint8_t *sw_major, uint8_t *sw_minor);

/* Bat Rotation Vector report voi chu ky `interval_ms` (vd 20 = ~50Hz).
 * Goi 1 lan sau Init. Tra ve 1 OK. */
uint8_t BNO08x_EnableRotationVector(uint16_t interval_ms);

/* Doc 1 goi quaternion moi nhat (neu co). Tra ve 1 neu cap nhat duoc.
 * qi,qj,qk,qr (co the NULL) nhan quaternion dang float.
 * euler (co the NULL) nhan goc yaw/pitch/roll (do). */
uint8_t BNO08x_ReadRotationVector(float *qi, float *qj, float *qk, float *qr,
                                  BNO08x_Euler *euler);

/* Tra ve yaw (do) moi nhat da doc duoc (cache, khong giao tiep I2C).
 * valid (co the NULL) = 1 neu da tung doc duoc it nhat 1 lan. */
float BNO08x_GetLastYaw(uint8_t *valid);

#endif /* IMU_BNO08X_H */
