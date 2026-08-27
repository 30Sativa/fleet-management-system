# AGENTS.md — `digital-twin/`

> **STATUS: SKELETON.** Nothing is implemented yet. Fill the TODO blocks when
> Digital Twin work starts; delete this banner at that point.

Synchronized Digital Twin and research tooling for CampusTour DT-AMR (WP3).
Read the repo-root `AGENTS.md` first; this file covers only this deploy unit.

---

## 1. Scope

This folder owns live twin synchronization, scenario orchestration, state
replay and repeatable synchronization latency/accuracy experiments.

It does not own the authoritative robot model, Nav2 configuration, firmware or
basic robot-stack simulation. Those remain under `robot/`; the minimal Gazebo
development package is `robot/ros2_ws/src/simulation/`.

---

## 2. Stack and layout

<!-- TODO(WP3): choose Gazebo/Isaac Sim, runtime versions, build/container
     strategy and local run command. -->

<!-- TODO(WP3): document the real bridge, scenarios, replay, experiments,
     config and tests layout after the stack is selected. -->

---

## 3. Architecture rules

- Do not copy robot models, Nav2 logic or ROS interface definitions from
  `robot/`. Consume the agreed contract or built artifact instead.
- Define synchronization transport, schemas, timestamps/clocks, update rates,
  authentication and replay format in `docs/architecture.md` before coding the
  bridge.
- A Digital Twin scenario must never directly command a physical robot.
  Applying a result goes through the authenticated backend/operator workflow.
- Experiments must record configuration, input dataset/replay, clock source and
  metrics so another team member can reproduce the result.
- Keep generated bags, recordings, simulation caches and experiment output out
  of Git unless a task explicitly adds a small reviewed fixture.

---

## 4. Verification

```bash
digital-twin/scripts/verify
```

<!-- TODO(WP3): replace the skeleton with format/lint, build, unit/integration
     tests and deterministic replay/metric checks required by the chosen stack. -->

---

## 5. Hard constraints

- Do not commit visitor data, production telemetry, secrets, large rosbags or
  generated simulation/experiment output.
- Do not present a simulator run as Digital Twin validation unless it used the
  documented synchronization path and recorded the required metrics.
- Any public interface change requires the matching update in
  `docs/architecture.md` in the same PR.
