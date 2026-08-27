# AI Tour-Guide Assistant

WP4 deploy unit for the visitor-facing conversational assistant. It owns the
multilingual speech and dialogue pipeline:

```text
visitor speech -> STT -> campus knowledge/dialogue -> TTS -> spoken response
```

## Boundary with robot perception

This service is not `robot_perception`.

| `robot_perception` (WP3) | `ai-assistant/` (WP4) |
|---|---|
| Detects people from RGB-D | Understands visitor speech |
| Publishes people poses and Nav2 speed limits | Produces narration and answers |
| Runs on the robot miniPC | Runs on a server/cloud runtime |
| May influence navigation speed | Has no robot motion authority |

The robot miniPC is limited to an i3-7100T and 8 GB RAM while already running
Nav2 and perception. The heavy STT, retrieval/dialogue and TTS pipeline must
therefore not be added to the robot runtime. A future thin adapter under
`robot/` may handle ROS stop events, audio I/O and cached narration.

## Status

**Not started.** The runtime stack and robot/backend integration contract are
not decided. Define the transport, schemas, authentication, timeouts and
offline fallback in `docs/architecture.md` before implementing either side.

## Verification

```bash
ai-assistant/scripts/verify
```

The script currently returns `SKIPPED` until source and a real verification
pipeline are added.
