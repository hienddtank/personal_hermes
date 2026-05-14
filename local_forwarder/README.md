# Local Forwarder

`local_forwarder.py` at the repository root is kept as a compatibility wrapper.
The implementation lives in this package and can also be started with:

```powershell
python -m local_forwarder
```

Module map:

- `config.py`: host, port, allowed roots, Codex defaults, Docker Compose defaults, log paths.
- `utils.py`: small shared helpers for timestamps, decoding, paths, and route normalization.
- `request_logging.py`: inbound request audit logs and retention pruning.
- `codex.py`: Codex request validation, command construction, and result payloads.
- `bridge.py`: direct Windows host script execution without going through `codex exec`.
- `jobs.py`: async Codex job storage, process streaming, and polling payloads.
- `compose.py`: Docker Compose service discovery and start/stop/restart actions.
- `docs.py`: help and OpenAPI response builders.
- `health.py`: health and diagnostics response builder.
- `handler.py`: HTTP route handling.
- `server.py`: startup logging and `ThreadingHTTPServer` launch.
