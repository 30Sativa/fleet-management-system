# AGENTS.md — `web/`

> **STATUS: SKELETON.** Nothing is implemented yet. Fill the TODO blocks in
> when WP5 starts; delete this banner at that point.

Visitor booking app and operations dashboard for CampusTour DT-AMR (Work
Package 5). Read the repo-root `AGENTS.md` first for the shared rules; this
file only covers what is specific to `web/`.

---

## 1. Stack

<!-- TODO(WP5): framework + version + package manager. Ví dụ: React 18 / Vite / pnpm -->
<!-- TODO(WP5): 1 app hay 2 app? Visitor app và ops dashboard có chung codebase không? Ghi rõ quyết định ở đây. -->
<!-- TODO(WP5): cách chạy local + backend URL lấy từ env nào -->

---

## 2. Layout

<!-- TODO(WP5): điền cây thư mục thật khi có code -->

---

## 3. Development Rules

- All backend access goes through one API client module. No `fetch` scattered
  through components.
- No business rule is reimplemented in the frontend. If the dashboard needs a
  computed value (robot utilisation, ETA, wait time), the backend returns it.
- The ops dashboard is used by campus staff with no robotics background: a
  robot state shown to them must be a plain-language label, not a raw ROS enum.

<!-- TODO(WP5): thêm rule về state management, styling convention, component structure. -->

---

## 4. Live robot data

The dashboard shows live fleet state. That data crosses a contract boundary
owned jointly with `robot/` and `backend/` — see `docs/architecture.md`.

<!-- TODO(WP5): chốt cách nhận realtime (websocket / SSE / polling) và ghi vào docs/architecture.md. -->

---

## 5. Verification

```bash
web/scripts/verify
```

<!-- TODO(WP5): điền lệnh thật — typecheck, lint, unit test, production build. Build phải nằm trong verify: một app typecheck sạch vẫn có thể fail lúc build. -->

---

## 6. Definition of Done

Standard **DONE (verified)** from the root `AGENTS.md`, plus: a UI change is
not done until it has been rendered and looked at. An agent that cannot render
the page reports what it changed and asks for a visual check — it does not
claim the UI is correct.

---

## 7. Hard Constraints

- No API token, DockerHub credential, or backend secret in frontend source or
  in a `VITE_*`/`NEXT_PUBLIC_*` style env var. Anything shipped to the browser
  is public.
- No control action (dispatch a robot, override an assignment, e-stop) without
  an explicit confirmation step.
- Do not commit `node_modules/` or build output.

<!-- TODO(WP5): thêm constraint khác khi có. -->
