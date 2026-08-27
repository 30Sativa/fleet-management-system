# Digital Twin

WP3 deploy unit for the synchronized virtual counterpart of the physical AMR
fleet. It runs on a simulation workstation/server and owns:

- live robot-state synchronization;
- Digital Twin scenarios and orchestration;
- state replay for investigation and comparison;
- repeatable synchronization latency and accuracy measurements.

## Boundary with robot simulation

This deploy unit is not the `simulation` ROS package.

| `robot/ros2_ws/src/simulation/` | `digital-twin/` |
|---|---|
| Minimal Gazebo worlds and launches | Synchronized operational twin |
| Tests Nav2 without hardware | Mirrors state from physical robots |
| Part of robot-stack development | Runs experiments and what-if scenarios |
| No fleet/backend synchronization | Integrates with robot/backend contracts |

The authoritative robot model, navigation behaviour and ROS interfaces remain
in `robot/`. Do not copy them into this folder. The integration mechanism must
be defined in `docs/architecture.md` before source is added.

## Safety boundary

The Digital Twin may evaluate a route or schedule, but it must not directly
command a physical robot. Applying a validated change goes through the
authenticated backend and an explicit operator workflow.

## Status

**Not started.** The synchronization transport, schemas, clock policy, update
rate, replay format and simulation runtime are not decided yet.

## Verification

```bash
digital-twin/scripts/verify
```

The script currently returns `SKIPPED` until source and a real verification
pipeline are added.
