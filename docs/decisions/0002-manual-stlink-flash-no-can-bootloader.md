# ADR-0002: STM32 firmware is flashed manually over ST-Link

## Context

The STM32G431 runs the motor controller: it owns stepping, reads encoders, and
talks to the miniPC over USB CDC serial. Flashing it automatically — from CI,
or from the miniPC over a CAN bootloader — would shorten the loop when firmware
changes.

It would also mean an automated system can put the board into a state where the
robot does not move, or moves wrongly, with a several-hundred-kilogram-class
platform among pedestrians. A bricked board mid-semester also costs lab days
this project does not have.

## Decision

Flashing is a manual act performed by a person with an ST-Link.

- GitHub Actions compiles the firmware and uploads `.elf`/`.bin`/`.hex`/`.map`/
  `.list` as artifacts. It must never flash.
- The miniPC must never flash the STM32.
- There is no CAN bootloader, and adding one is out of scope for this project.

## Consequences

Positive:

- No automated path can disable the motor controller.
- CI still catches firmware that does not compile, which is the common failure.
- The person flashing is present at the robot and can observe the first move.

Negative:

- Firmware iteration is slower and requires physical access.
- Firmware version on the board is not tracked anywhere automatic — it is
  whatever a human last flashed.
- A robot deployed away from the lab cannot receive a firmware fix remotely.

## Note

`.github/workflows/stm32-build.yml` rewrites the Windows absolute
linker-script path inside the generated STM32CubeIDE makefile before building.
That patch exists only so CI can compile on Linux; do not hand-edit
`robot/firmware/stm32/motor_controller/Debug/makefile` to "fix" it.
