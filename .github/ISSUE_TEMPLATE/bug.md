---
name: Bug report
about: Something is broken or behaving unexpectedly
title: "bug: "
labels: bug
assignees: ''
---

## What happened

<!--
Describe the behaviour you saw, in two or three sentences. Include
the command / surface / sequence of events. Paste log lines from
`logs/maez.log` or `logs/cognition.log` if relevant.
-->

## What you expected

<!-- A sentence or two. -->

## Reproduction steps

1.
2.
3.

## Environment

- OS and version (e.g. Ubuntu 22.04):
- Python version (`python3 --version`):
- GPU (`nvidia-smi --query-gpu=name --format=csv,noheader` or "CPU-only"):
- Commit SHA (`git rev-parse HEAD`):
- Local LLM backend (`llamacpp` / `ollama` / other):
- Which surface (cockpit / Telegram / CLI / daemon-only):

## Logs

<!--
`tail -n 100 logs/maez.log` is usually enough. Redact anything
personal before pasting; the SECURITY_AUDIT doc explains what to
look for.
-->

```
```

## Self-check

- [ ] I ran `./scripts/install.sh` to completion at least once
- [ ] `.venv/bin/python -m core.paths` shows the paths I expect
- [ ] The test suite (`python -m unittest discover -s tests -p 'test_*.py'`) was green on my commit before this bug appeared
- [ ] I searched existing issues for the same symptom
