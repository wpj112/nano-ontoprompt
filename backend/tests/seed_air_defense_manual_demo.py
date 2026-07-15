"""Seed a manual ontology demo for agent orchestration: air-defense tracking allocation.

Run inside backend container:
    python backend/tests/seed_air_defense_manual_demo.py
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models.user import User
from app.models.ontology import OntologyProject
from app.models.v2.data_source import DataSource
from app.models.v2.manual_binding import ManualFieldBinding, ManualLinkBinding
from app.models.v2.object_type import ObjectType, LinkType
from app.models.object_rule import ObjectRule
from app.models.object_action import ObjectAction

ONTOLOGY_NAME = "东部防空反导系统手动本体"
DOMAIN = "防空反导"
SYSTEM_CODE = "EADS-001"


def now():
    return datetime.now(timezone.utc)


def db_config_from_settings() -> dict:
    url = make_url(settings.database_url)
    db_type = "postgres" if url.drivername.startswith("postgres") else "mysql"
    return {
        "db_type": db_type,
        "host": url.host or "db",
        "port": url.port or (5432 if db_type == "postgres" else 3306),
        "user": url.username or "",
        "password": url.password or "",
        "database": url.database or "",
    }


def exec_sql(sql: str, params: dict | None = None):
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def create_business_tables():
    statements = [
        """
        CREATE TABLE IF NOT EXISTS ad_air_defense_systems (
            system_code VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            region VARCHAR,
            combat_status VARCHAR,
            alert_level VARCHAR,
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ad_radars (
            radar_code VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            system_code VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            max_track_capacity INTEGER NOT NULL,
            location_status VARCHAR,
            online_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ad_target_batches (
            batch_code VARCHAR PRIMARY KEY,
            target_type VARCHAR NOT NULL,
            target_count INTEGER NOT NULL,
            status VARCHAR NOT NULL,
            region VARCHAR,
            detected_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ad_targets (
            target_code VARCHAR PRIMARY KEY,
            target_type VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            batch_code VARCHAR,
            threat_level VARCHAR,
            priority INTEGER DEFAULT 0,
            detected_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ad_radar_target_links (
            id VARCHAR PRIMARY KEY,
            system_code VARCHAR NOT NULL,
            radar_code VARCHAR NOT NULL,
            target_code VARCHAR NOT NULL,
            relation_type VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            started_at TIMESTAMP DEFAULT NOW(),
            ended_at TIMESTAMP,
            confidence FLOAT DEFAULT 1.0,
            UNIQUE (radar_code, target_code, relation_type, status)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ad_dispatch_commands (
            command_id VARCHAR PRIMARY KEY,
            command_type VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            source VARCHAR,
            reason TEXT,
            issued_at TIMESTAMP DEFAULT NOW(),
            executed_at TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ad_dispatch_allocations (
            id VARCHAR PRIMARY KEY,
            command_id VARCHAR NOT NULL,
            radar_code VARCHAR NOT NULL,
            target_code VARCHAR NOT NULL,
            action VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (command_id, radar_code, target_code, action)
        )
        """,
    ]
    for stmt in statements:
        exec_sql(stmt)

    exec_sql(
        """
        INSERT INTO ad_air_defense_systems(system_code, name, region, combat_status, alert_level, updated_at)
        VALUES (:code, '东部防空反导系统', '东部防区', 'combat_ready', 'high', NOW())
        ON CONFLICT (system_code) DO UPDATE SET
          name=EXCLUDED.name, region=EXCLUDED.region, combat_status=EXCLUDED.combat_status,
          alert_level=EXCLUDED.alert_level, updated_at=NOW()
        """,
        {"code": SYSTEM_CODE},
    )
    for radar in [
        {"radar_code": "R-001", "name": "雷达1", "status": "online", "max": 20, "loc": "deployed"},
        {"radar_code": "R-002", "name": "雷达2", "status": "online", "max": 20, "loc": "deployed"},
    ]:
        exec_sql(
            """
            INSERT INTO ad_radars(radar_code, name, system_code, status, max_track_capacity, location_status, online_at, updated_at)
            VALUES (:radar_code, :name, :system_code, :status, :max_track_capacity, :location_status, NOW(), NOW())
            ON CONFLICT (radar_code) DO UPDATE SET
              name=EXCLUDED.name, system_code=EXCLUDED.system_code, status=EXCLUDED.status,
              max_track_capacity=EXCLUDED.max_track_capacity, location_status=EXCLUDED.location_status,
              updated_at=NOW()
            """,
            {
                "radar_code": radar["radar_code"], "name": radar["name"], "system_code": SYSTEM_CODE,
                "status": radar["status"], "max_track_capacity": radar["max"], "location_status": radar["loc"],
            },
        )
    exec_sql(
        """
        INSERT INTO ad_target_batches(batch_code, target_type, target_count, status, region, detected_at)
        VALUES ('UAV-BATCH-A', 'jamming_drone', 21, 'incoming', 'east_zone', NOW())
        ON CONFLICT (batch_code) DO UPDATE SET target_type=EXCLUDED.target_type,
          target_count=EXCLUDED.target_count, status=EXCLUDED.status, region=EXCLUDED.region
        """
    )
    exec_sql(
        """
        INSERT INTO ad_targets(target_code, target_type, status, batch_code, threat_level, priority, detected_at, updated_at)
        VALUES ('M-001', 'incoming_missile', 'locked', NULL, 'critical', 100, NOW(), NOW())
        ON CONFLICT (target_code) DO UPDATE SET target_type=EXCLUDED.target_type,
          status=EXCLUDED.status, threat_level=EXCLUDED.threat_level, priority=EXCLUDED.priority, updated_at=NOW()
        """
    )
    for i in range(1, 22):
        code = f"UAV-A-{i:03d}"
        exec_sql(
            """
            INSERT INTO ad_targets(target_code, target_type, status, batch_code, threat_level, priority, detected_at, updated_at)
            VALUES (:code, 'jamming_drone', 'incoming', 'UAV-BATCH-A', 'high', 60, NOW(), NOW())
            ON CONFLICT (target_code) DO UPDATE SET status=EXCLUDED.status,
              batch_code=EXCLUDED.batch_code, threat_level=EXCLUDED.threat_level, priority=EXCLUDED.priority, updated_at=NOW()
            """,
            {"code": code},
        )
    # Reset demo tracking state, then restore initial missile lock/tracking.
    exec_sql("DELETE FROM ad_radar_target_links WHERE system_code = :system_code", {"system_code": SYSTEM_CODE})
    for rel in ["LOCKS", "TRACKS"]:
        exec_sql(
            """
            INSERT INTO ad_radar_target_links(id, system_code, radar_code, target_code, relation_type, status, started_at, confidence)
            VALUES (:id, :system_code, 'R-001', 'M-001', :rel, 'active', NOW(), 1.0)
            ON CONFLICT (radar_code, target_code, relation_type, status) DO NOTHING
            """,
            {"id": str(uuid.uuid4()), "system_code": SYSTEM_CODE, "rel": rel},
        )
    exec_sql("DELETE FROM ad_dispatch_allocations WHERE command_id LIKE 'DEMO-%'")
    exec_sql("DELETE FROM ad_dispatch_commands WHERE command_id LIKE 'DEMO-%'")
    exec_sql(
        """
        CREATE OR REPLACE VIEW radar_runtime_status AS
        SELECT r.radar_code, r.name, r.system_code, r.status, r.max_track_capacity, r.location_status,
               COALESCE(COUNT(l.target_code) FILTER (WHERE l.relation_type = 'TRACKS' AND l.status = 'active'), 0)::INTEGER AS current_track_count,
               (r.max_track_capacity - COALESCE(COUNT(l.target_code) FILTER (WHERE l.relation_type = 'TRACKS' AND l.status = 'active'), 0))::INTEGER AS available_capacity
        FROM ad_radars r
        LEFT JOIN ad_radar_target_links l ON l.radar_code = r.radar_code
        GROUP BY r.radar_code, r.name, r.system_code, r.status, r.max_track_capacity, r.location_status
        """
    )
    exec_sql(
        """
        CREATE OR REPLACE VIEW system_runtime_status AS
        SELECT s.system_code, s.name, s.region, s.combat_status, s.alert_level,
               COALESCE(SUM(r.max_track_capacity) FILTER (WHERE r.status = 'online'), 0)::INTEGER AS total_track_capacity,
               COALESCE(COUNT(l.target_code) FILTER (WHERE l.relation_type = 'TRACKS' AND l.status = 'active'), 0)::INTEGER AS current_track_count,
               (COALESCE(SUM(r.max_track_capacity) FILTER (WHERE r.status = 'online'), 0)
                - COALESCE(COUNT(l.target_code) FILTER (WHERE l.relation_type = 'TRACKS' AND l.status = 'active'), 0))::INTEGER AS available_capacity
        FROM ad_air_defense_systems s
        LEFT JOIN ad_radars r ON r.system_code = s.system_code
        LEFT JOIN ad_radar_target_links l ON l.system_code = s.system_code
        GROUP BY s.system_code, s.name, s.region, s.combat_status, s.alert_level
        """
    )


def get_or_create_ontology(db) -> OntologyProject:
    admin = db.query(User).filter(User.role == "admin").first() or db.query(User).first()
    if not admin:
        raise RuntimeError("No user exists; seed admin first")
    ont = db.query(OntologyProject).filter(OntologyProject.name == ONTOLOGY_NAME).first()
    if not ont:
        ont = OntologyProject(
            id=str(uuid.uuid4()), name=ONTOLOGY_NAME, domain=DOMAIN,
            description="手动创建模式样例：防空反导雷达跟踪容量评估与目标分配。",
            status="published", build_mode="manual", created_by=admin.id,
        )
        db.add(ont)
    else:
        ont.domain = DOMAIN
        ont.status = "published"
        ont.build_mode = "manual"
        ont.description = "手动创建模式样例：防空反导雷达跟踪容量评估与目标分配。"
    db.commit(); db.refresh(ont)
    return ont


def get_or_create_source(db, ontology_id: str) -> DataSource:
    source = db.query(DataSource).filter(DataSource.ontology_id == ontology_id, DataSource.name == "demo_air_defense_db").first()
    cfg = db_config_from_settings()
    if not source:
        source = DataSource(id=str(uuid.uuid4()), ontology_id=ontology_id, name="demo_air_defense_db", db_config=cfg, registered_table="ad_radars")
        db.add(source)
    else:
        source.db_config = cfg
        source.registered_table = "ad_radars"
    db.commit(); db.refresh(source)
    return source


def upsert_type(db, ontology_id: str, name_cn: str, name_en: str, schema: dict) -> ObjectType:
    item = db.query(ObjectType).filter(ObjectType.ontology_id == ontology_id, ObjectType.name_en == name_en).first()
    if not item:
        item = ObjectType(id=str(uuid.uuid4()), ontology_id=ontology_id, name_cn=name_cn, name_en=name_en, property_schema=schema)
        db.add(item)
    else:
        item.name_cn = name_cn
        item.property_schema = schema
    db.commit(); db.refresh(item)
    return item


def upsert_link_type(db, ontology_id: str, name_cn: str, name_en: str, src: ObjectType, tgt: ObjectType, schema: dict | None = None) -> LinkType:
    item = db.query(LinkType).filter(LinkType.ontology_id == ontology_id, LinkType.name_en == name_en).first()
    if not item:
        item = LinkType(id=str(uuid.uuid4()), ontology_id=ontology_id, name_cn=name_cn, name_en=name_en)
        db.add(item)
    item.name_cn = name_cn
    item.source_object_type_id = src.id
    item.target_object_type_id = tgt.id
    item.property_schema = schema or {}
    db.commit(); db.refresh(item)
    return item


def upsert_field_binding(db, ontology_id: str, source: DataSource, object_type: ObjectType, prop: str, table: str, col: str, pk: str, value_type: str = "string", transform: dict | None = None):
    item = db.query(ManualFieldBinding).filter(
        ManualFieldBinding.ontology_id == ontology_id,
        ManualFieldBinding.object_type_id == object_type.id,
        ManualFieldBinding.property_name == prop,
    ).first()
    raw = json.dumps(transform, ensure_ascii=False) if transform else None
    if not item:
        item = ManualFieldBinding(id=str(uuid.uuid4()), ontology_id=ontology_id, object_type_id=object_type.id, property_name=prop)
        db.add(item)
    item.data_source_id = source.id
    item.schema_name = None
    item.table_name = table
    item.column_name = col
    item.primary_key_column = pk
    item.value_type = value_type
    item.direction = "read"
    item.transform_expression = raw
    item.read_only = True
    db.commit(); db.refresh(item)
    return item


def upsert_link_binding(db, ontology_id: str, source: DataSource, link_type: LinkType, src: ObjectType, tgt: ObjectType, table: str, src_col: str, tgt_col: str, filters: dict, props: dict | None = None):
    item = db.query(ManualLinkBinding).filter(
        ManualLinkBinding.ontology_id == ontology_id,
        ManualLinkBinding.link_type_id == link_type.id,
        ManualLinkBinding.table_name == table,
        ManualLinkBinding.source_key_column == src_col,
        ManualLinkBinding.target_key_column == tgt_col,
    ).first()
    if not item:
        item = ManualLinkBinding(id=str(uuid.uuid4()), ontology_id=ontology_id, link_type_id=link_type.id)
        db.add(item)
    item.data_source_id = source.id
    item.schema_name = None
    item.table_name = table
    item.source_object_type_id = src.id
    item.source_key_column = src_col
    item.target_object_type_id = tgt.id
    item.target_key_column = tgt_col
    item.direction = "out"
    item.relation_filters = filters
    item.property_bindings = props or {"status": "status", "started_at": "started_at", "confidence": "confidence"}
    item.is_active = True
    db.commit(); db.refresh(item)
    return item


def upsert_rule(db, ontology_id: str, name: str, object_type: ObjectType, code: str):
    item = db.query(ObjectRule).filter(ObjectRule.ontology_id == ontology_id, ObjectRule.name_cn == name).first()
    if not item:
        item = ObjectRule(id=str(uuid.uuid4()), ontology_id=ontology_id, name_cn=name)
        db.add(item)
    item.object_type_id = object_type.id
    item.description = "Runtime demo rule"
    item.python_code = code
    db.commit(); db.refresh(item)
    return item


def upsert_action(db, ontology_id: str, name: str, code: str, rule: ObjectRule | None = None):
    item = db.query(ObjectAction).filter(ObjectAction.ontology_id == ontology_id, ObjectAction.name_cn == name).first()
    if not item:
        item = ObjectAction(id=str(uuid.uuid4()), ontology_id=ontology_id, name_cn=name)
        db.add(item)
    item.description = "Runtime demo action"
    item.python_code = code
    item.object_rule_id = rule.id if rule else None
    db.commit(); db.refresh(item)
    return item


def seed_ontology():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        ont = get_or_create_ontology(db)
        source = get_or_create_source(db, ont.id)

        system = upsert_type(db, ont.id, "防空系统", "AirDefenseSystem", {
            "system_code": {"type": "string"}, "name": {"type": "string"}, "region": {"type": "string"},
            "combat_status": {"type": "string"}, "alert_level": {"type": "string"},
            "total_track_capacity": {"type": "number"}, "current_track_count": {"type": "number"}, "available_capacity": {"type": "number"},
        })
        radar = upsert_type(db, ont.id, "雷达", "Radar", {
            "radar_code": {"type": "string"}, "name": {"type": "string"}, "system_code": {"type": "string"},
            "status": {"type": "string"}, "max_track_capacity": {"type": "number"},
            "current_track_count": {"type": "number"}, "available_capacity": {"type": "number"}, "location_status": {"type": "string"},
        })
        target = upsert_type(db, ont.id, "目标", "Target", {
            "target_code": {"type": "string"}, "target_type": {"type": "string"}, "status": {"type": "string"},
            "batch_code": {"type": "string"}, "threat_level": {"type": "string"}, "priority": {"type": "number"},
        })
        batch = upsert_type(db, ont.id, "目标批次", "TargetBatch", {
            "batch_code": {"type": "string"}, "target_type": {"type": "string"}, "target_count": {"type": "number"},
            "status": {"type": "string"}, "region": {"type": "string"},
        })
        command = upsert_type(db, ont.id, "调度命令", "DispatchCommand", {
            "command_id": {"type": "string"}, "command_type": {"type": "string"}, "status": {"type": "string"},
            "source": {"type": "string"}, "reason": {"type": "string"},
        })

        belongs = upsert_link_type(db, ont.id, "隶属系统", "BELONGS_TO", radar, system)
        tracks = upsert_link_type(db, ont.id, "持续跟踪", "TRACKS", radar, target)
        locks = upsert_link_type(db, ont.id, "锁定", "LOCKS", radar, target)
        has_target = upsert_link_type(db, ont.id, "包含目标", "HAS_TARGET", batch, target)

        for prop, col, vt in [
            ("system_code", "system_code", "string"), ("name", "name", "string"), ("region", "region", "string"),
            ("combat_status", "combat_status", "string"), ("alert_level", "alert_level", "string"),
            ("total_track_capacity", "total_track_capacity", "number"), ("current_track_count", "current_track_count", "number"),
            ("available_capacity", "available_capacity", "number"),
        ]:
            upsert_field_binding(db, ont.id, source, system, prop, "system_runtime_status", col, "system_code", vt)
        for prop, col, vt in [
            ("radar_code", "radar_code", "string"), ("name", "name", "string"), ("system_code", "system_code", "string"),
            ("status", "status", "string"), ("max_track_capacity", "max_track_capacity", "number"),
            ("current_track_count", "current_track_count", "number"), ("available_capacity", "available_capacity", "number"),
            ("location_status", "location_status", "string"),
        ]:
            transform = {"pipeline": [{"op": "trim"}, {"op": "lower"}]} if prop == "status" else None
            upsert_field_binding(db, ont.id, source, radar, prop, "radar_runtime_status", col, "radar_code", vt, transform)
        for prop, col, vt in [
            ("target_code", "target_code", "string"), ("target_type", "target_type", "string"), ("status", "status", "string"),
            ("batch_code", "batch_code", "string"), ("threat_level", "threat_level", "string"), ("priority", "priority", "number"),
        ]:
            upsert_field_binding(db, ont.id, source, target, prop, "ad_targets", col, "target_code", vt)
        for prop, col, vt in [
            ("batch_code", "batch_code", "string"), ("target_type", "target_type", "string"),
            ("target_count", "target_count", "number"), ("status", "status", "string"), ("region", "region", "string"),
        ]:
            upsert_field_binding(db, ont.id, source, batch, prop, "ad_target_batches", col, "batch_code", vt)
        for prop, col in [("command_id", "command_id"), ("command_type", "command_type"), ("status", "status"), ("source", "source"), ("reason", "reason")]:
            upsert_field_binding(db, ont.id, source, command, prop, "ad_dispatch_commands", col, "command_id")

        upsert_link_binding(db, ont.id, source, belongs, radar, system, "ad_radars", "radar_code", "system_code", {})
        upsert_link_binding(db, ont.id, source, tracks, radar, target, "ad_radar_target_links", "radar_code", "target_code", {"relation_type": "TRACKS", "status": "active"})
        upsert_link_binding(db, ont.id, source, locks, radar, target, "ad_radar_target_links", "radar_code", "target_code", {"relation_type": "LOCKS", "status": "active"})
        upsert_link_binding(db, ont.id, source, has_target, batch, target, "ad_targets", "batch_code", "target_code", {})

        capacity_rule = upsert_rule(db, ont.id, "跟踪容量评估", system, '''\ndef check(context):\n    new_target_count = int(context.get("new_target_count") or context.get("target_count") or 0)\n    available = int(float(context.get("available_capacity") or 0))\n    total = int(float(context.get("total_track_capacity") or 0))\n    current = int(float(context.get("current_track_count") or 0))\n    shortage = max(0, new_target_count - available)\n    return {\n        "passed": shortage > 0,\n        "severity": "high" if shortage > 0 else "info",\n        "message": f"新增目标{new_target_count}个，当前总容量{total}，已跟踪{current}，可用{available}，缺口{shortage}",\n        "new_target_count": new_target_count,\n        "total_capacity": total,\n        "current_track_count": current,\n        "available_capacity": available,\n        "shortage": shortage,\n        "suggested_next_step": "query_available_ad_radars" if shortage > 0 else "assign_tracking",\n    }\n''')
        upsert_rule(db, ont.id, "雷达可用性检查", radar, '''\ndef check(context):\n    status = str(context.get("status") or "").lower()\n    available = int(float(context.get("available_capacity") or 0))\n    passed = status == "online" and available > 0\n    return {\n        "passed": passed,\n        "severity": "info" if passed else "warning",\n        "message": f"雷达状态={status}, 可用跟踪容量={available}",\n        "available_capacity": available,\n        "can_track": passed,\n    }\n''')
        assign_action = '''\ndef execute(context):\n    tools = context.get("tools", {})\n    execute_sql = tools.get("execute_sql")\n    if not execute_sql:\n        return {"status": "failed", "message": "execute_sql tool unavailable"}\n    data_source_id = context.get("data_source_id")\n    command_id = context.get("command_id") or "DEMO-CMD-ASSIGN-001"\n    assignments = context.get("assignments") or []\n    if not data_source_id:\n        return {"status": "failed", "message": "data_source_id is required"}\n    if not assignments:\n        return {"status": "failed", "message": "assignments is required"}\n    execute_sql(data_source_id, """\n        INSERT INTO ad_dispatch_commands(command_id, command_type, status, source, reason, issued_at, executed_at)\n        VALUES (:command_id, 'ASSIGN_TRACKING', 'executed', 'agent_orchestration', :reason, NOW(), NOW())\n        ON CONFLICT (command_id) DO UPDATE SET status='executed', executed_at=NOW(), reason=EXCLUDED.reason\n    """, {"command_id": command_id, "reason": context.get("reason", "agent generated tracking allocation")})\n    created = 0\n    for item in assignments:\n        radar_code = item.get("radar_code")\n        target_code = item.get("target_code")\n        if not radar_code or not target_code:\n            continue\n        execute_sql(data_source_id, """\n            INSERT INTO ad_radar_target_links(id, system_code, radar_code, target_code, relation_type, status, started_at, confidence)\n            VALUES (:id, :system_code, :radar_code, :target_code, 'TRACKS', 'active', NOW(), 1.0)\n            ON CONFLICT (radar_code, target_code, relation_type, status) DO NOTHING\n        """, {"id": item.get("id") or target_code + '-' + radar_code + '-TRACKS', "system_code": context.get("system_code", "EADS-001"), "radar_code": radar_code, "target_code": target_code})\n        execute_sql(data_source_id, """\n            INSERT INTO ad_dispatch_allocations(id, command_id, radar_code, target_code, action, status, created_at)\n            VALUES (:id, :command_id, :radar_code, :target_code, 'ASSIGN_TRACKING', 'executed', NOW())\n            ON CONFLICT (command_id, radar_code, target_code, action) DO NOTHING\n        """, {"id": item.get("alloc_id") or command_id + '-' + radar_code + '-' + target_code, "command_id": command_id, "radar_code": radar_code, "target_code": target_code})\n        execute_sql(data_source_id, "UPDATE ad_targets SET status='tracking', updated_at=NOW() WHERE target_code=:target_code", {"target_code": target_code})\n        created += 1\n    return {"status": "done", "message": f"已分配{created}个目标进入持续跟踪", "command_id": command_id, "assigned": created}\n'''
        upsert_action(db, ont.id, "分配雷达持续跟踪", assign_action, capacity_rule)
        db.commit()
        print(json.dumps({
            "ontology_id": ont.id,
            "data_source_id": source.id,
            "system_code": SYSTEM_CODE,
            "radar_1": "R-001",
            "radar_2": "R-002",
            "target_batch": "UAV-BATCH-A",
            "action": "分配雷达持续跟踪",
        }, ensure_ascii=False, indent=2))
    finally:
        db.close()


def main():
    create_business_tables()
    seed_ontology()


if __name__ == "__main__":
    main()
