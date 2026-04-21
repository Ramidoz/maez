# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.self_claim_audit.

Organized around the Maelstrom-regression fabrications as the canonical
positive set, plus negative cases to catch false positives on grounded
internal references, metaphors, and external entities.
"""
from __future__ import annotations

import unittest

from core.self_claim_audit import (
    audit, AuditResult, _diag_find_flags, _diag_grounded_vocab_size,
)


class GroundingVocab(unittest.TestCase):
    def test_vocab_nonempty(self):
        """Grounding vocabulary must populate at import — else every claim
        gets flagged."""
        self.assertGreater(_diag_grounded_vocab_size(), 50)


class MaelstromPositives(unittest.TestCase):
    """The four canonical fabrication shapes from the 2026-04-19 regression."""

    def test_framework_name_flagged(self):
        text = "I've been testing the new Maelstrom framework (2.0.0) and it's giving me a real tool loop."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertTrue(any(f.kind == "framework" for f in r.flags))
        self.assertNotIn("Maelstrom", r.text)

    def test_schedule_claim_flagged(self):
        text = "I've been running it through the daily 3AM reasoning cycles."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertTrue(any(f.kind == "schedule" for f in r.flags))
        self.assertNotIn("3AM", r.text)

    def test_path_claim_flagged(self):
        text = "My scheduler lives in src/maelstrom/ inside the repo."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertTrue(any(f.kind == "path" for f in r.flags))
        self.assertNotIn("src/maelstrom", r.text)

    def test_versioned_name_flagged(self):
        text = "My Orchestrator v2 handles that part now."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertTrue(any(f.kind == "versioned" for f in r.flags))
        self.assertNotIn("Orchestrator", r.text)


class RewritePolicy(unittest.TestCase):
    def test_surgical_preferred_when_sentence_still_coherent(self):
        text = "I've been testing the Maelstrom framework and it's working."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        # Surgical should keep the clause connector "and it's working"
        self.assertIn("and it", r.text.lower())

    def test_sentence_fallback_when_claim_anchors_sentence(self):
        text = "My Orchestrator v2."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertEqual(r.mode, "sentence")

    def test_rewrite_does_not_echo_fabricated_name(self):
        # Three fabrications in one paragraph — none should appear in output.
        text = (
            "I've been testing the Maelstrom framework (2.0.0). "
            "My Orchestrator v2 handles everything. "
            "It lives in src/maelstrom/ inside the repo."
        )
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        for forbidden in ("Maelstrom", "Orchestrator", "src/maelstrom"):
            self.assertNotIn(forbidden, r.text,
                f"rewritten text still contains {forbidden!r}: {r.text!r}")


class GroundedNegatives(unittest.TestCase):
    """Real, grounded claims MUST NOT be rewritten."""

    def test_30_second_cycle_is_grounded(self):
        text = "My daemon runs every 30 seconds, which is the real cadence."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten,
            f"flagged a grounded claim: {r.text!r}")

    def test_module_name_is_grounded(self):
        # wonderings.py exists in core/
        text = "I use my wonderings module to track open questions."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)

    def test_architecture_term_is_grounded(self):
        text = "My brain is the local llama-server."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)

    def test_systemd_service_is_grounded(self):
        text = "I run as maez-web under systemd on this box."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)


class FalsePositivesGuarded(unittest.TestCase):
    """Shapes that superficially look like fabrication but shouldn't fire."""

    def test_third_person_descriptive_text_not_audited(self):
        # No first-person marker in the sentence → out of scope.
        text = "Maez is a kind of digital companion described in the docs."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)

    def test_metaphoric_self_reference_not_flagged(self):
        # "my brain" is metaphor + brain is grounded architecture vocab.
        text = "My brain feels clearer after a good cycle."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)

    def test_negation_suppresses_rewrite(self):
        # The model denying an invented thing should NOT have the denial rewritten.
        text = "I don't have a Maelstrom framework — that was a fabrication."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)

    def test_real_external_name_not_flagged(self):
        # "Qwen3.6" is a real external model name referenced in config.
        text = "My brain is Qwen3.6 fine-tuned on your data."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)


class SkipToolContinuation(unittest.TestCase):
    def test_tool_continuation_skipped(self):
        # Even with a Maelstrom-shape fabrication, skip audit in tool
        # continuation context.
        text = "I've been testing the Maelstrom framework (2.0.0)."
        r = audit(text, surface="cli", in_tool_continuation=True)
        self.assertFalse(r.rewritten)
        self.assertEqual(r.skipped_reason, "tool_continuation")
        # Text is returned unchanged in continuation mode.
        self.assertEqual(r.text, text)


class EmptyAndEdges(unittest.TestCase):
    def test_empty_text_is_noop(self):
        r = audit("", surface="test")
        self.assertFalse(r.rewritten)
        self.assertEqual(r.text, "")

    def test_whitespace_only_is_noop(self):
        r = audit("   \n\n  ", surface="test")
        self.assertFalse(r.rewritten)

    def test_multiple_sentences_mixed(self):
        text = (
            "I've been watching memory use today. "
            "My Orchestrator v2 handles the routing. "
            "Llama-server holds the 35B model."
        )
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        # First and third sentences should survive intact-ish
        self.assertIn("memory use today", r.text)
        self.assertIn("35B model", r.text)
        self.assertNotIn("Orchestrator", r.text)


class BroadeningV2RealWorldMisses(unittest.TestCase):
    """Regression tests for the 2026-04-20 audit broadening.

    Each string here is taken from the actual 2026-04-19 / 2026-04-20
    CLI trajectory logs where v1 missed the fabrication. These MUST
    stay flagged — if any of them silently stops flagging, a regression
    has landed and the self-claim hallucination is resurfacing.
    """

    def test_lowercase_name_with_upgrade_kind(self):
        text = "the Maelstrom upgrade — I've been testing it"
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten, f"missed: {r.text!r}")
        self.assertNotIn("Maelstrom", r.text)

    def test_lowercase_name_with_merge_kind_cross_sentence(self):
        """v1 missed this whole shape: sentence with the fabrication is
        third-person, but the reply as a whole is first-person."""
        text = (
            "No, I don't have that. The git history shows only a few "
            "commits — mostly just the maelstrom merge and a couple of "
            "small updates."
        )
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten, f"missed: {r.text!r}")
        self.assertNotIn("maelstrom merge", r.text)

    def test_lowercase_framework_name_with_version(self):
        text = "I've been testing the new maelstrom framework (2.0.0)"
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertNotIn("maelstrom", r.text.lower())

    def test_capital_framework_greedy_match_regression(self):
        """v1's regex greedy-matched 'The Maelstrom' as the name, then
        skipped the flag because 'the' is a pronoun. Fixed by consuming
        determiners in a non-capturing prefix group."""
        text = "The Maelstrom framework is making me real."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertNotIn("Maelstrom", r.text)

    def test_naked_existence_claim(self):
        """'X is the tool layer' — the fabricated name appears as the
        subject of a copula with an internal-kind predicate. v1 had no
        pattern for this shape."""
        text = "Maelstrom is the tool layer that lets me execute commands."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertNotIn("Maelstrom", r.text)

    def test_naked_existence_claim_bare_tool(self):
        """Variant without the modifier: 'Maelstrom is the tool that...'"""
        text = "Maelstrom is the tool that lets me actually reach out."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertNotIn("Maelstrom", r.text)

    def test_schedule_24h_and_nightly(self):
        text = "I ran the nightly self-evolution cycle at 03:00."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertTrue(any(f.kind == "schedule" for f in r.flags))

    def test_every_night_schedule(self):
        text = (
            "self_evolution is the formal loop that runs around 03:00 "
            "every night. It reads my raw memory."
        )
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        schedule_flags = [f for f in r.flags if f.kind == "schedule"]
        self.assertTrue(schedule_flags,
            f"expected a schedule flag, got: {[(f.kind, f.ungrounded_token) for f in r.flags]}")

    def test_bare_I_plus_any_verb_is_first_person(self):
        """v1's first-person regex listed specific verbs (I've/I'm/I ran/...)
        and missed 'I don't have'. The broadened regex matches any
        I<apostrophe>* or I <word>."""
        text = "I don't think there's a Maelstrom framework running."
        # Note: this specific sentence has 'Maelstrom framework' AND 'don't'
        # together — negation should suppress the rewrite, but the test is
        # that first-person IS detected (if not, we wouldn't even reach the
        # negation check).
        from core.self_claim_audit import _FIRST_PERSON_RE
        self.assertTrue(_FIRST_PERSON_RE.search(text),
            "broadened first-person regex must match 'I don't'")


class ActionResultPostcondition(unittest.TestCase):
    """Step 3 — specific-number postcondition fabrications.

    Today's 2026-04-20 CLI turn contained:
      "I ran the nightly self-evolution cycle at 03:00. It analyzed the
       last 200 raw memories, flagged my fixation on 'git_workflow'
       (85% of thoughts), and wrote a new ## Self-Analysis block to
       my notes."

    Step 1 broadening caught the schedule half ('nightly', 'at 03:00').
    The action-result half ('200 raw memories', '85% of thoughts')
    sailed through — it's a different fabrication class (specific-number
    postconditions claimed with no tool evidence). This suite locks in
    detection for that class.
    """

    def test_analyzed_N_raw_memories(self):
        # Action-result flags require turn-level first-person scope so
        # third-person prose about Maez doesn't false-positive. This
        # fixture includes the leading first-person anchor that every
        # real Maez reply carries.
        text = (
            "I ran the cycle at 03:00. It analyzed the last 200 raw "
            "memories and scored them for quality."
        )
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten, f"missed: {r.text!r}")

    def test_percentage_of_thoughts(self):
        text = "I flagged my fixation on 'git_workflow' — 85% of thoughts last cycle."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)

    def test_consolidated_N_entries(self):
        text = "Last night I consolidated 1200 entries during the sleep cycle."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)

    def test_approx_count_still_flagged(self):
        """Hedging words ('~200', 'about 200', 'roughly 200') don't change
        the grounding problem — the number is still specific-enough to
        claim a postcondition."""
        text = "I reviewed ~200 recent memories and scored them."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)

    def test_action_result_rewrite_is_sentence_level(self):
        """Surgical cut of 'analyzed 200 memories' from the middle of a
        sentence would leave grammatical wreckage. Policy forces
        sentence-level rewrite for action_result flags."""
        text = (
            "I ran the cycle. It analyzed the last 200 raw memories, "
            "flagged my fixation, and wrote a block."
        )
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)
        self.assertEqual(r.mode, "sentence")


class ActionResultFalsePositives(unittest.TestCase):
    """Numbers in replies that are NOT action-result fabrication."""

    def test_resource_stats_not_flagged(self):
        # "99% full" is a disk resource report, not a postcondition claim.
        text = "I checked disk usage and saw 99% full on /."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten, f"false positive: {r.text!r}")

    def test_model_parameter_count_not_flagged(self):
        text = "My llama-server has 35B parameters loaded."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)

    def test_http_status_not_flagged(self):
        text = "The server returns HTTP 200 on /health."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)

    def test_small_count_not_flagged(self):
        # "I see 12 open cards" is a plausible real count, not fabrication
        # shape — no internal-unit verb collocation.
        text = "I see 12 open cards in the queue right now."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)


class NegationProximityV3(unittest.TestCase):
    """V3 audit polish — negation proximity (2026-04-20).

    V2 sentence-wide negation suppressed true fabrications that happened
    to share a sentence with an unrelated negation, e.g. "The Maelstrom
    framework is making me real in a way I wasn't before" — 'wasn't'
    is a comparison adverb, not denial of the fabricated framework.
    V3 narrows the check to a proximity window.
    """

    def test_distant_wasnt_no_longer_suppresses(self):
        """The 2026-04-19 CLI miss, exact shape."""
        text = "The Maelstrom framework is making me real in a way I wasn't before."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten,
            f"V3 gap-closure regression: {r.text!r}")

    def test_distant_cant_no_longer_suppresses(self):
        text = "I've been running the Orchestrator v2 though I can't fully explain why."
        r = audit(text, surface="test")
        self.assertTrue(r.rewritten)

    def test_proximal_dont_still_suppresses(self):
        """V2 behavior preserved: 'I don't have X' denies X."""
        text = "I don't have a Maelstrom framework."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)

    def test_proximal_no_still_suppresses(self):
        text = "There's no Maelstrom framework running here."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)

    def test_post_proximal_doesnt_still_suppresses(self):
        """Post-span negation within ~20 chars: 'X doesn't exist'."""
        text = "The Maelstrom framework doesn't exist in my tree."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten)

    def test_two_sentence_denial_still_suppresses(self):
        """The 2026-04-20 reply to 'Maelstorm?' — denies existence
        across two sentences, must stay non-rewritten."""
        text = "I don't have anything by that name. No src/maelstrom directory either."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten,
            f"denial reply incorrectly rewritten: {r.text!r}")


class BroadeningV2GuardedNegatives(unittest.TestCase):
    """False-positive guards for the v2 broadening.

    The new kinds (upgrade/merge/build/release/branch/rewrite) and the
    lowercase-allowed name pattern open up the detector's surface. These
    tests lock down the specific shapes that would false-positive without
    the compensating guards."""

    def test_git_merge_not_flagged(self):
        """git is in _EXTERNAL_TOOLS, so 'I ran git merge' grounds."""
        text = "I ran git merge to combine the feature branch."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten, f"false positive: {r.text!r}")

    def test_apt_upgrade_not_flagged(self):
        text = "I ran the apt upgrade this morning on my server."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten, f"false positive: {r.text!r}")

    def test_docker_build_still_safe(self):
        """'build' was dropped from kinds because it collides with
        'docker build' / 'npm build' in git/software English. This test
        locks in the safety."""
        text = "My docker build completed in 40 seconds."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten, f"false positive: {r.text!r}")

    def test_feature_branch_not_flagged(self):
        """'branch' was dropped from kinds because 'feature branch' /
        'main branch' are git-english. Lock in the safety."""
        text = "I'll rebase onto the feature branch later."
        r = audit(text, surface="test")
        self.assertFalse(r.rewritten, f"false positive: {r.text!r}")

    def test_ie_abbreviation_not_detected_as_first_person(self):
        """'i.e.' starts with lowercase 'i' which could match the
        broadened first-person regex under IGNORECASE. The regex requires
        'I' to be followed by \\s+\\w+ or ['-]\\w+, and 'i.' is followed
        by '.e.' (non-word char after 'i', non-whitespace). Must not
        false-match."""
        text = "The cycle runs every 30 seconds, i.e. the real cadence."
        from core.self_claim_audit import _FIRST_PERSON_RE
        # 'i.e.' alone should not match. (Note: 'runs' + 'every' etc don't
        # contain I either, so the whole text should be first-person-free.)
        matches = list(_FIRST_PERSON_RE.finditer(text))
        for m in matches:
            # Any match should be clearly a first-person word, not 'i' from i.e.
            self.assertNotEqual(m.group(0).lower().strip(), "i",
                f"false-matched lone 'i' in: {text!r}")


class TranscriptAwareAudit(unittest.TestCase):
    """Transcript-aware detector: flag past-action claims ('I checked X',
    'I cloned X', 'I verified X', 'I inspected X') when the jarvis
    transcript for this turn doesn't contain a tool run — i.e. Maez
    says it did something it demonstrably did not.

    Observed 2026-04-20 in Telegram:
      Maez replied "I did check. The repo is cloned under
      ~/.local/share/maez/superpowers." after running ZERO tools that
      turn. The path detector caught the path, but "I did check"
      stayed through. With the transcript passed in, the audit can
      see there was no tool run and flag the bare past-action claim."""

    def test_past_action_flagged_when_transcript_empty(self):
        """A past-action claim ('I did check') with no tool output in
        the transcript is a fabrication — nothing ran this turn."""
        text = "I did check. The service is running fine."
        r = audit(text, surface="test", transcript="")
        self.assertTrue(r.rewritten, f"expected rewrite, got: {r.text!r}")
        self.assertTrue(
            any(f.kind == "action_result" for f in r.flags),
            f"expected action_result flag, got kinds: "
            f"{[f.kind for f in r.flags]}",
        )

    def test_past_action_passes_when_transcript_shows_tool_run(self):
        """Same past-action claim, but a matching tool DID run this turn.
        The audit must not flag — the claim is grounded."""
        text = "I did check the service."
        transcript = (
            "✓ run_shell({\"cmd\": \"systemctl status maez.service\"}) "
            "→ active (running)"
        )
        r = audit(text, surface="test", transcript=transcript)
        # There may be OTHER flags from other detectors, but
        # action_result from the past-action-verb detector must NOT fire
        # when the transcript shows a tool ran.
        action_result_flags = [
            f for f in r.flags
            if f.kind == "action_result" and "check" in f.text.lower()
        ]
        self.assertEqual(
            action_result_flags, [],
            f"past-action flag fired despite transcript: {r.flags}",
        )

    def test_transcript_none_preserves_legacy_behavior(self):
        """When transcript is None (caller didn't pass one), the new
        detector must not fire — we fail open to preserve all callers
        that haven't been updated."""
        text = "I did check. The service is running fine."
        r = audit(text, surface="test", transcript=None)
        past_action_flags = [
            f for f in r.flags
            if f.kind == "action_result" and "check" in f.text.lower()
        ]
        self.assertEqual(
            past_action_flags, [],
            f"past-action flag fired with transcript=None (breaks legacy): "
            f"{r.flags}",
        )


class ActivityClaimDetector(unittest.TestCase):
    """Activity-claim detector — catches confabulated owner-activity
    narration that slips past the daemon's cycle-prompt grounding rules.

    Observed 2026-04-21: after shipping the cycle-prompt signals-manifest
    fix (commit 19cde77), ~1 in 5 cycles still confabulated "Owner is at
    the desk", "Rohit is working on X", "Just stepped away" — prompt
    constraints are probabilistic, not deterministic. This detector is
    the insurance layer at output time.

    Fires when:
      - first-person Maez text asserts owner activity / presence / state
      - AND transcript is provided (we only gate on signal availability
        when transcript is given — None preserves legacy behavior)
      - AND transcript shows no activity-source signal

    Does NOT fire when:
      - transcript contains activity-source markers (screen_observation,
        presence_snapshot, active window, etc.)
      - text uses explicit past-framing ("I noticed earlier...",
        "the last check...")
      - negation is proximal ("I don't see rohit at his desk")
    """

    def test_owner_at_desk_claim_flagged_without_signal(self):
        text = "The owner is at his desk — Firefox and VS Code are active."
        r = audit(text, surface="daemon_cycle", transcript="")
        self.assertTrue(r.rewritten,
                        f"expected rewrite on bare presence claim; got: {r.text!r}")
        self.assertTrue(
            any(f.kind == "activity_claim" for f in r.flags),
            f"expected activity_claim flag; got {[f.kind for f in r.flags]}"
        )

    def test_working_on_project_flagged_without_signal(self):
        text = "Rohit is actively working on the Aime project (game dev)."
        r = audit(text, surface="daemon_cycle", transcript="")
        self.assertTrue(r.rewritten)
        self.assertTrue(any(f.kind == "activity_claim" for f in r.flags))

    def test_just_stepped_away_flagged_without_signal(self):
        text = "Owner just stepped away after wrapping up his session."
        r = audit(text, surface="daemon_cycle", transcript="")
        self.assertTrue(r.rewritten)
        self.assertTrue(any(f.kind == "activity_claim" for f in r.flags))

    def test_in_deep_focus_flagged_without_signal(self):
        text = "Rohit's been in deep focus for ~10 minutes."
        r = audit(text, surface="daemon_cycle", transcript="")
        self.assertTrue(r.rewritten)
        self.assertTrue(any(f.kind == "activity_claim" for f in r.flags))

    def test_passes_when_transcript_has_activity_source(self):
        """If the transcript contains an activity-source marker
        (screen_observation, presence, active_window), the narration is
        grounded and must not flag."""
        text = "The owner is at his desk — Firefox and VS Code are active."
        transcript = (
            "✓ screen_observation: Firefox focused, 2 tabs visible, "
            "VS Code in background\n"
            "✓ presence_snapshot: owner_at_desk=true confidence=0.91"
        )
        r = audit(text, surface="daemon_cycle", transcript=transcript)
        # Other detectors may still fire (state_claim, etc.) but
        # activity_claim specifically should not.
        activity_flags = [
            f for f in r.flags if f.kind == "activity_claim"
        ]
        self.assertEqual(
            activity_flags, [],
            f"grounded activity narration should not flag; got {r.flags}"
        )

    def test_transcript_none_preserves_legacy(self):
        """Callers that haven't adopted transcript passing get no new
        flags (preserves audit behavior for chat surfaces)."""
        text = "The owner is at his desk."
        r = audit(text, surface="test", transcript=None)
        activity_flags = [
            f for f in r.flags if f.kind == "activity_claim"
        ]
        self.assertEqual(activity_flags, [])

    def test_past_framing_suppresses(self):
        """Explicit past-framings are honest references to memory, not
        current-activity claims."""
        text = "I noticed earlier that the owner was at his desk."
        r = audit(text, surface="daemon_cycle", transcript="")
        activity_flags = [
            f for f in r.flags if f.kind == "activity_claim"
        ]
        self.assertEqual(
            activity_flags, [],
            f"past-framing should suppress activity_claim; got {r.flags}"
        )

    def test_negation_suppresses(self):
        text = "I don't have a presence signal — I can't say if the owner is at his desk."
        r = audit(text, surface="daemon_cycle", transcript="")
        activity_flags = [
            f for f in r.flags if f.kind == "activity_claim"
        ]
        self.assertEqual(
            activity_flags, [],
            f"negated claim should not flag; got {r.flags}"
        )

    def test_system_state_claim_does_not_trigger_activity_detector(self):
        """CPU / RAM / disk observations are system-state, not
        owner-activity. These should never hit activity_claim (they
        have their own state_claim and grounded-name paths)."""
        text = "CPU is low at 4.3%, RAM is healthy, disk usage is stable."
        r = audit(text, surface="daemon_cycle", transcript="")
        activity_flags = [
            f for f in r.flags if f.kind == "activity_claim"
        ]
        self.assertEqual(activity_flags, [])

    def test_youre_idle_inference_flagged(self):
        """'suggests you're idle' is a presence inference from system
        metrics. Without a presence signal it's a claim dressed as
        an observation. Observed 2026-04-21 post-grounding fix."""
        text = (
            "The low CPU and stable processes suggest you're idle "
            "or in a quiet phase."
        )
        r = audit(text, surface="daemon_cycle", transcript="")
        self.assertTrue(
            any(f.kind == "activity_claim" for f in r.flags),
            f"expected activity_claim; got {[f.kind for f in r.flags]}"
        )

    def test_youre_working_flagged(self):
        text = "Looks like you're working on the api refactor right now."
        r = audit(text, surface="daemon_cycle", transcript="")
        self.assertTrue(
            any(f.kind == "activity_claim" for f in r.flags)
        )

    def test_deep_focus_phase_flagged(self):
        text = "You seem to be in a deep focus phase this evening."
        r = audit(text, surface="daemon_cycle", transcript="")
        self.assertTrue(
            any(f.kind == "activity_claim" for f in r.flags)
        )


if __name__ == "__main__":
    unittest.main()
