# AGENTS.md — `web/`

> **STATUS: STACK DECIDED, NOT SCAFFOLDED YET.** No app has been created yet
> (`npm create vite` not run). This file records the decisions so whoever
> scaffolds it (agent or human) follows the same structure. Delete this
> banner once the app exists and Section 2 reflects the real tree.

Visitor booking app and operations dashboard for CampusTour DT-AMR (Work
Package 5). Read the repo-root `AGENTS.md` first for the shared rules; this
file only covers what is specific to `web/`.

---

## 1. Stack

- Language: **TypeScript**. No plain `.jsx`/`.js` for app source.
- Framework: **React + Vite**.
- Styling: **Tailwind CSS**.
- Server state (data fetched from the backend API): **TanStack Query**.
- Client/UI state (filters, selected robot, modal open/closed, etc.):
  **Zustand**. Do not put server data (bookings, robot status, ...) in
  Zustand — that belongs to TanStack Query's cache.
- Package manager: **npm** (no workspaces needed — see below).
- Codebase shape: **one app, one deploy**. Visitor booking (public) and ops
  dashboard (staff-only) live in the same React app, same Vercel project,
  same domain. They are split by route + role, not by separate apps:
  - `/` and public routes: visitor booking flow, no login required.
  - `/admin/*`: ops dashboard, behind auth. A route guard checks the logged-in
    user's role and redirects to login (or a 403 page) if they lack the
    `staff`/`ops` role. Never hide `/admin/*` by UI alone (e.g. just not
    showing a nav link) — the guard must actually block navigation.
  - `/admin/*` is **lazy-loaded** (`React.lazy` + route-based code splitting)
    so a visitor loading `/` never downloads dashboard code, and vice versa
    for a staff member going straight to `/admin`.
- Local run + backend URL: <!-- TODO(WP5): once scaffolded, fill in the exact
  `npm run dev` command and which env var carries the backend base URL (e.g.
  `VITE_API_BASE_URL`). -->
- Auth mechanism: **JWT access token + refresh token in an HttpOnly cookie**.
  - Access token: short-lived JWT, sent in the `Authorization: Bearer` header
    on every API request. Carries the user's role (`staff`/`ops`/etc.) as a
    claim — the `/admin/*` route guard reads the role from the decoded token,
    not from a separate call.
  - Refresh token: long-lived, stored in an **HttpOnly, Secure** cookie (not
    readable by JS, mitigates XSS token theft). Used to silently obtain a new
    access token when the old one expires, without forcing re-login.
  - Never store the access token in `localStorage`/`sessionStorage` if it can
    be avoided — prefer an in-memory store (e.g. the TanStack Query/Zustand
    auth store) so a page reload re-derives it via the refresh cookie.
  - Token lifetimes: access token **15 minutes**, refresh token **7 days**
    (cookie, set by the backend — the frontend never reads or sets it
    directly).
  - Claims on the access token: **`sub` (user id) and `role` only**. If a
    display name or email is needed in the UI, fetch it separately (e.g.
    `GET /api/auth/me`) — do not decode the JWT for anything beyond `role`
    (and `sub` if needed for cache keys).
  - Endpoints: `POST /api/auth/login`, `POST /api/auth/refresh`,
    `POST /api/auth/logout`.
  - Logout: call `POST /api/auth/logout` (revokes the refresh token
    server-side — see `backend/AGENTS.md` Section 5), then clear local
    in-memory auth state and redirect to the public app. Do not treat
    "clear local state" alone as logout — always call the endpoint first, or
    a stolen refresh token from that session stays valid.

---

## 2. Layout

Planned structure — a single Vite + React app, split internally by route:

```
web/
├── package.json
├── src/
│   ├── routes/
│   │   ├── public/            visitor booking flow ("/")
│   │   └── admin/              ops dashboard ("/admin/*"), lazy-loaded
│   ├── components/             shared UI components used by both areas
│   ├── api/                    the one API client module (Section 3)
│   ├── auth/                   route guard, role check, login flow
│   └── ...
└── scripts/verify
```

<!-- TODO(WP5): once scaffolded for real, replace this planned tree with the
actual one and delete this note. -->

---

## 3. Development Rules

- All backend access goes through one API client module. No `fetch` scattered
  through components.
- No business rule is reimplemented in the frontend. If the dashboard needs a
  computed value (robot utilisation, ETA, wait time), the backend returns it.
- The ops dashboard is used by campus staff with no robotics background: a
  robot state shown to them must be a plain-language label, not a raw ROS enum.
- Server data goes through TanStack Query hooks (`useQuery`/`useMutation`),
  never a raw `useEffect` + `fetch`/`useState` combo.
- Any route under `/admin/*` must be wrapped by the role-checking route
  guard. A new admin page is not done until it is behind the guard — do not
  rely on "nobody will guess the URL".
- Zustand stores are for client-only state. If you find yourself caching
  server data in a Zustand store, it belongs in TanStack Query instead.
- Styling is Tailwind utility classes in JSX. Avoid a separate CSS file per
  component unless Tailwind genuinely cannot express it (e.g. a keyframe
  animation).

<!-- TODO(WP5): thêm rule về component structure (folder-by-feature vs
folder-by-type) khi bắt đầu viết component đầu tiên. -->

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

Order once scaffolded: `npm run typecheck` -> `npm run lint` ->
`npm run test` -> `npm run build`. Build must be part of verify — a clean
typecheck can still fail at build time.

<!-- TODO(WP5): once the app exists, replace the SKIPPED branch in
web/scripts/verify with these real npm commands. -->

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
