# Roadmap – Azure Foundry Claude Proxy (OpenAI-Compatible)

This roadmap outlines planned enhancements for the proxy, focusing on keeping full OpenAI API compatibility while extending capabilities for real-world use.

## 1. Multi-tenant configuration and routing (Completed)

1.1 Per-request tenancy via standard OpenAI fields  
- Implemented: the proxy now uses `baseUrl` + `apiKey` + `model` as the sole multi-tenant interface:
  - `apiKey` (optionally `resource:key`) and/or `model` (`resource/model`) are decoded per request to derive Foundry `resource`, `model`, and `api_key`.  
- Unknown or unsupported combinations result in clear, OpenAI-style error responses.

1.1.1 No central Foundry config  
- Implemented: there is no central registry or env-based Foundry config; all Foundry credentials and routing information are supplied via `apiKey` + `model`.  
- Env is only used for proxy behavior flags (e.g., `PROXY_DEBUG`, `HOST`, `PORT`, `DEV_DEFAULT_LOGICAL_API_KEY`).

1.2 Optional advanced overrides (headers/URL)  
- Not yet implemented; remains a possible future enhancement.  
- Any future headers or URL-based overrides must remain strictly optional; standard OpenAI clients using only `baseUrl`, `apiKey`, and `model` already get full functionality.

1.3 Safe defaults and access control  
- Not yet implemented; future work may add allowlists/denylists and quotas per logical `apiKey`/resource.

1.4 VS Code-specific configuration patterns  
- Implemented: README documents concrete examples for:
  - `github.copilot.chat.customOAIModels` in VS Code.  
  - Continue extension OpenAI-compatible provider `config.yaml` entries using only `baseUrl`, `apiKey`, and `model`.

## 2. WebUI for configuration and usage stats (Completed)

2.1 WebUI surface  
- Implemented: `/admin` router serves a rich HTML/CSS/JS dashboard with navigation to dashboard, users, metrics, config, and logs. Dashboard shows uptime, req/error counts, users, and latency cards; users table supports search, pagination, detail drawer, enable/disable/reset/delete with token copy; metrics table + req/error + latency charts (poll-based).

2.2 Authentication and security  
- Implemented: HTTP Basic auth with bcrypt hashes; `/admin` isolated from `/v1/*`; admin disabled by default and gated by env flags.

2.3 Configuration editing  
- Implemented (minimal): versioned config store for safe fields (`default_model`, `default_resource`, `flags`) with `/admin/config` GET/POST, optional persistence file.

2.4 User authentication management  
- Implemented: optional proxy auth tokens (`X-Proxy-Token` or `token:model`) enforced via env flag; tokens stored hashed with `/admin/users` CRUD; proxy auth separated from `/v1/*` and admin Basic auth; user metadata (email/display name), enable/disable, reset token, and last-used tracking supported.

2.5 Admin events/logs  
- Implemented: in-memory admin event log with optional file persistence (`ADMIN_EVENTS_FILE`) and NDJSON download endpoint + UI control; logs surface user/config/metrics actions in the `/admin` Logs view.

## 3. HTTPS termination and TLS automation

3.1 Built-in HTTPS support  
- Add optional HTTPS termination directly in the proxy:
  - Support `--certfile` / `--keyfile` configuration (or env vars) for uvicorn-based TLS.  
  - Keep HTTP-only mode as the default for localhost/dev, with HTTPS recommended for remote access.

3.2 Let's Encrypt integration  
- Provide a documented path to use Let's Encrypt for certificates:
  - Either via a lightweight ACME client in the proxy or via integration with a reverse proxy (e.g., Caddy, nginx, Traefik).  
  - Automate certificate renewal where feasible, or clearly document external automation.

3.3 Reverse proxy guidance  
- Document recommended deployments with a fronting reverse proxy that:
  - Terminates TLS using Let's Encrypt.  
  - Forwards HTTPS traffic to the proxy’s HTTP port (e.g., 18000).  
- Emphasize that the OpenAI API surface and URLs remain the same (`/v1/...`), only the scheme/port change.

## 4. Dockerization and deployment profiles

4.1 Official Docker image  
- Create a Dockerfile that:
  - Uses a slim Python base image.  
  - Installs dependencies via `requirements.txt`.  
  - Runs `uvicorn foundry_openai_proxy:app --host 0.0.0.0 --port 18000`.  
- Document environment variables for container deployments:
  - `PROXY_DEBUG`, `HOST`, `PORT`, `DEV_DEFAULT_LOGICAL_API_KEY`.

4.2 Example deployment templates  
- Provide example manifests for:
  - Docker Compose.  
  - Kubernetes (simple Deployment/Service), if useful.  
- Ensure health/readiness probes do not interfere with OpenAI routes.

4.3 Versioning and tags  
- Define a simple versioning scheme for images (e.g., `v0.1.0`, `latest`).  
- Consider separate tags for:
  - Stable vs. experimental builds.  
  - CPU vs. GPU-optimized (if workload justifies it).

## 5. Extended OpenAI endpoint support (Completed)

5.1 Embeddings  
- Implemented: `/v1/embeddings` added, maps OpenAI embeddings request to Foundry OpenAI-style endpoint, returns standard embeddings + usage, explicit not-supported error when unavailable.

5.2 Moderations and other endpoints  
- Implemented: `/v1/moderations` returns an OpenAI-style `not_supported_error` by default (no compatible Foundry endpoint); optional forwarding to Content Safety left for future opt-in.

5.3 Batch and tools enhancements  
- Implemented: batch guardrails (array payloads rejected to preserve single-request semantics) and tool bridge expanded beyond `read_file` to support `write_file` and `search` tags/schema. Sequential batch processing intentionally not enabled.

## 6. Observability and resilience

6.1 Metrics and logging improvements  
- Partially implemented: per-route counts, errors, token usage, and latency (avg/p50/p95/p99) recorded; surfaced via `/admin` APIs and dashboards with charts.  
- TODO: optional structured logging (JSON) and Prometheus-style `/metrics` export for external ingestion.

6.2 Retry and timeout policies  
- Introduce configurable timeouts and limited retry logic for upstream Foundry calls.  
- Surface timeout/retry events to logs while still returning OpenAI-style error responses.

6.3 Request IDs and tracing  
- Generate a per-request ID and include it in:
  - Logs (`dlog` records).  
  - Error responses (e.g., in an `x-request-id` header) to aid debugging.

## 7. Developer experience and testing

7.1 Automated tests  
- Partially implemented: pytest coverage for embeddings/moderations, tool parsing, admin enablement/disablement, and proxy auth enforcement. Additional coverage for `/v1/chat/completions`, `/v1/completions`, `/v1/models`, and config validation still recommended.

7.2 Local dev tooling  
- Provide convenience scripts or Make targets for:
  - Running tests.  
  - Starting the proxy with common configs.  
  - Formatting/linting, if desired.

7.3 Example clients  
- Add small examples showing how to point:
  - OpenAI Python SDK.  
  - curl / HTTP clients.  
  - Popular OpenAI-compatible tools (LM Studio, etc.)  
  at the proxy, emphasizing that no client changes are required.

7.4 Admin smoke walkthrough  
- Implemented: manual smoke checklist for `/admin` flows (users, metrics, logs/download, config) in `tests/ADMIN_SMOKE.md`; automated UI tests still optional future work.

## 8. Backwards compatibility and versioning

8.1 API stability  
- Maintain strict compatibility with OpenAI request/response shapes for existing routes.  
- If breaking changes become necessary, introduce them behind:
  - Versioned routes (e.g., `/v1beta`) or  
  - Explicit configuration flags.

8.2 Deprecation strategy  
- Document any deprecated behaviors (e.g., legacy tag formats) and provide timelines for removal.  
- Ensure deprecations are opt-in or well signposted to avoid surprising existing clients.
