#include "motor/motor_driver.h"

#define MOTOR_PI 3.14159265358979323846f

extern TIM_HandleTypeDef htim2;

typedef struct
{
	GPIO_TypeDef *step_port;
	uint16_t step_pin;
	GPIO_TypeDef *dir_port;
	uint16_t dir_pin;
	uint8_t dir_invert;
	volatile uint8_t running;
	volatile uint8_t pulse_ticks_remaining;
	volatile int8_t direction;
	volatile uint32_t phase_accumulator;
	volatile uint32_t phase_increment;
	volatile int32_t count;
	float target_mm_s;
	float target_freq_hz;
} MotorState;

static MotorState motors[2] =
{
	{
		GPIOA,
		GPIO_PIN_0,
		PA1___M1_DIR_GPIO_Port,
		PA1___M1_DIR_Pin,
		MOTOR_LEFT_DIR_INVERT,
		0U,
		0U,
		1,
		0U,
		0U,
		0,
		0.0f,
		0.0f
	},
	{
		GPIOA,
		GPIO_PIN_2,
		PA3___M2_DIR_GPIO_Port,
		PA3___M2_DIR_Pin,
		MOTOR_RIGHT_DIR_INVERT,
		0U,
		0U,
		1,
		0U,
		0U,
		0,
		0.0f,
		0.0f
	}
};

static uint32_t motor_base_timer_hz = MOTOR_BASE_TIMER_HZ;
static uint32_t legacy_speed_hz = 1000U;
static uint8_t legacy_dir1 = 1U;
static uint8_t legacy_dir2 = 1U;

static MotorState *Motor_GetState(uint8_t motor_id);
static uint32_t Motor_GetTimerClockHz(void);
static void Motor_ConfigStepPins(void);
static void Motor_ConfigBaseTimer(void);
static float Motor_ClampFrequency(float freq_hz);
static uint32_t Motor_FrequencyToPhaseIncrement(float freq_hz);
static void Motor_SetStepFrequencyHz(uint8_t motor_id, float freq_hz, int8_t direction, float wheel_mm_s);
static void Motor_StopState(MotorState *motor);
static void Motor_WriteDir(MotorState *motor, int8_t direction);
static void Motor_WriteStepHigh(MotorState *motor);
static void Motor_WriteStepLow(MotorState *motor);
static void Motor_TickState(MotorState *motor);

void Motor_Init(void)
{
	Motor_ConfigStepPins();
	Motor_ConfigBaseTimer();

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
	float abs_speed = (wheel_mm_s < 0.0f) ? -wheel_mm_s : wheel_mm_s;
	float wheel_circumference_mm;
	float wheel_rev_s;
	float motor_rev_s;
	float step_freq_hz;
	int8_t direction;

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

	Motor_SetStepFrequencyHz(motor_id, step_freq_hz, direction, wheel_mm_s);
}

void Motor_Stop(uint8_t motor_id)
{
	MotorState *motor = Motor_GetState(motor_id);
	if (motor == NULL)
	{
		return;
	}

	Motor_StopState(motor);
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
	int32_t count;

	__disable_irq();
	count = motors[0].count;
	__enable_irq();

	return count;
}

int32_t Motor_GetRightCount(void)
{
	int32_t count;

	__disable_irq();
	count = motors[1].count;
	__enable_irq();

	return count;
}

float Motor_GetWheelSpeedMMPS(uint8_t motor_id)
{
	MotorState *motor = Motor_GetState(motor_id);
	if (motor == NULL)
	{
		return 0.0f;
	}

	return motor->target_mm_s;
}

uint32_t Motor_GetStepFrequencyHz(uint8_t motor_id)
{
	MotorState *motor = Motor_GetState(motor_id);
	if (motor == NULL)
	{
		return 0U;
	}

	return (uint32_t)(motor->target_freq_hz + 0.5f);
}

void MotorDriver_Init(void)
{
	Motor_Init();
}

void MotorDriver_Start(void)
{
	MotorDriver_StartMotor(1U);
	MotorDriver_StartMotor(2U);
}

void MotorDriver_Stop(void)
{
	Motor_StopAll();
}

void MotorDriver_StartMotor(uint8_t motor)
{
	int8_t direction = 1;

	if (motor == 1U)
	{
		direction = (legacy_dir1 != 0U) ? 1 : -1;
	}
	else if (motor == 2U)
	{
		direction = (legacy_dir2 != 0U) ? 1 : -1;
	}

	Motor_SetStepFrequencyHz(motor, (float)legacy_speed_hz, direction, 0.0f);
}

void MotorDriver_StopMotor(uint8_t motor)
{
	Motor_Stop(motor);
}

void MotorDriver_SetSpeedHz(uint32_t hz)
{
	if (hz < (uint32_t)MOTOR_MIN_STEP_FREQ_HZ)
	{
		hz = (uint32_t)MOTOR_MIN_STEP_FREQ_HZ;
	}
	else if (hz > (uint32_t)MOTOR_MAX_STEP_FREQ_HZ)
	{
		hz = (uint32_t)MOTOR_MAX_STEP_FREQ_HZ;
	}

	legacy_speed_hz = hz;

	if (MotorDriver_IsMotorRunning(1U) != 0U)
	{
		MotorDriver_StartMotor(1U);
	}

	if (MotorDriver_IsMotorRunning(2U) != 0U)
	{
		MotorDriver_StartMotor(2U);
	}
}

void MotorDriver_SetDir1(uint8_t dir)
{
	legacy_dir1 = dir ? 1U : 0U;

	if (MotorDriver_IsMotorRunning(1U) != 0U)
	{
		MotorDriver_StartMotor(1U);
	}
	else
	{
		Motor_WriteDir(&motors[0], (legacy_dir1 != 0U) ? 1 : -1);
	}
}

void MotorDriver_SetDir2(uint8_t dir)
{
	legacy_dir2 = dir ? 1U : 0U;

	if (MotorDriver_IsMotorRunning(2U) != 0U)
	{
		MotorDriver_StartMotor(2U);
	}
	else
	{
		Motor_WriteDir(&motors[1], (legacy_dir2 != 0U) ? 1 : -1);
	}
}

uint32_t MotorDriver_GetSpeedHz(void)
{
	return legacy_speed_hz;
}

uint8_t MotorDriver_GetDir1(void)
{
	return legacy_dir1;
}

uint8_t MotorDriver_GetDir2(void)
{
	return legacy_dir2;
}

uint8_t MotorDriver_IsMotorRunning(uint8_t motor)
{
	MotorState *state = Motor_GetState(motor);
	if (state == NULL)
	{
		return 0U;
	}

	return state->running;
}

void Motor_HandleTimerInterrupt(void)
{
	if (((htim2.Instance->SR & TIM_FLAG_UPDATE) != 0U) &&
		((htim2.Instance->DIER & TIM_IT_UPDATE) != 0U))
	{
		htim2.Instance->SR &= (uint32_t)~TIM_FLAG_UPDATE;
		Motor_TickState(&motors[0]);
		Motor_TickState(&motors[1]);
	}
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
	if (htim->Instance != TIM2)
	{
		return;
	}

	Motor_TickState(&motors[0]);
	Motor_TickState(&motors[1]);
}

static MotorState *Motor_GetState(uint8_t motor_id)
{
	if (motor_id == MOTOR_LEFT)
	{
		return &motors[0];
	}

	if (motor_id == MOTOR_RIGHT)
	{
		return &motors[1];
	}

	return NULL;
}

static uint32_t Motor_GetTimerClockHz(void)
{
	RCC_ClkInitTypeDef clock_config;
	uint32_t flash_latency;
	uint32_t timer_clock_hz = HAL_RCC_GetPCLK1Freq();

	HAL_RCC_GetClockConfig(&clock_config, &flash_latency);
	if (clock_config.APB1CLKDivider != RCC_HCLK_DIV1)
	{
		timer_clock_hz *= 2U;
	}

	return timer_clock_hz;
}

static void Motor_ConfigStepPins(void)
{
	GPIO_InitTypeDef GPIO_InitStruct = {0};

	__HAL_RCC_GPIOA_CLK_ENABLE();

	HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0 | GPIO_PIN_2, GPIO_PIN_RESET);

	GPIO_InitStruct.Pin = GPIO_PIN_0 | GPIO_PIN_2;
	GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
	GPIO_InitStruct.Pull = GPIO_NOPULL;
	GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
	HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

	Motor_WriteDir(&motors[0], 1);
	Motor_WriteDir(&motors[1], 1);
}

static void Motor_ConfigBaseTimer(void)
{
	uint32_t timer_clock_hz = Motor_GetTimerClockHz();
	uint32_t prescaler_div = timer_clock_hz / 1000000U;
	uint32_t counter_hz;
	uint32_t period_ticks;

	if (prescaler_div == 0U)
	{
		prescaler_div = 1U;
	}
	else if (prescaler_div > 65536U)
	{
		prescaler_div = 65536U;
	}

	counter_hz = timer_clock_hz / prescaler_div;
	period_ticks = counter_hz / MOTOR_BASE_TIMER_HZ;
	if (period_ticks == 0U)
	{
		period_ticks = 1U;
	}

	motor_base_timer_hz = counter_hz / period_ticks;

	(void)HAL_TIM_Base_Stop_IT(&htim2);

	__HAL_TIM_DISABLE(&htim2);
	htim2.Instance->DIER = 0U;
	htim2.Instance->CCER = 0U;
	__HAL_TIM_SET_PRESCALER(&htim2, prescaler_div - 1U);
	__HAL_TIM_SET_AUTORELOAD(&htim2, period_ticks - 1U);
	__HAL_TIM_SET_COUNTER(&htim2, 0U);
	if (HAL_TIM_GenerateEvent(&htim2, TIM_EVENTSOURCE_UPDATE) != HAL_OK)
	{
		Error_Handler();
	}
	__HAL_TIM_CLEAR_FLAG(&htim2, TIM_FLAG_UPDATE | TIM_FLAG_CC1 | TIM_FLAG_CC3);

	htim2.Init.Prescaler = prescaler_div - 1U;
	htim2.Init.Period = period_ticks - 1U;
}

static float Motor_ClampFrequency(float freq_hz)
{
	float max_safe_hz = (float)motor_base_timer_hz / (float)((MOTOR_STEP_PULSE_TICKS + 1U) * 2U);

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

static uint32_t Motor_FrequencyToPhaseIncrement(float freq_hz)
{
	double scale = 4294967296.0 / (double)motor_base_timer_hz;
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

static void Motor_SetStepFrequencyHz(uint8_t motor_id, float freq_hz, int8_t direction, float wheel_mm_s)
{
	MotorState *motor = Motor_GetState(motor_id);
	float clamped_hz;
	uint32_t phase_increment;
	uint8_t reset_phase;

	if ((motor == NULL) || (direction == 0) || (freq_hz <= 0.0f))
	{
		Motor_Stop(motor_id);
		return;
	}

	clamped_hz = Motor_ClampFrequency(freq_hz);
	phase_increment = Motor_FrequencyToPhaseIncrement(clamped_hz);

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
		Motor_WriteStepLow(motor);
		Motor_WriteDir(motor, direction);
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
	motor->target_mm_s = wheel_mm_s;
	motor->running = (phase_increment != 0U) ? 1U : 0U;
	__enable_irq();

	if (phase_increment == 0U)
	{
		Motor_WriteStepLow(motor);
	}
}

static void Motor_StopState(MotorState *motor)
{
	__disable_irq();
	motor->running = 0U;
	motor->pulse_ticks_remaining = 0U;
	motor->phase_accumulator = 0U;
	motor->phase_increment = 0U;
	motor->target_mm_s = 0.0f;
	motor->target_freq_hz = 0.0f;
	__enable_irq();

	Motor_WriteStepLow(motor);
}

static void Motor_WriteDir(MotorState *motor, int8_t direction)
{
	uint8_t logical_forward = (direction >= 0) ? 1U : 0U;
	uint8_t physical_dir = logical_forward ^ motor->dir_invert;

	HAL_GPIO_WritePin(
		motor->dir_port,
		motor->dir_pin,
		physical_dir ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

static void Motor_WriteStepHigh(MotorState *motor)
{
	motor->step_port->BSRR = motor->step_pin;
}

static void Motor_WriteStepLow(MotorState *motor)
{
	motor->step_port->BSRR = ((uint32_t)motor->step_pin << 16U);
}

static void Motor_TickState(MotorState *motor)
{
	uint32_t previous_phase;

	if (motor->pulse_ticks_remaining > 0U)
	{
		motor->pulse_ticks_remaining--;
		if (motor->pulse_ticks_remaining == 0U)
		{
			Motor_WriteStepLow(motor);
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
		Motor_WriteStepHigh(motor);
		motor->pulse_ticks_remaining = MOTOR_STEP_PULSE_TICKS;
		motor->count += motor->direction;
	}
}
