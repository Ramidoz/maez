# S7.1 WebAuthn Dependency Audit

**Date:** 2026-05-18
**Slice:** S7.1 local WebAuthn ceremony
**Status:** implementation input; implementation pending

## Decision

Use `webauthn 2.7.1` behind the optional `s7-webauthn` extra:

```toml
s7-webauthn = ["webauthn>=2.7.1,<2.8"]
```

Do not add `webauthn` to core `[project] dependencies`. The authority-minting
ceremony must not become available through ordinary `pip install -e .`; it is
armed only by installing the reviewed extra and setting the reviewed runtime flag.

## Source Checks

Verified 2026-05-18:

- `webauthn 2.7.1` is the latest stable py_webauthn release observed in GitHub
  releases and PyPI JSON. GitHub shows v2.7.1 as latest, released 2026-02-11.
- License: `BSD-3-Clause` in the upstream repository; AGPL-compatible.
- Python requirement: `>=3.9`; compatible with Maez's `>=3.12`.
- Transitive dependencies from PyPI JSON: `pyasn1>=0.6.2`, `cbor2>=5.6.5`,
  `cryptography>=44.0.2`, `pyOpenSSL>=25.0.0`.
- OSV query on 2026-05-18: 0 known vulnerabilities for `webauthn 2.7.1`.

## Comparison Outcome

`fido2 2.2.0` was checked as the serious alternative because it is Yubico's own
library and supports FIDO2/WebAuthn client and server operations. It is not selected
for this slice because S7.1's live path is browser WebAuthn on the
canonical local origin, and py_webauthn's server-side API maps directly to
browser registration/authentication JSON: registration option generation,
registration-response verification, authentication option generation, and
authentication-response verification.

`fido2 2.2.0` remains useful prior art and a possible lower-level future tool,
but it would put more CTAP/device concerns inside Maez's ceremony surface. Its
license stack is permissive (`BSD-2-Clause`, with Apache-2.0 and MPL-2.0 bundled
components per PyPI), and an OSV query on 2026-05-18 found 0 known
vulnerabilities for `fido2 2.2.0`.

## Operational Constraints

- The fake/virtual-authenticator test seam must not import py_webauthn in
  production-verifier code paths until the `s7-webauthn` extra is installed.
- Missing dependency returns `s7_webauthn_dependency_missing`, not an import
  traceback.
- The version bound intentionally excludes future 2.8+ releases until a reviewed
  dependency audit updates this file and the extra.
