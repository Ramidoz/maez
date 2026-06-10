"""Future plug-points for the Brain-Audition organ. v0: stubs only.

- candidate_source: where a candidate enters. v0 manual; later the curiosity-trigger
  reading a model mention in Maez's perception.
- advisor_consult: external-model second opinion; later via decide_egress as a
  PUBLIC-topic call about model specs, never owner content.
- owner_proposal: the "I found this, want me to audition it?" surface; later.
- swap_breath: the actual brain swap. ALWAYS an owner's breath; never auto-fired.
"""


def candidate_source() -> list:
    return []


def advisor_consult(candidate: str) -> None:
    raise NotImplementedError(
        "advisor_consult is a future seam for decide_egress public-topic shape"
    )


def owner_proposal(report: dict) -> None:
    raise NotImplementedError("owner_proposal is a future seam")


def swap_breath(candidate: str) -> None:
    raise NotImplementedError(
        "swap_breath is the owner's breath and is never auto-fired by the organ"
    )
