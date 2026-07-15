"""
OntoPrompt API v2

架构：FastAPI + PostgreSQL + Neo4j + ChromaDB + MinIO + Celery/Redis
v2 新增：Pipelines 全链路（Connection→Dataset→Transform→Curated→Mapping）
v1 兼容：/api/v1/* 路由全部保留

启动：uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import asyncio
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import engine, Base, SessionLocal
from app.config import settings
from app.routers import auth, users, overview, ontologies, files, prompts, models, entities, logic, actions, extraction, graph, settings as settings_router, export
from app.routers.v2 import connections as connections_v2
from app.routers.v2 import datasets as datasets_v2
from app.routers.v2 import pipelines as pipelines_v2
from app.routers.v2 import graph as graph_v2
from app.routers.v2 import search as search_v2
from app.routers.v2 import curated as curated_v2
from app.routers.v2 import mappings as mappings_v2
from app.routers.v2 import incremental as incremental_v2
from app.routers.v2 import logic_actions as logic_actions_v2
from app.routers.v2 import object_types as object_types_v2
from app.routers.v2 import object_rules as object_rules_v2
from app.routers.v2 import object_actions as object_actions_v2
from app.routers.v2 import database_explorer
from app.routers.v2 import data_sources as data_sources_v2
from app.routers.v2 import manual as manual_v2
from app.routers.v2 import runtime as runtime_v2
from app.routers import skills
from app.routers import intel_demo
from app.routers import templates

def _seed_db():
    from app.services.auth_service import seed_admin
    from app.models.rules_config import RulesConfig
    import uuid

    db = SessionLocal()
    try:
        # Import all models to ensure tables are created
        from app.models import user, ontology, file, prompt, model_config, entity, logic as logic_model, action, relation, extraction_task, rules_config, entity_template  # noqa: F401
        from app.models.v2 import dataset as v2_dataset, pipeline as v2_pipeline, connection as v2_connection  # noqa: F401
        from app.models.v2.logic import OntologyLogicRule, OntologyStateMachine  # noqa: F401
        from app.models.v2.action import OntologyActionType, OntologyActionRun  # noqa: F401
        from app.models.v2.object_type import ObjectType, ObjectInstance, Interface, LinkType, Link  # noqa: F401
        from app.models.v2.data_source import DataSource  # noqa: F401
        from app.models.v2.manual_binding import ManualFieldBinding, ManualLinkBinding, ManualOrchestrationRun, ManualRuntimeActionRun  # noqa: F401
        from app.models.object_rule import ObjectRule  # noqa: F401
        from app.models.object_action import ObjectAction  # noqa: F401
        from app.models.skill import Skill, SkillTrigger  # noqa: F401
        from app.models.intel_snapshot import IntelSnapshot  # noqa: F401
        Base.metadata.create_all(bind=engine)

        # SQLite column migrations — create_all skips existing tables
        with engine.connect() as conn:
            def _run_ddl(stmt: str) -> None:
                """Best-effort schema patching for older databases.

                A failed DDL statement aborts the current PostgreSQL transaction, so we
                must roll back before trying the next statement or the remaining
                migrations will silently fail.
                """
                try:
                    conn.execute(text(stmt))
                    conn.commit()
                except Exception:
                    conn.rollback()

            for stmt in [
                "ALTER TABLE extraction_tasks ADD COLUMN validation_report TEXT",
                "ALTER TABLE model_configs ADD COLUMN config_type VARCHAR(30) DEFAULT 'llm'",
                "ALTER TABLE model_configs ADD COLUMN options JSON DEFAULT '{}'",
                "ALTER TABLE ontology_projects ADD COLUMN build_mode VARCHAR(30) DEFAULT 'simple_llm'",
                "ALTER TABLE v2_pipelines ADD COLUMN domain VARCHAR(100) DEFAULT '通用'",
                "ALTER TABLE v2_pipelines ADD COLUMN description TEXT DEFAULT ''",
                "ALTER TABLE v2_pipelines ADD COLUMN definition JSON",
                "ALTER TABLE v2_pipelines ADD COLUMN branch VARCHAR(50) DEFAULT 'main'",
                "ALTER TABLE v2_pipelines ADD COLUMN version INTEGER DEFAULT 1",
                "ALTER TABLE logic_rules ADD COLUMN enabled BOOLEAN DEFAULT 1",
                "ALTER TABLE logic_rules ADD COLUMN status VARCHAR(20) DEFAULT 'draft'",
                "ALTER TABLE actions ADD COLUMN enabled BOOLEAN DEFAULT 1",
                "ALTER TABLE actions ADD COLUMN status VARCHAR(20) DEFAULT 'draft'",
                # Phase 1 结构化提取: Action / LogicRule / Entity 新增字段
                "ALTER TABLE entities ADD COLUMN property_schema JSON DEFAULT '{}'",
                "ALTER TABLE actions ADD COLUMN submission_criteria JSON DEFAULT '[]'",
                "ALTER TABLE actions ADD COLUMN target_entity_type VARCHAR(200)",
                "ALTER TABLE actions ADD COLUMN needs_review BOOLEAN DEFAULT false",
                "ALTER TABLE logic_rules ADD COLUMN conditions JSON DEFAULT '[]'",
                "ALTER TABLE logic_rules ADD COLUMN needs_review BOOLEAN DEFAULT false",
                # Phase 2: 新 object_types 体系外键
                "ALTER TABLE actions ADD COLUMN target_object_type_id VARCHAR",
                "ALTER TABLE logic_rules ADD COLUMN linked_object_type_ids JSON DEFAULT '[]'",
                "ALTER TABLE object_types ADD COLUMN parent_id VARCHAR(200)",
                "ALTER TABLE link_types ADD COLUMN property_schema JSON DEFAULT '{}'",
                "ALTER TABLE links ADD COLUMN properties JSON DEFAULT '{}'",
                "ALTER TABLE extraction_tasks ADD COLUMN raw_output JSON",
                "ALTER TABLE intel_snapshots ADD COLUMN IF NOT EXISTS created_entity_ids JSON DEFAULT '[]'",
                "ALTER TABLE intel_snapshots ADD COLUMN IF NOT EXISTS created_relation_ids JSON DEFAULT '[]'",
                "CREATE TABLE IF NOT EXISTS manual_field_bindings ("
                "id VARCHAR PRIMARY KEY, "
                "ontology_id VARCHAR NOT NULL REFERENCES ontology_projects(id) ON DELETE CASCADE, "
                "object_type_id VARCHAR(200) NOT NULL, "
                "property_name VARCHAR(200) NOT NULL, "
                "data_source_id VARCHAR REFERENCES data_sources(id) ON DELETE SET NULL, "
                "schema_name VARCHAR(200), table_name VARCHAR(200) NOT NULL, column_name VARCHAR(200) NOT NULL, "
                "primary_key_column VARCHAR(200), value_type VARCHAR(50) DEFAULT 'string', direction VARCHAR(20) DEFAULT 'read', "
                "transform_expression TEXT, is_required BOOLEAN DEFAULT false, read_only BOOLEAN DEFAULT true, "
                "created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()"
                ")",
                "CREATE TABLE IF NOT EXISTS manual_link_bindings ("
                "id VARCHAR PRIMARY KEY, "
                "ontology_id VARCHAR NOT NULL REFERENCES ontology_projects(id) ON DELETE CASCADE, "
                "link_type_id VARCHAR(200) NOT NULL, "
                "data_source_id VARCHAR REFERENCES data_sources(id) ON DELETE SET NULL, "
                "schema_name VARCHAR(200), table_name VARCHAR(200) NOT NULL, "
                "source_object_type_id VARCHAR(200) NOT NULL, source_key_column VARCHAR(200) NOT NULL, "
                "target_object_type_id VARCHAR(200) NOT NULL, target_key_column VARCHAR(200) NOT NULL, "
                "direction VARCHAR(20) DEFAULT 'out', relation_filters JSON DEFAULT '{}', property_bindings JSON DEFAULT '{}', "
                "transform_expression TEXT, is_active BOOLEAN DEFAULT true, "
                "created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()"
                ")",
                "CREATE TABLE IF NOT EXISTS manual_orchestration_runs ("
                "id VARCHAR PRIMARY KEY, "
                "ontology_id VARCHAR NOT NULL REFERENCES ontology_projects(id) ON DELETE CASCADE, "
                "external_run_id VARCHAR(200), agent_key VARCHAR(200), status VARCHAR(30) DEFAULT 'running', "
                "input_context JSON DEFAULT '{}', result_summary JSON DEFAULT '{}', error TEXT, "
                "started_at TIMESTAMP DEFAULT NOW(), completed_at TIMESTAMP"
                ")",
                "CREATE INDEX IF NOT EXISTS ix_manual_orchestration_runs_ontology ON manual_orchestration_runs(ontology_id)",
                "ALTER TABLE manual_runtime_action_runs ADD COLUMN IF NOT EXISTS orchestration_run_id VARCHAR(200)",
                "CREATE TABLE IF NOT EXISTS manual_runtime_action_runs ("
                "id VARCHAR PRIMARY KEY, "
                "ontology_id VARCHAR NOT NULL REFERENCES ontology_projects(id) ON DELETE CASCADE, "
                "action_key VARCHAR(200) NOT NULL, orchestration_run_id VARCHAR(200), "
                "idempotency_key VARCHAR(200), status VARCHAR(30) DEFAULT 'running', "
                "request_payload JSON DEFAULT '{}', result_payload JSON DEFAULT '{}', error TEXT, "
                "started_at TIMESTAMP DEFAULT NOW(), completed_at TIMESTAMP"
                ")",
                "CREATE INDEX IF NOT EXISTS ix_manual_runtime_action_runs_orchestration "
                "ON manual_runtime_action_runs(ontology_id, orchestration_run_id)",
                "DROP INDEX IF EXISTS ux_manual_runtime_action_runs_idem",
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_manual_runtime_action_runs_idem_global "
                "ON manual_runtime_action_runs(ontology_id, idempotency_key) "
                "WHERE idempotency_key IS NOT NULL AND orchestration_run_id IS NULL",
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_manual_runtime_action_runs_idem_orch "
                "ON manual_runtime_action_runs(ontology_id, orchestration_run_id, idempotency_key) "
                "WHERE idempotency_key IS NOT NULL AND orchestration_run_id IS NOT NULL",
                "CREATE TABLE IF NOT EXISTS intel_snapshots ("
                "id VARCHAR PRIMARY KEY, ontology_id VARCHAR NOT NULL REFERENCES ontology_projects(id) ON DELETE CASCADE,"
                "label VARCHAR(50) NOT NULL, intel_text TEXT NOT NULL,"
                "extraction_task_id VARCHAR REFERENCES extraction_tasks(id) ON DELETE SET NULL,"
                "danger_score FLOAT DEFAULT 0.0, danger_level VARCHAR(20) DEFAULT 'low',"
                "recommendations JSON DEFAULT '[]', entity_count INTEGER DEFAULT 0, relation_count INTEGER DEFAULT 0,"
                "status VARCHAR(20) DEFAULT 'extracting',"
                "created_at TIMESTAMP DEFAULT NOW()"
                ")",
            ]:
                _run_ddl(stmt)

        seed_admin(db)

        # Seed confidence rules
        if db.query(RulesConfig).count() == 0:
            rules = [
                ("confidence_entity_min", "0.5", "实体最低置信度", "Entity min confidence"),
                ("confidence_logic_min", "0.6", "逻辑规则最低置信度", "Logic rule min confidence"),
                ("confidence_action_min", "0.6", "动作最低置信度", "Action min confidence"),
                ("confidence_relation_min", "0.5", "关系最低置信度", "Relation min confidence"),
                ("confidence_high_threshold", "0.9", "高置信度阈值", "High confidence threshold"),
                ("confidence_medium_threshold", "0.7", "中置信度阈值", "Medium confidence threshold"),
                ("confidence_low_threshold", "0.5", "低置信度阈值", "Low confidence threshold"),
                ("confidence_display_dashed_below", "0.7", "低于此值显示虚线边", "Show dashed edge below threshold"),
            ]
            for key, val, label_cn, label_en in rules:
                db.add(RulesConfig(id=str(uuid.uuid4()), rule_key=key, rule_value=val,
                                   rule_label_cn=label_cn, rule_label_en=label_en))
            db.commit()

        # Seed / update snapshot interval rule
        existing = db.query(RulesConfig).filter(RulesConfig.rule_key == "db_snapshot_interval_hours").first()
        if not existing:
            db.add(RulesConfig(id=str(uuid.uuid4()),
                               rule_key="db_snapshot_interval_hours",
                               rule_value="1",
                               rule_label_cn="自动快照间隔(小时)",
                               rule_label_en="Auto snapshot interval (hours)",
                               editable=True))
            db.commit()

        # Seed / update builtin prompts (upsert by name)
        from app.models.prompt import Prompt
        from app.models.user import User
        from app.routers.prompts import BUILTIN_PROMPTS
        admin = db.query(User).filter(User.role == "admin").first()
        if admin:
            for p in BUILTIN_PROMPTS:
                existing = db.query(Prompt).filter(Prompt.name == p["name"]).first()
                if existing:
                    existing.content = p["content"]
                    existing.domain = p["domain"]
                else:
                    db.add(Prompt(id=str(uuid.uuid4()), name=p["name"], domain=p["domain"],
                                  content=p["content"], version="v1.0", created_by=admin.id))
            db.commit()
    finally:
        db.close()

async def _auto_snapshot_loop():
    from app.services.db_snapshot_service import DatabaseSnapshotService
    from app.models.rules_config import RulesConfig

    await asyncio.sleep(30)
    while True:
        try:
            db = SessionLocal()
            rule = db.query(RulesConfig).filter(RulesConfig.rule_key == "db_snapshot_interval_hours").first()
            db.close()
            interval_hours = float(rule.rule_value) if rule else 1.0
        except Exception:
            interval_hours = 1.0
        if interval_hours <= 0:
            print(f"[auto-snapshot] Disabled (interval={interval_hours}h)")
            await asyncio.sleep(60)
            continue

        print(f"[auto-snapshot] Interval={interval_hours}h, creating snapshot...")
        try:
            svc = DatabaseSnapshotService()
            info = svc.create_snapshot(label="auto")
            print(f"[auto-snapshot] Created: {info.name} ({info.size} bytes)")
        except Exception as e:
            print(f"[auto-snapshot] Failed: {e}")

        await asyncio.sleep(interval_hours * 3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_db()
    try:
        from app.services.v2.graph.index_setup import setup_indexes
        setup_indexes()
    except Exception:
        pass
    task = asyncio.create_task(_auto_snapshot_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="OntoPrompt API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://192.168.111.79:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(overview.router, prefix="/api/v1/overview", tags=["overview"])
app.include_router(ontologies.router, prefix="/api/v1/ontologies", tags=["ontologies"])
app.include_router(files.router, prefix="/api/v1/ontologies/{ontology_id}/files", tags=["files"])
app.include_router(entities.router, prefix="/api/v1/ontologies/{ontology_id}/entities", tags=["entities"])
app.include_router(templates.router, prefix="/api/v1/ontologies/{ontology_id}/templates", tags=["templates"])
app.include_router(logic.router, prefix="/api/v1/ontologies/{ontology_id}/logic", tags=["logic"])
app.include_router(actions.router, prefix="/api/v1/ontologies/{ontology_id}/actions", tags=["actions"])
app.include_router(extraction.router, prefix="/api/v1/ontologies/{ontology_id}/execute", tags=["extraction"])
app.include_router(graph.router, prefix="/api/v1/ontologies/{ontology_id}/graph", tags=["graph"])
app.include_router(export.router, prefix="/api/v1/ontologies/{ontology_id}/export", tags=["export"])
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])
app.include_router(skills.router, prefix="/api/v2/skills", tags=["v2-skills"])
app.include_router(intel_demo.router, prefix="/api/v2/intel-demo", tags=["v2-intel-demo"])
app.include_router(models.router, prefix="/api/v1/models", tags=["models"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(connections_v2.router, prefix="/api/v2/connections", tags=["v2-connections"])
app.include_router(datasets_v2.router, prefix="/api/v2/datasets", tags=["v2-datasets"])
app.include_router(pipelines_v2.router, prefix="/api/v2/pipelines", tags=["v2-pipelines"])
app.include_router(graph_v2.router, prefix="/api/v2/ontologies", tags=["v2-graph"])
app.include_router(search_v2.router, prefix="/api/v2/ontologies", tags=["v2-search"])
app.include_router(curated_v2.router, prefix="/api/v2/curated", tags=["v2-curated"])
app.include_router(mappings_v2.router, prefix="/api/v2/ontologies", tags=["v2-mappings"])
app.include_router(incremental_v2.router, prefix="/api/v2/incremental", tags=["v2-incremental"])
app.include_router(logic_actions_v2.router, prefix="/api/v2/ontologies", tags=["v2-logic-actions"])
app.include_router(object_types_v2.router, prefix="/api/v2/ontologies", tags=["v2-object-types"])
app.include_router(object_rules_v2.router, prefix="/api/v2/ontologies", tags=["v2-object-rules"])
app.include_router(object_actions_v2.router, prefix="/api/v2/ontologies", tags=["v2-object-actions"])
app.include_router(database_explorer.router, prefix="/api/v2", tags=["v2-database"])
app.include_router(data_sources_v2.router, prefix="/api/v2/ontologies", tags=["v2-data-sources"])
app.include_router(manual_v2.router, prefix="/api/v2/manual", tags=["v2-manual-runtime-authoring"])
app.include_router(runtime_v2.router, prefix="/api/v2/runtime", tags=["v2-runtime-api"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health(db: Session = Depends(get_db)):
    checks = {
        "status": "ok",
        "db": "unknown",
        "neo4j": "unknown",
        "minio": "unknown",
        "chroma": "unknown",
    }

    # PostgreSQL check
    try:
        db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    # Neo4j check
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        driver.verify_connectivity()
        driver.close()
        checks["neo4j"] = "ok"
    except Exception:
        checks["neo4j"] = "unavailable"

    # MinIO check
    try:
        from minio import Minio
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )
        client.list_buckets()
        checks["minio"] = "ok"
    except Exception:
        checks["minio"] = "unavailable"

    # ChromaDB check
    try:
        import chromadb
        client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        client.heartbeat()
        checks["chroma"] = "ok"
    except Exception:
        checks["chroma"] = "unavailable"

    return checks
