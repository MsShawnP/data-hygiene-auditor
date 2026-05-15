"""Detection engines: field type inference, null analysis, mixed formats,
wrong purpose, placeholders, and phantom duplicates."""

import hashlib
import re
from collections import Counter, defaultdict

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

PLACEHOLDER_PATTERNS = [
    r'^test$', r'^n/?a$', r'^null$', r'^none$', r'^tbd$', r'^xxx+$',
    r'^placeholder$', r'^default$', r'^dummy$', r'^sample$', r'^todo$',
    r'^temp$', r'^unknown$', r'^undefined$', r'^blank$', r'^\.+$',
    r'^0{3,}$', r'^-+$', r'^na$',
]
PLACEHOLDER_RE = re.compile('|'.join(PLACEHOLDER_PATTERNS), re.IGNORECASE)

DATE_PATTERNS = [
    (re.compile(r'^\d{4}-\d{2}-\d{2}$'), 'YYYY-MM-DD'),
    (re.compile(r'^\d{2}/\d{2}/\d{4}$'), 'MM/DD/YYYY'),
    (re.compile(r'^\d{1,2}/\d{1,2}/\d{4}$'), 'M/D/YYYY'),
    (re.compile(r'^[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}$'), 'Mon DD, YYYY'),
    (re.compile(r'^\d{1,2}-[A-Za-z]{3}-\d{4}$'), 'DD-Mon-YYYY'),
    (re.compile(r'^\d{4}/\d{2}/\d{2}$'), 'YYYY/MM/DD'),
    (re.compile(r'^\d{4}\.\d{2}\.\d{2}$'), 'YYYY.MM.DD'),
    (re.compile(r'^\d{2}-\d{2}-\d{4}$'), 'MM-DD-YYYY'),
    (re.compile(r'^[A-Za-z]{3,9}\s+\d{1,2}\s+\d{4}$'), 'Mon DD YYYY'),
]

PHONE_PATTERNS = [
    (re.compile(r'^\(\d{3}\)\s?\d{3}-\d{4}$'), '(XXX) XXX-XXXX'),
    (re.compile(r'^\d{3}-\d{3}-\d{4}$'), 'XXX-XXX-XXXX'),
    (re.compile(r'^\d{10}$'), 'XXXXXXXXXX'),
    (re.compile(r'^\d{3}\.\d{3}\.\d{4}$'), 'XXX.XXX.XXXX'),
    (re.compile(r'^\d{3}\s\d{3}\s\d{4}$'), 'XXX XXX XXXX'),
    (re.compile(r'^\+?1-?\d{3}-\d{3}-\d{4}$'), '+1-XXX-XXX-XXXX'),
    (re.compile(r'^\(\d{3}\)\d{7}$'), '(XXX)XXXXXXX'),
]

CURRENCY_PATTERNS = [
    (re.compile(r'^\$[\d,]+\.\d{2}$'), '$X,XXX.XX'),
    (re.compile(r'^\$[\d,]+$'), '$X,XXX'),
    (re.compile(r'^[\d,]+\.\d{2}$'), 'X,XXX.XX (no symbol)'),
    (re.compile(r'^[\d,]+$'), 'X,XXX (bare number)'),
    (re.compile(r'^\$-?[\d,]+\.\d{2}\s*(USD)?$'), '$X,XXX.XX USD'),
    (re.compile(r'^\$[\d,]+\.\d{2}\s+USD$'), '$X,XXX.XX USD'),
]

_NORMALIZE_WS = re.compile(r'\s+')
_NORMALIZE_PUNCT = re.compile(r'[^\w\s@.]')

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def infer_field_type(col_name, values):
    """Infer the semantic type of a field from its name and sample values."""
    name_lower = col_name.lower().replace('_', '').replace(' ', '')
    non_null = [str(v).strip() for v in values if pd.notna(v) and str(v).strip()]
    if not non_null:
        return 'empty'
    sample = non_null[:200]

    if any(k in name_lower for k in [
        'date', 'time', 'created', 'updated', 'ship', 'join', 'birth', 'dob',
    ]):
        return 'date'
    if any(k in name_lower for k in ['phone', 'fax', 'mobile', 'cell', 'tel']):
        return 'phone'
    if any(k in name_lower for k in ['email', 'mail']):
        return 'email'
    if any(k in name_lower for k in [
        'price', 'amount', 'balance', 'cost', 'fee', 'total', 'revenue', 'salary',
    ]):
        return 'currency'
    if any(k in name_lower for k in ['zip', 'postal']):
        return 'zipcode'
    if (
        any(k in name_lower for k in ['id', 'code', 'key', 'sku', 'ref', 'number'])
        and 'phone' not in name_lower
    ):
        return 'id'
    if any(k in name_lower for k in ['first', 'last', 'name', 'fname', 'lname']):
        return 'name'
    if any(k in name_lower for k in ['status', 'state', 'type', 'category', 'flag']):
        return 'categorical'
    if any(k in name_lower for k in ['note', 'comment', 'desc', 'remark', 'memo']):
        return 'freetext'

    date_hits = sum(
        1 for v in sample if any(p.match(v) for p, _ in DATE_PATTERNS)
    )
    if date_hits > len(sample) * 0.5:
        return 'date'
    phone_hits = sum(
        1 for v in sample if any(p.match(v) for p, _ in PHONE_PATTERNS)
    )
    if phone_hits > len(sample) * 0.5:
        return 'phone'
    curr_hits = sum(
        1 for v in sample if any(p.match(v) for p, _ in CURRENCY_PATTERNS)
    )
    if curr_hits > len(sample) * 0.5:
        return 'currency'
    email_hits = sum(1 for v in sample if EMAIL_RE.match(v))
    if email_hits > len(sample) * 0.5:
        return 'email'

    return 'freetext'


def analyze_nulls(series):
    """Baseline null/missing analysis for every field."""
    total = len(series)
    null_count = series.isna().sum()
    whitespace_only = sum(
        1 for v in series if pd.notna(v) and len(str(v)) > 0 and str(v).strip() == ''
    )
    blank_count = sum(1 for v in series if pd.notna(v) and str(v) == '')
    missing = null_count + blank_count + whitespace_only
    pct = (missing / total * 100) if total > 0 else 0
    return {
        'null_count': int(null_count),
        'blank_count': int(blank_count),
        'whitespace_only': int(whitespace_only),
        'total_missing': int(missing),
        'missing_pct': round(pct, 1),
        'total_rows': total,
    }


def analyze_mixed_formats(series, field_type):
    """Detect inconsistent formatting within a field."""
    non_null = [
        (i, str(v).strip()) for i, v in series.items()
        if pd.notna(v) and str(v).strip()
    ]
    if not non_null:
        return None

    if field_type == 'date':
        patterns = DATE_PATTERNS
    elif field_type == 'phone':
        patterns = PHONE_PATTERNS
    elif field_type == 'currency':
        patterns = CURRENCY_PATTERNS
    else:
        return None

    format_counts = Counter()
    unmatched = []
    for idx, val in non_null:
        matched = False
        for regex, label in patterns:
            if regex.match(val):
                format_counts[label] += 1
                matched = True
                break
        if not matched:
            format_counts['(non-standard)'] += 1
            unmatched.append(val)

    if len(format_counts) <= 1:
        return None

    dominant = format_counts.most_common(1)[0]
    total_typed = sum(format_counts.values())
    inconsistent_count = total_typed - dominant[1]
    inconsistent_pct = round(inconsistent_count / total_typed * 100, 1)

    return {
        'field_type': field_type,
        'format_distribution': dict(format_counts.most_common()),
        'dominant_format': dominant[0],
        'dominant_count': dominant[1],
        'inconsistent_count': inconsistent_count,
        'inconsistent_pct': inconsistent_pct,
        'sample_nonstandard': unmatched[:5],
    }


def analyze_wrong_purpose(series, col_name, field_type):
    """Detect fields being used for the wrong purpose."""
    findings = []
    non_null = [
        (i, str(v).strip()) for i, v in series.items()
        if pd.notna(v) and str(v).strip()
    ]
    if not non_null:
        return findings

    if field_type == 'name':
        for idx, val in non_null:
            if re.match(r'^[A-Z]{2,}-\d+', val) or re.match(r'^REF-', val, re.IGNORECASE):
                findings.append({
                    'issue': 'Code/ID stuffed in name field',
                    'example': val,
                    'row': idx,
                })
            elif re.match(r'^\d+$', val):
                findings.append({
                    'issue': 'Numeric value in name field',
                    'example': val,
                    'row': idx,
                })

    if field_type == 'currency':
        for idx, val in non_null:
            if re.match(r'^[a-zA-Z]', val):
                findings.append({
                    'issue': 'Text in currency field',
                    'example': val,
                    'row': idx,
                })

    if field_type == 'email':
        for idx, val in non_null:
            if not EMAIL_RE.match(val) and not PLACEHOLDER_RE.match(val):
                findings.append({
                    'issue': 'Invalid email format',
                    'example': val,
                    'row': idx,
                })

    if field_type == 'id':
        type_counts = Counter()
        for idx, val in non_null:
            if re.match(r'^[A-Za-z]+-\d+$', val):
                type_counts['alphanumeric_code'] += 1
            elif re.match(r'^\d+$', val):
                type_counts['bare_number'] += 1
            else:
                type_counts['other'] += 1
        if len(type_counts) > 1:
            label_map = {
                'alphanumeric_code': 'coded (e.g. CUST-001)',
                'bare_number': 'bare numbers',
                'other': 'other',
            }
            parts = [
                f"{type_counts[k]} {label_map[k]}"
                for k, _ in type_counts.most_common()
            ]
            findings.append({
                'issue': 'Mixed ID formats',
                'example': ' vs '.join(parts),
                'row': None,
            })

    if field_type == 'categorical':
        unique_vals = set(v.lower() for _, v in non_null)
        if unique_vals and all(
            v in ('0', '1', 'y', 'n', 'yes', 'no', 'true', 'false')
            for v in unique_vals
        ):
            raw_vals = set(v for _, v in non_null)
            bool_types = set()
            for v in raw_vals:
                vl = v.lower()
                if vl in ('0', '1'):
                    bool_types.add('numeric')
                elif vl in ('y', 'n'):
                    bool_types.add('y/n')
                elif vl in ('yes', 'no'):
                    bool_types.add('yes/no')
                elif vl in ('true', 'false'):
                    bool_types.add('true/false')
            if len(bool_types) > 1:
                findings.append({
                    'issue': 'Mixed boolean representations',
                    'example': ', '.join(raw_vals),
                    'row': None,
                })
        case_variants = defaultdict(set)
        for _, v in non_null:
            case_variants[v.lower()].add(v)
        for key, variants in case_variants.items():
            if len(variants) > 1:
                findings.append({
                    'issue': 'Inconsistent casing in categorical values',
                    'example': ' / '.join(sorted(variants)),
                    'row': None,
                })

    return findings


def analyze_placeholders(series, col_name):
    """Detect suspiciously uniform or placeholder data."""
    findings = []
    non_null = [str(v).strip() for v in series if pd.notna(v) and str(v).strip()]
    if not non_null:
        return findings

    placeholder_hits = [v for v in non_null if PLACEHOLDER_RE.match(v)]
    if placeholder_hits:
        counter = Counter(placeholder_hits)
        for val, count in counter.most_common(5):
            findings.append({
                'type': 'placeholder_value',
                'value': val,
                'count': count,
                'pct': round(count / len(non_null) * 100, 1),
            })

    val_counts = Counter(non_null)
    total = len(non_null)
    for val, count in val_counts.most_common(5):
        if count >= 3 and (count / total) >= 0.1 and not PLACEHOLDER_RE.match(val):
            findings.append({
                'type': 'suspicious_repetition',
                'value': val,
                'count': count,
                'pct': round(count / total * 100, 1),
            })

    return findings


def analyze_phantom_duplicates(df, sheet_name, field_types=None):
    """Detect records that are the same after normalizing whitespace/case/punctuation."""
    findings = []
    if df.empty or len(df) < 2:
        return findings

    field_types = field_types or {}

    def normalize(val):
        if pd.isna(val):
            return ''
        s = str(val).strip().lower()
        s = _NORMALIZE_WS.sub(' ', s)
        s = _NORMALIZE_PUNCT.sub('', s)
        return s

    id_cols = set()
    for col in df.columns:
        ft = field_types.get(col, infer_field_type(col, df[col].values))
        if ft == 'id':
            id_cols.add(col)
        elif df[col].nunique() == len(df):
            id_cols.add(col)

    content_cols = [c for c in df.columns if c not in id_cols]
    if not content_cols:
        content_cols = list(df.columns)

    normalized = df[content_cols].apply(lambda col: col.map(normalize))

    sig_cols = [c for c in content_cols if normalized[c].nunique() < len(df)]
    if not sig_cols:
        return findings

    norm_subset = normalized[sig_cols]
    combined = norm_subset.iloc[:, 0].astype(str)
    for col in sig_cols[1:]:
        combined = combined + '||' + norm_subset[col].astype(str)
    sigs = combined.apply(
        lambda x: hashlib.md5(x.encode()).hexdigest()
    )
    dup_sigs = sigs[sigs.duplicated(keep=False)]
    if dup_sigs.empty:
        return findings

    groups = defaultdict(list)
    for idx, sig in dup_sigs.items():
        groups[sig].append(idx)

    for sig, indices in groups.items():
        if len(indices) < 2:
            continue
        row_nums = [i + 2 for i in indices]
        sample_rows = []
        for i in indices[:3]:
            row_data = {col: str(df.iloc[i][col]) for col in df.columns[:6]}
            sample_rows.append(row_data)

        raw_match = True
        first_raw = tuple(str(df.iloc[indices[0]][c]) for c in content_cols)
        for i in indices[1:]:
            if tuple(str(df.iloc[i][c]) for c in content_cols) != first_raw:
                raw_match = False
                break

        findings.append({
            'rows': row_nums,
            'group_size': len(indices),
            'exact_match': raw_match,
            'sample_data': sample_rows,
            'matched_on': sig_cols,
            'excluded_id_cols': list(id_cols),
            'type': 'exact_duplicate' if raw_match else 'phantom_duplicate',
        })

    return findings


_FINGERPRINT_PUNCT = re.compile(r'[^\w\s]')


def _fingerprint(val):
    """Key-collision fingerprint: lowercase, strip all punctuation, sort tokens."""
    if pd.isna(val):
        return ''
    s = str(val).strip().lower()
    s = _FINGERPRINT_PUNCT.sub('', s)
    tokens = sorted(s.split())
    return ' '.join(tokens)


def _levenshtein_distance(s1, s2):
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (c1 != c2),
            ))
        prev = curr
    return prev[-1]


def _levenshtein_similarity(s1, s2):
    """Similarity ratio (0.0-1.0) based on Levenshtein distance."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1.0 - _levenshtein_distance(s1, s2) / max_len


def analyze_fuzzy_duplicates(
    df, sheet_name, field_types=None, threshold=0.85,
    phantom_row_sets=None,
):
    """Detect fuzzy duplicates via fingerprint clustering and Levenshtein.

    Finds matches that normalize-and-hash misses: token reordering,
    abbreviations, and typos.
    """
    findings = []
    if df.empty or len(df) < 2:
        return findings

    field_types = field_types or {}
    phantom_row_sets = phantom_row_sets or []

    already_matched = set()
    for row_set in phantom_row_sets:
        already_matched.update(row_set)

    id_cols = set()
    for col in df.columns:
        ft = field_types.get(col, infer_field_type(col, df[col].values))
        if ft == 'id':
            id_cols.add(col)
        elif df[col].nunique() == len(df):
            id_cols.add(col)

    content_cols = [c for c in df.columns if c not in id_cols]
    if not content_cols:
        content_cols = list(df.columns)

    fingerprinted = df[content_cols].apply(lambda col: col.map(_fingerprint))
    combined_fp = fingerprinted.iloc[:, 0].astype(str)
    for col in content_cols[1:]:
        combined_fp = combined_fp + '||' + fingerprinted[col].astype(str)

    fp_groups = defaultdict(list)
    for idx, fp in combined_fp.items():
        fp_groups[fp].append(idx)

    fp_matched = set()
    for fp, indices in fp_groups.items():
        if len(indices) < 2:
            continue
        index_set = frozenset(indices)
        if index_set.issubset(already_matched):
            continue

        fp_matched.update(indices)
        row_nums = [i + 2 for i in indices]
        sample_rows = []
        for i in indices[:3]:
            sample_rows.append(
                {col: str(df.iloc[i][col]) for col in df.columns[:6]},
            )

        differences = {}
        for col in content_cols:
            vals = [str(df.iloc[i][col]) for i in indices]
            unique_vals = list(dict.fromkeys(vals))
            if len(unique_vals) > 1:
                differences[col] = unique_vals[:5]

        findings.append({
            'rows': row_nums,
            'group_size': len(indices),
            'match_method': 'fingerprint',
            'sample_data': sample_rows,
            'field_differences': differences,
            'matched_on': content_cols,
            'excluded_id_cols': list(id_cols),
            'type': 'fuzzy_duplicate',
        })

    skip = already_matched | fp_matched
    unmatched = [i for i in range(len(df)) if i not in skip]

    if len(unmatched) >= 2 and len(unmatched) <= 500:
        norm_strings = {}
        for idx in unmatched:
            parts = [
                str(df.iloc[idx][c]).strip().lower() for c in content_cols
            ]
            norm_strings[idx] = '||'.join(parts)

        used = set()
        for pos, idx_a in enumerate(unmatched):
            if idx_a in used:
                continue
            group = [idx_a]
            for idx_b in unmatched[pos + 1:]:
                if idx_b in used:
                    continue
                sim = _levenshtein_similarity(
                    norm_strings[idx_a], norm_strings[idx_b],
                )
                if sim >= threshold:
                    group.append(idx_b)
                    used.add(idx_b)
            if len(group) < 2:
                continue
            used.add(idx_a)

            row_nums = [i + 2 for i in group]
            sample_rows = []
            for i in group[:3]:
                sample_rows.append(
                    {col: str(df.iloc[i][col]) for col in df.columns[:6]},
                )

            differences = {}
            for col in content_cols:
                vals = [str(df.iloc[i][col]).strip() for i in group]
                unique_vals = list(dict.fromkeys(vals))
                if len(unique_vals) > 1:
                    sim = _levenshtein_similarity(
                        unique_vals[0].lower(), unique_vals[1].lower(),
                    )
                    differences[col] = {
                        'values': unique_vals[:5],
                        'similarity': round(sim, 2),
                    }

            findings.append({
                'rows': row_nums,
                'group_size': len(group),
                'match_method': 'levenshtein',
                'similarity_threshold': threshold,
                'sample_data': sample_rows,
                'field_differences': differences,
                'matched_on': content_cols,
                'excluded_id_cols': list(id_cols),
                'type': 'fuzzy_duplicate',
            })

    return findings


def rate_severity(finding_type, details):
    """Assign High / Medium / Low severity."""
    if finding_type == 'fuzzy_duplicate':
        if details.get('match_method') == 'fingerprint':
            return 'Medium'
        return 'Low'

    if finding_type == 'phantom_duplicate':
        if details.get('type') == 'exact_duplicate':
            return 'High'
        return 'High' if details.get('group_size', 0) > 3 else 'Medium'

    if finding_type == 'mixed_format':
        pct = details.get('inconsistent_pct', 0)
        if pct > 30:
            return 'High'
        elif pct > 10:
            return 'Medium'
        return 'Low'

    if finding_type == 'wrong_purpose':
        return 'High'

    if finding_type == 'placeholder':
        pct = details.get('pct', 0)
        if pct > 20:
            return 'High'
        elif pct > 5:
            return 'Medium'
        return 'Low'

    if finding_type == 'null_analysis':
        pct = details.get('missing_pct', 0)
        if pct > 50:
            return 'High'
        elif pct > 20:
            return 'Medium'
        elif pct > 5:
            return 'Low'
        return None

    return 'Medium'
