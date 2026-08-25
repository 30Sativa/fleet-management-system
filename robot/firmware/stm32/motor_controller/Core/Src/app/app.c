#include "app/app.h"
#include "motor/motor.h"
#include "usb_protocol.h"
#include "imu/bno08x.h"
#include "sonar/sr04t.h"

/* = 1: chay self-test BNO08x luc boot + chan doan I2C, in ra USB CDC. */
#ifndef BNO08X_SELFTEST_ON_BOOT
#define BNO08X_SELFTEST_ON_BOOT 1
#endif

/* = 1: in dong "IMU yaw/pitch/roll" ra USB CDC de debug. */
#ifndef BNO08X_DEBUG_PRINT_EULER
#define BNO08X_DEBUG_PRINT_EULER 0
#endif

#ifndef BNO08X_BOOT_DIAG_DELAY_MS
#define BNO08X_BOOT_DIAG_DELAY_MS 5000U
#endif

#if BNO08X_SELFTEST_ON_BOOT || BNO08X_DEBUG_PRINT_EULER
#include "usbd_cdc_if.h"
#include <string.h>
#include <stdio.h>

static void app_cdc_log(const char *s)
{
	uint16_t len = (uint16_t)strlen(s);
	for (uint32_t t = 0U; t < 50U; t++)
	{
		if (CDC_Transmit_FS((uint8_t *)s, len) == USBD_OK) return;
		HAL_Delay(2);
	}
}
#endif

void App_Init(void)
{
	Motor_Init();
	Protocol_Init();

	BNO08x_Init();

#if BNO08X_SELFTEST_ON_BOOT
	{
		HAL_Delay(BNO08X_BOOT_DIAG_DELAY_MS);   /* cho USB CDC enumerate/reconnect */
		app_cdc_log("[boot] BNO08x diagnostics start\r\n");

		/* In chan doan bit-bang PB6/PB7 NHIEU LAN de chac chan bat duoc
		 * tren Tera Term du mo tre. */
		for (uint8_t k = 0; k < 5U; k++)
		{
			uint32_t err = 0;
			uint8_t d = BNO08x_Diag(&err);
			char line[96];
			const char *txt = (d == 0) ? "ACK-OK" : "NOACK";
			snprintf(line, sizeof(line),
			         "[diag %u] BNO08x PB6/PB7=%s, err=0x%lX\r\n",
			         k, txt, (unsigned long)err);
			app_cdc_log(line);
			HAL_Delay(300);
		}

		uint8_t maj = 0, min = 0;
		if (BNO08x_SelfTest(&maj, &min))
		{
			char line[64];
			snprintf(line, sizeof(line),
			         "BNO08x self-test: OK (SW %u.%u)\r\n", maj, min);
			app_cdc_log(line);
		}
		else
		{
			app_cdc_log("BNO08x self-test: FAIL\r\n");
		}
	}
#endif

	BNO08x_EnableRotationVector(20);
}

void App_Loop(void)
{
	Motor_Update();
	SR04T_Update();
	Protocol_Update();

	{
		BNO08x_Euler e;
		if (BNO08x_ReadRotationVector(NULL, NULL, NULL, NULL, &e))
		{
#if BNO08X_DEBUG_PRINT_EULER
			static uint32_t last_ms = 0U;
			uint32_t now = HAL_GetTick();
			if (now - last_ms >= 100U)
			{
				char line[80];
				int y = (int)e.yaw, p = (int)e.pitch, r = (int)e.roll;
				snprintf(line, sizeof(line),
				         "IMU yaw=%d pitch=%d roll=%d\r\n", y, p, r);
				app_cdc_log(line);
				last_ms = now;
			}
#else
			(void)e;
#endif
		}
	}
}

void App_OnUsbRx(uint8_t *data, uint32_t length)
{
	for (uint32_t i = 0U; i < length; i++)
	{
		Protocol_ProcessRxByte(data[i]);
	}
}
