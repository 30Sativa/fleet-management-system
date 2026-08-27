# CampusTour DT-AMR

Monorepo for the CampusTour DT-AMR capstone: visitors book a campus tour, an
autonomous mobile robot guides them, and an operations team schedules and
monitors the fleet through a Digital Twin synchronised over ROS 2. This repo
contains the complete system as separate robot, Digital Twin, backend,
AI tour-guide and web deploy units.

## Layout

Each top-level folder is one deploy unit with its own build and its own
verification gate.

| Folder | Work package | What it is | Status |
|---|---|---|---|
| [`robot/`](robot/README.md) | WP3 | ROS 2 Humble workspace + STM32 motor firmware | active |
| [`digital-twin/`](digital-twin/README.md) | WP3 | Live twin synchronization, scenarios and research metrics | not started |
| `backend/` | WP2 | Booking, scheduling & dispatch API | not started |
| [`ai-assistant/`](ai-assistant/README.md) | WP4 | Multilingual STT, dialogue/LLM and TTS service | not started |
| `web/` | WP5 | Visitor app + operations dashboard | not started |
| [`docs/`](docs/architecture.md) | WP1 | System architecture + decision records | active |

## Getting started

Pick the folder you are working in and read its README:

- Robot / ROS 2 / firmware → [`robot/README.md`](robot/README.md)
- Digital Twin → [`digital-twin/README.md`](digital-twin/README.md)
- Backend → `backend/AGENTS.md` <!-- TODO(WP2): đổi thành backend/README.md khi có -->
- AI tour-guide assistant → [`ai-assistant/README.md`](ai-assistant/README.md)
- Frontend → `web/AGENTS.md` <!-- TODO(WP5): đổi thành web/README.md khi có -->

## Verification

One command answers "does the current code pass?":

```bash
scripts/verify            # all folders
scripts/verify robot      # one folder
```

Exit code `0` = pass, anything else = fail.

Note that for `robot/` a passing script is **not** the same as a working robot —
navigation and hardware behaviour are only verified by running it. See
[`AGENTS.md`](AGENTS.md) for the two completion states this repo uses.

## Working with coding agents

[`AGENTS.md`](AGENTS.md) at the repo root holds the shared rules; each folder
has its own `AGENTS.md` with the rules specific to that stack. Agents should
read the root file first, then the one for the folder they are changing.

## Team

<!-- TODO(Duy): điền 5 thành viên + WP mỗi người, để agent biết hỏi ai khi đụng contract giữa 2 folder.
| Name | WP | Owns |
|---|---|---|
|  | WP1 | Project management & system architecture |
|  | WP2 | backend/ |
|  | WP3 | robot/ + digital-twin/ |
|  | WP4 | ai-assistant/ |
|  | WP5 | web/ |
-->
