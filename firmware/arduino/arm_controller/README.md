# arm_controller (Arduino Uno + CNC Shield V3)

Firmware for the SCARA arm controller. Mirror of the role
`firmware/stm32/motor_controller` plays for the car, but for the arm and on
Arduino for now (uses the existing Uno + CNC Shield + A4988 hardware).

## Hardware

- Arduino Uno (ATmega328, CH340 USB).
- CNC Shield V3 stacked on top.
- 3x A4988 stepper drivers -> X = J1 (shoulder), Y = J2 (elbow), Z = Z (lift).
- 1x servo on the shield SVG/servo header -> gripper.
- Separate 12-36V supply into the CNC Shield for motor power.

> A4988 suits NEMA17-class motors (~1-2 A). **Check the arm motor labels.** If
> the arm uses NEMA23 (like the car wheels, ~4.2 A), A4988 is NOT enough and
> this path must change to larger drivers (TB6600/DM542) or an STM32 board.

## Link to the miniPC

USB CDC serial (CH340). The miniPC runs `arm_bridge` and talks to this board on
the arm's own port (e.g. `/dev/ttyUSB0`), separate from the car STM32
(`/dev/ttyACM0`). Later this can move to CAN; the command vocabulary stays the
same (see `arm_bridge`).

## Command vocabulary (must match arm_bridge)

Received over serial, one per line, `\r\n` terminated:

```text
ARM,<seq>,<j1_deg>,<j2_deg>,<z_mm>
GRIP,<seq>,<OPEN|CLOSE>
HOME,<seq>
STOP,<seq>
```

Sent back as feedback:

```text
AFB,<seq>,<DONE|BUSY|ERR>
```

## Division of work (keep it simple)

The miniPC (ROS2) does the heavy math (inverse kinematics, trajectory). This
board only executes: convert target joint values to steps and drive them.
The Uno is weak (16 MHz, 2 KB RAM) — do not put kinematics here.

## Suggested approach

- `AccelStepper` / `MultiStepper` for smooth accel on 3 axes, or
- flash GRBL and send G-code if that is easier for the team.
- Add 3 limit switches (one per axis) for HOME — open-loop steppers need a
  reference or position drifts.

## Status

Skeleton only. `arm_controller.ino` is a starter stub that parses the command
lines and acks them; fill in the real stepping/servo logic when hardware
arrives.
