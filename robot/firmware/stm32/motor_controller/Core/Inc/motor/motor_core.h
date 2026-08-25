#ifndef MOTOR_CORE_H
#define MOTOR_CORE_H

#include "motor/motor_hal.h"
#include <stdint.h>

/* Lop loi sinh xung (step pulse generator).
 * Quan ly phase accumulator + tick trong ngat. MotorState la PRIVATE trong
 * motor_core.c; tang tren chi cam motor_index (0/1) va goi qua API duoi day.
 *
 * Gioi han tan so step (Hz). */
#ifndef MOTOR_MIN_STEP_FREQ_HZ
#define MOTOR_MIN_STEP_FREQ_HZ 1.0f
#endif

#ifndef MOTOR_MAX_STEP_FREQ_HZ
#define MOTOR_MAX_STEP_FREQ_HZ 12000.0f
#endif

#define MOTOR_CORE_COUNT 2U

/* Khoi tao loi: dang ky chan cho 2 motor (copy vao state private). */
void MotorCore_Init(const MotorHalPins *left, const MotorHalPins *right);

/* Dat tan so step (Hz) + chieu cho 1 motor. freq_hz<=0 hoac dir==0 -> stop. */
void MotorCore_SetStepFrequencyHz(uint8_t index, float freq_hz, int8_t direction);

void MotorCore_Stop(uint8_t index);

/* Truy van trang thai (an toan ngat). */
int32_t  MotorCore_GetCount(uint8_t index);
uint8_t  MotorCore_IsRunning(uint8_t index);
float    MotorCore_GetStepFrequencyHz(uint8_t index);
void     MotorCore_SetDirIfIdle(uint8_t index, int8_t direction);

/* Goi tu TIM2_IRQHandler. Tick tat ca motor. */
void MotorCore_HandleTimerInterrupt(void);

#endif
