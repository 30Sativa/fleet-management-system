#ifndef APP_H
#define APP_H

#include <stdint.h>

void App_Init(void);
void App_Loop(void);
void App_OnUsbRx(uint8_t *data, uint32_t length);

#endif
