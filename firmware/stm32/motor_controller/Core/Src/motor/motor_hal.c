#include "motor/motor_hal.h"

extern TIM_HandleTypeDef htim2;

/* Base timer hz thuc te sau khi config - private, core lay qua getter. */
static uint32_t motor_base_timer_hz = MOTOR_BASE_TIMER_HZ;

static uint32_t MotorHal_GetTimerClockHz(void)
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

void MotorHal_ConfigStepPins(const MotorHalPins *left, const MotorHalPins *right)
{
	GPIO_InitTypeDef GPIO_InitStruct = {0};

	__HAL_RCC_GPIOA_CLK_ENABLE();

	HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0 | GPIO_PIN_2, GPIO_PIN_RESET);

	GPIO_InitStruct.Pin = GPIO_PIN_0 | GPIO_PIN_2;
	GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
	GPIO_InitStruct.Pull = GPIO_NOPULL;
	GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
	HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

	MotorHal_WriteDir(left, 1);
	MotorHal_WriteDir(right, 1);
}

void MotorHal_ConfigBaseTimer(void)
{
	uint32_t timer_clock_hz = MotorHal_GetTimerClockHz();
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

uint32_t MotorHal_GetBaseTimerHz(void)
{
	return motor_base_timer_hz;
}

void MotorHal_WriteDir(const MotorHalPins *pins, int8_t direction)
{
	uint8_t logical_forward = (direction >= 0) ? 1U : 0U;
	uint8_t physical_dir = logical_forward ^ pins->dir_invert;

	HAL_GPIO_WritePin(
		pins->dir_port,
		pins->dir_pin,
		physical_dir ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

void MotorHal_WriteStepHigh(const MotorHalPins *pins)
{
	pins->step_port->BSRR = pins->step_pin;
}

void MotorHal_WriteStepLow(const MotorHalPins *pins)
{
	pins->step_port->BSRR = ((uint32_t)pins->step_pin << 16U);
}
