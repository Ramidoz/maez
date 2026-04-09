"""
eval_proposals.py — Replay real proposal evidence and score proposal quality.

Read-only: never writes to DB, never touches live target file.
Safe to run anytime.

Usage:
  python -m scripts.eval_proposals [--output FILE]
"""

import ast
import difflib
import json
import os
import sqlite3
import sys
import tempfile
import subprocess

sys.path.insert(0, '/home/rohit/maez')

MAEZ_ROOT = '/home/rohit/maez'
TARGET = 'core/cognition_quality.py'
EVOLUTION_DB = os.path.join(MAEZ_ROOT, 'memory', 'evolution_track.db')
FULL_TARGET = os.path.join(MAEZ_ROOT, TARGET)

# Threshold-like naming patterns for rank 2
_THRESHOLD_NAMES = {'THRESHOLD', 'FLOOR', 'CEILING', 'MIN', 'MAX', 'LIMIT', 'RATIO'}


def _compute_target_rank(name: str, typ: str) -> int:
    """Rank: 1=threshold scalar, 2=other scalar, 3=keyword list, 4=other."""
    if typ in ('int', 'float', 'bool'):
        parts = set(name.upper().split('_'))
        if parts & _THRESHOLD_NAMES:
            return 1
        return 2
    if typ == 'list_str':
        return 3
    return 4


def _get_replay_cases() -> list[dict]:
    """Get recent candidates/jobs with evidence for replay."""
    db = sqlite3.connect(EVOLUTION_DB)
    db.row_factory = sqlite3.Row
    cases = []

    # From candidates with evidence
    rows = db.execute(
        "SELECT id, weakness_description, cognition_evidence, target_file "
        "FROM candidates WHERE cognition_evidence IS NOT NULL "
        "ORDER BY id DESC LIMIT 10"
    ).fetchall()
    for r in rows:
        try:
            ev = json.loads(r['cognition_evidence'])
            cases.append({
                'source': 'candidate',
                'source_id': r['id'],
                'weakness': r['weakness_description'] or '',
                'evidence': ev,
                'target': r['target_file'] or TARGET,
            })
        except Exception:
            pass

    # From proposal_jobs with evidence
    rows = db.execute(
        "SELECT id, weakness_description, evidence_json "
        "FROM proposal_jobs WHERE evidence_json IS NOT NULL "
        "ORDER BY id DESC LIMIT 10"
    ).fetchall()
    for r in rows:
        try:
            ev = json.loads(r['evidence_json'])
            cases.append({
                'source': 'job',
                'source_id': r['id'],
                'weakness': r['weakness_description'] or '',
                'evidence': ev,
                'target': TARGET,
            })
        except Exception:
            pass

    db.close()
    # Deduplicate by weakness
    seen = set()
    unique = []
    for c in cases:
        key = c['weakness'][:50]
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _extract_targets():
    """Extract editable targets via AST."""
    from skills.evolution_engine import _extract_editable_targets
    return _extract_editable_targets(FULL_TARGET)


def _run_single_eval(case: dict, editable_targets: list) -> dict:
    """Evaluate a single replay case. Returns metrics dict."""
    import hashlib
    from skills.evolution_engine import (
        _generate_patch_intent, _validate_patch_intent,
        _synthesize_edit, _validate_diff_structure, _file_sha256,
    )

    pre_hash = _file_sha256(FULL_TARGET)
    metrics = {
        'source': case['source'],
        'source_id': case['source_id'],
        'weakness': case['weakness'][:80],
        'target_name': None,
        'target_rank': None,
        'intent_valid': False,
        'value_changed': False,
        'diff_valid': False,
        'diff_lines_changed': 0,
        'formatting_preserved': False,
        'rationale_specific': False,
        'live_file_untouched': True,
        'error': None,
        'failure_mode': None,
        'retry_attempted': False,
        'retry_succeeded': False,
        'usefulness_overall': None,
        'addresses_failure_mode': None,
        'direction_sane': None,
        'change_minimal': None,
        'derived_from_failure_mode': None,
        'failure_mode_count': None,
        'filtered_by_failure_mode': None,
        'family_match_count': None,
        'failure_family_alignment': None,
    }

    # Add rank to targets
    ranked = sorted(editable_targets, key=lambda t: _compute_target_rank(t['name'], t['type']))
    for t in ranked:
        t['target_rank'] = _compute_target_rank(t['name'], t['type'])

    # Generate intent
    try:
        intent = _generate_patch_intent(case['weakness'], case['evidence'], ranked)
    except Exception as e:
        metrics['error'] = f'intent generation: {e}'
        metrics['failure_mode'] = 'timeout' if 'timeout' in str(e).lower() else 'parse_failed'
        metrics['live_file_untouched'] = _file_sha256(FULL_TARGET) == pre_hash
        return metrics

    if not intent:
        metrics['error'] = 'no intent returned'
        metrics['failure_mode'] = 'empty_response'
        metrics['live_file_untouched'] = _file_sha256(FULL_TARGET) == pre_hash
        return metrics

    # Extract retry and failure-mode info from intent
    metrics['retry_attempted'] = intent.get('retry_attempted', False)
    metrics['retry_succeeded'] = intent.get('retry_succeeded', False)
    metrics['target_name'] = intent.get('target_name')
    metrics['filtered_by_failure_mode'] = intent.get('filtered_by_failure_mode', False)
    metrics['family_match_count'] = intent.get('family_match_count')
    metrics['failure_family_alignment'] = intent.get('failure_family_alignment', False)
    # Check if weakness was failure-mode-led (from evidence metadata)
    metrics['derived_from_failure_mode'] = case['evidence'].get('_weakness_derived_from_failure_mode', False)
    metrics['failure_mode_count'] = case['evidence'].get('_weakness_failure_count')

    # Find rank
    target_map = {t['name']: t for t in ranked}
    if metrics['target_name'] in target_map:
        metrics['target_rank'] = target_map[metrics['target_name']].get('target_rank')

    # Validate intent
    valid, reason = _validate_patch_intent(intent, ranked)
    metrics['intent_valid'] = valid
    if not valid:
        metrics['error'] = f'intent invalid: {reason}'
        metrics['live_file_untouched'] = _file_sha256(FULL_TARGET) == pre_hash
        return metrics

    metrics['value_changed'] = intent.get('proposed_value') != intent.get('current_value')

    # Synthesize edit
    try:
        original, edited = _synthesize_edit(FULL_TARGET, intent['target_name'],
                                             intent['proposed_value'], ranked)
    except Exception as e:
        metrics['error'] = f'synthesis: {e}'
        metrics['live_file_untouched'] = _file_sha256(FULL_TARGET) == pre_hash
        return metrics

    # Diff
    diff_lines = list(difflib.unified_diff(
        original.split('\n'), edited.split('\n'),
        fromfile=f'a/{TARGET}', tofile=f'b/{TARGET}', lineterm='',
    ))
    diff_text = '\n'.join(diff_lines)
    metrics['diff_lines_changed'] = sum(1 for l in diff_lines
                                         if l.startswith('+') and not l.startswith('+++')
                                         or l.startswith('-') and not l.startswith('---'))

    # Validate diff structure
    struct_ok, struct_reason = _validate_diff_structure(diff_text)
    if not struct_ok:
        metrics['error'] = f'structural: {struct_reason}'
        metrics['live_file_untouched'] = _file_sha256(FULL_TARGET) == pre_hash
        return metrics

    # patch --dry-run
    with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as tf:
        tf.write(diff_text)
        pf = tf.name
    try:
        pr = subprocess.run(['patch', '--dry-run', '-p1', '-d', MAEZ_ROOT, '-i', pf],
                            capture_output=True, text=True, timeout=10)
        if pr.returncode != 0:
            metrics['error'] = f'patch dry-run: {pr.stderr.strip()[:100]}'
            metrics['live_file_untouched'] = _file_sha256(FULL_TARGET) == pre_hash
            return metrics
    finally:
        os.unlink(pf)

    # py_compile on temp
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as ef:
        ef.write(edited)
        tmp = ef.name
    try:
        cr = subprocess.run([sys.executable, '-m', 'py_compile', tmp],
                            capture_output=True, text=True, timeout=15)
        if cr.returncode != 0:
            metrics['error'] = f'py_compile: {cr.stderr.strip()[:100]}'
            metrics['live_file_untouched'] = _file_sha256(FULL_TARGET) == pre_hash
            return metrics
    finally:
        os.unlink(tmp)

    metrics['diff_valid'] = True

    # Usefulness scoring
    try:
        from skills.evolution_engine import score_proposal_usefulness
        usefulness = score_proposal_usefulness(intent, case['evidence'], metrics['diff_lines_changed'])
        metrics['usefulness_overall'] = usefulness.get('overall')
        metrics['addresses_failure_mode'] = usefulness.get('addresses_failure_mode')
        metrics['direction_sane'] = usefulness.get('direction_sane')
        metrics['change_minimal'] = usefulness.get('change_minimal')
    except Exception:
        pass

    # Formatting check: did we preserve inline comment for scalars?
    if metrics['target_rank'] in (1, 2):
        # Check if original line had comment and edited line preserved it
        orig_lines = original.split('\n')
        edit_lines = edited.split('\n')
        target_info = target_map.get(metrics['target_name'], {})
        ln = target_info.get('lineno', 0) - 1
        if 0 <= ln < len(orig_lines):
            orig_has_comment = '#' in orig_lines[ln].split('=', 1)[-1] if '=' in orig_lines[ln] else False
            if orig_has_comment:
                # Find the corresponding edited line
                for el in edit_lines:
                    if el.strip().startswith(metrics['target_name']):
                        metrics['formatting_preserved'] = '#' in el
                        break
            else:
                metrics['formatting_preserved'] = True  # no comment to preserve
    elif metrics['target_rank'] == 3:
        # Check multiline list preserved
        target_info = target_map.get(metrics['target_name'], {})
        start = target_info.get('lineno', 0) - 1
        end = target_info.get('end_lineno', start + 1) - 1
        orig_span = end - start + 1
        # Count lines in edited version for this target
        edit_span = 0
        for el in edited.split('\n'):
            if el.strip().startswith(metrics['target_name']) or (edit_span > 0 and el.strip().startswith("'")):
                edit_span += 1
        metrics['formatting_preserved'] = orig_span <= 2 or edit_span > 1  # multiline preserved if > 1
    else:
        metrics['formatting_preserved'] = True

    # Rationale specificity
    rationale = intent.get('rationale', '')
    weakness_lower = case['weakness'].lower()
    topic = case['evidence'].get('dominant_topic') or ''
    metrics['rationale_specific'] = (
        (topic.replace('_', ' ') in rationale.lower() if topic else False)
        or 'fixation' in rationale.lower()
        or 'threshold' in rationale.lower()
    )

    metrics['live_file_untouched'] = _file_sha256(FULL_TARGET) == pre_hash
    return metrics


def run_eval(output_path: str = None) -> dict:
    """Run full eval. Returns aggregate metrics."""
    from skills.evolution_engine import _file_sha256

    cases = _get_replay_cases()
    if not cases:
        print("No replay cases found")
        return {}

    targets = _extract_targets()
    pre_hash = _file_sha256(FULL_TARGET)

    print(f"Running eval on {len(cases)} replay cases...")
    results = []
    for i, case in enumerate(cases):
        print(f"  [{i+1}/{len(cases)}] {case['weakness'][:60]}...")
        m = _run_single_eval(case, targets)
        results.append(m)
        print(f"    → intent={m['intent_valid']} diff={m['diff_valid']} "
              f"rank={m['target_rank']} target={m['target_name']} "
              f"error={(m.get('error') or 'none')[:40]}")

    # Aggregate
    total = len(results)
    scalars = sum(1 for r in results if r['target_rank'] in (1, 2) and r['intent_valid'])
    valid_intents = sum(1 for r in results if r['intent_valid'])
    valid_diffs = sum(1 for r in results if r['diff_valid'])
    avg_lines = sum(r['diff_lines_changed'] for r in results) / max(total, 1)
    fmt_preserved = sum(1 for r in results if r['formatting_preserved'] and r['diff_valid'])
    live_safe = sum(1 for r in results if r['live_file_untouched'])

    retries_attempted = sum(1 for r in results if r.get('retry_attempted'))
    retries_succeeded = sum(1 for r in results if r.get('retry_succeeded'))
    empty_responses = sum(1 for r in results if r.get('failure_mode') == 'empty_response')
    timeouts = sum(1 for r in results if r.get('failure_mode') == 'timeout')
    parse_failed_after_retry = sum(1 for r in results
                                    if r.get('retry_attempted') and not r.get('retry_succeeded')
                                    and not r.get('intent_valid'))
    missing_fields = sum(1 for r in results if r.get('failure_mode') == 'missing_fields')

    # Usefulness aggregates — only count evidence-complete proposals for quality rates
    all_with_usefulness = [r for r in results if r.get('usefulness_overall')]
    evidence_complete = [r for r in all_with_usefulness if r.get('usefulness_overall') != 'unknown']
    unknown_count = sum(1 for r in all_with_usefulness if r['usefulness_overall'] == 'unknown')
    strong_count = sum(1 for r in evidence_complete if r['usefulness_overall'] == 'strong')
    acceptable_count = sum(1 for r in evidence_complete if r['usefulness_overall'] == 'acceptable')
    weak_count = sum(1 for r in evidence_complete if r['usefulness_overall'] == 'weak')
    u_total = max(len(evidence_complete), 1)
    addresses_count = sum(1 for r in evidence_complete if r.get('addresses_failure_mode'))
    direction_count = sum(1 for r in evidence_complete if r.get('direction_sane'))
    minimal_count = sum(1 for r in all_with_usefulness if r.get('change_minimal'))

    agg = {
        'total_cases': total,
        'scalar_preference_rate': scalars / max(valid_intents, 1),
        'intent_parse_rate': valid_intents / max(total, 1),
        'validator_pass_rate': valid_diffs / max(total, 1),
        'avg_lines_changed': round(avg_lines, 1),
        'formatting_preservation_rate': fmt_preserved / max(valid_diffs, 1) if valid_diffs else 0,
        'live_file_safety_rate': live_safe / max(total, 1),
        'retry_success_rate': retries_succeeded / max(retries_attempted, 1) if retries_attempted else None,
        'empty_response_rate': empty_responses / max(total, 1),
        'timeout_rate': timeouts / max(total, 1),
        'parse_failed_after_retry_rate': parse_failed_after_retry / max(total, 1),
        'missing_fields_rate': missing_fields / max(total, 1),
        'strong_rate': strong_count / u_total,
        'acceptable_rate': acceptable_count / u_total,
        'weak_rate': weak_count / u_total,
        'addresses_failure_rate': addresses_count / u_total,
        'direction_sane_rate': direction_count / u_total,
        'change_minimal_rate': minimal_count / max(len(all_with_usefulness), 1),
        'unknown_rate': unknown_count / max(len(all_with_usefulness), 1),
        'evidence_complete_rate': len(evidence_complete) / max(len(all_with_usefulness), 1),
        'failure_led_framing_rate': sum(1 for r in results if r.get('derived_from_failure_mode')) / max(valid_intents, 1),
        'failure_filtered_targets_rate': sum(1 for r in results if r.get('filtered_by_failure_mode')) / max(valid_intents, 1),
        'failure_family_alignment_rate': sum(1 for r in results if r.get('failure_family_alignment')) / max(valid_intents, 1),
        'per_case': results,
    }

    post_hash = _file_sha256(FULL_TARGET)
    agg['file_hash_before'] = pre_hash
    agg['file_hash_after'] = post_hash
    agg['file_unchanged'] = pre_hash == post_hash

    # Print summary
    print(f"\n{'='*50}")
    print(f"EVAL SUMMARY ({total} cases)")
    print(f"{'='*50}")
    print(f"  Scalar preference rate:       {agg['scalar_preference_rate']:.0%}")
    print(f"  Intent parse rate:            {agg['intent_parse_rate']:.0%}")
    print(f"  Validator pass rate:          {agg['validator_pass_rate']:.0%}")
    print(f"  Avg lines changed:            {agg['avg_lines_changed']}")
    print(f"  Formatting preservation rate: {agg['formatting_preservation_rate']:.0%}")
    print(f"  Live file safety rate:        {agg['live_file_safety_rate']:.0%}")
    print(f"  Retry success rate:           {agg['retry_success_rate']:.0%}" if agg['retry_success_rate'] is not None else "  Retry success rate:           N/A (no retries)")
    print(f"  Empty response rate:          {agg['empty_response_rate']:.0%}")
    print(f"  Timeout rate:                 {agg['timeout_rate']:.0%}")
    print(f"  Parse failed after retry:     {agg['parse_failed_after_retry_rate']:.0%}")
    print(f"  Missing fields rate:          {agg['missing_fields_rate']:.0%}")
    print(f"  Strong rate:                  {agg['strong_rate']:.0%}")
    print(f"  Acceptable rate:              {agg['acceptable_rate']:.0%}")
    print(f"  Weak rate:                    {agg['weak_rate']:.0%}")
    print(f"  Addresses failure rate:       {agg['addresses_failure_rate']:.0%}")
    print(f"  Direction sane rate:          {agg['direction_sane_rate']:.0%}")
    print(f"  Change minimal rate:          {agg['change_minimal_rate']:.0%}")
    print(f"  Unknown rate:                 {agg['unknown_rate']:.0%}")
    print(f"  Evidence complete rate:       {agg['evidence_complete_rate']:.0%}")
    print(f"  Failure-led framing rate:    {agg['failure_led_framing_rate']:.0%}")
    print(f"  Failure-filtered targets:    {agg['failure_filtered_targets_rate']:.0%}")
    print(f"  Failure family alignment:    {agg['failure_family_alignment_rate']:.0%}")
    print(f"  File unchanged:               {agg['file_unchanged']}")

    if output_path:
        with open(output_path, 'w') as f:
            json.dump(agg, f, indent=2, default=str)
        print(f"\nMetrics saved to: {output_path}")

    return agg


if __name__ == '__main__':
    output = 'scripts/eval_proposals_latest.json'
    for i, arg in enumerate(sys.argv):
        if arg == '--output' and i + 1 < len(sys.argv):
            output = sys.argv[i + 1]
    run_eval(os.path.join(MAEZ_ROOT, output))
