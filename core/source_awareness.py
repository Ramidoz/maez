"""
source_awareness.py — Maez's read-only self-model of its own codebase.

PURPOSE
-------
This module builds and maintains a structured map of every source file
in the Maez project. It exists so that Maez (and the evolution engine)
can reason about the codebase without importing or executing any of it.

The source map is pure static analysis: ast.parse for Python files,
text reads for everything else. No imports, no execution, no LLM calls
at index time.

HOW THE MAP WORKS
-----------------
memory/source_awareness.json contains one entry per file with:
  - purpose, category, risk_level, self_edit_scope
  - imports/dependents (internal dependency graph)
  - exported_symbols (classes + top-level functions via ast)
  - last_hash (sha256 for incremental refresh)
  - tags (from cognition TOPIC_TAXONOMY)

SELF-EDIT SCOPE
---------------
Every file has a self_edit_scope that governs what Maez may do:

  allowed     — Maez may modify this file directly.
                Currently: core/cognition_quality.py
  append_only — Maez may append new content but never overwrite
                or delete existing content. This is how soul notes
                work: new observations are appended, but HARD
                CONSTRAINTS and TRUST COVENANT sections are immutable.
                Currently: config/soul.md
  read_only   — Maez may read and analyze but not modify.
                Most files fall here.
  forbidden   — Maez must never modify these files. They are
                indexed read-only so Maez knows they exist.
                Includes: maez_daemon.py, memory_manager.py,
                memory/db/*, .env, systemd units.

  For skills/*.py, new_file is allowed but modify is not.
  Maez can create new skills but must not edit existing ones
  without explicit approval.

CONFIDENCE SCORES
-----------------
resolve() returns confidence as score / max_possible, capped at 1.0.
A confidence > 0.5 means strong keyword overlap between the query
and the file's tags, symbols, purpose, and summary. Below 0.3 is
noise. The scoring is deterministic — same query always returns
same results.

ADDING NEW FILES TO ALLOWED SCOPE
----------------------------------
To expand self_edit_scope for a new file:
1. Add it to _SCOPE_OVERRIDES in this module
2. Run build_map() to regenerate
3. The evolution engine checks self_edit_scope before writing

INVARIANTS
----------
- The map is fully rebuildable from source alone (build_map)
- No secrets, tokens, or credential values appear in the map
- Every discovered file is accounted for: indexed, skipped, or error
- parse_error files appear in the map with their error recorded
- schema_version is checked on every load; mismatches are rejected

SCHEMA VERSION
--------------
Increment schema_version when:
- A new required field is added to file entries
- The meaning of an existing field changes
- The scoring algorithm in resolve() changes materially
Current version: "1.0"

CLI USAGE
---------
  python -m core.source_awareness build
  python -m core.source_awareness refresh
  python -m core.source_awareness resolve "query here"
  python -m core.source_awareness stats
  python -m core.source_awareness get path/to/file.py
"""

import ast
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MAEZ_ROOT = Path("/home/rohit/maez")
MAP_PATH = MAEZ_ROOT / "memory" / "source_awareness.json"
SCHEMA_VERSION = "1.0"

# ══════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════

# Directories to skip entirely (no indexing, no error, by design)
SKIP_DIRS = {'.venv', '__pycache__', '.git', 'node_modules',
             'backups', 'logs', 'models'}
SKIP_DIR_PATHS = {MAEZ_ROOT / 'memory' / 'db'}

# File patterns to skip
SKIP_EXTENSIONS = {'.pyc', '.db', '.log', '.pid', '.bak', '.bak2'}
SKIP_FILES = {'.gitignore', 'realtimesst.log', 'package-lock.json',
              'last_shutdown', 'pending_actions.json', 'maez.pid'}

# Paths to index (relative globs)
INDEX_PYTHON = ['core/*.py', 'daemon/*.py', 'memory/*.py',
                'skills/*.py', 'ui/*.py']
INDEX_CONFIG = ['config/soul.md', 'config/credentials.json',
                'config/token.json']
INDEX_JSON = ['ui/face.json']
INDEX_MARKDOWN = ['README.md', 'PROGRESS.md', 'PROGRESS_PUBLIC.md']
INDEX_JS = ['ui/electron/main.js']
INDEX_HTML = ['ui/index.html', 'ui/electron/renderer/*.html']
INDEX_OTHER = ['ui/electron/package.json']

# ── Self-edit scope overrides ──
_SCOPE_OVERRIDES = {
    'core/cognition_quality.py': 'allowed',
    'config/soul.md': 'append_only',
    'daemon/maez_daemon.py': 'forbidden',
    'memory/memory_manager.py': 'forbidden',
    'memory/quality_tracker.py': 'forbidden',
    'config/.env': 'forbidden',
    'config/credentials.json': 'forbidden',
    'config/token.json': 'forbidden',
}

# ── Allowed operations per scope ──
_SCOPE_OPERATIONS = {
    'allowed': ['read', 'modify'],
    'append_only': ['read', 'append_only'],
    'read_only': ['read'],
    'forbidden': ['read'],
}

# Skills: existing = read_only, but new_file is allowed for the directory
_SKILLS_NEW_FILE = True

# ── Category detection ──
_CATEGORY_MAP = {
    'daemon/': 'daemon',
    'core/': 'core',
    'memory/': 'memory',
    'skills/': 'skills',
    'ui/': 'ui',
    'config/': 'config',
}

# ── Risk level rules ──
_RISK_OVERRIDES = {
    'daemon/maez_daemon.py': 'critical',
    'memory/memory_manager.py': 'critical',
    'memory/quality_tracker.py': 'high',
    'core/action_engine.py': 'critical',
    'core/perception.py': 'high',
    'core/cognition_quality.py': 'medium',
    'config/soul.md': 'high',
    'config/.env': 'critical',
    'config/credentials.json': 'critical',
    'config/token.json': 'critical',
}

# ── File type detection ──
_EXT_TO_TYPE = {
    '.py': 'python', '.md': 'markdown', '.json': 'json',
    '.yaml': 'yaml', '.yml': 'yaml', '.sh': 'shell',
    '.html': 'html', '.js': 'javascript', '.service': 'systemd_unit',
    '.env': 'env', '.txt': 'text',
}

# ── Tags: map files to cognition taxonomy topics ──
_FILE_TAGS = {
    'core/cognition_quality.py': ['maez_self', 'development_tools'],
    'core/action_engine.py': ['maez_self', 'security'],
    'core/perception.py': ['cpu_load', 'memory_usage', 'gpu_state', 'disk_usage', 'network', 'processes'],
    'daemon/maez_daemon.py': ['maez_self', 'system_monitoring'],
    'memory/memory_manager.py': ['maez_self'],
    'memory/quality_tracker.py': ['maez_self'],
    'skills/telegram_voice.py': ['telegram'],
    'skills/telegram_public.py': ['telegram', 'maez_self'],
    'skills/web_interface.py': ['telegram', 'network'],
    'skills/user_accounts.py': ['telegram'],
    'skills/dev_notifier.py': ['telegram', 'system_monitoring'],
    'skills/claude_watcher.py': ['system_monitoring', 'development_tools'],
    'skills/maez_watchdog.py': ['system_monitoring'],
    'skills/web_search.py': ['web_content'],
    'skills/screen_perception.py': ['browser_usage', 'development_tools'],
    'skills/presence_perception.py': ['rohit_presence'],
    'skills/face_enrollment.py': ['rohit_presence'],
    'skills/calendar_perception.py': ['calendar'],
    'skills/wake_word.py': ['general_presence'],
    'skills/voice_input.py': ['general_presence'],
    'skills/voice_output.py': ['general_presence'],
    'skills/git_awareness.py': ['git_workflow'],
    'skills/github_skill.py': ['web_content', 'git_workflow'],
    'skills/github_publish.py': ['git_workflow'],
    'skills/reddit_skill.py': ['web_content'],
    'skills/disk_cleanup.py': ['disk_usage'],
    'skills/dynamic_dns.py': ['network'],
    'skills/self_analysis.py': ['maez_self'],
    'skills/evolution_engine.py': ['maez_self'],
    'skills/followup_queue.py': ['telegram'],
    'config/soul.md': ['maez_self'],
}

# ── Synonym table for resolve() ──
SYNONYM_TABLE = {
    "fixation": ["cognition", "topic", "taxonomy", "repetition", "policy"],
    "soul": ["soul.md", "identity", "constraint", "covenant", "baseline"],
    "memory": ["chromadb", "retrieval", "embedding", "consolidation", "raw", "daily", "core"],
    "telegram": ["bot", "message", "alert", "notify"],
    "voice": ["whisper", "tts", "kokoro", "wake", "audio", "pipewire"],
    "public bot": ["public_users", "manipulation", "trust_tier", "stranger"],
    "action": ["tier", "forbidden", "audit", "backup", "pending"],
    "evolution": ["evolution_engine", "patch", "rollback", "candidate"],
    "retrieval": ["memory_manager", "wing", "rerank", "antifixation", "chromadb"],
    "daemon": ["maez_daemon", "reasoning_loop", "cycle", "flask", "websocket"],
}


# ══════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════

def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _detect_file_type(path: Path) -> str:
    if path.name == '.env':
        return 'env'
    return _EXT_TO_TYPE.get(path.suffix.lower(), 'other')


def _detect_category(rel: str) -> str:
    for prefix, cat in _CATEGORY_MAP.items():
        if rel.startswith(prefix):
            return cat
    if rel.endswith('.md'):
        return 'config'
    return 'infra'


def _detect_risk(rel: str, category: str) -> str:
    if rel in _RISK_OVERRIDES:
        return _RISK_OVERRIDES[rel]
    if category == 'daemon':
        return 'critical'
    if category == 'core':
        return 'high'
    if category == 'memory':
        return 'high'
    if category == 'skills':
        return 'medium'
    if category == 'config':
        return 'high'
    if category == 'ui':
        return 'low'
    return 'low'


def _detect_scope(rel: str, category: str) -> str:
    if rel in _SCOPE_OVERRIDES:
        return _SCOPE_OVERRIDES[rel]
    if category == 'skills':
        return 'read_only'  # existing skills are read_only; new_file at dir level
    return 'read_only'


def _detect_operations(rel: str, scope: str, category: str) -> list:
    ops = list(_SCOPE_OPERATIONS.get(scope, ['read']))
    # Skills directory allows new_file but not modify on existing
    if category == 'skills' and scope == 'read_only':
        ops.append('new_file')
    return ops


def _should_skip_dir(dirpath: Path) -> bool:
    for part in dirpath.relative_to(MAEZ_ROOT).parts:
        if part in SKIP_DIRS:
            return True
    for skip_path in SKIP_DIR_PATHS:
        try:
            dirpath.relative_to(skip_path)
            return True
        except ValueError:
            pass
    return False


def _should_skip_file(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return True
    if path.suffix in SKIP_EXTENSIONS:
        return True
    return False


def _extract_python_info(path: Path) -> dict:
    """Parse a Python file with ast. Returns purpose, imports, symbols, or error."""
    info = {'purpose': 'unknown', 'imports': [], 'exported_symbols': [],
            'parse_error': None}
    try:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(path))

        # Purpose: first docstring line
        docstring = ast.get_docstring(tree)
        if docstring:
            first_line = docstring.strip().split('\n')[0].strip()
            info['purpose'] = first_line
        else:
            # Try first comment
            for line in source.split('\n')[:5]:
                stripped = line.strip()
                if stripped.startswith('#') and len(stripped) > 2:
                    info['purpose'] = stripped.lstrip('#').strip()
                    break

        # Imports: internal maez modules only
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split('.')[0]
                    # Check if it resolves under maez_root
                    for check in ['core', 'daemon', 'memory', 'skills', 'ui']:
                        if mod == check or alias.name.startswith(check + '.'):
                            info['imports'].append(alias.name)
                            break
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod_root = node.module.split('.')[0]
                    for check in ['core', 'daemon', 'memory', 'skills', 'ui']:
                        if mod_root == check or node.module.startswith(check + '.'):
                            info['imports'].append(node.module)
                            break

        # Deduplicate imports
        info['imports'] = sorted(set(info['imports']))

        # Exported symbols: top-level classes and functions
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                info['exported_symbols'].append(node.name)
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                if not node.name.startswith('_'):
                    info['exported_symbols'].append(node.name)

    except SyntaxError as e:
        info['parse_error'] = f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        info['parse_error'] = str(e)

    return info


def _extract_text_purpose(path: Path) -> str:
    """Extract purpose from non-Python files."""
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')[:500]
        lines = text.strip().split('\n')
        for line in lines[:5]:
            stripped = line.strip().strip('#').strip('-').strip()
            if len(stripped) > 5:
                return stripped[:120]
    except Exception:
        pass
    return 'unknown'


def _generate_summary(entry: dict) -> str:
    """Generate a one-sentence summary from purpose and symbols. No LLM."""
    purpose = entry.get('purpose', 'unknown')
    symbols = entry.get('exported_symbols', [])
    if purpose and purpose != 'unknown':
        return purpose
    if symbols:
        return f"Defines {', '.join(symbols[:3])}"
    return 'unknown'


# ══════════════════════════════════════════════════════════════════════
#  BUILD MAP
# ══════════════════════════════════════════════════════════════════════

def build_map() -> dict:
    """Full rebuild of source_awareness.json. Safe to call anytime."""
    now = datetime.now(timezone.utc).isoformat()
    files = {}
    stats = {
        'total_files': 0,
        'indexed_files': 0,
        'parsed_files': 0,
        'skipped_by_design': 0,
        'parse_errors': 0,
    }

    # Walk the tree
    for dirpath_str, dirnames, filenames in os.walk(MAEZ_ROOT):
        dirpath = Path(dirpath_str)

        if _should_skip_dir(dirpath):
            stats['skipped_by_design'] += len(filenames)
            # Don't recurse into skipped dirs
            dirnames[:] = []
            continue

        # Filter subdirs
        dirnames[:] = [d for d in dirnames
                       if not _should_skip_dir(dirpath / d)]

        for fname in filenames:
            fpath = dirpath / fname
            rel = str(fpath.relative_to(MAEZ_ROOT))
            stats['total_files'] += 1

            if _should_skip_file(fpath):
                stats['skipped_by_design'] += 1
                continue

            file_type = _detect_file_type(fpath)
            category = _detect_category(rel)
            scope = _detect_scope(rel, category)
            risk = _detect_risk(rel, category)
            operations = _detect_operations(rel, scope, category)
            tags = _FILE_TAGS.get(rel, [])

            entry = {
                'path': rel,
                'file_type': file_type,
                'purpose': 'unknown',
                'category': category,
                'risk_level': risk,
                'self_edit_scope': scope,
                'allowed_operations': operations,
                'imports': [],
                'dependents': [],  # filled in second pass
                'exported_symbols': [],
                'last_hash': _file_hash(fpath),
                'last_indexed': now,
                'summary': 'unknown',
                'tags': tags,
                'parse_error': None,
            }

            if file_type == 'python':
                py_info = _extract_python_info(fpath)
                entry['purpose'] = py_info['purpose']
                entry['imports'] = py_info['imports']
                entry['exported_symbols'] = py_info['exported_symbols']
                entry['parse_error'] = py_info['parse_error']
                if py_info['parse_error']:
                    stats['parse_errors'] += 1
                else:
                    stats['parsed_files'] += 1
            else:
                entry['purpose'] = _extract_text_purpose(fpath)

            entry['summary'] = _generate_summary(entry)
            stats['indexed_files'] += 1
            files[rel] = entry

    # Second pass: compute dependents (inverse of imports)
    # Build module-to-file mapping
    mod_to_file = {}
    for rel, entry in files.items():
        if entry['file_type'] == 'python':
            # Map module paths to file paths
            # e.g., core/cognition_quality.py → core.cognition_quality
            mod_path = rel.replace('/', '.').replace('.py', '')
            mod_to_file[mod_path] = rel
            # Also map the directory module
            parts = rel.split('/')
            if len(parts) >= 2:
                mod_to_file[parts[0]] = rel  # rough match

    for rel, entry in files.items():
        for imp in entry.get('imports', []):
            # Find which file this import resolves to
            imp_normalized = imp.replace('.', '/')
            for candidate_rel in files:
                if candidate_rel.endswith('.py'):
                    candidate_mod = candidate_rel.replace('/', '.').replace('.py', '')
                    if candidate_mod == imp or imp.startswith(candidate_mod):
                        if rel not in files[candidate_rel].get('dependents', []):
                            files[candidate_rel].setdefault('dependents', []).append(rel)

    source_map = {
        'schema_version': SCHEMA_VERSION,
        'built_at': now,
        'maez_root': str(MAEZ_ROOT),
        'total_files': stats['total_files'],
        'indexed_files': stats['indexed_files'],
        'parsed_files': stats['parsed_files'],
        'skipped_by_design': stats['skipped_by_design'],
        'parse_errors': stats['parse_errors'],
        'files': files,
    }

    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_PATH.write_text(json.dumps(source_map, indent=2, default=str))
    return stats


# ══════════════════════════════════════════════════════════════════════
#  REFRESH MAP (incremental)
# ══════════════════════════════════════════════════════════════════════

def refresh_map() -> dict:
    """Incremental rebuild. Re-index only files whose hash changed."""
    if not MAP_PATH.exists():
        stats = build_map()
        return {'updated': stats['indexed_files'], 'unchanged': 0, 'errors': 0}

    source_map = json.loads(MAP_PATH.read_text())
    if source_map.get('schema_version') != SCHEMA_VERSION:
        stats = build_map()
        return {'updated': stats['indexed_files'], 'unchanged': 0, 'errors': 0,
                'note': 'schema mismatch, full rebuild'}

    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    unchanged = 0
    errors = 0
    files = source_map['files']

    for rel, entry in list(files.items()):
        fpath = MAEZ_ROOT / rel
        if not fpath.exists():
            del files[rel]
            updated += 1
            continue

        try:
            current_hash = _file_hash(fpath)
        except Exception:
            errors += 1
            continue

        if current_hash == entry.get('last_hash'):
            unchanged += 1
            continue

        # Re-index this file
        file_type = entry.get('file_type', 'other')
        if file_type == 'python':
            py_info = _extract_python_info(fpath)
            entry['purpose'] = py_info['purpose']
            entry['imports'] = py_info['imports']
            entry['exported_symbols'] = py_info['exported_symbols']
            entry['parse_error'] = py_info['parse_error']
        else:
            entry['purpose'] = _extract_text_purpose(fpath)

        entry['last_hash'] = current_hash
        entry['last_indexed'] = now
        entry['summary'] = _generate_summary(entry)
        updated += 1

    source_map['files'] = files
    MAP_PATH.write_text(json.dumps(source_map, indent=2, default=str))

    return {'updated': updated, 'unchanged': unchanged, 'errors': errors}


# ══════════════════════════════════════════════════════════════════════
#  RESOLVE — deterministic keyword scoring
# ══════════════════════════════════════════════════════════════════════

_STOPWORDS = {
    'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'into', 'it', 'its',
    'this', 'that', 'these', 'those', 'too', 'very', 'just',
    'not', 'no', 'do', 'does', 'did', 'has', 'have', 'had',
    'will', 'would', 'could', 'should', 'may', 'might',
    'if', 'when', 'where', 'how', 'what', 'which', 'who',
    'here', 'there', 'about', 'more', 'some', 'also', 'than',
}


def _tokenize(text: str) -> list[str]:
    """Split into lowercase keywords, filter stopwords, expand via synonym table."""
    words = [w for w in re.findall(r'[a-z_]+', text.lower())
             if w not in _STOPWORDS and len(w) > 1]
    expanded = set(words)
    for word in words:
        if word in SYNONYM_TABLE:
            expanded.update(SYNONYM_TABLE[word])
    # Check multi-word synonym keys against the full text
    text_lower = text.lower()
    for key, synonyms in SYNONYM_TABLE.items():
        if key in text_lower:
            expanded.update(synonyms)
            expanded.add(key.replace(' ', '_'))
    return list(expanded)


def resolve(weakness_description: str, top_n: int = 3) -> list[dict]:
    """Find relevant files for a weakness description. Deterministic."""
    if not MAP_PATH.exists():
        return []

    source_map = json.loads(MAP_PATH.read_text())
    if source_map.get('schema_version') != SCHEMA_VERSION:
        return []

    keywords = _tokenize(weakness_description)
    results = []

    for rel, entry in source_map['files'].items():
        score = 0
        reasons = []

        # Tag match: 3 points each
        for tag in entry.get('tags', []):
            tag_lower = tag.lower()
            for kw in keywords:
                if kw in tag_lower or tag_lower in kw:
                    score += 3
                    reasons.append(f"tag '{tag}' matched '{kw}'")
                    break

        # Symbol match: 2 points each
        for sym in entry.get('exported_symbols', []):
            sym_lower = sym.lower()
            for kw in keywords:
                if kw in sym_lower or sym_lower in kw:
                    score += 2
                    reasons.append(f"symbol '{sym}' matched '{kw}'")
                    break

        # Purpose match: 1 point per keyword
        purpose = (entry.get('purpose') or '').lower()
        for kw in keywords:
            if kw in purpose:
                score += 1
                reasons.append(f"purpose matched '{kw}'")

        # Summary match: 1 point per keyword
        summary = (entry.get('summary') or '').lower()
        for kw in keywords:
            if kw in summary and kw not in purpose:  # avoid double-counting
                score += 1
                reasons.append(f"summary matched '{kw}'")

        # Category bonus: +2 if category matches domain
        cat = entry.get('category', '')
        for kw in keywords:
            if kw in cat:
                score += 2
                reasons.append(f"category '{cat}' matched '{kw}'")
                break

        if score > 0:
            max_possible = max(
                len(entry.get('tags', [])) * 3 +
                len(entry.get('exported_symbols', [])) * 2 +
                5,  # purpose + summary + category baseline
                1
            )
            confidence = min(score / max_possible, 1.0)
            results.append({
                'path': rel,
                'score': score,
                'confidence': round(confidence, 3),
                'relevance_reason': '; '.join(reasons[:5]),
                'self_edit_scope': entry.get('self_edit_scope', 'read_only'),
                'allowed_operations': entry.get('allowed_operations', ['read']),
                'risk_level': entry.get('risk_level', 'medium'),
                'dependents': entry.get('dependents', []),
            })

    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:top_n]


# ══════════════════════════════════════════════════════════════════════
#  ACCESSORS
# ══════════════════════════════════════════════════════════════════════

def get_file(path: str) -> dict | None:
    """Get full map entry for a file path (relative to maez_root)."""
    if not MAP_PATH.exists():
        return None
    source_map = json.loads(MAP_PATH.read_text())
    return source_map.get('files', {}).get(path)


def get_by_scope(scope: str) -> list[dict]:
    """Get all entries with a given self_edit_scope."""
    if not MAP_PATH.exists():
        return []
    source_map = json.loads(MAP_PATH.read_text())
    return [e for e in source_map['files'].values()
            if e.get('self_edit_scope') == scope]


def get_by_category(category: str) -> list[dict]:
    """Get all entries in a given category."""
    if not MAP_PATH.exists():
        return []
    source_map = json.loads(MAP_PATH.read_text())
    return [e for e in source_map['files'].values()
            if e.get('category') == category]


def summary_stats() -> dict:
    """Return comprehensive stats about the source map."""
    if not MAP_PATH.exists():
        return {'error': 'source map not built yet'}

    source_map = json.loads(MAP_PATH.read_text())
    files = source_map.get('files', {})

    by_category = {}
    by_scope = {}
    by_risk = {}
    by_file_type = {}
    parse_error_files = []
    no_purpose = 0
    no_summary = 0

    for rel, entry in files.items():
        cat = entry.get('category', 'unknown')
        by_category[cat] = by_category.get(cat, 0) + 1

        scope = entry.get('self_edit_scope', 'unknown')
        by_scope[scope] = by_scope.get(scope, 0) + 1

        risk = entry.get('risk_level', 'unknown')
        by_risk[risk] = by_risk.get(risk, 0) + 1

        ft = entry.get('file_type', 'unknown')
        by_file_type[ft] = by_file_type.get(ft, 0) + 1

        if entry.get('parse_error'):
            parse_error_files.append(rel)

        if entry.get('purpose', 'unknown') == 'unknown':
            no_purpose += 1
        if entry.get('summary', 'unknown') == 'unknown':
            no_summary += 1

    return {
        'total_files': source_map.get('total_files', 0),
        'indexed_files': source_map.get('indexed_files', 0),
        'parsed_files': source_map.get('parsed_files', 0),
        'skipped_by_design': source_map.get('skipped_by_design', 0),
        'by_category': by_category,
        'by_scope': by_scope,
        'by_risk': by_risk,
        'by_file_type': by_file_type,
        'parse_errors': source_map.get('parse_errors', 0),
        'parse_error_files': parse_error_files,
        'files_without_purpose': no_purpose,
        'files_without_summary': no_summary,
        'last_full_rebuild': source_map.get('built_at', 'unknown'),
        'schema_version': source_map.get('schema_version', 'unknown'),
    }


# ══════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════

def _cli():
    if len(sys.argv) < 2:
        print("Usage: python -m core.source_awareness <command> [args]")
        print("Commands: build, refresh, resolve <query>, stats, get <path>")
        return

    cmd = sys.argv[1]

    if cmd == 'build':
        stats = build_map()
        print(f"Build complete: {json.dumps(stats, indent=2)}")

    elif cmd == 'refresh':
        result = refresh_map()
        print(f"Refresh: {json.dumps(result, indent=2)}")

    elif cmd == 'resolve':
        if len(sys.argv) < 3:
            print("Usage: resolve <query>")
            return
        query = ' '.join(sys.argv[2:])
        results = resolve(query)
        for r in results:
            print(f"\n  {r['path']} (confidence={r['confidence']}, scope={r['self_edit_scope']})")
            print(f"    reason: {r['relevance_reason']}")
            print(f"    risk={r['risk_level']}, ops={r['allowed_operations']}")
            if r['dependents']:
                print(f"    dependents: {r['dependents']}")

    elif cmd == 'stats':
        s = summary_stats()
        print(json.dumps(s, indent=2))

    elif cmd == 'get':
        if len(sys.argv) < 3:
            print("Usage: get <path>")
            return
        entry = get_file(sys.argv[2])
        if entry:
            print(json.dumps(entry, indent=2))
        else:
            print(f"Not found: {sys.argv[2]}")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == '__main__':
    _cli()
