#include "motor/motor_core.h"
#include <stddef.h>

extern TIM_HandleTypeDef htim2;

/* Trang thai mot motor - PRIVATE, khong phoi ra header.
 * Cac field volatile la vung chia se voi ISR. */
typedef struct
{
	MotorHalPins pins;
	volatile uint8_t running;
	volatile uint8_t pulse_ticks_remaining;
	volatile int8_t direction;
	volatile uint32_t phase_accumulator;
	volatile uint32_t phase_increment;
	volatile int32_t count;
	float target_freq_hz;
} MotorCoreState;

static MotorCoreState motors[MOTOR_CORE_COUNT];

static MotorCoreState *MotorCore_Get(uint8_t index)
{
	if (index >= MOTOR_CORE_COUNT)
	{
		return NULL;
	}
	return &motors[index];
}

static float MotorCore_ClampFrequency(float freq_hz)
{
	float max_safe_hz =
		(float)MotorHal_GetBaseTimerHz() / (float)((MOTOR_STEP_PULSE_TICKS + 1U) * 2U);

	if (max_safe_hz > MOTOR_MAX_STEP_FREQ_HZ)
	{
		max_safe_hz = MOTOR_MAX_STEP_FREQ_HZ;
	}

	if (freq_hz < MOTOR_MIN_STEP_FREQ_HZ)
	{
		return MOTOR_MIN_STEP_FREQ_HZ;
	}

	if (freq_hz > max_safe_hz)
	{
		return max_safe_hz;
	}

	return freq_hz;
}

static uint32_t MotorCore_FrequencyToPhaseIncrement(float freq_hz)
{
	double scale = 4294967296.0 / (double)MotorHal_GetBaseTimerHz();
	double increment = (double)freq_hz * scale;

	if (increment <= 0.0)
	{
		return 0U;
	}

	if (increment >= 4294967295.0)
	{
		return 0xFFFFFFFFU;
	}

	return (uint32_t)(increment + 0.5);
}

static void MotorCore_Tick(MotorCoreState *motor)
{
	uint32_t previous_phase;

	if (motor->pulse_ticks_remaining > 0U)
	{
		motor->pulse_ticks_remaining--;
		if (motor->pulse_ticks_remaining == 0U)
		{
			MotorHal_WriteStepLow(&motor->pins);
		}
	}

	if ((motor->running == 0U) || (motor->phase_increment == 0U))
	{
		return;
	}

	previous_phase = motor->phase_accumulator;
	motor->phase_accumulator += motor->phase_increment;

	if (motor->phase_accumulator < previous_phase)
	{
		MotorHal_WriteStepHigh(&motor->pins);
		motor->pulse_ticks_remaining = MOTOR_STEP_PULSE_TICKS;
		motor->count += motor->direction;
	}
}

void MotorCore_Init(const MotorHalPins *left, const MotorHalPins *right)
{
	motors[0].pins = *left;
	motors[1].pins = *right;

	for (uint8_t i = 0U; i < MOTOR_CORE_COUNT; i++)
	{
		motors[i].running = 0U;
		motors[i].pulse_ticks_remaining = 0U;
		motors[i].direction = 1;
		motors[i].phase_accumulator = 0U;
		motors[i].phase_increment = 0U;
		motors[i].count = 0;
		motors[i].target_freq_hz = 0.0f;
	}
}

void MotorCore_SetStepFrequencyHz(uint8_t index, float freq_hz, int8_t direction)
{
	MotorCoreState *motor = MotorCore_Get(index);
	float clamped_hz;
	uint32_t phase_increment;
	uint8_t reset_phase;

	if ((motor == NULL) || (direction == 0) || (freq_hz <= 0.0f))
	{
		MotorCore_Stop(index);
		return;
	}

	clamped_hz = MotorCore_ClampFrequency(freq_hz);
	phase_increment = MotorCore_FrequencyToPhaseIncrement(clamped_hz);

	__disable_irq();
	reset_phase = (uint8_t)((motor->running == 0U) || (motor->direction != direction));
	if (reset_phase != 0U)
	{
		motor->running = 0U;
		motor->pulse_ticks_remaining = 0U;
		motor->phase_accumulator = 0U;
		motor->phase_increment = 0U;
	}
	__enable_irq();

	if (reset_phase != 0U)
	{
		MotorHal_WriteStepLow(&motor->pins);
		MotorHal_WriteDir(&motor->pins, direction);
	}

	__disable_irq();
	motor->direction = direction;
	if (reset_phase != 0U)
	{
		motor->phase_accumulator = 0U;
		motor->pulse_ticks_remaining = 0U;
	}
	motor->phase_increment = phase_increment;
	motor->target_freq_hz = clamped_hz;
	motor->running = (phase_increment != 0U) ? 1U : 0U;
	__enable_irq();

	if (phase_increment == 0U)
	{
		MotorHal_WriteStepLow(&motor->pins);
	}
}

void MotorCore_Stop(uint8_t index)
{
	MotorCoreState *motor = MotorCore_Get(index);
	if (motor == NULL)
	{
		return;
	}

	__disable_irq();
	motor->running = 0U;
	motor->pulse_ticks_remaining = 0U;
	motor->phase_accumulator = 0U;
	motor->phase_increment = 0U;
	motor->target_freq_hz = 0.0f;
	__enable_irq();

	MotorHal_WriteStepLow(&motor->pins);
}

int32_t MotorCore_GetCount(uint8_t index)
{
	MotorCoreState *motor = MotorCore_Get(index);
	int32_t count;

	if (motor == NULL)
	{
		return 0;
	}

	__disable_irq();
	count = motor->count;
	__enable_irq();

	return count;
}

uint8_t MotorCore_IsRunning(uint8_t index)
{
	MotorCoreState *motor = MotorCore_Get(index);
	if (motor == NULL)
	{
		return 0U;
	}
	return motor->running;
}

float MotorCore_GetStepFrequencyHz(uint8_t index)
{
	MotorCoreState *motor = MotorCore_Get(index);
	if (motor == NULL)
	{
		return 0.0f;
	}
	return motor->target_freq_hz;
}

void MotorCore_SetDirIfIdle(uint8_t index, int8_t direction)
{
	MotorCoreState *motor = MotorCore_Get(index);
	if (motor == NULL)
	{
		return;
	}
	MotorHal_WriteDir(&motor->pins, direction);
}

void MotorCore_HandleTimerInterrupt(void)
{
	if (((htim2.Instance->SR & TIM_FLAG_UPDATE) != 0U) &&
		((htim2.Instance->DIER & TIM_IT_UPDATE) != 0U))
	{
		htim2.Instance->SR &= (uint32_t)~TIM_FLAG_UPDATE;
		MotorCore_Tick(&motors[0]);
		MotorCore_Tick(&motors[1]);
	}
}
/* end of file */
