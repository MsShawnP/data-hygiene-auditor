"""Schema validation — compare actual data against user-defined type expectations."""

import json

VALID_TYPES = {
    'date', 'phone', 'currency', 'email', 'id', 'name',
    'categorical', 'freetext', 'zipcode', 'empty',
}


def load_schema(path):
    """Load and normalize a schema definition from a JSON file.

    Supports shorthand ("col": "type") and full form
    ("col": {"type": "phone", "required": true, "max_missing_pct": 5.0}).

    Top-level "columns" apply to all sheets. Per-sheet overrides go under
    "sheets": {"SheetName": {"columns": {...}}}.
    """
    with open(path) as f:
        raw = json.load(f)

    schema: dict = {'columns': {}, 'sheets': {}}

    for col, spec in raw.get('columns', {}).items():
        schema['columns'][col] = _normalize_spec(spec)

    for sheet_name, sheet_spec in raw.get('sheets', {}).items():
        cols = {}
        for col, spec in sheet_spec.get('columns', {}).items():
            cols[col] = _normalize_spec(spec)
        schema['sheets'][sheet_name] = {'columns': cols}

    return schema


def _normalize_spec(spec):
    """Normalize shorthand spec ("phone") to full dict form."""
    if isinstance(spec, str):
        return {'type': spec}
    return dict(spec)


def generate_schema(results):
    """Generate a schema from audit results (inferred types).

    Returns a dict suitable for ``json.dump()`` to create an editable
    schema file that users can customize with ``required`` and
    ``max_missing_pct`` constraints.
    """
    all_columns = {}
    for sheet_data in results['sheets'].values():
        for col_name, field_data in sheet_data['fields'].items():
            if col_name not in all_columns:
                all_columns[col_name] = field_data['inferred_type']

    schema = {
        'columns': {
            col: {'type': ftype, 'required': False}
            for col, ftype in all_columns.items()
        },
    }
    return schema


def validate_schema(sheet_data, schema, sheet_name):
    """Validate a sheet against a schema. Returns list of violation dicts."""
    findings: list[dict] = []

    col_specs = dict(schema.get('columns', {}))
    sheet_spec = schema.get('sheets', {}).get(sheet_name, {})
    col_specs.update(sheet_spec.get('columns', {}))

    if not col_specs:
        return findings

    actual_cols = set(sheet_data['fields'].keys())

    for col_name, spec in col_specs.items():
        expected_type = spec.get('type')
        required = spec.get('required', False)
        max_missing = spec.get('max_missing_pct')

        if col_name not in actual_cols:
            if required:
                findings.append({
                    'type': 'schema_missing_column',
                    'severity': 'High',
                    'column': col_name,
                    'detail': {
                        'expected_column': col_name,
                        'expected_type': expected_type,
                    },
                    'why': (
                        f"Required column '{col_name}' defined in the schema "
                        f"is missing from the data. This may indicate a structural "
                        f"change in the data source or an incorrect column mapping."
                    ),
                })
            continue

        field_data = sheet_data['fields'][col_name]

        if expected_type and field_data['inferred_type'] != expected_type:
            findings.append({
                'type': 'schema_type_mismatch',
                'severity': 'High',
                'column': col_name,
                'detail': {
                    'column': col_name,
                    'expected_type': expected_type,
                    'actual_type': field_data['inferred_type'],
                },
                'why': (
                    f"Column '{col_name}' was expected to contain "
                    f"{expected_type} data but was inferred as "
                    f"{field_data['inferred_type']}. This may indicate "
                    f"data corruption, a schema change, or values being "
                    f"entered in the wrong column."
                ),
            })

        if max_missing is not None:
            actual_pct = field_data['null_analysis']['missing_pct']
            if actual_pct > max_missing:
                severity = 'High' if actual_pct > max_missing * 2 else 'Medium'
                findings.append({
                    'type': 'schema_completeness_violation',
                    'severity': severity,
                    'column': col_name,
                    'detail': {
                        'column': col_name,
                        'max_missing_pct': max_missing,
                        'actual_missing_pct': actual_pct,
                    },
                    'why': (
                        f"Column '{col_name}' has {actual_pct}% missing values, "
                        f"exceeding the schema threshold of {max_missing}%. "
                        f"This violates the data completeness requirement "
                        f"defined in the schema."
                    ),
                })

    return findings
