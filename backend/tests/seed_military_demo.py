"""
Military Air Defense Demo — Ontology Seed Script
=================================================

Creates a complete "防空态势感知" (Air Defense Situational Awareness) ontology
with types, field bindings, rules, actions, and test instances.

Run:
    python -m tests.seed_military_demo
"""

from __future__ import annotations

import json
import requests
import uuid

API_BASE = "http://localhost:8000/api"
HEADERS = {"Content-Type": "application/json"}


def login() -> str:
    r = requests.post(f"{API_BASE}/v1/auth/login",
                      json={"username": "admin", "password": "changeme123"})
    return r.json()["data"]["access_token"]


def main():
    token = login()
    auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("=" * 60)
    print("Military Air Defense Ontology — Seeding")
    print("=" * 60)

    # ── 1. Create ontology ──────────────────────────────────
    oid = _create_ontology(auth)
    print(f"Ontology: {oid}")

    # ── 2. Create DataSource ────────────────────────────────
    ds_id = _create_datasource(auth, oid)
    print(f"DataSource: {ds_id}")

    # ── 3. Create ObjectTypes ───────────────────────────────
    radar_type = _create_object_type(auth, oid, "雷达站", "RadarStation", {
        "名称": {"type": "string"},
        "位置": {"type": "string"},
        "最大探测距离": {"type": "number", "unit": "km"},
        "频率": {"type": "string"},
        "扫描模式": {"type": "string"},
        "状态": {"type": "string"},
    })
    launcher_type = _create_object_type(auth, oid, "导弹发射车", "MissileLauncher", {
        "名称": {"type": "string"},
        "位置": {"type": "string"},
        "备弹数量": {"type": "number", "unit": "枚"},
        "导弹型号": {"type": "string"},
        "所属指挥中心": {"type": "string"},
        "状态": {"type": "string"},
    })
    threat_type = _create_object_type(auth, oid, "威胁目标", "Threat", {
        "名称": {"type": "string"},
        "威胁类型": {"type": "string"},
        "速度": {"type": "number", "unit": "km/h"},
        "高度": {"type": "number", "unit": "m"},
        "航向": {"type": "number", "unit": "°"},
        "距离": {"type": "number", "unit": "km"},
        "状态": {"type": "string"},
        "探测来源": {"type": "string"},
    })
    cmd_type = _create_object_type(auth, oid, "指挥中心", "CommandCenter", {
        "名称": {"type": "string"},
        "位置": {"type": "string"},
        "级别": {"type": "string"},
    })
    print(f"Types: radar={radar_type} launcher={launcher_type} threat={threat_type} cmd={cmd_type}")

    # ── 4. Create LinkTypes ─────────────────────────────────
    detect_lt = _create_link_type(auth, oid, "探测", "DETECTS", radar_type, threat_type)
    assign_lt = _create_link_type(auth, oid, "隶属", "ASSIGNED_TO", launcher_type, cmd_type)
    target_lt = _create_link_type(auth, oid, "瞄准", "TARGETS", launcher_type, threat_type)
    print(f"LinkTypes: detect={detect_lt} assign={assign_lt} target={target_lt}")

    # ── 5. Create ObjectInstances ───────────────────────────
    radars = [
        _create_instance(auth, oid, radar_type, "R-001", "东海前哨雷达站", {"位置": "浙江舟山", "状态": "active"}),
        _create_instance(auth, oid, radar_type, "R-002", "南海礁岛雷达",   {"位置": "南沙群岛", "状态": "active"}),
        _create_instance(auth, oid, radar_type, "R-003", "西部防空雷达",   {"位置": "新疆喀什", "状态": "active"}),
    ]
    launchers = [
        _create_instance(auth, oid, launcher_type, "M-001", "红旗-9B 一连", {"位置": "浙江宁波", "导弹型号": "HQ-9B"}),
        _create_instance(auth, oid, launcher_type, "M-002", "红旗-9B 二连", {"位置": "上海崇明", "导弹型号": "HQ-9B"}),
        _create_instance(auth, oid, launcher_type, "M-003", "红旗-16 一连", {"位置": "南沙永暑", "导弹型号": "HQ-16"}),
    ]
    threats = [
        _create_instance(auth, oid, threat_type, "T-001", "不明飞行器 A", {"威胁类型": "UAV", "状态": "tracking"}),
        _create_instance(auth, oid, threat_type, "T-002", "不明飞行器 B", {"威胁类型": "fighter", "状态": "tracking"}),
        _create_instance(auth, oid, threat_type, "T-003", "不明飞行器 C", {"威胁类型": "UAV", "状态": "tracking"}),
        _create_instance(auth, oid, threat_type, "T-004", "不明飞行器 D", {"威胁类型": "fighter", "状态": "warning"}),
        _create_instance(auth, oid, threat_type, "T-005", "不明飞行器 E", {"威胁类型": "UAV", "状态": "tracking"}),
    ]
    cmd = _create_instance(auth, oid, cmd_type, "CC-EAST", "东部战区指挥中心", {"位置": "上海", "级别": "战区级"})
    print(f"Instances: {len(radars)} radars, {len(launchers)} launchers, {len(threats)} threats, 1 cmd")

    # ── 6. Create Links ─────────────────────────────────────
    _create_link(auth, oid, detect_lt, radars[0], threats[0])
    _create_link(auth, oid, detect_lt, radars[0], threats[1])
    _create_link(auth, oid, detect_lt, radars[1], threats[2])
    _create_link(auth, oid, detect_lt, radars[2], threats[3])
    _create_link(auth, oid, detect_lt, radars[2], threats[4])
    _create_link(auth, oid, assign_lt, launchers[0], cmd)
    _create_link(auth, oid, assign_lt, launchers[1], cmd)
    _create_link(auth, oid, assign_lt, launchers[2], cmd)
    _create_link(auth, oid, target_lt, launchers[0], threats[1])
    _create_link(auth, oid, target_lt, launchers[1], threats[3])
    print("Links: 10 created")

    # ── 7. Create Field Bindings ────────────────────────────
    for prop, table, col, pk, vtype in [
        ("名称",       "radars",    "name",         "code", "string"),
        ("位置",       "radars",    "position",     "code", "string"),
        ("状态",       "radars",    "status",       "code", "string"),
        ("最大探测距离","radars",    "max_range",    "code", "number"),
        ("频率",       "radars",    "frequency",    "code", "string"),
        ("扫描模式",   "radars",    "scan_mode",    "code", "string"),
    ]:
        _create_binding(auth, oid, radar_type, prop, ds_id, table, col, pk, vtype)

    for prop, table, col, pk, vtype in [
        ("名称",       "launchers", "name",           "code", "string"),
        ("位置",       "launchers", "position",       "code", "string"),
        ("备弹数量",   "launchers", "missiles",       "code", "number"),
        ("导弹型号",   "launchers", "missile_type",   "code", "string"),
        ("所属指挥中心","launchers","command_center",  "code", "string"),
        ("状态",       "launchers", "status",         "code", "string"),
    ]:
        _create_binding(auth, oid, launcher_type, prop, ds_id, table, col, pk, vtype)

    for prop, table, col, pk, vtype in [
        ("名称",       "threats",   "name",         "code", "string"),
        ("威胁类型",   "threats",   "threat_type",  "code", "string"),
        ("速度",       "threats",   "speed",        "code", "number"),
        ("高度",       "threats",   "altitude",     "code", "number"),
        ("航向",       "threats",   "heading",      "code", "number"),
        ("距离",       "threats",   "distance",     "code", "number"),
        ("状态",       "threats",   "status",       "code", "string"),
        ("探测来源",   "threats",   "detected_by",  "code", "string"),
    ]:
        _create_binding(auth, oid, threat_type, prop, ds_id, table, col, pk, vtype)

    # Threat speed with pipeline config
    _create_binding(auth, oid, threat_type, "危险速度评估", ds_id, "threats", "speed", "code", "number",
                    transform={"pipeline": [{"op": "to_number"}]})

    # Latest engagement for launcher  
    _create_binding(auth, oid, launcher_type, "最新交战目标", ds_id, "engagements", "threat_code", "launcher_code", "string",
                    transform={"select": {"mode": "latest", "value_column": "threat_code", "order_by": "assigned_at"}})

    print("Bindings: created")

    # ── 8. Create Rules ─────────────────────────────────────
    _create_rule(auth, oid, "威胁等级评估", radar_type, """
import math

def check(context: dict) -> dict:
    speed = context.get("速度", 0)
    altitude = context.get("高度", 0)
    distance = context.get("距离", 999)
    threat_type = context.get("威胁类型", "")

    score = 0
    reasons = []

    if speed > 1000:
        score += 3
        reasons.append("高速目标 (>{})".format(1000))
    elif speed > 600:
        score += 1

    if altitude < 2000:
        score += 2
        reasons.append("超低空飞行 (<2000m)")

    if distance < 100:
        score += 4
        reasons.append("极近距离 (<100km)")
    elif distance < 200:
        score += 2
        reasons.append("近距离 ({})km".format(distance))

    if threat_type == "fighter":
        score += 2
        reasons.append("战斗机目标")

    severity = "low"
    if score >= 8:
        severity = "critical"
    elif score >= 5:
        severity = "high"
    elif score >= 3:
        severity = "medium"

    return {
        "passed": score >= 3,
        "severity": severity,
        "message": "威胁评分: {} ({}威胁)".format(score, severity),
        "threat_score": score,
        "reasons": reasons,
        "suggest_engage": score >= 5,
    }
""")
    print(f"Rule: 威胁等级评估 created")

    _create_rule(auth, oid, "战备状态检查", launcher_type, """
import math

def check(context: dict) -> dict:
    missiles = context.get("备弹数量", 0)
    status = context.get("状态", "standby")

    ready = status == "standby" and missiles > 0

    return {
        "passed": ready,
        "severity": "info",
        "message": "发射车待命: missiles={}, status={}".format(missiles, status),
        "missiles_available": missiles,
        "can_engage": ready,
    }
""")
    print(f"Rule: 战备状态检查 created")

    # ── 9. Create Actions ───────────────────────────────────
    _create_action(auth, oid, "锁定威胁", launcher_type, """
import json

def execute(context: dict) -> dict:
    input_data = context.get("input_data", context)
    return {
        "status": "done",
        "message": "已锁定威胁目标，拦截方案已生成",
        "target_locked": True,
        "target_id": input_data.get("target_id", "unknown"),
        "launcher_id": input_data.get("launcher_id", "unknown"),
        "intercept_plan": {
            "method": "动能拦截",
            "estimated_impact": "3分钟内",
            "probability": 0.85,
        },
    }
""")
    print(f"Action: 锁定威胁 created")

    _create_action(auth, oid, "发射拦截弹", launcher_type, """
import json

def execute(context: dict) -> dict:
    return {
        "status": "done",
        "message": "拦截弹已发射",
        "missiles_remaining": 7,
        "engagement_id": "ENG-2026-001",
    }
""")
    print(f"Action: 发射拦截弹 created")

    print("\n" + "=" * 60)
    print("Seed complete!")
    print(f"Ontology ID: {oid}")
    print(f"Runtime API: /api/v2/runtime/ontologies/{oid}/")
    print("=" * 60)


# ── helpers ─────────────────────────────────────────────────

def _create_ontology(auth):
    name = f"防空态势感知 {uuid.uuid4().hex[:4]}"
    r = requests.post(f"{API_BASE}/v1/ontologies",
                      headers=auth,
                      json={"name": name, "domain": "军事", "build_mode": "manual"})
    if r.status_code != 201:
        raise RuntimeError(f"Ontology create failed: {r.json()}")
    return r.json()["data"]["id"]

def _create_datasource(auth, oid):
    r = requests.post(f"{API_BASE}/v2/ontologies/{oid}/data-sources",
                      headers=auth,
                      json={
                          "name": "防空数据库",
                          "db_config": {"db_type": "postgres", "host": "db", "port": 5432,
                                        "user": "ontoprompt", "password": "ontoprompt", "database": "ontoprompt"}
                      })
    if r.status_code != 201:
        raise RuntimeError(f"DataSource create failed: {r.json()}")
    return r.json()["id"]

def _create_object_type(auth, oid, name_cn, name_en, schema):
    r = requests.post(f"{API_BASE}/v2/ontologies/{oid}/object-types",
                      headers=auth,
                      json={"name_cn": name_cn, "name_en": name_en, "property_schema": schema})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"ObjectType create failed: {r.json()}")
    return r.json().get("id") or r.json().get("data", {}).get("id")

def _create_link_type(auth, oid, name_cn, name_en, source_id, target_id):
    r = requests.post(f"{API_BASE}/v2/ontologies/{oid}/link-types",
                      headers=auth,
                      json={"name_cn": name_cn, "name_en": name_en,
                            "source_object_type_id": source_id, "target_object_type_id": target_id,
                            "property_schema": {}})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"LinkType create failed: {r.json()}")
    return r.json().get("id") or r.json().get("data", {}).get("id")

def _create_instance(auth, oid, type_id, key, label, props):
    r = requests.post(f"{API_BASE}/v2/ontologies/{oid}/object-instances",
                      headers=auth,
                      json={"object_type_id": type_id, "name_cn": label, "name_en": key,
                            "properties": props})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Instance create failed: {r.json()}")
    return r.json().get("id") or r.json().get("data", {}).get("id")

def _create_link(auth, oid, lt_id, source_id, target_id):
    r = requests.post(f"{API_BASE}/v2/ontologies/{oid}/links",
                      headers=auth,
                      json={"link_type_id": lt_id, "source_instance_id": source_id,
                            "target_instance_id": target_id, "properties": {}})
    if r.status_code not in (200, 201):
        print(f"  Warning: Link create failed: {r.text[:80]}")

def _create_binding(auth, oid, type_id, prop, ds_id, table, col, pk, vtype, transform=None):
    body = {
        "object_type_id": type_id,
        "property_name": prop,
        "data_source_id": ds_id,
        "table_name": table,
        "column_name": col,
        "primary_key_column": pk,
        "value_type": vtype,
        "direction": "read",
    }
    if transform:
        body["transform_expression"] = json.dumps(transform)
    else:
        # default: trim for string fields
        if vtype == "string":
            body["transform_expression"] = json.dumps({"pipeline": [{"op": "trim"}]})

    r = requests.post(f"{API_BASE}/v2/manual/ontologies/{oid}/field-bindings",
                      headers=auth, json=body)
    if r.status_code not in (200, 201):
        # binding may already exist
        pass

def _create_rule(auth, oid, name_cn, type_id, python_code):
    r = requests.post(f"{API_BASE}/v2/ontologies/{oid}/rules",
                      headers=auth,
                      json={"name_cn": name_cn, "object_type_id": type_id, "python_code": python_code})
    if r.status_code not in (200, 201):
        print(f"  Warning: Rule create failed: {r.text[:80]}")

def _create_action(auth, oid, name_cn, type_id, python_code):
    r = requests.post(f"{API_BASE}/v2/ontologies/{oid}/actions-v2",
                      headers=auth,
                      json={"name_cn": name_cn, "object_type_id": type_id, "python_code": python_code})
    if r.status_code not in (200, 201):
        print(f"  Warning: Action create failed: {r.text[:80]}")


if __name__ == "__main__":
    main()
