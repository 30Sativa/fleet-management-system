#ifndef SR04T_H
#define SR04T_H

#include <stdint.h>

/* Four SR04T connectors from the schematic:
 *   SONAR1: PB0  = TRIG, PB1  = ECHO
 *   SONAR2: PB11 = TRIG, PB12 = ECHO
 *   SONAR3: PB13 = TRIG, PB14 = ECHO
 *   SONAR4: PB15 = TRIG, PA6  = ECHO
 */
#define SR04T_SENSOR_COUNT 4U

void SR04T_Init(void);
void SR04T_Update(void);
void SR04T_OnGpioExti(uint16_t gpio_pin);
void SR04T_GetReading(uint8_t sensor_index, uint16_t *distance_mm,
                      uint8_t *valid);

#endif /* SR04T_H */
