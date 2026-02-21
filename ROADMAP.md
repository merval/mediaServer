# MediaServer Plan Forward

This roadmap turns the current prototype into a scalable media platform with robust ingestion, adaptive streaming, and synchronized group viewing.

## Guiding decisions

- **Keep Python** as the control plane for cataloging, metadata enrichment, APIs, and session orchestration.
- Use **FFprobe/FFmpeg** for media inspection/transcoding rather than custom parsing logic.
- Adopt **HLS** for broad playback compatibility and adaptive bitrate streaming.
- Build watch parties with **real-time state sync** (WebSockets) and server-authoritative playback state.

---

## Phase 0 — Stabilize foundations (1 week)

### Goals
- Make configuration and data access production-safe.
- Remove hardcoded keys and in-memory catalog assumptions.

### Deliverables
1. **Configuration module**
   - Load TMDB key and runtime settings from environment variables.
   - Validate required settings at startup.
2. **Database integration in app layer**
   - Replace hardcoded home-page library data with database-backed queries.
3. **Basic API surface**
   - `/api/library/movies`
   - `/api/library/shows`
   - `/api/library/media-files`
4. **Logging and errors**
   - Structured logging for scanner and metadata enrichment.

### Exit criteria
- App starts with explicit config checks.
- UI/API can render records persisted in DB without hardcoded catalogs.

---

## Phase 1 — Ingestion overhaul (2 weeks)

### Goals
- Turn scanner into reliable technical metadata ingestion.
- Support accurate format/quality detection.

### Deliverables
1. **Single-pass ffprobe ingestion**
   - Parse `format` + all `streams` once per file.
   - Extract container, bitrate, duration, codecs, resolution, fps, channels, sample rate, subtitle tracks.
2. **Schema upgrades**
   - Extend `MediaFile` fields for core technical metadata.
   - Add stream-level table(s) for video/audio/subtitle stream details.
3. **Idempotent indexing**
   - Upsert behavior by path + content signature (mtime/size hash).
4. **Metadata enrichment hardening**
   - Confidence-based TMDB matching using title/year/episode cues.
   - API backoff + lightweight local cache.

### Exit criteria
- Scanner captures meaningful quality attributes.
- Re-running scanner does not duplicate records.

---

## Phase 2 — Playback pipeline (2–3 weeks)

### Goals
- Deliver smooth, compatible, adaptive streaming.

### Deliverables
1. **Playback service**
   - Source media registration and profile selection (direct play vs transcode).
2. **HLS generation strategy**
   - Start with VOD pre-processing for a subset of files.
   - Generate master playlist + renditions (e.g., 360p/720p/1080p).
3. **Serving layer**
   - Secure access to manifests/segments via short-lived playback tokens.
4. **Player integration**
   - Web player switches to HLS playback path.

### Exit criteria
- Clients can stream at least one title using adaptive HLS renditions.
- Playback works on major browsers with stable seeking.

---

## Phase 3 — Shared viewing sessions (2 weeks)

### Goals
- Enable simple multi-user synchronized watch sessions.

### Deliverables
1. **Session model**
   - `watch_session` entity: host, media_id, status, current_time, playback_state, updated_at.
   - Participant membership table.
2. **Real-time sync channel**
   - WebSocket events: `join`, `leave`, `play`, `pause`, `seek`, `state_sync`.
3. **Authority + conflict policy**
   - Host-controlled by default.
   - Optional collaborative mode later.
4. **Drift correction**
   - Clients periodically reconcile against server-authoritative timestamp.
5. **Join UX**
   - Session link/code for one-click entry.

### Exit criteria
- 2+ users can join one session and stay synced through play/pause/seek.

---

## Phase 4 — Reliability and scale (ongoing)

### Goals
- Improve performance, observability, and operational safety.

### Deliverables
1. **Background jobs**
   - Move scanning/transcoding into worker queue.
2. **Storage/CDN strategy**
   - Segment storage abstraction + cache headers.
3. **Observability**
   - Metrics: scan throughput, transcode queue depth, session concurrency, playback errors.
4. **Security hardening**
   - Tokenized playback URLs, authn/authz checks, rate limiting.

---

## Technical choices (recommended)

- **Backend:** Flask (current) + SQLAlchemy.
- **Queue:** RQ or Celery for scan/transcode jobs.
- **Media tooling:** FFprobe + FFmpeg.
- **Realtime:** Flask-SocketIO (initial), optional migration to dedicated realtime service later.
- **Playback:** HLS with hls.js on web.

---

## MVP cut (first shippable milestone)

Target scope:
1. DB-backed library API + UI.
2. Enhanced scanner with ffprobe stream metadata.
3. One-title HLS playback path.
4. Host-controlled watch session with sync for play/pause/seek.

Success metric:
- Two users on separate browsers can join a session and remain within ±1 second sync during normal interactions.

---

## Proposed implementation order for next 10 working days

1. **Day 1–2:** Config cleanup + DB-backed read APIs.
2. **Day 3–4:** ffprobe scanner refactor and schema migration.
3. **Day 5–6:** Metadata matcher hardening + cache.
4. **Day 7–8:** HLS pipeline and secure manifest/segment serving.
5. **Day 9–10:** WebSocket watch sessions + basic synchronized controls.

