# AGENTS.md — `backend/`

> **STATUS: STACK DECIDED, NOT SCAFFOLDED YET.** Solution/projects have not
> been created (`dotnet new` not run). This file records the decisions so
> whoever scaffolds it (agent or human) follows the same structure. Delete
> this banner once the solution exists and Section 2 reflects the real tree.

Booking, tour scheduling and multi-robot dispatch API for CampusTour DT-AMR
(Work Package 2). Read the repo-root `AGENTS.md` first for the shared rules;
this file only covers what is specific to `backend/`.

---

## 1. Stack

- Language / runtime: **C# / .NET 10 (LTS)**.
- Framework: **ASP.NET Core Web API** (controller-based, not Minimal API).
- Database: **SQL Server**.
- ORM: **Entity Framework Core**, code-first, migrations checked into
  `src/CampusTour.Infrastructure/Persistence/Migrations/`.
- Architecture style: **Clean Architecture**, not DDD — no aggregates, domain
  events, or value-object-heavy modelling unless a task explicitly asks for
  it. Entities are plain, services hold behaviour.
- Local run: <!-- TODO(WP2): connection string source (User Secrets / appsettings.Development.json / env var), and the exact `dotnet run` / docker compose command once scaffolded. -->

---

## 2. Layout

Planned structure — **4 separate `.csproj` per layer** in one solution, not
folders inside one project. Dependencies point inward only (API ->
Infrastructure/Application -> Domain; nothing points back out to API).

```
backend/
├── CampusTour.sln
├── src/
│   ├── CampusTour.Domain/          entities, enums, domain exceptions.
│   │                                No dependency on any other project.
│   ├── CampusTour.Application/     use cases / services, interfaces
│   │                                (IRepository, IEmailSender, ...).
│   │                                Depends on Domain only.
│   ├── CampusTour.Infrastructure/  EF Core DbContext, migrations,
│   │                                repository implementations, external
│   │                                service clients. Depends on Application
│   │                                + Domain.
│   └── CampusTour.Api/             controllers, DI wiring, Program.cs,
│                                    appsettings. Depends on all three.
├── tests/
│   ├── CampusTour.Application.Tests/       unit tests, xUnit
│   ├── CampusTour.Api.Tests/                unit tests, xUnit
│   └── CampusTour.Infrastructure.IntegrationTests/  <!-- TODO(WP2): tên/tồn tại tùy quyết định integration test ở mục 4 -->
└── scripts/verify
```

<!-- TODO(WP2): once `dotnet new` has been run for real, replace this planned
tree with the actual one (exact folder names inside each project, e.g.
Domain/Entities, Application/Common/Interfaces, etc.) and delete this note. -->

---

## 3. Architecture Rules

Clean Architecture, dependencies point inward only:

```
CampusTour.Api
    v
CampusTour.Infrastructure  --\
    v                         > both depend on
CampusTour.Application     --/
    v
CampusTour.Domain
```

- `Domain` has zero project references. No EF Core, no ASP.NET, no external
  package beyond the BCL. Plain entities, enums, and domain exceptions only.
- `Application` defines interfaces (`IFooRepository`, `IClock`, ...) and the
  use-case/service classes that implement business logic. It must not
  reference EF Core, ASP.NET Core, or any HTTP-specific type — only
  `Domain` and abstractions.
- `Infrastructure` implements the `Application` interfaces: EF Core
  `DbContext`, entity configurations, repository classes, external service
  clients (email, storage, ROS bridge client, ...). Query construction lives
  here only, never in `Application`.
- `Api` is composition + transport: controllers, DTOs, DI registration
  (`Program.cs`), model validation, HTTP status mapping. Controllers must not
  contain business logic and must not touch `DbContext` or EF Core types
  directly — they call into `Application` services through an interface.
- A new feature adds a service in `Application` and, if it needs persistence,
  an interface in `Application` + implementation in `Infrastructure`. Do not
  reach from `Api` straight into `Infrastructure`.

Scheduling / dispatch specifically:

- The robot-assignment algorithm (which robot takes which tour, when) lives in
  an **`Application` service** — e.g. `DispatchService`. It fetches robots and
  bookings through repository interfaces and returns the decision. Do not put
  it in a controller, a repository, or the ROS bridge.
- The fleet bridge client (the thing that actually talks to the robot over
  REST/gRPC) is **`Infrastructure`**, behind an `Application` interface such as
  `IFleetGateway`. `Application` code calls the interface, never an HTTP/gRPC
  client directly.
- **A controller must never call the bridge directly.** The path is always
  `Api -> Application service -> IFleetGateway -> Infrastructure`, even for a
  one-line "send this command" endpoint.

---

## 4. Testing Strategy

- Unit test framework: **xUnit**.
- Mock/assertion library: <!-- TODO(WP2): chưa chốt. Ứng viên: Moq + FluentAssertions, hoặc NSubstitute + FluentAssertions, hoặc xUnit thuần (Assert.*). Chốt khi bắt đầu viết test đầu tiên. -->
- Layout: `tests/CampusTour.Application.Tests/` covers `Application` services
  (mock the repository interfaces, no real database). `tests/CampusTour.Api.Tests/`
  covers controllers/HTTP concerns (status codes, validation, routing) —
  mock `Application` services, do not hit a real database here either.
- Integration tests (real EF Core against real SQL Server, not mocked):
  <!-- TODO(WP2): chưa chốt cách chạy. Ứng viên: Testcontainers (SQL Server
  container thật, chính xác nhất nhưng cần Docker trong môi trường verify/CI)
  vs. EF Core In-Memory provider (nhanh, không cần Docker, nhưng không bắt
  được lỗi đặc thù SQL Server: constraint, index, raw SQL). Chốt khi biết
  môi trường CI có Docker hay không, rồi ghi rõ project test riêng (ví dụ
  `tests/CampusTour.Infrastructure.IntegrationTests/`) và cách nó chạy trong
  `backend/scripts/verify`. -->
- No coverage threshold for now — `dotnet test` passing is the bar. Revisit
  if/when the team wants a minimum coverage gate.
- A new service or controller change ships with tests in the same PR. Do not
  add "TODO: write tests" — write them or say explicitly why not.

---

## 5. Authentication

Contract with `web/` (see `web/AGENTS.md`) — decided, details TBD:

- **JWT access token + refresh token in an HttpOnly cookie.**
- Access token: short-lived, returned in the login response body, sent by the
  client as `Authorization: Bearer <token>`. Carries the user's role
  (`staff`/`ops`/visitor, etc.) as a claim so the frontend can gate `/admin/*`
  without an extra round trip.
- Refresh token: long-lived, issued as an **HttpOnly, Secure** cookie — the
  API sets it via `Set-Cookie`, never returns it in a JSON body. A dedicated
  refresh endpoint reads the cookie and issues a new access token.
- Password storage: hash with a modern algorithm (BCrypt or ASP.NET Core
  Identity's default) — never plaintext, never a fast general-purpose hash
  (MD5/SHA1/SHA256 alone).
- Token lifetimes: access token **15 minutes**, refresh token **7 days**.
- Claims on the access token: **`sub` (user id) and `role` only** — no
  display name, email, or other PII in the JWT payload. If the frontend needs
  a display name, it fetches that separately (e.g. a `/api/auth/me` call),
  not from the token.
- Endpoints: `POST /api/auth/login` (returns access token in the body, sets
  the refresh token as an HttpOnly cookie), `POST /api/auth/refresh` (reads
  the refresh cookie, returns a new access token), `POST /api/auth/logout`.
- Logout/revocation: **server-side revocation, not just cookie deletion.**
  Refresh tokens are persisted (e.g. a `RefreshTokens` table/entity — token
  hash, user id, expiry, revoked flag — schema change needs an ADR per
  Section 9). `POST /api/auth/logout` marks the presented refresh token as
  revoked in storage, then clears the cookie. `POST /api/auth/refresh` must
  reject a revoked or unknown token even if it has not yet expired. This
  means a stolen refresh token can be invalidated by the legitimate user
  logging out, instead of staying valid until its 7-day expiry.
- Store a hash of the refresh token (not the raw token) — same reasoning as
  password storage: a DB leak should not hand out usable tokens.

---

## 6. Interface with the robot fleet

The robot side (`robot/`) is a separate deploy unit maintained by WP3. Any
change to the telemetry the backend consumes or the commands it sends is a
**contract change**: update `docs/architecture.md` in the same PR and tell WP3.

The backend does **not** speak ROS. It talks to a thin bridge node that lives
in `robot/` and translates to ROS 2 on the other side — full topology in
`docs/architecture.md` §3. For the backend that means:

- One `Application` interface (`IFleetGateway` or similar) describes what the
  fleet can do — send a tour assignment, cancel, read last-known state. Its
  implementation in `Infrastructure` is the REST/gRPC client for the bridge.
- Do not add ROS concepts (topic names, action names, message types) to
  `Domain` or `Application`. They stop at the `Infrastructure` boundary.
- Treat the robot as unreliable: it can be offline, slow, or mid-reboot. A
  dispatch call that cannot reach a robot must fail the booking cleanly, not
  hang a request thread or leave a half-assigned booking in the database.

<!-- TODO(WP2+WP3): chốt wire protocol (REST vs gRPC), auth cho kênh điều
khiển robot, và schema telemetry/command — rồi ghi vào docs/architecture.md §3
trước khi code hai đầu. -->

---

## 7. Verification

```bash
backend/scripts/verify
```

Order once scaffolded: `dotnet restore` -> `dotnet build -warnaserror` ->
`dotnet test` -> (if migrations exist) `dotnet ef migrations has-pending-model-changes`
or equivalent check that no model change is missing a migration.

<!-- TODO(WP2): once CampusTour.sln exists, replace the SKIPPED branch in
backend/scripts/verify with these real dotnet commands. -->

---

## 8. Definition of Done

Standard **DONE (verified)** from the root `AGENTS.md`. The backend has no
tier-3 hardware step — if a change is fully covered by tests and
`backend/scripts/verify` passes, it is DONE.

Exception: anything that sends commands to a real robot. That is tier 3 and
must be reported as READY FOR HARDWARE TEST.

---

## 9. Hard Constraints

- Do not change the database schema without an ADR in `docs/decisions/`.
- Do not weaken authentication on robot-control endpoints. An unauthenticated
  path that can move a robot is a safety bug, not a convenience.
- Visitor personal data (name, contact, booking history) must never appear in
  logs or in an error response body.

<!-- TODO(WP2): thêm constraint khác khi có. -->
