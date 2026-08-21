#include "sonar/sr04t.h"

#include "main.h"

#include <stddef.h>

#define SR04T_INVALID_SENSOR       0xFFU
#define SR04T_INTER_SENSOR_GAP_MS  60U
#define SR04T_ECHO_TIMEOUT_MS      45U
#define SR04T_MIN_DISTANCE_MM      200U
#define SR04T_MAX_DISTANCE_MM      6000U

typedef struct
{
	uint16_t distance_mm;
	uint8_t valid;
} Sr04tReading;

static volatile Sr04tReading readings[SR04T_SENSOR_COUNT];
static volatile uint8_t active_sensor = SR04T_INVALID_SENSOR;
static volatile uint8_t waiting_for_falling = 0U;
static volatile uint32_t echo_start_cycles = 0U;
static uint8_t next_sensor = 0U;
static uint32_t measurement_start_ms = 0U;
static uint32_t next_trigger_ms = 0U;
static uint32_t cycles_per_us = 1U;

static void SR04T_DelayUs(uint32_t delay_us)
{
	uint32_t start = DWT->CYCCNT;
	uint32_t ticks = delay_us * cycles_per_us;

	while ((uint32_t)(DWT->CYCCNT - start) < ticks)
	{
	}
}

static GPIO_TypeDef *SR04T_TrigPort(uint8_t sensor_index)
{
	(void)sensor_index;
	return GPIOB;
}

static uint16_t SR04T_TrigPin(uint8_t sensor_index)
{
	return (sensor_index == 0U) ? PB0_SONAR1_TRIG_Pin : PB11_SONAR2_TRIG_Pin;
}

static GPIO_TypeDef *SR04T_EchoPort(uint8_t sensor_index)
{
	(void)sensor_index;
	return GPIOB;
}

static uint16_t SR04T_EchoPin(uint8_t sensor_index)
{
	return (sensor_index == 0U) ? PB1_SONAR1_ECHO_Pin : PB12_SONAR2_ECHO_Pin;
}

static void SR04T_FinishMeasurement(uint8_t sensor_index, uint8_t valid,
								uint16_t distance_mm)
{
	if (sensor_index < SR04T_SENSOR_COUNT)
	{
		readings[sensor_index].distance_mm = distance_mm;
		readings[sensor_index].valid = valid;
	}

	active_sensor = SR04T_INVALID_SENSOR;
	waiting_for_falling = 0U;
	next_trigger_ms = HAL_GetTick() + SR04T_INTER_SENSOR_GAP_MS;
}

void SR04T_Init(void)
{
	CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
	DWT->CYCCNT = 0U;
	DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

	cycles_per_us = SystemCoreClock / 1000000U;
	if (cycles_per_us == 0U)
	{
		cycles_per_us = 1U;
	}

	for (uint8_t i = 0U; i < SR04T_SENSOR_COUNT; i++)
	{
		readings[i].distance_mm = 0U;
		readings[i].valid = 0U;
	}

	active_sensor = SR04T_INVALID_SENSOR;
	waiting_for_falling = 0U;
	next_sensor = 0U;
	next_trigger_ms = HAL_GetTick() + 100U;

	HAL_GPIO_WritePin(GPIOB,
					 PB0_SONAR1_TRIG_Pin | PB11_SONAR2_TRIG_Pin,
					 GPIO_PIN_RESET);
}

void SR04T_Update(void)
{
	uint32_t now_ms = HAL_GetTick();
	uint8_t sensor_index;

	if (active_sensor != SR04T_INVALID_SENSOR)
	{
		if ((uint32_t)(now_ms - measurement_start_ms) >= SR04T_ECHO_TIMEOUT_MS)
		{
			__disable_irq();
			SR04T_FinishMeasurement(active_sensor, 0U, 0U);
			__enable_irq();
		}
		return;
	}

	if ((int32_t)(now_ms - next_trigger_ms) < 0)
	{
		return;
	}

	sensor_index = next_sensor;
	next_sensor ^= 1U;
	active_sensor = sensor_index;
	waiting_for_falling = 0U;
	measurement_start_ms = now_ms;

	HAL_GPIO_WritePin(SR04T_TrigPort(sensor_index),
					 SR04T_TrigPin(sensor_index), GPIO_PIN_SET);
	SR04T_DelayUs(12U);
	HAL_GPIO_WritePin(SR04T_TrigPort(sensor_index),
					 SR04T_TrigPin(sensor_index), GPIO_PIN_RESET);
}

void SR04T_OnGpioExti(uint16_t gpio_pin)
{
	uint8_t sensor_index;
	uint32_t now_cycles;
	uint32_t echo_width_us;
	uint32_t distance_mm;

	if (active_sensor == SR04T_INVALID_SENSOR)
	{
		return;
	}

	if (gpio_pin == PB1_SONAR1_ECHO_Pin)
	{
		sensor_index = 0U;
	}
	else if (gpio_pin == PB12_SONAR2_ECHO_Pin)
	{
		sensor_index = 1U;
	}
	else
	{
		return;
	}

	if (sensor_index != active_sensor)
	{
		return;
	}

	now_cycles = DWT->CYCCNT;
	if ((HAL_GPIO_ReadPin(SR04T_EchoPort(sensor_index),
						 SR04T_EchoPin(sensor_index)) == GPIO_PIN_SET) &&
		(waiting_for_falling == 0U))
	{
		echo_start_cycles = now_cycles;
		waiting_for_falling = 1U;
		return;
	}

	if ((HAL_GPIO_ReadPin(SR04T_EchoPort(sensor_index),
						 SR04T_EchoPin(sensor_index)) == GPIO_PIN_RESET) &&
		(waiting_for_falling != 0U))
	{
		echo_width_us = (now_cycles - echo_start_cycles) / cycles_per_us;
		distance_mm = (echo_width_us * 343U) / 2000U;
		if ((distance_mm >= SR04T_MIN_DISTANCE_MM) &&
			(distance_mm <= SR04T_MAX_DISTANCE_MM))
		{
			SR04T_FinishMeasurement(sensor_index, 1U,
								(uint16_t)distance_mm);
		}
		else
		{
			SR04T_FinishMeasurement(sensor_index, 0U, 0U);
		}
	}
}

void SR04T_GetReading(uint8_t sensor_index, uint16_t *distance_mm,
						 uint8_t *valid)
{
	if ((sensor_index >= SR04T_SENSOR_COUNT) ||
		(distance_mm == NULL) || (valid == NULL))
	{
		return;
	}

	__disable_irq();
	*distance_mm = readings[sensor_index].distance_mm;
	*valid = readings[sensor_index].valid;
	__enable_irq();
}

/* HAL calls this weak callback after EXTI1/EXTI15_10_IRQHandler dispatch. */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
	SR04T_OnGpioExti(GPIO_Pin);
}
