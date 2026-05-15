"""Fix suggestion generator — produces actionable pandas code snippets per finding."""

from __future__ import annotations


def generate_fix(issue_type: str, detail: dict, col_name: str = '',
                 field_type: str = '') -> dict | None:
    """Generate a fix suggestion for an audit finding.

    Returns a dict with 'description', 'code', and 'strategy' keys,
    or None if no automated fix applies.
    """
    handler = _HANDLERS.get(issue_type)
    if handler:
        return handler(detail, col_name, field_type)
    return None


def _fix_mixed_format(detail, col_name, field_type):
    c = _col(col_name)
    dominant = detail.get('dominant_format', '')
    ftype = detail.get('field_type', field_type)

    if ftype == 'date':
        return {
            'strategy': 'normalize_dates',
            'description': (
                f'Standardize all dates in "{col_name}" to'
                f' {dominant or "YYYY-MM-DD"} format'
            ),
            'code': (
                f'df[{c}] = pd.to_datetime(\n'
                f'    df[{c}], format="mixed", dayfirst=False\n'
                f').dt.strftime("%Y-%m-%d")'
            ),
        }

    if ftype == 'phone':
        return {
            'strategy': 'normalize_phones',
            'description': (
                f'Standardize all phone numbers in "{col_name}" to'
                f' {dominant or "(XXX) XXX-XXXX"} format'
            ),
            'code': (
                f'digits = df[{c}].str.replace(r"\\D", "", regex=True)\n'
                f'digits = digits.str.slice(-10)\n'
                f'df[{c}] = (\n'
                f'    "(" + digits.str[:3] + ") "\n'
                f'    + digits.str[3:6] + "-" + digits.str[6:]\n'
                f')'
            ),
        }

    if ftype == 'currency':
        return {
            'strategy': 'normalize_currency',
            'description': (
                f'Standardize all currency values in "{col_name}" to'
                ' numeric format'
            ),
            'code': (
                f'df[{c}] = (\n'
                f'    df[{c}].str.replace(r"[^\\d.]", "", regex=True)\n'
                f'    .astype(float)\n'
                f')'
            ),
        }

    return None


def _fix_placeholder(detail, col_name, field_type):
    c = _col(col_name)
    val = detail.get('value', '')
    count = detail.get('count', 0)

    return {
        'strategy': 'replace_placeholders',
        'description': (
            f'Replace {count} placeholder values ("{val}") in'
            f' "{col_name}" with NaN for proper missing-data handling'
        ),
        'code': (
            f'import numpy as np\n'
            f'df[{c}] = df[{c}].replace({_col(val)}, np.nan)'
        ),
    }


def _fix_suspicious_repetition(detail, col_name, field_type):
    c = _col(col_name)
    val = detail.get('value', '')
    count = detail.get('count', 0)
    pct = detail.get('pct', 0)

    return {
        'strategy': 'flag_repetitions',
        'description': (
            f'Flag {count} rows where "{col_name}" = "{val}"'
            f' ({pct}%) for manual review'
        ),
        'code': (
            f'df["_{col_name}_review"] = (\n'
            f'    df[{c}] == {_col(val)}\n'
            f')'
        ),
    }


def _fix_wrong_purpose(detail, col_name, field_type):
    c = _col(col_name)
    issue = detail.get('issue', '')
    example = detail.get('example', '')

    if 'invalid email' in issue.lower():
        return {
            'strategy': 'flag_invalid_emails',
            'description': (
                f'Flag invalid email addresses in "{col_name}"'
                ' for correction'
            ),
            'code': (
                f'email_re = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$"\n'
                f'df["_{col_name}_invalid"] = ~df[{c}].str.match(\n'
                f'    email_re, na=False\n'
                f')'
            ),
        }

    if 'mixed id' in issue.lower():
        return {
            'strategy': 'standardize_ids',
            'description': (
                f'Identify rows with inconsistent ID formats in'
                f' "{col_name}" ({example})'
            ),
            'code': (
                f'df["_{col_name}_format"] = df[{c}].apply(\n'
                f'    lambda x: "coded" if isinstance(x, str)\n'
                f'    and "-" in x else "numeric"\n'
                f')'
            ),
        }

    if 'text in currency' in issue.lower():
        return {
            'strategy': 'flag_non_numeric',
            'description': (
                f'Flag non-numeric values in currency field'
                f' "{col_name}"'
            ),
            'code': (
                f'df["_{col_name}_invalid"] = ~df[{c}].str.match(\n'
                f'    r"^[\\$\\d,\\.\\-]+$", na=False\n'
                f')'
            ),
        }

    return {
        'strategy': 'flag_misuse',
        'description': (
            f'Flag misused values in "{col_name}": {issue}'
        ),
        'code': (
            f'# Review rows where {col_name} contains unexpected data\n'
            f'mask = df[{c}].notna()\n'
            f'suspect = df.loc[mask, {c}]'
        ),
    }


def _fix_null_analysis(detail, col_name, field_type):
    c = _col(col_name)
    pct = detail.get('missing_pct', 0)
    total_missing = detail.get('total_missing', 0)

    if pct > 50:
        return {
            'strategy': 'evaluate_column',
            'description': (
                f'"{col_name}" is {pct}% missing ({total_missing} values)'
                ' — evaluate whether to drop the column'
            ),
            'code': (
                f'# Option A: Drop the column entirely\n'
                f'df = df.drop(columns=[{c}])\n\n'
                f'# Option B: Keep but document the gap\n'
                f'# {pct}% missing — flag in metadata'
            ),
        }

    if pct > 20:
        return {
            'strategy': 'impute_or_flag',
            'description': (
                f'Fill {total_missing} missing values in'
                f' "{col_name}" ({pct}%)'
            ),
            'code': (
                f'# Option A: Fill with most common value\n'
                f'df[{c}] = df[{c}].fillna(df[{c}].mode()[0])\n\n'
                f'# Option B: Fill with a sentinel\n'
                f'df[{c}] = df[{c}].fillna("MISSING")'
            ),
        }

    return {
        'strategy': 'fill_missing',
        'description': (
            f'Fill {total_missing} missing values in'
            f' "{col_name}" ({pct}%)'
        ),
        'code': (
            f'df[{c}] = df[{c}].fillna(df[{c}].mode()[0])'
        ),
    }


def generate_dup_fix(dup_type: str, detail: dict,
                     sheet_name: str = '') -> dict | None:
    """Generate a fix suggestion for a duplicate finding."""
    rows = detail.get('rows', [])
    row_str = ', '.join(str(r) for r in rows[:10])

    if dup_type == 'exact_duplicate':
        return {
            'strategy': 'drop_exact_duplicates',
            'description': (
                f'Remove {detail.get("group_size", 0)} exact duplicate'
                f' rows (rows {row_str})'
            ),
            'code': 'df = df.drop_duplicates(keep="first").reset_index(drop=True)',
        }

    if dup_type == 'phantom_duplicate':
        return {
            'strategy': 'normalize_and_dedup',
            'description': (
                f'Normalize and deduplicate {detail.get("group_size", 0)}'
                f' phantom duplicate rows (rows {row_str})'
            ),
            'code': (
                '# Normalize text columns before deduplication\n'
                'text_cols = df.select_dtypes(include="object").columns\n'
                'for col in text_cols:\n'
                '    df[col] = df[col].str.strip().str.lower()\n'
                'df = df.drop_duplicates(keep="first").reset_index(drop=True)'
            ),
        }

    if dup_type == 'fuzzy_duplicate':
        method = detail.get('match_method', 'fingerprint')
        return {
            'strategy': 'review_fuzzy_matches',
            'description': (
                f'Review {detail.get("group_size", 0)} fuzzy duplicates'
                f' (rows {row_str}) found via {method} matching'
            ),
            'code': (
                f'# Flag fuzzy matches for manual review\n'
                f'fuzzy_rows = [{", ".join(str(r - 1) for r in rows)}]'
                f'  # 0-indexed\n'
                f'df["_fuzzy_review"] = df.index.isin(fuzzy_rows)'
            ),
        }

    return None


def _col(name: str) -> str:
    """Quote a column name or value for safe use in generated code."""
    if '"' in name:
        return f"'{name}'"
    return f'"{name}"'


_HANDLERS = {
    'mixed_format': _fix_mixed_format,
    'placeholder_value': _fix_placeholder,
    'placeholder': _fix_placeholder,
    'suspicious_repetition': _fix_suspicious_repetition,
    'wrong_purpose': _fix_wrong_purpose,
    'null_analysis': _fix_null_analysis,
}
