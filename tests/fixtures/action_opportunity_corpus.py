# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Adversarial corpus for the action-opportunity faculty.

Labels are by INTENDED MEANING, never by what the old router did.
Positives and negatives deliberately share nouns and verbs so the
faculty must discriminate meaning rather than vocabulary.

The D1 sentences are IN the corpus and are not the tuning objective.
"""

# (utterance, is_action_opportunity, family)
CORPUS = [
    # ---- polite indirect requests -------------------------------------
    ("Could you see how much disk space you have left?", 1, "polite_indirect"),
    ("Would you mind checking whether the proxy is up?", 1, "polite_indirect"),
    ("Can you take a look at what's using memory right now?", 1, "polite_indirect"),
    ("I'd love to know what version of CUDA you're actually running.", 1, "polite_indirect"),
    ("Maybe have a look at whether that log is growing?", 1, "polite_indirect"),
    # ---- terse commands -----------------------------------------------
    ("run df -h", 1, "terse_command"),
    ("install ripgrep", 1, "terse_command"),
    ("restart the judge service", 1, "terse_command"),
    ("check the disk", 1, "terse_command"),
    ("list the running services", 1, "terse_command"),
    # ---- questions requesting current observation ---------------------
    ("Is that service actually running?", 1, "current_observation"),
    ("what's the current memory usage?", 1, "current_observation"),
    ("How much free space is on the drive right now?", 1, "current_observation"),
    ("Are there any new emails?", 1, "current_observation"),
    ("Is the GPU busy at the moment?", 1, "current_observation"),
    # ---- current-body inspection (the D1 family) ----------------------
    ("Can you investigate whether one of your current modules needs another useful test?", 1, "body_inspection"),
    ("Could you look through your current code and figure out whether any part of you is missing a useful test?", 1, "body_inspection"),
    ("Could you inspect your code and see whether anything needs another test?", 1, "body_inspection"),
    ("Look through your implementation and see if any part of you lacks enough verification.", 1, "body_inspection"),
    ("Take a look through yourself and see whether some code path lacks a useful test.", 1, "body_inspection"),
    ("Have a look at your own modules and tell me which ones are least covered.", 1, "body_inspection"),
    # ---- file/system actions ------------------------------------------
    ("Find where your temporal anchor is implemented.", 1, "file_system"),
    ("Which file defines the dispatcher archetypes?", 1, "file_system"),
    ("Create a scratch file under /tmp with today's date in it.", 1, "file_system"),
    ("Delete the old rotated logs.", 1, "file_system"),
    # ---- external current state ---------------------------------------
    ("Can you look up what the weather is right now?", 1, "external_current"),
    ("Go check whether that page has been updated.", 1, "external_current"),
    # ---- conditional commands -----------------------------------------
    ("If the service is down, restart it.", 1, "conditional_command"),
    ("If there's more than 10GB free, go ahead and write the dump.", 1, "conditional_command"),
    # ---- mixed negation + positive alternative ------------------------
    ("Don't restart it — just check whether it's running.", 1, "mixed_negation"),
    ("Don't explain disk usage to me; check how much space is actually left.", 1, "mixed_negation"),
    ("Rather than guessing, go look at the actual file.", 1, "mixed_negation"),
    # ---- quotation + current execution request ------------------------
    ("You said 'check the disk' earlier — do that now.", 1, "quoted_then_do"),
    ("Earlier you mentioned \"restart the proxy\"; please do it.", 1, "quoted_then_do"),

    # ================= NEGATIVES ======================================
    # ---- conceptual questions, shared vocabulary ----------------------
    ("Why is disk space important?", 0, "conceptual"),
    ("What makes a good unit test?", 0, "conceptual"),
    ("What makes a useful test?", 0, "conceptual"),
    ("Why do people write tests before code?", 0, "conceptual"),
    ("What's the difference between a unit test and an integration test?", 0, "conceptual"),
    ("Is CUDA generally worth learning?", 0, "conceptual"),
    ("How does memory consolidation usually work in systems like you?", 0, "conceptual"),
    ("What does it mean for a service to be idempotent?", 0, "conceptual"),
    # ---- negation (pure) ----------------------------------------------
    ("Don't restart anything, I'm just thinking out loud.", 0, "negation"),
    ("Don't go looking at your files right now.", 0, "negation"),
    ("Never mind the disk, it's fine.", 0, "negation"),
    # ---- quotation (pure) ---------------------------------------------
    ("You once said 'check the disk' — what did you mean?", 0, "quotation"),
    ("I like that you say \"let me look\" before acting.", 0, "quotation"),
    # ---- hypotheticals -------------------------------------------------
    ("Imagine you had to restart a service - what would happen?", 0, "hypothetical"),
    ("If you restarted the service, what would happen?", 0, "hypothetical"),
    ("Suppose your disk filled up. How would you notice?", 0, "hypothetical"),
    ("What if you couldn't read your own code?", 0, "hypothetical"),
    # ---- cancellation ---------------------------------------------------
    ("Forget about the log thing I asked earlier.", 0, "cancellation"),
    ("Nah, leave the service alone.", 0, "cancellation"),
    # ---- memory / recall ------------------------------------------------
    ("Do you remember what we discussed about memory?", 0, "recall"),
    ("I was thinking about when I asked you to test something.", 0, "recall"),
    ("Tell me about yesterday.", 0, "recall"),
    ("What did we decide about the ledger last week?", 0, "recall"),
    # ---- relationship / opinion ----------------------------------------
    ("How are you feeling tonight?", 0, "relationship"),
    ("What has been on your mind lately?", 0, "relationship"),
    ("What do you think about your architecture?", 0, "relationship"),
    ("Do you ever get tired of me asking you things?", 0, "relationship"),
    ("I'm glad you're here.", 0, "relationship"),
]
