/**
 ******************************************************************************
 * @file    bno08x.c
 * @brief   Driver BNO080/085 qua I2C bit-bang tren PB6/PB7.
 ******************************************************************************
 */
#include "imu/bno08x.h"
#include "main.h"
#include <string.h>
#include <math.h>

/* ---- cau hinh chan ---- */
#define BB_PORT     GPIOB
#define BB_SCL      GPIO_PIN_6      /* PB6 */
#define BB_SDA      GPIO_PIN_7      /* PB7 */
#define BB_RST_PORT GPIOA
#define BB_RST_PIN  GPIO_PIN_4      /* PA4 */
#define BB_INT_PIN  GPIO_PIN_5      /* PA5 */

/* De tiet kiem chan STM32: BNO08x chi can SCL/SDA.
 * RST co the keo len 3V3, INT co the bo trong neu poll bang bit-bang. */
#ifndef BNO08X_USE_HW_RST
#define BNO08X_USE_HW_RST 0
#endif

#ifndef BNO08X_USE_INT_PIN
#define BNO08X_USE_INT_PIN 0
#endif

#define BNO_ADDR    0x4A            /* ADD=GND */

#define SHTP_CH_EXECUTABLE             1
#define EXEC_CMD_RESET                 0x01
#define SHTP_CH_CONTROL                 2
#define SHTP_REPORT_PRODUCT_ID_REQUEST  0xF9
#define SHTP_REPORT_PRODUCT_ID_RESPONSE 0xF8

#define BB_STRETCH_TIMEOUT_MS  25U

#define SHTP_CH_REPORTS                 3
#define SHTP_REPORT_BASE_TIMESTAMP      0xFB
#define SENSOR_REPORTID_ROTATION_VECTOR 0x05
#define SENSOR_REPORTID_GAME_ROTATION_VECTOR 0x08
#define SENSOR_REPORTID_ODOM_VECTOR     SENSOR_REPORTID_GAME_ROTATION_VECTOR
#define SHTP_REPORT_SET_FEATURE_COMMAND 0xFD
#define Q14_SCALE   (1.0f / 16384.0f)

#ifndef BNO08X_YAW_TIMEOUT_MS
#define BNO08X_YAW_TIMEOUT_MS 200U
#endif

static uint8_t s_seq[8];
static float   s_last_yaw = 0.0f;
static uint8_t s_yaw_valid = 0U;
static uint32_t s_last_yaw_ms = 0U;

/* ---- delay & line control ----
 * I2C uses open-drain lines: writing HIGH releases the line, writing LOW
 * actively pulls it low.  The board must provide external pull-ups to 3V3.
 */
static void bb_delay(void) { for (volatile int i = 0; i < 150; i++) { __NOP(); } }

static void scl_release(void)
{
    HAL_GPIO_WritePin(BB_PORT, BB_SCL, GPIO_PIN_SET);
}
static void scl_low(void)
{
    HAL_GPIO_WritePin(BB_PORT, BB_SCL, GPIO_PIN_RESET);
}
static void sda_release(void)
{
    HAL_GPIO_WritePin(BB_PORT, BB_SDA, GPIO_PIN_SET);
}
static void sda_low(void)
{
    HAL_GPIO_WritePin(BB_PORT, BB_SDA, GPIO_PIN_RESET);
}
static uint8_t sda_read(void) { return (BB_PORT->IDR & BB_SDA) ? 1U : 0U; }
static uint8_t scl_read(void) { return (BB_PORT->IDR & BB_SCL) ? 1U : 0U; }

static uint8_t scl_release_wait(void)
{
    scl_release();
    uint32_t start = HAL_GetTick();
    while (scl_read() == 0U)
    {
        if ((HAL_GetTick() - start) >= BB_STRETCH_TIMEOUT_MS) return 0U;
    }
    return 1U;
}

/* ---- I2C primitives ---- */
static uint8_t bb_start(void)
{
    sda_release();
    if (!scl_release_wait()) return 0U;
    bb_delay();
    if (!sda_read()) return 0U;  /* Bus is busy: do not corrupt another transfer. */
    sda_low();     bb_delay();
    scl_low();     bb_delay();
    return 1U;
}
static uint8_t bb_stop(void)
{
    sda_low();          bb_delay();
    if (!scl_release_wait()) return 0U;
    bb_delay();
    sda_release();      bb_delay();
    return sda_read();
}
static uint8_t bb_write_bit(uint8_t b)
{
    if (b) sda_release(); else sda_low();
    bb_delay();
    if (!scl_release_wait()) { scl_low(); return 0U; }
    bb_delay();
    scl_low();
    return 1U;
}
static uint8_t bb_read_bit(uint8_t *bit)
{
    sda_release();
    bb_delay();
    if (!scl_release_wait()) { scl_low(); return 0U; }
    bb_delay();
    *bit = sda_read();
    scl_low();
    return 1U;
}
static uint8_t bb_write_byte(uint8_t v)
{
    uint8_t ack;
    for (int i = 0; i < 8; i++)
    {
        if (!bb_write_bit((v & 0x80) ? 1U : 0U)) return 0U;
        v <<= 1;
    }
    return bb_read_bit(&ack) && (ack == 0U);
}
static uint8_t bb_read_byte(uint8_t ack, uint8_t *value)
{
    uint8_t v = 0;
    uint8_t bit;
    for (int i = 0; i < 8; i++)
    {
        if (!bb_read_bit(&bit)) return 0U;
        v = (uint8_t)((v << 1) | bit);
    }
    if (!bb_write_bit(ack ? 0U : 1U)) return 0U;
    *value = v;
    return 1U;
}
static uint8_t i2c_write(uint8_t addr7, const uint8_t *d, uint16_t n)
{
    if (!bb_start()) return 0U;
    if (!bb_write_byte((uint8_t)(addr7 << 1))) { (void)bb_stop(); return 0U; }
    for (uint16_t i = 0; i < n; i++)
        if (!bb_write_byte(d[i])) { (void)bb_stop(); return 0U; }
    return bb_stop();
}
static uint16_t i2c_read(uint8_t addr7, uint8_t *buf, uint16_t n)
{
    if ((buf == NULL) || (n == 0U)) return 0U;
    if (!bb_start()) return 0U;
    if (!bb_write_byte((uint8_t)((addr7 << 1) | 1U))) { (void)bb_stop(); return 0U; }
    for (uint16_t i = 0; i < n; i++)
        if (!bb_read_byte((i + 1U < n) ? 1U : 0U, &buf[i])) { (void)bb_stop(); return 0U; }
    return bb_stop() ? n : 0U;
}
static uint8_t i2c_ping(uint8_t addr7)
{
    uint8_t ack;
    if (!bb_start()) return 0U;
    ack = bb_write_byte((uint8_t)((addr7 << 1) | 0U));
    return bb_stop() && ack;
}

/* ---- SHTP ---- */
static int shtp_read(uint8_t *buf, uint16_t cap)
{
    uint8_t hdr[4];
    if ((buf == NULL) || (cap < sizeof(hdr))) return -1;
    if (i2c_read(BNO_ADDR, hdr, 4) != 4) return -1;
    uint16_t total = (uint16_t)((hdr[0] | (hdr[1] << 8)) & 0x7FFF);

    /* BNO08x supports partial I2C reads.  After reading the first SHTP
     * header, the next read starts with an updated 4-byte header followed by
     * the remaining payload; its size is therefore the original packet size. */
    if (total <= 4U) return 0;
    if (total > cap) return -1;
    uint16_t got = i2c_read(BNO_ADDR, buf, total);
    if (got != total) return -1;
    return (int)(got - 4U);
}
static uint8_t shtp_send_pid_request(void)
{
    uint8_t pkt[6] = {6, 0, SHTP_CH_CONTROL, 0, SHTP_REPORT_PRODUCT_ID_REQUEST, 0};
    pkt[3] = s_seq[SHTP_CH_CONTROL]++;
    return i2c_write(BNO_ADDR, pkt, 6);
}

/* ---- public ---- */
void BNO08x_Init(void)
{
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    memset(s_seq, 0, sizeof(s_seq));
    s_last_yaw = 0.0f;
    s_yaw_valid = 0U;
    s_last_yaw_ms = 0U;

#if BNO08X_USE_HW_RST || BNO08X_USE_INT_PIN
    GPIO_InitTypeDef g = {0};
#endif

#if BNO08X_USE_HW_RST
    g.Pin = BB_RST_PIN; g.Mode = GPIO_MODE_OUTPUT_PP; g.Pull = GPIO_NOPULL; g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(BB_RST_PORT, &g);
    HAL_GPIO_WritePin(BB_RST_PORT, BB_RST_PIN, GPIO_PIN_SET);
#endif

#if BNO08X_USE_INT_PIN
    g.Pin = BB_INT_PIN; g.Mode = GPIO_MODE_INPUT; g.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(BB_RST_PORT, &g);
#endif

    GPIO_InitTypeDef bus = {0};
    bus.Pin = BB_SCL | BB_SDA;
    bus.Mode = GPIO_MODE_OUTPUT_OD;
    bus.Pull = GPIO_PULLUP;
    bus.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(BB_PORT, &bus);
    sda_release();
    scl_release();
    HAL_Delay(5);
}

static void bno_reset(void)
{
#if BNO08X_USE_HW_RST
    HAL_GPIO_WritePin(BB_RST_PORT, BB_RST_PIN, GPIO_PIN_RESET);
    HAL_Delay(20);
    HAL_GPIO_WritePin(BB_RST_PORT, BB_RST_PIN, GPIO_PIN_SET);
#else
    uint8_t pkt[5];
    pkt[0] = 5; pkt[1] = 0;
    pkt[2] = SHTP_CH_EXECUTABLE;
    pkt[3] = s_seq[SHTP_CH_EXECUTABLE]++;
    pkt[4] = EXEC_CMD_RESET;
    (void)i2c_write(BNO_ADDR, pkt, 5);
#endif
    HAL_Delay(300);
}

uint8_t BNO08x_SelfTest(uint8_t *sw_major, uint8_t *sw_minor)
{
    uint8_t buf[256];

    if (!i2c_ping(BNO_ADDR)) return 0U;

    bno_reset();

    for (uint8_t i = 0; i < 4; i++) { (void)shtp_read(buf, sizeof(buf)); HAL_Delay(20); }

    if (!shtp_send_pid_request()) return 0U;
    HAL_Delay(50);

    for (uint8_t i = 0; i < 8; i++)
    {
        int plen = shtp_read(buf, sizeof(buf));
        if (plen <= 0) { HAL_Delay(20); continue; }
        if (buf[2] == SHTP_CH_CONTROL && buf[4] == SHTP_REPORT_PRODUCT_ID_RESPONSE)
        {
            if (sw_major) *sw_major = buf[6];
            if (sw_minor) *sw_minor = buf[7];
            return 1U;
        }
        HAL_Delay(20);
    }
    return 0U;
}

uint8_t BNO08x_Diag(uint32_t *err_code)
{
    if (err_code) *err_code = 0U;
    return i2c_ping(BNO_ADDR) ? 0U : 1U;
}

/* ---- Rotation Vector ---- */
static uint8_t shtp_set_feature(uint8_t report_id, uint32_t interval_us)
{
    uint8_t pkt[4 + 17];
    pkt[0]  = (uint8_t)((4 + 17) & 0xFF);
    pkt[1]  = (uint8_t)(((4 + 17) >> 8) & 0xFF);
    pkt[3]  = s_seq[SHTP_CH_CONTROL]++;
    pkt[4]  = SHTP_REPORT_SET_FEATURE_COMMAND;
    pkt[5]  = report_id;
    pkt[6]  = 0;            /* feature flags */
    pkt[7]  = 0;            /* change sensitivity LSB */
    pkt[8]  = 0;            /* change sensitivity MSB */
    pkt[9]  = (uint8_t)(interval_us & 0xFF);
    pkt[10] = (uint8_t)((interval_us >> 8) & 0xFF);
    pkt[11] = (uint8_t)((interval_us >> 16) & 0xFF);
    pkt[12] = (uint8_t)((interval_us >> 24) & 0xFF);
    pkt[13] = 0; pkt[14] = 0; pkt[15] = 0; pkt[16] = 0;
    pkt[17] = 0; pkt[18] = 0; pkt[19] = 0; pkt[20] = 0;
    return i2c_write(BNO_ADDR, pkt, 4 + 17);
}

uint8_t BNO08x_EnableRotationVector(uint16_t interval_ms)
{
    if (interval_ms == 0U) interval_ms = 20U;
    return shtp_set_feature(SENSOR_REPORTID_ROTATION_VECTOR,
                            (uint32_t)interval_ms * 1000U);
}

uint8_t BNO08x_ReadRotationVector(float *qi, float *qj, float *qk, float *qr,
                                  BNO08x_Euler *euler)
{
    uint8_t buf[256];
    int plen = shtp_read(buf, sizeof(buf));
    if (plen <= 0) return 0U;
    if (buf[2] != SHTP_CH_REPORTS) return 0U;

    uint8_t *p = buf + 4;
    int n = plen;
    int idx = -1;
    for (int i = 0; i + 11 < n; i++)
    {
        if (p[i] == SENSOR_REPORTID_ROTATION_VECTOR) { idx = i; break; }
    }
    if (idx < 0) return 0U;

    int16_t ri = (int16_t)(p[idx + 4] | (p[idx + 5] << 8));
    int16_t rj = (int16_t)(p[idx + 6] | (p[idx + 7] << 8));
    int16_t rk = (int16_t)(p[idx + 8] | (p[idx + 9] << 8));
    int16_t rr = (int16_t)(p[idx + 10] | (p[idx + 11] << 8));

    float fi = (float)ri * Q14_SCALE;
    float fj = (float)rj * Q14_SCALE;
    float fk = (float)rk * Q14_SCALE;
    float fr = (float)rr * Q14_SCALE;

    if (qi) *qi = fi;
    if (qj) *qj = fj;
    if (qk) *qk = fk;
    if (qr) *qr = fr;

    if (euler)
    {
        const float RAD2DEG = 57.2957795f;
        float sinr_cosp = 2.0f * (fr * fi + fj * fk);
        float cosr_cosp = 1.0f - 2.0f * (fi * fi + fj * fj);
        euler->roll = atan2f(sinr_cosp, cosr_cosp) * RAD2DEG;

        float sinp = 2.0f * (fr * fj - fk * fi);
        if (sinp > 1.0f)  sinp = 1.0f;
        if (sinp < -1.0f) sinp = -1.0f;
        euler->pitch = asinf(sinp) * RAD2DEG;

        float siny_cosp = 2.0f * (fr * fk + fi * fj);
        float cosy_cosp = 1.0f - 2.0f * (fj * fj + fk * fk);
        euler->yaw = atan2f(siny_cosp, cosy_cosp) * RAD2DEG;

        s_last_yaw = euler->yaw;
        s_yaw_valid = 1U;
        s_last_yaw_ms = HAL_GetTick();
    }
    return 1U;
}

float BNO08x_GetLastYaw(uint8_t *valid)
{
    uint8_t fresh = (uint8_t)(
        (s_yaw_valid != 0U) &&
        ((uint32_t)(HAL_GetTick() - s_last_yaw_ms) <= BNO08X_YAW_TIMEOUT_MS));
    if (valid) *valid = fresh;
    return s_last_yaw;
}
