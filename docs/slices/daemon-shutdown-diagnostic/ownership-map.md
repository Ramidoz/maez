# Daemon Shutdown Thread Ownership Map

Status: DIAGNOSTIC ONLY
Date: 2026-05-14
Scope: map surviving shutdown thread families to likely library owners before patching shutdown behavior.

## Question

Which libraries own the thread families that survive `maez.service` SIGTERM?

Answer: the dominant families map to ChromaDB Rust bindings, MediaPipe, OpenCV, and ordinary Python thread contexts that native libraries inherit. The earlier surface labels are useful clues, but not sufficient proof of ownership.

## Evidence Summary

Live process thread histogram after the restart:

```text
160 tokio-rt-worker
 33 reasoning-loop
 32 presence-observ
 32 python
 16 sqlx-sqlite-wor
 14 mediapipe/<pid>
```

Loaded native libraries include:

```text
chromadb_rust_bindings/chromadb_rust_bindings.abi3.so
tokenizers/tokenizers.abi3.so
mediapipe/tasks/c/libmediapipe.so
cv2/cv2.abi3.so
onnxruntime/capi/onnxruntime_pybind11_state...
```

Native-symbol scan:

```text
chromadb_rust_bindings: tokio-1.50.0, sqlx-core-0.8.6, sqlx-sqlite-0.8.6, rayon-core
tokenizers: tokio-1.52.1, rayon, pyo3_async_runtimes
mediapipe: MpFaceDetectorClose, MpFaceDetectorCloseResult, pthread_create, pthread_join
cv2: setNumThreads, getNumThreads, OpenCVThread, ThreadPool
```

Local introspection:

```text
mediapipe FaceDetector methods: close(), __enter__(), __exit__()
chromadb PersistentClient client methods: close(), reset(), clear_system_cache()
chromadb Rust backend methods: stop(), reset_state()
cv2.getNumThreads(): 32
```

## Owner Map

| Thread family | Likely owner | Confidence | Why |
| --- | --- | --- | --- |
| `tokio-rt-worker` | ChromaDB Rust bindings, with tokenizers as possible secondary source | High for Chroma; medium for tokenizers | `chromadb_rust_bindings.abi3.so` carries Tokio and SQLx symbols. `tokenizers.abi3.so` also carries Tokio/Rayon symbols, but the paired `sqlx-sqlite-wor` threads point strongly at Chroma. |
| `sqlx-sqlite-wor` | ChromaDB Rust bindings | High | `chromadb_rust_bindings.abi3.so` contains `sqlx-core`, `sqlx-sqlite`, and Chroma Rust SQLite paths. No standalone Python `sqlx` package is installed. |
| `mediapipe/<pid>` | MediaPipe C++ task runtime | High | `libmediapipe.so` is loaded and exposes explicit `MpFaceDetectorClose`. |
| `presence-observ` | Native children spawned under the presence-observation Python thread, likely MediaPipe/OpenCV | Medium | The name matches Maez's bounded worker context, but `BoundedSingletonWorker` cannot create 32 Python workers. The count fits OpenCV's default `cv2.getNumThreads() == 32`. Treat as inherited context label, not Maez pool ownership. |
| `reasoning-loop` | Native children spawned under the reasoning-loop Python thread, likely ChromaDB / vector work | Medium | The main Python reasoning thread is one thread. The extra 32 same-name threads are likely native child threads inheriting the parent thread name while memory/vector work runs inside the loop. |
| `python` | Process-main/native thread pools initialized before custom Python thread names | Medium | 32 count again matches OpenCV thread default; also may include native pools initialized on the main thread before named Python worker contexts. |

## Chroma Lifecycle Finding

ChromaDB clients are not opaque: local introspection shows `PersistentClient` has a public `close()` method, and its Rust backend exposes `stop()`.

Maez creates Chroma clients in multiple places:

```text
memory/memory_manager.py: raw, daily, core clients
daemon/maez_daemon.py: _get_public_context() per-call client
skills/telegram_public.py: UserProfileStore long-lived client
skills/telegram_voice.py: public-context per-call client
skills/user_accounts.py: sync helper client
```

The strongest shutdown hypothesis is that some clients are either long-lived and never closed, or created as "temporary" clients and never closed. Each Chroma system can own Tokio/SQLx workers, so even a small number of leaked clients can explain the 160 `tokio-rt-worker` family.

## Presence Lifecycle Finding

`skills/presence_perception.py` creates one persistent MediaPipe detector:

```text
_detector = mp_vision.FaceDetector.create_from_options(options)
```

The detector is deliberately kept open forever:

```text
# detector stays open (persistent)
```

But MediaPipe exposes `FaceDetector.close()`, and the implementation calls:

```text
MpFaceDetectorClose(...)
_dispatcher.close()
_lib.close()
```

So the presence organ has an explicit cleanup hook available; Maez currently does not call it.

OpenCV also defaults to 32 worker threads in this process. That exactly matches the 32-count thread families and supports the interpretation that `presence-observ` is a native thread-pool label inherited from the bounded presence worker, not 32 Maez Python workers.

## Uncertainty Boundaries

- Do not say "32 presence workers leaked." The architecture rules that out. Say "32 native threads were observed with the presence-observation context name."
- Do not say tokenizers is innocent. It carries Tokio/Rayon symbols. Say Chroma is the stronger owner for the observed SQLx/Tokio pair.
- Do not say Chroma close alone will fix SIGTERM. MediaPipe and OpenCV also have explicit lifecycle concerns.
- Do not patch thread owners by name. Patch library lifecycle boundaries: close clients, close detectors, reduce or close native pools where the library provides APIs.

## Fix Shape Suggested By The Map

The next implementation slice should be small and engineering-only:

1. Add a `MemoryManager.close()` that closes `_raw_client`, `_daily_client`, and `_core_client`.
2. Close temporary Chroma clients in `daemon._get_public_context()` and `skills.telegram_voice` public-context reads with `try/finally`.
3. Add `UserProfileStore.close()` and call it from `MaezPublicBot.stop()`.
4. Add `presence_perception.shutdown()` that closes the persistent MediaPipe detector and releases OpenCV window/thread state best-effort.
5. Call presence shutdown and memory close in `MaezDaemon.stop()` after surfaces stop submitting work.
6. Re-test SIGTERM. Success criterion: `systemctl --user stop maez.service` exits before systemd timeout without SIGKILL.

## Plain English

The shutdown hang is not one monster. It is a few tools left running after Maez tries to leave the room.

Chroma is the big one: it brings Rust worker threads for vector memory and SQLite. Maez opens several Chroma clients and currently does not consistently close them. The camera stack is the second one: MediaPipe has a real close button, but Maez never presses it. OpenCV also brings a 32-thread pool, which explains why several thread families show up in neat groups of 32.

So the next fix is not "kill threads." It is "put away each tool at the door": close Chroma clients, close the MediaPipe detector, and then retest whether Maez can stop without systemd using SIGKILL.
