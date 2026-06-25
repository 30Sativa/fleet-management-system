// =============================================================================
// arm_controller.ino  (Arduino Uno + CNC Shield V3)
// SCARA arm controller skeleton for the AMR.
//
// Talks to the miniPC over USB CDC serial. Mirrors the command vocabulary used
// by the ROS2 `arm_bridge` package so the transport can later move to CAN
// without changing what the commands mean.
//
// THIS IS A STARTER STUB. It parses commands and acknowledges them so the
// serial link can be verified end-to-end before the real motion logic and the
// hardware are in place. Fill in stepping/servo where marked TODO.
//
// Command lines in (\r\n terminated):
//   ARM,<seq>,<j1_deg>,<j2_deg>,<z_mm>
//   GRIP,<seq>,<OPEN|CLOSE>
//   HOME,<seq>
//   STOP,<seq>
// Feedback out:
//   AFB,<seq>,<DONE|BUSY|ERR>
//
// CNC Shield V3 pin map (standard):
//   X: STEP D2  DIR D5      -> J1 (shoulder)
//   Y: STEP D3  DIR D6      -> J2 (elbow)
//   Z: STEP D4  DIR D7      -> Z  (lift)
//   Enable (active LOW): D8
//   Servo (gripper): use a free header, e.g. D11 / D12 (SpnEn/SpnDir pins).
// =============================================================================

const uint8_t PIN_X_STEP = 2, PIN_X_DIR = 5;
const uint8_t PIN_Y_STEP = 3, PIN_Y_DIR = 6;
const uint8_t PIN_Z_STEP = 4, PIN_Z_DIR = 7;
const uint8_t PIN_ENABLE  = 8;   // active LOW
const uint8_t PIN_SERVO   = 11;  // gripper servo signal (TODO: confirm header)

// Optional limit switches for HOME (add when wired). Active depends on wiring.
// const uint8_t PIN_LIM_X = 9, PIN_LIM_Y = 10, PIN_LIM_Z = 12;

char buf[64];
uint8_t len = 0;

void ack(long seq, const char* state) {
  Serial.print("AFB,");
  Serial.print(seq);
  Serial.print(',');
  Serial.println(state);
}

void handleLine(char* line) {
  // Split on commas in place.
  char* tok = strtok(line, ",");
  if (!tok) return;

  if (strcmp(tok, "ARM") == 0) {
    long seq  = atol(strtok(NULL, ","));
    // float j1 = atof(strtok(NULL, ","));
    // float j2 = atof(strtok(NULL, ","));
    // float z  = atof(strtok(NULL, ","));
    // TODO: convert j1/j2/z to step targets and drive the 3 axes.
    ack(seq, "DONE");
  } else if (strcmp(tok, "GRIP") == 0) {
    long seq = atol(strtok(NULL, ","));
    // char* action = strtok(NULL, ",");  // "OPEN" | "CLOSE"
    // TODO: drive the gripper servo to open/close angle.
    ack(seq, "DONE");
  } else if (strcmp(tok, "HOME") == 0) {
    long seq = atol(strtok(NULL, ","));
    // TODO: home each axis against its limit switch, then zero positions.
    ack(seq, "DONE");
  } else if (strcmp(tok, "STOP") == 0) {
    long seq = atol(strtok(NULL, ","));
    // TODO: immediately halt motion.
    ack(seq, "DONE");
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(PIN_X_STEP, OUTPUT); pinMode(PIN_X_DIR, OUTPUT);
  pinMode(PIN_Y_STEP, OUTPUT); pinMode(PIN_Y_DIR, OUTPUT);
  pinMode(PIN_Z_STEP, OUTPUT); pinMode(PIN_Z_DIR, OUTPUT);
  pinMode(PIN_ENABLE, OUTPUT);
  pinMode(PIN_SERVO, OUTPUT);

  digitalWrite(PIN_ENABLE, LOW);  // enable drivers (active LOW)
}

void loop() {
  // Non-blocking line reader.
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      buf[len] = '\0';
      if (len > 0) handleLine(buf);
      len = 0;
    } else if (c != '\r' && len < sizeof(buf) - 1) {
      buf[len++] = c;
    }
  }

  // TODO: service stepper motion here (e.g. AccelStepper::run() for each axis).
}
