"""Tests for schema validation."""

import json

import pandas as pd

from data_hygiene_auditor.core import run_audit
from data_hygiene_auditor.schema import (
    generate_schema,
    load_schema,
    validate_schema,
)


def _make_sheet_data(fields):
    """Build a minimal sheet_data dict for validation tests."""
    return {
        'fields': {
            name: {
                'inferred_type': ftype,
                'null_analysis': {
                    'missing_pct': missing_pct,
                    'null_count': 0,
                    'blank_count': 0,
                    'whitespace_only': 0,
                    'total_missing': 0,
                    'total_rows': 100,
                },
            }
            for name, ftype, missing_pct in fields
        },
    }


class TestLoadSchema:
    def test_shorthand_format(self, tmp_path):
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps({
            "columns": {"Phone": "phone", "Email": "email"},
        }))
        schema = load_schema(str(schema_file))
        assert schema['columns']['Phone'] == {'type': 'phone'}
        assert schema['columns']['Email'] == {'type': 'email'}

    def test_full_format(self, tmp_path):
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps({
            "columns": {
                "Phone": {"type": "phone", "required": True},
                "Email": {"type": "email", "max_missing_pct": 5.0},
            },
        }))
        schema = load_schema(str(schema_file))
        assert schema['columns']['Phone']['required'] is True
        assert schema['columns']['Email']['max_missing_pct'] == 5.0

    def test_sheet_overrides(self, tmp_path):
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps({
            "columns": {"Name": "name"},
            "sheets": {
                "Orders": {
                    "columns": {"Amount": {"type": "currency"}},
                },
            },
        }))
        schema = load_schema(str(schema_file))
        assert 'Name' in schema['columns']
        assert 'Amount' in schema['sheets']['Orders']['columns']


class TestValidateSchema:
    def test_type_mismatch(self):
        sheet = _make_sheet_data([('Phone', 'freetext', 0)])
        schema = {'columns': {'Phone': {'type': 'phone'}}, 'sheets': {}}
        violations = validate_schema(sheet, schema, 'Sheet1')
        assert len(violations) == 1
        assert violations[0]['type'] == 'schema_type_mismatch'
        assert violations[0]['severity'] == 'High'

    def test_type_match_no_violation(self):
        sheet = _make_sheet_data([('Phone', 'phone', 0)])
        schema = {'columns': {'Phone': {'type': 'phone'}}, 'sheets': {}}
        violations = validate_schema(sheet, schema, 'Sheet1')
        assert len(violations) == 0

    def test_missing_required_column(self):
        sheet = _make_sheet_data([('Name', 'name', 0)])
        schema = {
            'columns': {
                'Email': {'type': 'email', 'required': True},
            },
            'sheets': {},
        }
        violations = validate_schema(sheet, schema, 'Sheet1')
        assert len(violations) == 1
        assert violations[0]['type'] == 'schema_missing_column'

    def test_missing_optional_column_no_violation(self):
        sheet = _make_sheet_data([('Name', 'name', 0)])
        schema = {
            'columns': {'Email': {'type': 'email'}},
            'sheets': {},
        }
        violations = validate_schema(sheet, schema, 'Sheet1')
        assert len(violations) == 0

    def test_completeness_violation(self):
        sheet = _make_sheet_data([('Email', 'email', 15.0)])
        schema = {
            'columns': {
                'Email': {'type': 'email', 'max_missing_pct': 10.0},
            },
            'sheets': {},
        }
        violations = validate_schema(sheet, schema, 'Sheet1')
        assert len(violations) == 1
        assert violations[0]['type'] == 'schema_completeness_violation'
        assert violations[0]['severity'] == 'Medium'

    def test_completeness_high_severity(self):
        sheet = _make_sheet_data([('Email', 'email', 50.0)])
        schema = {
            'columns': {
                'Email': {'type': 'email', 'max_missing_pct': 10.0},
            },
            'sheets': {},
        }
        violations = validate_schema(sheet, schema, 'Sheet1')
        assert violations[0]['severity'] == 'High'

    def test_sheet_specific_overrides(self):
        sheet = _make_sheet_data([('Amount', 'freetext', 0)])
        schema = {
            'columns': {},
            'sheets': {
                'Orders': {
                    'columns': {
                        'Amount': {'type': 'currency'},
                    },
                },
            },
        }
        violations = validate_schema(sheet, schema, 'Orders')
        assert len(violations) == 1
        violations2 = validate_schema(sheet, schema, 'Other')
        assert len(violations2) == 0

    def test_empty_schema_no_violations(self):
        sheet = _make_sheet_data([('Phone', 'phone', 0)])
        schema = {'columns': {}, 'sheets': {}}
        violations = validate_schema(sheet, schema, 'Sheet1')
        assert len(violations) == 0

    def test_multiple_violations(self):
        sheet = _make_sheet_data([
            ('Phone', 'freetext', 0),
            ('Email', 'email', 30.0),
        ])
        schema = {
            'columns': {
                'Phone': {'type': 'phone'},
                'Email': {'type': 'email', 'max_missing_pct': 5.0},
                'Name': {'type': 'name', 'required': True},
            },
            'sheets': {},
        }
        violations = validate_schema(sheet, schema, 'Sheet1')
        types = {v['type'] for v in violations}
        assert 'schema_type_mismatch' in types
        assert 'schema_completeness_violation' in types
        assert 'schema_missing_column' in types


class TestGenerateSchema:
    def test_generates_from_results(self):
        results = {
            'sheets': {
                'Customers': {
                    'fields': {
                        'Name': {'inferred_type': 'name'},
                        'Phone': {'inferred_type': 'phone'},
                    },
                },
            },
        }
        schema = generate_schema(results)
        assert schema['columns']['Name']['type'] == 'name'
        assert schema['columns']['Phone']['type'] == 'phone'
        assert schema['columns']['Name']['required'] is False


class TestSchemaIntegration:
    def test_schema_in_run_audit(self, tmp_path):
        df = pd.DataFrame({
            'Phone': ['(555) 123-4567', '555-234-5678', '(555) 345-6789'],
            'Status': ['Active', 'Inactive', 'Active'],
        })
        csv_path = tmp_path / "data.csv"
        df.to_csv(str(csv_path), index=False)

        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps({
            "columns": {
                "Phone": {"type": "phone"},
                "Status": {"type": "date"},
            },
        }))

        results = run_audit(
            str(csv_path), schema_path=str(schema_file),
        )
        sheet = list(results['sheets'].values())[0]
        assert len(sheet['schema_violations']) == 1
        assert sheet['schema_violations'][0]['type'] == 'schema_type_mismatch'

    def test_schema_affects_health_score(self, tmp_path):
        df = pd.DataFrame({
            'Phone': ['(555) 123-4567', '555-234-5678', '(555) 345-6789'],
        })
        csv_path = tmp_path / "data.csv"
        df.to_csv(str(csv_path), index=False)

        results_no_schema = run_audit(str(csv_path))
        score_no_schema = results_no_schema['overall_score']

        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps({
            "columns": {
                "Phone": {"type": "date"},
                "Missing": {"type": "name", "required": True},
            },
        }))
        results_with = run_audit(
            str(csv_path), schema_path=str(schema_file),
        )
        assert results_with['overall_score'] < score_no_schema

    def test_generate_schema_cli_flow(self, tmp_path):
        df = pd.DataFrame({
            'Name': ['Alice', 'Bob'],
            'Phone': ['555-1234', '555-5678'],
        })
        csv_path = tmp_path / "data.csv"
        df.to_csv(str(csv_path), index=False)

        results = run_audit(str(csv_path))
        schema = generate_schema(results)
        schema_path = tmp_path / "generated.json"
        with open(str(schema_path), 'w') as f:
            json.dump(schema, f)

        loaded = load_schema(str(schema_path))
        assert 'Name' in loaded['columns']
