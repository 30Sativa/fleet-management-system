#ifndef MOTOR_DRIVER_H
#define MOTOR_DRIVER_H

#include "main.h"
#include <stdint.h>

/* Tune these values to match the real drivetrain and HBS57H DIP switches. */
#ifndef WHEEL_DIAMETER_MM
#define WHEEL_DIAMETER_MM      100.0f
#endif

#ifndef GEAR_RATIO
#define GEAR_RATIO             10.0f
#endif

#ifndef DRIVER_PULSE_PER_REV
#define DRIVER_PULSE_PER_REV   1600.0f
#endif

#ifndef MOTOR_MIN_STEP_FREQ_HZ
#define MOTOR_MIN_STEP_FREQ_HZ 1.0f
#endif

#ifndef MOTOR_MAX_STEP_FREQ_HZ
#define MOTOR_MAX_STEP_FREQ_HZ 12000.0f
#endif

#ifndef MOTOR_BASE_TIMER_HZ
#define MOTOR_BASE_TIMER_HZ    50000U
#endif

#ifndef MOTOR_STEP_PULSE_TICKS
#define MOTOR_STEP_PULSE_TICKS 1U
#endif

#ifndef MOTOR_LEFT_DIR_INVERT
#define MOTOR_LEFT_DIR_INVERT  0U
#endif

#ifndef MOTOR_RIGHT_DIR_INVERT
#define MOTOR_RIGHT_DIR_INVERT 1U
#endif

#define MOTOR_LEFT             1U
#define MOTOR_RIGHT            2U

void Motor_Init(void);
void Motor_SetWheelSpeedMMPS(uint8_t motor_id, float wheel_mm_s);
void Motor_Stop(uint8_t motor_id);
void Motor_StopAll(void);
void Motor_Update(void);
void Motor_HandleTimerInterrupt(void);
int32_t Motor_GetLeftCount(void);
int32_t Motor_GetRightCount(void);
float Motor_GetWheelSpeedMMPS(uint8_t motor_id);
uint32_t Motor_GetStepFrequencyHz(uint8_t motor_id);

/* Legacy helpers kept for the earlier manual USB terminal test commands. */
void MotorDriver_Init(void);
void MotorDriver_Start(void);
void MotorDriver_Stop(void);
void MotorDriver_StartMotor(uint8_t motor);
void MotorDriver_StopMotor(uint8_t motor);
void MotorDriver_SetSpeedHz(uint32_t hz);

void MotorDriver_SetDir1(uint8_t dir);
void MotorDriver_SetDir2(uint8_t dir);
uint32_t MotorDriver_GetSpeedHz(void);
uint8_t MotorDriver_GetDir1(void);
uint8_t MotorDriver_GetDir2(void);
uint8_t MotorDriver_IsMotorRunning(uint8_t motor);

#endif
