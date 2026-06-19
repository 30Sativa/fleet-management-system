#include "usb_protocol.h"

#include "main.h"
#include "motor/motor_driver.h"
#include "usbd_cdc_if.h"

#include <ctype.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PROTOCOL_RX_LINE_SIZE 96U
#define PROTOCOL_RX_QUEUE_COUNT 8U
#define PROTOCOL_TX_BUFFER_SIZE 128U
#define PROTOCOL_TX_BUFFER_COUNT 2U

typedef enum
{
	PROTOCOL_STATUS_OK = 0,
	PROTOCOL_STATUS_STOP,
	PROTOCOL_STATUS_TIMEOUT,
	PROTOCOL_STATUS_ERR
} ProtocolStatus;

static char rx_active_line[PROTOCOL_RX_LINE_SIZE];
static char rx_line_queue[PROTOCOL_RX_QUEUE_COUNT][PROTOCOL_RX_LINE_SIZE];
static volatile uint32_t rx_active_line_len = 0U;
static volatile uint8_t rx_queue_head = 0U;
static volatile uint8_t rx_queue_tail = 0U;
static volatile uint8_t rx_queue_count = 0U;
static volatile uint8_t rx_overflow = 0U;
static volatile uint8_t rx_bad_line_ready = 0U;

static char tx_buffers[PROTOCOL_TX_BUFFER_COUNT][PROTOCOL_TX_BUFFER_SIZE];
static uint8_t tx_write_index = 0U;

static uint32_t last_seq = 0U;
static uint32_t last_valid_rx_ms = 0U;
static uint32_t last_feedback_sent_ms = 0U;
static uint32_t last_feedback_attempt_ms = 0U;
static uint32_t last_error_attempt_ms = 0U;
static ProtocolStatus protocol_status = PROTOCOL_STATUS_STOP;
static uint8_t pending_bad_command = 0U;

static void Protocol_CheckRxLine(void);
static void Protocol_CheckTimeout(uint32_t now_ms);
static void Protocol_CheckFeedback(uint32_t now_ms);
static void Protocol_ReportBadCommand(void);
static uint8_t Protocol_TrySendPendingError(void);
static uint8_t Protocol_TrySendFeedback(uint32_t now_ms);
static uint8_t Protocol_TrySendRaw(const char *text);
static uint8_t Protocol_TrySendFormatted(const char *format, ...);
static uint8_t Protocol_TokenizeCsv(char *line, char *tokens[], uint8_t max_tokens, uint8_t *token_count);
static char *Protocol_Trim(char *text);
static uint8_t Protocol_EqualsIgnoreCase(const char *left, const char *right);
static uint8_t Protocol_ParseU32(const char *text, uint32_t *value);
static uint8_t Protocol_ParseFloat(const char *text, float *value);
static const char *Protocol_StatusText(void);

void Protocol_Init(void)
{
	uint32_t now = HAL_GetTick();

	__disable_irq();
	rx_active_line_len = 0U;
	rx_queue_head = 0U;
	rx_queue_tail = 0U;
	rx_queue_count = 0U;
	rx_overflow = 0U;
	rx_bad_line_ready = 0U;
	__enable_irq();

	last_seq = 0U;
	last_valid_rx_ms = now;
	last_feedback_sent_ms = now;
	last_feedback_attempt_ms = now;
	last_error_attempt_ms = now - FEEDBACK_PERIOD_MS;
	protocol_status = PROTOCOL_STATUS_STOP;
	pending_bad_command = 0U;
}

void Protocol_Update(void)
{
	uint32_t now;

	Protocol_CheckRxLine();
	now = HAL_GetTick();
	Protocol_CheckTimeout(now);

	if (Protocol_TrySendPendingError() != 0U)
	{
		return;
	}

	Protocol_CheckFeedback(now);
}

void Protocol_ProcessRxByte(uint8_t b)
{
	char c = (char)b;

	if ((c == '\r') || (c == '\n'))
	{
		if (rx_overflow != 0U)
		{
			rx_bad_line_ready = 1U;
			rx_overflow = 0U;
			rx_active_line_len = 0U;
		}
		else if (rx_active_line_len > 0U)
		{
			if (rx_queue_count < PROTOCOL_RX_QUEUE_COUNT)
			{
				uint8_t write_index = rx_queue_head;
				rx_active_line[rx_active_line_len] = '\0';
				memcpy(rx_line_queue[write_index], rx_active_line, PROTOCOL_RX_LINE_SIZE);
				rx_queue_head = (uint8_t)((rx_queue_head + 1U) % PROTOCOL_RX_QUEUE_COUNT);
				rx_queue_count++;
			}
			else
			{
				rx_bad_line_ready = 1U;
			}
			rx_active_line_len = 0U;
		}
		return;
	}

	if ((c == '\b') || (b == 0x7FU))
	{
		if ((rx_overflow == 0U) && (rx_active_line_len > 0U))
		{
			rx_active_line_len--;
		}
		return;
	}

	if (rx_overflow != 0U)
	{
		return;
	}

	if (rx_active_line_len < (PROTOCOL_RX_LINE_SIZE - 1U))
	{
		rx_active_line[rx_active_line_len] = c;
		rx_active_line_len++;
	}
	else
	{
		rx_overflow = 1U;
		rx_active_line_len = 0U;
	}
}

void Protocol_ProcessLine(char *line)
{
	char *tokens[5];
	uint8_t token_count = 0U;

	if ((line == NULL) || (Protocol_TokenizeCsv(line, tokens, 5U, &token_count) == 0U) || (token_count == 0U))
	{
		Protocol_ReportBadCommand();
		return;
	}

	if (Protocol_EqualsIgnoreCase(tokens[0], "CMD") != 0U)
	{
		uint32_t seq;
		float left_mm_s;
		float right_mm_s;

		if ((token_count != 4U) ||
			(Protocol_ParseU32(tokens[1], &seq) == 0U) ||
			(Protocol_ParseFloat(tokens[2], &left_mm_s) == 0U) ||
			(Protocol_ParseFloat(tokens[3], &right_mm_s) == 0U))
		{
			Protocol_ReportBadCommand();
			return;
		}

		last_seq = seq;
		last_valid_rx_ms = HAL_GetTick();
		protocol_status = PROTOCOL_STATUS_OK;
		Motor_SetWheelSpeedMMPS(MOTOR_LEFT, left_mm_s);
		Motor_SetWheelSpeedMMPS(MOTOR_RIGHT, right_mm_s);
		return;
	}

	if (Protocol_EqualsIgnoreCase(tokens[0], "STOP") != 0U)
	{
		uint32_t seq;

		if ((token_count != 2U) || (Protocol_ParseU32(tokens[1], &seq) == 0U))
		{
			Protocol_ReportBadCommand();
			return;
		}

		last_seq = seq;
		last_valid_rx_ms = HAL_GetTick();
		protocol_status = PROTOCOL_STATUS_STOP;
		Motor_StopAll();
		return;
	}

	Protocol_ReportBadCommand();
}

void Protocol_SendFeedback(void)
{
	uint32_t now = HAL_GetTick();

	if (Protocol_TrySendFeedback(now) != 0U)
	{
		last_feedback_sent_ms = now;
		last_feedback_attempt_ms = now;
	}
}

uint32_t Protocol_GetLastSeq(void)
{
	return last_seq;
}

static void Protocol_CheckRxLine(void)
{
	char line[PROTOCOL_RX_LINE_SIZE];
	uint8_t has_line = 0U;
	uint8_t has_bad_line = 0U;

	__disable_irq();
	if (rx_bad_line_ready != 0U)
	{
		rx_bad_line_ready = 0U;
		has_bad_line = 1U;
	}
	else if (rx_queue_count > 0U)
	{
		uint8_t read_index = rx_queue_tail;
		memcpy(line, rx_line_queue[read_index], PROTOCOL_RX_LINE_SIZE);
		rx_queue_tail = (uint8_t)((rx_queue_tail + 1U) % PROTOCOL_RX_QUEUE_COUNT);
		rx_queue_count--;
		has_line = 1U;
	}
	__enable_irq();

	if (has_bad_line != 0U)
	{
		Protocol_ReportBadCommand();
	}

	if (has_line != 0U)
	{
		Protocol_ProcessLine(line);
	}
}

static void Protocol_CheckTimeout(uint32_t now_ms)
{
	if ((uint32_t)(now_ms - last_valid_rx_ms) <= CMD_TIMEOUT_MS)
	{
		return;
	}

	if (protocol_status != PROTOCOL_STATUS_TIMEOUT)
	{
		Motor_StopAll();
		protocol_status = PROTOCOL_STATUS_TIMEOUT;
	}
}

static void Protocol_CheckFeedback(uint32_t now_ms)
{
	if ((uint32_t)(now_ms - last_feedback_sent_ms) < FEEDBACK_PERIOD_MS)
	{
		return;
	}

	if ((uint32_t)(now_ms - last_feedback_attempt_ms) < FEEDBACK_PERIOD_MS)
	{
		return;
	}

	last_feedback_attempt_ms = now_ms;
	if (Protocol_TrySendFeedback(now_ms) != 0U)
	{
		last_feedback_sent_ms = now_ms;
	}
}

static void Protocol_ReportBadCommand(void)
{
	protocol_status = PROTOCOL_STATUS_ERR;
	pending_bad_command = 1U;
}

static uint8_t Protocol_TrySendPendingError(void)
{
	uint32_t now;

	if (pending_bad_command == 0U)
	{
		return 0U;
	}

	now = HAL_GetTick();
	if ((uint32_t)(now - last_error_attempt_ms) < FEEDBACK_PERIOD_MS)
	{
		return 1U;
	}

	last_error_attempt_ms = now;
	if (Protocol_TrySendRaw("ERR,bad_command\r\n") != 0U)
	{
		pending_bad_command = 0U;
		return 1U;
	}

	return 1U;
}

static uint8_t Protocol_TrySendFeedback(uint32_t now_ms)
{
	uint32_t dt_ms = now_ms - last_feedback_sent_ms;

	return Protocol_TrySendFormatted(
		"FB,%lu,%ld,%ld,%lu,%s\r\n",
		(unsigned long)last_seq,
		(long)Motor_GetLeftCount(),
		(long)Motor_GetRightCount(),
		(unsigned long)dt_ms,
		Protocol_StatusText());
}

static uint8_t Protocol_TrySendRaw(const char *text)
{
	return (uint8_t)(CDC_Transmit_FS((uint8_t*)text, (uint16_t)strlen(text)) == USBD_OK);
}

static uint8_t Protocol_TrySendFormatted(const char *format, ...)
{
	char *buffer = tx_buffers[tx_write_index];
	va_list args;
	int length;
	uint8_t status;

	va_start(args, format);
	length = vsnprintf(buffer, PROTOCOL_TX_BUFFER_SIZE, format, args);
	va_end(args);

	if (length <= 0)
	{
		return 0U;
	}

	if (length >= (int)PROTOCOL_TX_BUFFER_SIZE)
	{
		length = (int)PROTOCOL_TX_BUFFER_SIZE - 1;
	}

	status = CDC_Transmit_FS((uint8_t*)buffer, (uint16_t)length);
	if (status == USBD_OK)
	{
		tx_write_index ^= 1U;
		return 1U;
	}

	return 0U;
}

static uint8_t Protocol_TokenizeCsv(char *line, char *tokens[], uint8_t max_tokens, uint8_t *token_count)
{
	char *start = line;
	uint8_t count = 0U;

	while (1)
	{
		char *end = start;
		while ((*end != '\0') && (*end != ','))
		{
			end++;
		}

		if (count >= max_tokens)
		{
			return 0U;
		}

		if (*end == ',')
		{
			*end = '\0';
			tokens[count] = Protocol_Trim(start);
			count++;
			start = end + 1;
		}
		else
		{
			tokens[count] = Protocol_Trim(start);
			count++;
			break;
		}
	}

	*token_count = count;
	return 1U;
}

static char *Protocol_Trim(char *text)
{
	char *end;

	while ((*text != '\0') && (isspace((unsigned char)*text) != 0))
	{
		text++;
	}

	end = text + strlen(text);
	while ((end > text) && (isspace((unsigned char)*(end - 1)) != 0))
	{
		end--;
	}
	*end = '\0';

	return text;
}

static uint8_t Protocol_EqualsIgnoreCase(const char *left, const char *right)
{
	while ((*left != '\0') && (*right != '\0'))
	{
		if (tolower((unsigned char)*left) != tolower((unsigned char)*right))
		{
			return 0U;
		}

		left++;
		right++;
	}

	return (uint8_t)((*left == '\0') && (*right == '\0'));
}

static uint8_t Protocol_ParseU32(const char *text, uint32_t *value)
{
	char *end;
	unsigned long parsed;

	if ((text == NULL) || (*text == '\0') || (*text == '-'))
	{
		return 0U;
	}

	parsed = strtoul(text, &end, 10);
	if ((end == text) || (*end != '\0'))
	{
		return 0U;
	}

	*value = (uint32_t)parsed;
	return 1U;
}

static uint8_t Protocol_ParseFloat(const char *text, float *value)
{
	char *end;
	float parsed;

	if ((text == NULL) || (*text == '\0'))
	{
		return 0U;
	}

	parsed = strtof(text, &end);
	if ((end == text) || (*end != '\0') || (parsed != parsed) || (parsed > 1000000.0f) || (parsed < -1000000.0f))
	{
		return 0U;
	}

	*value = parsed;
	return 1U;
}

static const char *Protocol_StatusText(void)
{
	switch (protocol_status)
	{
	case PROTOCOL_STATUS_OK:
		return "OK";
	case PROTOCOL_STATUS_STOP:
		return "STOP";
	case PROTOCOL_STATUS_TIMEOUT:
		return "TIMEOUT";
	case PROTOCOL_STATUS_ERR:
	default:
		return "ERR";
	}
}
