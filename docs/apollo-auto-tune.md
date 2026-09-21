# Apollo Auto-Tune

## Investigation, 2026-09-19

The previous implementation started an isolated server per GPU candidate, but only
checked the app's own main-server handle. Other AgentFoundry instances and manually
started servers were invisible to that check. A forced kill was not followed by a
wait, and the next candidate could start before resources recovered. Server output
was discarded. Forge called any saved GPU/worker value VERIFIED, with no quality
assessment or configuration identity.

Read-only inspection of the target laptop found three llama-server processes
(PIDs 7080, 6848, 388), all configured for port 8080 and the same Qwen model.
Their commands requested 24, 6 and 6 GPU layers respectively, all at 32768 context
with `--no-kv-offload`. NVIDIA telemetry reported 8151 MiB total, 5984 MiB used
and 1908 MiB free. This is a concrete source of interference, not proof of the
cause of every historical slowdown. None of these processes was terminated.

The old tok/s value included prompt processing and HTTP overhead and used variable
completion lengths. It was not pure decode throughput. Historical numbers without
a fingerprint cannot validate a new run, especially across context changes.

## Controlled measurement

Both buttons run the complete pipeline: preflight, hardware/model checks, GPU
comparison, independent winner reload, temporary worker runtime, confidence check,
and a single atomic settings write. There is no manual Apply Best or worker-start
step. Automatic GPU candidates use the existing hardware recommendation and nearby
layer counts; an advanced override remains available under Show Details. This is
a bounded search, not a guarantee of the global optimum.

Preflight checks system-wide llama-server PIDs, the benchmark port, model existence
and GGUF magic, and available RAM/VRAM. Foreign processes are reported, never killed.
Every owned server is stopped and waited for, including forced termination and error
paths. RAM/VRAM must return close to the initial baseline before the next session:
at most 1 GiB RAM and 256 MiB VRAM below baseline, two consecutive observations,
with a 30-second recovery deadline. A runtime leaving less than 1 GiB RAM is rejected.
Unobservable memory/GPU data prevents VERIFIED.

GPU tests keep the configured context/KV settings unchanged, use a warmup, seed 42,
temperature zero, disabled prompt caching and a fixed output length. The response
must contain exactly the requested token count. Quick uses 96 tokens and one sample;
Deep uses 192 tokens and three samples. Worker tests use 1/2/4 concurrent requests
with 64 tokens/one cycle or 128 tokens/three cycles. Worker counts describe client
requests against the same runtime configuration, not separately tuned server slots.
The displayed metric is explicitly **end-to-end tok/s**. The llama.cpp request
extensions are documented in the [server API](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

## Confidence and persistence

- VERIFIED: complete successful Deep measurements, no GPU or worker spread above
  20%, winner reload within 20%, and complete telemetry.
- UNCERTAIN: Quick Tune, unstable measurements, incomplete candidate comparison,
  missing telemetry, or a >30% difference from a matching historical winner.
- RETEST REQUIRED: missing/invalid results, failed pipeline, changed identity,
  cancellation, or legacy measurements without identity.

These thresholds are conservative heuristics, not statistical confidence intervals.
Only VERIFIED results change the active configuration. Provisional results retain
their measurements and explanation but leave the current profile unchanged.

The settings file stores the full selected profile, worker count, confirmation
throughput, per-run GPU samples, worker summary, confidence explanation, baseline
memory, and fingerprint together. Startup validates identity in a background thread
before restoring an accepted configuration. Changes to the current profile invalidate
the visible verification state immediately. UI changes while tuning reject its result.

The fingerprint covers CPU/GPU/RAM, NVIDIA UUID/VRAM/driver, model path/size/mtime,
runtime executable and DLL paths/sizes/mtimes, relevant environment variables,
context/KV/RoPE/reasoning configuration, and benchmark protocol revision. GPU layer
selection is stored and checked separately. Model quantization is reported as a
filename hint; identity uses the exact file metadata, not that hint. It is not a
full model content hash and cannot detect a replacement preserving path, size and
timestamp. A changed runtime build normally changes executable/DLL metadata; a
human-readable runtime version and parsed GGUF metadata remain future refinements.

The UI reports elapsed time, current phase/run, latest throughput and available
memory. Expandable details include captured server diagnostics. Cancellation waits
for an in-flight request to finish or time out before cleaning up the owned process;
closing the app waits for that cleanup too.

## Validation and limits

Automated tests cover confidence, identity changes, foreign processes, port conflicts,
memory recovery, forced-kill reaping, worker failures, cancellation, and Tk save/error
callbacks. Tests use temporary settings and mocked runtimes, never the user's model
or saved configuration. Tk tests skip when no display is available.

A real GPU/worker benchmark is intentionally not run while the three existing
servers occupy the machine. Close those workloads and use Deep Benchmark for a new
measurement. No 12/16/20/24-layer configuration is claimed as the hardware winner.
This work does not change Trading Pack risk gates or PAPER ONLY operation.
