/**
 ******************************************************************************
 * @file    bno08x.h
 * @brief   Driver BNO080/085/086 (GY-BNO080X) qua I2C bit-bang PB6/PB7.
 *
 * Wiring (board GY-BNO080X) -> STM32G431:
 *   VCC -> 3V3        GND -> GND
 *   SCL -> PB6        SDA -> PB7     (2 chan MCU duy nhat)
 *   ADD -> GND (0x4A) CS  -> 3V3     (BAT BUOC cao = che do I2C)
 *   PS1 -> GND        PS0 -> GND
 *   RST -> 3V3        INT -> bo trong
 *   BOOT-> VCC (keo cao, qua 10k neu co)
 *
 * Ghi chu: dung bit-bang de chiu duoc clock stretching cua BNO08x va tranh
 * dung cac chan dac biet nhu PF0-OSC_IN. Neu can RST/INT rieng, bat macro
 * BNO08X_USE_HW_RST/BNO08X_USE_INT_PIN trong bno08x.c.
 ******************************************************************************
 */
#ifndef IMU_BNO08X_H
#define IMU_BNO08X_H

#include <stdint.h>

typedef struct
{
    float yaw;     /* quay quanh Z (heading) */
    float pitch;   /* quay quanh Y */
    float roll;    /* quay quanh X */
} BNO08x_Euler;

void BNO08x_Init(void);
uint8_t BNO08x_SelfTest(uint8_t *sw_major, uint8_t *sw_minor);
uint8_t BNO08x_EnableRotationVector(uint16_t interval_ms);
uint8_t BNO08x_ReadRotationVector(float *qi, float *qj, float *qk, float *qr,
                                  BNO08x_Euler *euler);
float BNO08x_GetLastYaw(uint8_t *valid);

/* Chan doan bit-bang. 0=ACK, 1=NOACK. */
uint8_t BNO08x_Diag(uint32_t *err_code);

#endif /* IMU_BNO08X_H */
