#include "app/app.h"
#include "motor/motor_driver.h"
#include "usb_protocol.h"
#include "imu/bno08x.h"

/* = 1: chay self-test BNO08x luc boot, in ket qua ra USB CDC. */
#ifndef BNO08X_SELFTEST_ON_BOOT
#define BNO08X_SELFTEST_ON_BOOT 1
#endif

/* = 1: in them dong "IMU yaw/pitch/roll" ra USB CDC de debug.
 * (Du lieu yaw VAN luon duoc doc & cache cho odometry du co bat cai nay hay
 *  khong; cai nay chi them dong log debug.) */
#ifndef BNO08X_DEBUG_PRINT_EULER
#define BNO08X_DEBUG_PRINT_EULER 0
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
		uint8_t maj = 0, min = 0;
		HAL_Delay(2000);   /* cho USB CDC enumerate */
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

	/* Bat Rotation Vector ~50Hz de co yaw lien tuc cho odometry. */
	BNO08x_EnableRotationVector(20);
}

void App_Loop(void)
{
	Motor_Update();
	Protocol_Update();

	/* Doc IMU thuong xuyen de cap nhat cache yaw (dung trong goi FB).
	 * ReadRotationVector tu luu yaw moi nhat vao cache ben trong driver. */
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
