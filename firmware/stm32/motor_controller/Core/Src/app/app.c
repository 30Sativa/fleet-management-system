#include "app/app.h"
#include "motor/motor_driver.h"
#include "usb_protocol.h"

void App_Init(void)
{
	Motor_Init();
	Protocol_Init();
}

void App_Loop(void)
{
	Motor_Update();
	Protocol_Update();
}

void App_OnUsbRx(uint8_t *data, uint32_t length)
{
	for (uint32_t i = 0U; i < length; i++)
	{
		Protocol_ProcessRxByte(data[i]);
	}
}
