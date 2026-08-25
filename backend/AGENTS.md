# AGENTS.md — `backend/`

> **STATUS: SKELETON.** Nothing is implemented yet. Fill the TODO blocks in
> when WP2 starts; delete this banner at that point.

Booking, tour scheduling and multi-robot dispatch API for CampusTour DT-AMR
(Work Package 2). Read the repo-root `AGENTS.md` first for the shared rules;
this file only covers what is specific to `backend/`.

---

## 1. Stack

<!-- TODO(WP2): ngôn ngữ + framework + runtime version. Ví dụ: TypeScript 5.x / NestJS / Node 20 -->
<!-- TODO(WP2): database. Ví dụ: PostgreSQL 16 + Prisma -->
<!-- TODO(WP2): cách chạy local. Ví dụ: docker compose up db && npm run dev -->

---

## 2. Layout

<!-- TODO(WP2): điền cây thư mục thật khi có code, ví dụ:
backend/
├── src/
│   ├── modules/<domain>/{controller,service,repository}
│   └── ...
├── tests/
└── scripts/verify
-->

---

## 3. Architecture Rules

Layered: `Controller -> Service -> Repository -> Database`.

Allowed direction only:

```
Controller
    v
 Service
    v
Repository
    v
 Database
```

- Controllers parse the request, validate input, call a service, return a
  response. Controllers must not contain business logic and must not touch the
  database.
- Services hold business logic and coordinate repositories. Services must not
  depend on HTTP-specific objects and must not build database queries directly.
- Repositories own persistence and query construction only.

<!-- TODO(WP2): rule riêng cho scheduling/dispatch — ví dụ: thuật toán assign robot nằm ở service nào, có được gọi trực tiếp ROS bridge từ controller không (mặc định: không). -->

---

## 4. Interface with the robot fleet

The robot side (`robot/`) is a separate deploy unit maintained by WP3. Any
change to the telemetry the backend consumes or the commands it sends is a
**contract change**: update `docs/architecture.md` in the same PR and tell WP3.

<!-- TODO(WP2+WP3): chốt transport (rosbridge websocket / MQTT / REST) và schema, rồi ghi vào docs/architecture.md. Trước khi chốt, đừng hardcode field name ở hai đầu. -->

---

## 5. Verification

```bash
backend/scripts/verify
```

<!-- TODO(WP2): điền các lệnh thật vào backend/scripts/verify — typecheck, lint, test, và migration check nếu có. -->

---

## 6. Definition of Done

Standard **DONE (verified)** from the root `AGENTS.md`. The backend has no
tier-3 hardware step — if a change is fully covered by tests and
`backend/scripts/verify` passes, it is DONE.

Exception: anything that sends commands to a real robot. That is tier 3 and
must be reported as READY FOR HARDWARE TEST.

---

## 7. Hard Constraints

- Do not change the database schema without an ADR in `docs/decisions/`.
- Do not weaken authentication on robot-control endpoints. An unauthenticated
  path that can move a robot is a safety bug, not a convenience.
- Visitor personal data (name, contact, booking history) must never appear in
  logs or in an error response body.

<!-- TODO(WP2): thêm constraint khác khi có. -->
