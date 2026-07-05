#ifndef MOTOR_H
#define MOTOR_H

#include "main.h"
#include <stdint.h>

/* Tang public API + kinematics.
 * Day la giao dien duy nhat ma app.c / usb_protocol.c nen dung.
 * Chuyen doi mm/s <-> Hz dua tren drivetrain, roi uy quyen xuong motor_core.
 *
 * Tune cac gia tri sau cho khop drivetrain va DIP switch HBS57H:
 *   - Wheel: 190 mm.
 *   - Motor 57EBP98ALC, 1.8 deg/step (200 step/rev).
 *   - Driver HBS57H SW1-4 = on/off/on/on -> 1600 pulse/rev.
 *   - Gearbox F57-L1-10-P2, 10:1.
 *   => 1600 * 10 = 16000 pulse / vong banh.
 */
#ifndef WHEEL_DIAMETER_MM
#define WHEEL_DIAMETER_MM      190.0f
#endif

#ifndef GEAR_RATIO
#define GEAR_RATIO             10.0f
#endif

#ifndef DRIVER_PULSE_PER_REV
#define DRIVER_PULSE_PER_REV   1600.0f
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

#endif
