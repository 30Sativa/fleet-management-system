#ifndef USB_PROTOCOL_H
#define USB_PROTOCOL_H

#include <stdint.h>

#ifndef CMD_TIMEOUT_MS
#define CMD_TIMEOUT_MS       300U
#endif

#ifndef FEEDBACK_PERIOD_MS
#define FEEDBACK_PERIOD_MS   20U
#endif

void Protocol_Init(void);
void Protocol_Update(void);
void Protocol_ProcessRxByte(uint8_t b);
void Protocol_ProcessLine(char *line);
void Protocol_SendFeedback(void);
uint32_t Protocol_GetLastSeq(void);

#endif
