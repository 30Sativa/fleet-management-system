# AGENTS.md

Repo-wide instructions for coding agents. Read this first, then read the
`AGENTS.md` inside the folder you are actually changing.

---

## 1. Project Overview

**CampusTour DT-AMR** — an AI-driven campus tour system: visitors book a tour,
an autonomous mobile robot (AMR) guides them around campus, and an operations
team schedules and monitors the fleet through a Digital Twin kept in sync with
the real robots over ROS 2.

<!-- TODO(Duy): 1-2 câu mô tả phạm vi của repo NÀY (repo này chứa gì, cái gì nằm repo khác). -->

---

## 2. Repository Layout

This is a monorepo. Each top-level folder is one **deploy unit** with its own
build, its own verification, and its own `AGENTS.md`.

| Folder | What it is | Deploys to | Read before editing |
|---|---|---|---|
| `robot/` | ROS 2 Humble workspace + STM32 motor firmware | robot miniPC (Docker image) | `robot/AGENTS.md` |
| `digital-twin/` | Twin synchronization, scenarios and research metrics | simulation workstation/server | `digital-twin/AGENTS.md` |
| `backend/` | Booking, scheduling & dispatch API | <!-- TODO(Duy): server nào --> | `backend/AGENTS.md` |
| `ai-assistant/` | Multilingual STT, dialogue/LLM and TTS service | server/cloud, not the robot miniPC | `ai-assistant/AGENTS.md` |
| `web/` | Visitor app + operations dashboard | <!-- TODO(Duy): host nào --> | `web/AGENTS.md` |
| `docs/` | System-level architecture and decisions | — | `docs/architecture.md` |
| `scripts/` | Cross-folder entry points | — | — |

Rules that follow from this layout:

- **Do not move code across the top-level boundary** to "share" it. If two
  folders need the same thing, define a contract in `docs/` first.
- **Do not add a root-level build tool** (workspace manager, task runner,
  monorepo framework) unless a task explicitly asks for one.
- **Every path written in a doc, a comment, or a commit message is relative to
  the repo root**, e.g. `robot/ros2_ws/src/robot_control/`.

---

## 3. Working on a Task

Before changing code:

1. Identify which top-level folder the task belongs to. Read that folder's
   `AGENTS.md`.
2. Read the existing implementation before proposing a change.
3. Read the relevant doc: `docs/architecture.md` for cross-system behaviour,
   the folder's own README/docs for local behaviour.
4. Inspect existing tests for the code you are about to touch.
5. Identify the **smallest** change that satisfies the task.

While changing code:

- Stay inside the folder the task belongs to. Touching a second top-level
  folder means the task has an integration component — say so explicitly
  instead of doing it silently.
- Do not refactor, rename, reformat, or upgrade anything the task did not ask
  for. Unrelated cleanup goes in a separate task.
- Prefer an existing utility, node, or endpoint over a new one.
- Do not add a dependency unless there is no reasonable alternative; say why.

After changing code:

1. Add or update tests for the behaviour you changed.
2. Run `scripts/verify` (see below).
3. Fix every failure. Do not weaken a check to make it pass.
4. Review the final diff yourself before reporting.

---

## 4. Verification

From the repo root:

```bash
scripts/verify            # every folder that has a verify script
scripts/verify robot      # one folder only
```

Exit code is the contract:

```
0     -> PASS
!= 0  -> FAIL
```

Never report a task as complete while `scripts/verify` is failing.

---

## 5. Definition of Done

This repo has **two** completion states. Use the right one.

### DONE (verified)

Everything the task changed is covered by automated checks. All of:

1. The requested behaviour is implemented.
2. Tests covering the change exist and pass.
3. `scripts/verify` exits 0.
4. No existing test was deleted or weakened without a stated reason.
5. The diff contains no unrelated changes.
6. You can state what changed and how it was verified.

### READY FOR HARDWARE TEST

Use this — **not** DONE — whenever the change affects behaviour that cannot be
proven by a script: robot navigation, TF frames, costmaps, motor/serial
protocol, firmware, or anything whose correctness is only visible in Gazebo,
RViz, or on the real robot.

Report it as:

```
READY FOR HARDWARE TEST

Changed:      <what>
Verified:     scripts/verify robot -> PASS (tier 1 + 2)
Not verified: <the behaviour a script cannot check>
Run this:     <exact launch command>
Expect:       <what a correct run looks like>
Watch for:    <the failure mode this change could introduce>
```

Never claim DONE for behaviour you were not able to execute.

---

## 6. Hard Constraints

- Do not commit build output: `build/`, `install/`, `log/`, `__pycache__/`,
  `node_modules/`, firmware `Debug/*.elf|bin|hex|map|list|o|d`.
- Do not commit secrets: DockerHub tokens, API keys, `.env` files, ST-Link or
  machine credentials.
- Do not edit `.github/workflows/` to skip, disable, or bypass a failing check.
- Do not remove a test to turn CI green. Fix the behaviour or explain why the
  test was wrong.
- Do not change a folder's public interface (API route, ROS topic/action name,
  message field) without recording it in `docs/architecture.md` — another
  work package depends on it.

<!-- TODO(Duy): thêm constraint riêng của team nếu có (ví dụ: branch naming, ai được merge vào main). -->
