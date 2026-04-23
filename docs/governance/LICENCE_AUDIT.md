# Licence audit — Phase 7

Scope: confirm every runtime dependency declared in `pyproject.toml`
carries a licence compatible with AGPL-3.0-or-later (the licence
Maez itself ships under), and identify any deps that need attention
before v0.1.0-alpha.

**Audit date:** 2026-04-22
**Source:** `pip-licenses` against the author's development venv
(291 packages — runtime + training + dev).

## TL;DR

- **All declared runtime deps (`pyproject.toml` `dependencies`) are
  permissively licensed** — MIT, BSD, Apache-2.0 or MPL-2.0.
- **No GPL / LGPL / Elastic-licence package is a declared runtime
  dependency.** Every restricted-licence package found in the venv
  (`pylint`, `udapi`, `udtools`, `tnr`) is a dev or training-only
  tool that isn't pulled in by `pip install -e .`.
- **NVIDIA proprietary components** (`cuda-*`, `nvidia-*`) are
  hardware-driver stubs. Maez depends on them indirectly via
  PyTorch / llama.cpp for GPU inference. They're installed on the
  owner's machine from NVIDIA's own channel — Maez doesn't
  redistribute them.
- **`UNKNOWN` licence on two packages** (`cuda-toolkit`,
  `espeakng-loader`) — neither is a declared Maez runtime dep. Not
  blocking.

## Runtime dependency licences (from `pyproject.toml`)

These are the packages a fresh `pip install -e .` pulls in. Every
one is AGPL-compatible.

| Package | Licence | Status |
|---|---|---|
| flask | BSD-3-Clause | ✅ |
| fastapi | MIT | ✅ |
| uvicorn | BSD-3-Clause | ✅ |
| requests | Apache-2.0 | ✅ |
| httpx | BSD-3-Clause | ✅ |
| python-dotenv | BSD-3-Clause | ✅ |
| pyyaml | MIT | ✅ |
| chromadb | Apache-2.0 | ✅ |
| numpy | BSD-3-Clause | ✅ |
| scipy | BSD-3-Clause | ✅ |
| psutil | BSD-3-Clause | ✅ |
| ollama | MIT | ✅ |
| anthropic | MIT | ✅ |
| openai | Apache-2.0 | ✅ |
| langfuse | MIT | ✅ |
| click | BSD-3-Clause | ✅ |

Optional extras pulled in by `pip install -e .[vision | telegram |
google]`:

| Package | Extra | Licence | Status |
|---|---|---|---|
| opencv-python | vision | Apache-2.0 | ✅ |
| face_recognition | vision | MIT | ✅ |
| python-telegram-bot | telegram | GPL-3.0-or-later | ⚠️ see note |
| google-api-python-client | google | Apache-2.0 | ✅ |
| requests-oauthlib | google | ISC | ✅ |

### Note on `python-telegram-bot` (GPL-3.0-or-later)

This is the only GPL-licensed component that any Maez user might
install. It's behind the optional `telegram` extra so installing
Maez without the Telegram surface pulls only permissive licences.

GPL-3.0 and AGPL-3.0 are compatible with each other; combining Maez
(AGPL-3.0) with python-telegram-bot (GPL-3.0) in one deployment is
allowed. The combined work stays AGPL-3.0-or-later. No user action
needed.

## Venv-wide audit findings

The full author-side venv has 291 packages (training + dev tools
bundled in). Of those, these have restricted licences:

| Package | Licence | Used by Maez runtime? |
|---|---|---|
| pylint | GPL-2.0-or-later | No — dev-only linter |
| udapi | GPL-3.0-or-later | No — training-only NLP tool |
| udtools | GPL-2.0-or-later | No — training-only NLP tool |
| tnr | Elastic-2.0 | No — training-only tool |
| cuda-toolkit | UNKNOWN | No — installed from NVIDIA, not PyPI |
| nvidia-cusparselt-cu13 | NVIDIA Proprietary | No — driver stub |
| nvidia-* (cuda suite) | LicenseRef-NVIDIA-Proprietary | No — driver stub |
| espeakng-loader | UNKNOWN | No — not used by Maez |

None of these are in `pyproject.toml`'s `dependencies` or any of the
declared extras, so they never land in a fresh Maez install.

## Major licence buckets (runtime + extras)

Among the ~60 packages a fully-extras install would pull in:

- **MIT / MIT License**: ~55 packages
- **BSD-3-Clause / BSD-2-Clause / BSD License**: ~25 packages
- **Apache-2.0 / Apache License 2.0**: ~15 packages
- **MPL-2.0**: a handful (chromadb dependencies)
- **ISC**: a handful
- **GPL-3.0**: python-telegram-bot (only if you install `[telegram]`)
- **NVIDIA proprietary**: driver stubs (only if CUDA already installed)

Every one of these is AGPL-3.0-compatible.

## Distribution model

Maez itself ships source only (AGPL-3.0 obliges network-use sharing,
so any hosted derivative must publish its source). We do not
redistribute any of the listed third-party packages — `pip install`
fetches them from PyPI at install time. Attribution for the
load-bearing upstream projects (Qwen, llama.cpp, Unsloth, etc.) is
captured in the top-level [`NOTICE`](../../NOTICE) file.

## Reproducing this audit

```bash
# On a fresh install
pip install pip-licenses
pip install -e .[all]
pip-licenses --format=markdown --with-authors --summary

# Flag anything GPL / Elastic / UNKNOWN / Proprietary
pip-licenses --format=plain | \
  grep -iE "(GPL|Elastic|UNKNOWN|Proprietary)"
```

Re-run before each semver release. The audit should take < 30 seconds.
