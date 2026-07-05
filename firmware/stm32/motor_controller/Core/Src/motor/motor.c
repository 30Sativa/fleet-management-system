#include "motor/motor.h"
#include "motor/motor_core.h"
#include "motor/motor_hal.h"

#define MOTOR_PI 3.14159265358979323846f

extern TIM_HandleTypeDef htim2;

/* Cau hinh chan cho 2 motor. */
static const MotorHalPins motor_pins[MOTOR_CORE_COUNT] =
{
	{
		GPIOA, GPIO_PIN_0,
		PA1___M1_DIR_GPIO_Port, PA1___M1_DIR_Pin,
		MOTOR_LEFT_DIR_INVERT
	},
	{
		GPIOA, GPIO_PIN_2,
		PA3___M2_DIR_GPIO_Port, PA3___M2_DIR_Pin,
		MOTOR_RIGHT_DIR_INVERT
	}
};

/* Toc do banh (mm/s) co dau - chi tang nay biet, core chi biet Hz. */
static float motor_target_mm_s[MOTOR_CORE_COUNT] = {0.0f, 0.0f};

/* motor_id (1/2) -> index core (0/1). Tra ve 0xFF neu sai. */
static uint8_t Motor_IndexOf(uint8_t motor_id)
{
	if (motor_id == MOTOR_LEFT)
	{
		return 0U;
	}
	if (motor_id == MOTOR_RIGHT)
	{
		return 1U;
	}
	return 0xFFU;
}

void Motor_Init(void)
{
	MotorHal_ConfigStepPins(&motor_pins[0], &motor_pins[1]);
	MotorHal_ConfigBaseTimer();
	MotorCore_Init(&motor_pins[0], &motor_pins[1]);

	HAL_NVIC_SetPriority(TIM2_IRQn, 1U, 0U);
	HAL_NVIC_EnableIRQ(TIM2_IRQn);

	Motor_StopAll();

	if (HAL_TIM_Base_Start_IT(&htim2) != HAL_OK)
	{
		Error_Handler();
	}
}

void Motor_SetWheelSpeedMMPS(uint8_t motor_id, float wheel_mm_s)
{
	uint8_t index = Motor_IndexOf(motor_id);
	float abs_speed = (wheel_mm_s < 0.0f) ? -wheel_mm_s : wheel_mm_s;
	float wheel_circumference_mm;
	float wheel_rev_s;
	float motor_rev_s;
	float step_freq_hz;
	int8_t direction;

	if (index == 0xFFU)
	{
		return;
	}

	if (abs_speed <= 0.001f)
	{
		Motor_Stop(motor_id);
		return;
	}

	wheel_circumference_mm = MOTOR_PI * WHEEL_DIAMETER_MM;
	if ((wheel_circumference_mm <= 0.0f) || (GEAR_RATIO <= 0.0f) || (DRIVER_PULSE_PER_REV <= 0.0f))
	{
		Motor_Stop(motor_id);
		return;
	}

	wheel_rev_s = abs_speed / wheel_circumference_mm;
	motor_rev_s = wheel_rev_s * GEAR_RATIO;
	step_freq_hz = motor_rev_s * DRIVER_PULSE_PER_REV;
	direction = (wheel_mm_s >= 0.0f) ? 1 : -1;

	motor_target_mm_s[index] = wheel_mm_s;
	MotorCore_SetStepFrequencyHz(index, step_freq_hz, direction);
}

void Motor_Stop(uint8_t motor_id)
{
	uint8_t index = Motor_IndexOf(motor_id);
	if (index == 0xFFU)
	{
		return;
	}

	motor_target_mm_s[index] = 0.0f;
	MotorCore_Stop(index);
}

void Motor_StopAll(void)
{
	Motor_Stop(MOTOR_LEFT);
	Motor_Stop(MOTOR_RIGHT);
}

void Motor_Update(void)
{
}

int32_t Motor_GetLeftCount(void)
{
	return MotorCore_GetCount(0U);
}

int32_t Motor_GetRightCount(void)
{
	return MotorCore_GetCount(1U);
}

float Motor_GetWheelSpeedMMPS(uint8_t motor_id)
{
	uint8_t index = Motor_IndexOf(motor_id);
	if (index == 0xFFU)
	{
		return 0.0f;
	}
	return motor_target_mm_s[index];
}

uint32_t Motor_GetStepFrequencyHz(uint8_t motor_id)
{
	uint8_t index = Motor_IndexOf(motor_id);
	if (index == 0xFFU)
	{
		return 0U;
	}
	return (uint32_t)(MotorCore_GetStepFrequencyHz(index) + 0.5f);
}

void Motor_HandleTimerInterrupt(void)
{
	MotorCore_HandleTimerInterrupt();
}
