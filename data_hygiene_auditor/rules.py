"""Custom rule engine — load and evaluate user-defined detection rules."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

VALID_CONDITIONS = {
    'regex_match',
    'not_regex_match',
    'min_length',
    'max_length',
    'allowed_values',
    'disallowed_values',
    'max_missing_pct',
}


@dataclass
class Rule:
    name: str
    description: str
    severity: str
    condition: str
    threshold: Any
    column_pattern: str = '*'
    columns: List[str] = field(default_factory=list)

    def matches_column(self, col_name: str) -> bool:
        if self.columns:
            return col_name in self.columns
        if self.column_pattern == '*':
            return True
        return bool(re.search(self.column_pattern, col_name, re.IGNORECASE))


def load_rules(path: str) -> List[Rule]:
    """Load custom rules from a JSON file.

    Expected format:
    {
      "rules": [
        {
          "name": "Phone format",
          "description": "All phone numbers must match E.164 or US format",
          "severity": "High",
          "column_pattern": "phone|tel",
          "condition": "regex_match",
          "threshold": "^\\+?1?\\d{10,14}$"
        }
      ]
    }
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")

    with open(path) as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in rules file: {e}") from e

    if not isinstance(raw, dict) or 'rules' not in raw:
        raise ValueError(
            "Rules file must contain a top-level 'rules' array"
        )

    rules_list = raw['rules']
    if not isinstance(rules_list, list):
        raise ValueError("'rules' must be an array")

    rules = []
    for i, entry in enumerate(rules_list):
        rules.append(_parse_rule(entry, i))
    return rules


def _parse_rule(entry: Dict[str, Any], index: int) -> Rule:
    """Parse and validate a single rule entry."""
    prefix = f"Rule [{index}]"

    if not isinstance(entry, dict):
        raise ValueError(f"{prefix}: each rule must be an object")

    required = ('name', 'description', 'severity', 'condition', 'threshold')
    for field_name in required:
        if field_name not in entry:
            raise ValueError(
                f"{prefix}: missing required field '{field_name}'"
            )

    name = entry['name']
    condition = entry['condition']
    severity = entry['severity']
    threshold = entry['threshold']

    if condition not in VALID_CONDITIONS:
        raise ValueError(
            f"{prefix} ({name}): invalid condition '{condition}'."
            f" Valid: {', '.join(sorted(VALID_CONDITIONS))}"
        )

    if severity not in ('High', 'Medium', 'Low'):
        raise ValueError(
            f"{prefix} ({name}): severity must be 'High', 'Medium', or 'Low'"
        )

    if condition in ('regex_match', 'not_regex_match'):
        if not isinstance(threshold, str):
            raise ValueError(
                f"{prefix} ({name}): threshold must be a regex string"
                f" for condition '{condition}'"
            )
        try:
            re.compile(threshold)
        except re.error as e:
            raise ValueError(
                f"{prefix} ({name}): invalid regex in threshold: {e}"
            ) from e

    if condition in ('min_length', 'max_length'):
        if not isinstance(threshold, (int, float)) or threshold < 0:
            raise ValueError(
                f"{prefix} ({name}): threshold must be a non-negative number"
                f" for condition '{condition}'"
            )

    if condition in ('allowed_values', 'disallowed_values'):
        if not isinstance(threshold, list):
            raise ValueError(
                f"{prefix} ({name}): threshold must be an array"
                f" for condition '{condition}'"
            )

    if condition == 'max_missing_pct':
        if not isinstance(threshold, (int, float)) or not (0 <= threshold <= 100):
            raise ValueError(
                f"{prefix} ({name}): threshold must be a number 0-100"
                f" for condition 'max_missing_pct'"
            )

    return Rule(
        name=name,
        description=entry['description'],
        severity=severity,
        condition=condition,
        threshold=threshold,
        column_pattern=entry.get('column_pattern', '*'),
        columns=entry.get('columns', []),
    )


def evaluate_rule(rule: Rule, series, col_name: str) -> Optional[Dict[str, Any]]:
    """Evaluate a single rule against a column. Returns a finding dict or None."""
    if not rule.matches_column(col_name):
        return None

    non_null = series.dropna()
    non_null_str = non_null.astype(str).str.strip()
    non_empty = non_null_str[non_null_str != '']
    total = len(series)

    if rule.condition == 'max_missing_pct':
        missing = total - len(non_empty)
        pct = (missing / total * 100) if total > 0 else 0
        if pct > rule.threshold:
            return {
                'type': 'custom_rule',
                'rule_name': rule.name,
                'severity': rule.severity,
                'detail': {
                    'condition': rule.condition,
                    'threshold': rule.threshold,
                    'actual': round(pct, 1),
                    'message': (
                        f"{pct:.1f}% missing (threshold: {rule.threshold}%)"
                    ),
                },
                'why': rule.description,
            }
        return None

    if len(non_empty) == 0:
        return None

    if rule.condition == 'regex_match':
        pattern = re.compile(rule.threshold)
        violations = non_empty[~non_empty.str.fullmatch(pattern, na=False)]
        if len(violations) == 0:
            return None
        examples = violations.head(5).tolist()
        return {
            'type': 'custom_rule',
            'rule_name': rule.name,
            'severity': rule.severity,
            'detail': {
                'condition': rule.condition,
                'threshold': rule.threshold,
                'violations': len(violations),
                'total_checked': len(non_empty),
                'examples': examples,
                'message': (
                    f"{len(violations)}/{len(non_empty)} values don't match"
                    f" pattern '{rule.threshold}'"
                ),
            },
            'why': rule.description,
        }

    if rule.condition == 'not_regex_match':
        pattern = re.compile(rule.threshold)
        violations = non_empty[non_empty.str.fullmatch(pattern, na=False)]
        if len(violations) == 0:
            return None
        examples = violations.head(5).tolist()
        return {
            'type': 'custom_rule',
            'rule_name': rule.name,
            'severity': rule.severity,
            'detail': {
                'condition': rule.condition,
                'threshold': rule.threshold,
                'violations': len(violations),
                'total_checked': len(non_empty),
                'examples': examples,
                'message': (
                    f"{len(violations)}/{len(non_empty)} values match"
                    f" disallowed pattern '{rule.threshold}'"
                ),
            },
            'why': rule.description,
        }

    if rule.condition == 'min_length':
        violations = non_empty[non_empty.str.len() < rule.threshold]
        if len(violations) == 0:
            return None
        examples = violations.head(5).tolist()
        return {
            'type': 'custom_rule',
            'rule_name': rule.name,
            'severity': rule.severity,
            'detail': {
                'condition': rule.condition,
                'threshold': rule.threshold,
                'violations': len(violations),
                'total_checked': len(non_empty),
                'examples': examples,
                'message': (
                    f"{len(violations)}/{len(non_empty)} values shorter than"
                    f" {int(rule.threshold)} characters"
                ),
            },
            'why': rule.description,
        }

    if rule.condition == 'max_length':
        violations = non_empty[non_empty.str.len() > rule.threshold]
        if len(violations) == 0:
            return None
        examples = violations.head(5).tolist()
        return {
            'type': 'custom_rule',
            'rule_name': rule.name,
            'severity': rule.severity,
            'detail': {
                'condition': rule.condition,
                'threshold': rule.threshold,
                'violations': len(violations),
                'total_checked': len(non_empty),
                'examples': examples,
                'message': (
                    f"{len(violations)}/{len(non_empty)} values longer than"
                    f" {int(rule.threshold)} characters"
                ),
            },
            'why': rule.description,
        }

    if rule.condition == 'allowed_values':
        allowed_set = {v.lower() for v in rule.threshold}
        violations = non_empty[~non_empty.str.lower().isin(allowed_set)]
        if len(violations) == 0:
            return None
        examples = violations.head(5).tolist()
        return {
            'type': 'custom_rule',
            'rule_name': rule.name,
            'severity': rule.severity,
            'detail': {
                'condition': rule.condition,
                'threshold': rule.threshold,
                'violations': len(violations),
                'total_checked': len(non_empty),
                'examples': examples,
                'message': (
                    f"{len(violations)}/{len(non_empty)} values not in"
                    f" allowed set"
                ),
            },
            'why': rule.description,
        }

    if rule.condition == 'disallowed_values':
        disallowed_set = {v.lower() for v in rule.threshold}
        violations = non_empty[non_empty.str.lower().isin(disallowed_set)]
        if len(violations) == 0:
            return None
        examples = violations.head(5).tolist()
        return {
            'type': 'custom_rule',
            'rule_name': rule.name,
            'severity': rule.severity,
            'detail': {
                'condition': rule.condition,
                'threshold': rule.threshold,
                'violations': len(violations),
                'total_checked': len(non_empty),
                'examples': examples,
                'message': (
                    f"{len(violations)}/{len(non_empty)} values contain"
                    f" disallowed entries"
                ),
            },
            'why': rule.description,
        }

    return None
