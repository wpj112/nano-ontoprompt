"""
Transform Engine Demo Cases
============================
Run inside the nano-ontoprompt-backend container with:
    python -m tests.transform_demo
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/app")

from app.services.v2.transform import execute as transform_execute
from app.models.v2.manual_binding import ManualFieldBinding
from app.models.v2.data_source import DataSource


def make_binding(
    table_name: str = "suppliers",
    column_name: str = "name",
    primary_key_column: str = "code",
    value_type: str = "string",
    transform_expression: str | None = None,
) -> ManualFieldBinding:
    b = ManualFieldBinding()
    b.id = "test-binding"
    b.ontology_id = "demo"
    b.object_type_id = "supplier"
    b.property_name = "test_prop"
    b.data_source_id = "test-ds"
    b.schema_name = None
    b.table_name = table_name
    b.column_name = column_name
    b.primary_key_column = primary_key_column
    b.value_type = value_type
    b.direction = "read"
    b.transform_expression = transform_expression
    b.is_required = False
    b.read_only = True
    return b


def make_source() -> DataSource:
    s = DataSource()
    s.id = "test-ds"
    s.ontology_id = "demo"
    s.name = "Test PostgreSQL"
    s.db_config = {
        "db_type": "postgres",
        "host": os.environ.get("POSTGRES_HOST", "db"),
        "port": 5432,
        "user": "ontoprompt",
        "password": "ontoprompt",
        "database": "ontoprompt",
    }
    return s


def run_tests():
    print("=" * 60)
    print("Transform Engine Demo Cases")
    print("=" * 60)

    source = make_source()

    Case = tuple[str, ManualFieldBinding, str, any]
    cases: list[Case] = []

    # 1: trim + upper
    cases.append((
        "Case 1: trim + upper on supplier name",
        make_binding(
            column_name="name",
            transform_expression=json.dumps({
                "pipeline": [{"op": "trim"}, {"op": "upper"}],
            }),
        ),
        "SUP-001",
        "东方钢铁有限公司",
    ))

    # 2: replace + concat
    cases.append((
        "Case 2: replace suffix + concat template",
        make_binding(
            column_name="name",
            transform_expression=json.dumps({
                "pipeline": [
                    {"op": "trim"},
                    {"op": "replace", "src": "有限公司", "dst": ""},
                    {"op": "concat", "template": "供应商: {value}"},
                ],
            }),
        ),
        "SUP-001",
        "供应商: 东方钢铁",
    ))

    # 3: aggregate MAX
    cases.append((
        "Case 3: aggregate MAX quality score",
        make_binding(
            table_name="quality_checks",
            column_name="score",
            primary_key_column="supplier_code",
            value_type="number",
            transform_expression=json.dumps({
                "select": {"mode": "aggregate", "op": "max", "column": "score"},
            }),
        ),
        "SUP-001",
        95,
    ))

    # 4: aggregate AVG + round
    cases.append((
        "Case 4: aggregate AVG + round(1)",
        make_binding(
            table_name="quality_checks",
            column_name="score",
            primary_key_column="supplier_code",
            value_type="number",
            transform_expression=json.dumps({
                "select": {"mode": "aggregate", "op": "avg", "column": "score"},
                "pipeline": [{"op": "round", "digits": 1}],
            }),
        ),
        "SUP-001",
        91.7,
    ))

    # 5: latest quality result
    cases.append((
        "Case 5: latest quality check result by date",
        make_binding(
            table_name="quality_checks",
            column_name="result",
            primary_key_column="supplier_code",
            value_type="string",
            transform_expression=json.dumps({
                "select": {"mode": "latest", "value_column": "result", "order_by": "check_date"},
            }),
        ),
        "SUP-004",
        "fail",
    ))

    # 6: phone number cleanup
    cases.append((
        "Case 6: phone number strip spaces + remove dashes",
        make_binding(
            column_name="phone",
            transform_expression=json.dumps({
                "pipeline": [
                    {"op": "trim"},
                    {"op": "replace", "src": "-", "dst": ""},
                ],
            }),
        ),
        "SUP-001",
        "02112345678",
    ))

    # 7: score to number
    cases.append((
        "Case 7: score as number",
        make_binding(
            column_name="score",
            value_type="number",
            transform_expression=json.dumps({
                "pipeline": [{"op": "to_number"}],
            }),
        ),
        "SUP-002",
        78.0,
    ))

    # ── run ──
    passed = 0
    failed = 0
    for label, binding, obj_key, expected in cases:
        try:
            result = transform_execute(binding, obj_key, source)
            ok = result == expected
            status = "✓" if ok else "✗"
            if ok:
                passed += 1
            else:
                failed += 1
            print(f"  {status} {label}")
            if not ok:
                print(f"      expected: {expected!r}")
                print(f"      got:      {result!r}")
        except Exception as exc:
            failed += 1
            print(f"  ✗ {label}")
            print(f"      ERROR: {exc}")

    print(f"\n  passed: {passed}, failed: {failed}")
    return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
