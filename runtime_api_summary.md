# Runtime API 接口文档

## 概述

Runtime API 是面向**第三方代理编排系统**的语义接口层，基于 `build_mode=manual` 的本体工作。
Agent 通过此 API 以业务语义（ObjectType / Object / Property / Relation / Rule / Action）操作本体，
无需接触底层数据库表、SQL 或 DataSource 连接串。

**领域示例:** 防空反导（以下所有示例数据均来自项目种子数据）

---

## 一、Runtime API (`/api/v2/runtime`)

**路由文件:** `backend/app/routers/v2/runtime/__init__.py`
**前置条件:** `ontology.build_mode == "manual"`，否则返回 409

---

### 1. 获取本体元数据

```
GET /api/v2/runtime/ontologies/{ontology_id}/metadata
```

**说明:** Agent 的**第一个调用**。获取本体完整 schema：所有 ObjectType、属性、关系类型、规则、动作。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID，如 `"ont_air_defense_001"` |

**输出示例:**
```json
{
  "ontology": {
    "id": "ont_air_defense_001",
    "name": "东部防空反导系统手动本体",
    "domain": "防空反导",
    "version": "1.0"
  },
  "object_types": [
    {
      "key": "AirDefenseSystem",
      "label": "防空系统",
      "id": "ot_ads_001",
      "properties": [
        { "name": "system_code", "type": "string", "unit": null, "bound": true },
        { "name": "combat_status", "type": "string", "unit": null, "bound": true },
        { "name": "alert_level", "type": "string", "unit": null, "bound": true },
        { "name": "total_track_capacity", "type": "number", "unit": null, "bound": true },
        { "name": "current_track_count", "type": "number", "unit": null, "bound": true },
        { "name": "available_capacity", "type": "number", "unit": null, "bound": true }
      ]
    },
    {
      "key": "Radar",
      "label": "雷达",
      "id": "ot_radar_001",
      "properties": [
        { "name": "radar_code", "type": "string", "unit": null, "bound": true },
        { "name": "status", "type": "string", "unit": null, "bound": true },
        { "name": "max_track_capacity", "type": "number", "unit": null, "bound": true },
        { "name": "current_track_count", "type": "number", "unit": null, "bound": true },
        { "name": "available_capacity", "type": "number", "unit": null, "bound": true },
        { "name": "loc", "type": "string", "unit": null, "bound": true }
      ]
    },
    {
      "key": "Target",
      "label": "目标",
      "id": "ot_target_001",
      "properties": [
        { "name": "target_code", "type": "string", "unit": null, "bound": true },
        { "name": "target_type", "type": "string", "unit": null, "bound": true },
        { "name": "threat_level", "type": "string", "unit": null, "bound": true },
        { "name": "status", "type": "string", "unit": null, "bound": true },
        { "name": "bearing", "type": "number", "unit": "deg", "bound": true },
        { "name": "speed", "type": "number", "unit": "m/s", "bound": true }
      ]
    },
    {
      "key": "TargetBatch",
      "label": "目标批次",
      "id": "ot_tbatch_001",
      "properties": [
        { "name": "batch_code", "type": "string", "unit": null, "bound": true },
        { "name": "batch_type", "type": "string", "unit": null, "bound": true },
        { "name": "count", "type": "number", "unit": null, "bound": true },
        { "name": "status", "type": "string", "unit": null, "bound": true },
        { "name": "zone", "type": "string", "unit": null, "bound": true }
      ]
    },
    {
      "key": "DispatchCommand",
      "label": "调度命令",
      "id": "ot_dcmd_001",
      "properties": [
        { "name": "command_id", "type": "string", "unit": null, "bound": true },
        { "name": "command_type", "type": "string", "unit": null, "bound": true },
        { "name": "status", "type": "string", "unit": null, "bound": true },
        { "name": "issued_at", "type": "string", "unit": null, "bound": true }
      ]
    }
  ],
  "relations": [
    {
      "key": "BELONGS_TO",
      "label": "隶属系统",
      "source_type_id": "ot_radar_001",
      "target_type_id": "ot_ads_001"
    },
    {
      "key": "TRACKS",
      "label": "持续跟踪",
      "source_type_id": "ot_radar_001",
      "target_type_id": "ot_target_001"
    },
    {
      "key": "LOCKS",
      "label": "锁定",
      "source_type_id": "ot_radar_001",
      "target_type_id": "ot_target_001"
    },
    {
      "key": "HAS_TARGET",
      "label": "包含目标",
      "source_type_id": "ot_tbatch_001",
      "target_type_id": "ot_target_001"
    }
  ],
  "rules": [
    {
      "key": "跟踪容量评估",
      "id": "rule_capacity_001",
      "description": "检查新增目标数是否超过系统可用容量",
      "target_type_id": "ot_ads_001"
    },
    {
      "key": "雷达可用性检查",
      "id": "rule_radar_avail_001",
      "description": "检查雷达是否在线且有空闲跟踪能力",
      "target_type_id": "ot_radar_001"
    },
    {
      "key": "威胁等级评估",
      "id": "rule_threat_001",
      "description": "根据目标类型、速度、高度评估威胁等级",
      "target_type_id": "ot_target_001"
    }
  ],
  "actions": [
    {
      "key": "分配雷达持续跟踪",
      "id": "act_assign_radar_001",
      "description": "将新增目标分配给指定雷达进行持续跟踪",
      "linked_rule_id": "rule_capacity_001"
    },
    {
      "key": "锁定威胁",
      "id": "act_lock_threat_001",
      "description": "对高威胁目标执行火控锁定",
      "linked_rule_id": "rule_threat_001"
    }
  ],
  "runtime_capabilities": {
    "field_bindings": 22,
    "link_bindings": 4,
    "dynamic_relations": true
  }
}
```

---

### 2. 列出所有 ObjectType

```
GET /api/v2/runtime/ontologies/{ontology_id}/types
```

**说明:** 轻量列出所有 ObjectType（含属性 schema，不含关系/规则/动作）。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |

**输出示例:**
```json
{
  "types": [
    {
      "key": "AirDefenseSystem",
      "label": "防空系统",
      "id": "ot_ads_001",
      "properties": [
        { "name": "system_code", "type": "string", "unit": null, "bound": true },
        { "name": "combat_status", "type": "string", "unit": null, "bound": true },
        { "name": "alert_level", "type": "string", "unit": null, "bound": true },
        { "name": "total_track_capacity", "type": "number", "unit": null, "bound": true },
        { "name": "current_track_count", "type": "number", "unit": null, "bound": true },
        { "name": "available_capacity", "type": "number", "unit": null, "bound": true }
      ]
    },
    {
      "key": "Radar",
      "label": "雷达",
      "id": "ot_radar_001",
      "properties": [
        { "name": "radar_code", "type": "string", "unit": null, "bound": true },
        { "name": "status", "type": "string", "unit": null, "bound": true },
        { "name": "max_track_capacity", "type": "number", "unit": null, "bound": true },
        { "name": "current_track_count", "type": "number", "unit": null, "bound": true },
        { "name": "available_capacity", "type": "number", "unit": null, "bound": true },
        { "name": "loc", "type": "string", "unit": null, "bound": true }
      ]
    }
  ]
}
```

---

### 3. 获取单个 ObjectType 详情

```
GET /api/v2/runtime/ontologies/{ontology_id}/types/{type_key}
```

**说明:** 单个 ObjectType 的详细 property schema。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| type_key | string | path | ObjectType 的 id / name_en / name_cn |

**输出示例 (查询 `Radar`):**
```json
{
  "key": "Radar",
  "label": "雷达",
  "id": "ot_radar_001",
  "properties": [
    { "name": "radar_code", "type": "string", "unit": null, "bound": true },
    { "name": "status", "type": "string", "unit": null, "bound": true },
    { "name": "max_track_capacity", "type": "number", "unit": null, "bound": true },
    { "name": "current_track_count", "type": "number", "unit": null, "bound": true },
    { "name": "available_capacity", "type": "number", "unit": null, "bound": true },
    { "name": "loc", "type": "string", "unit": null, "bound": true }
  ]
}
```

---

### 4. 列出某类型的所有对象

```
GET /api/v2/runtime/ontologies/{ontology_id}/objects/{type_key}?limit=50
```

**说明:** 列出指定 ObjectType 的所有实例，返回业务主键及所有 bound 属性。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| type_key | string | path | ObjectType key，如 `"Radar"` |
| limit | int | query | 限制数量，默认 50，范围 1-500 |

**输出示例 (查询 `Radar`):**
```json
{
  "items": [
    {
      "id": "R-001",
      "type_key": "Radar",
      "type_label": "雷达",
      "properties": {
        "radar_code": "R-001",
        "status": "online",
        "max_track_capacity": 20,
        "current_track_count": 12,
        "available_capacity": 8,
        "loc": "deployed"
      },
      "_sources": {
        "status": {
          "data_source_id": "ds_radar_runtime_001",
          "table": "public.radar_runtime_status",
          "column": "status",
          "pk_column": "radar_code"
        },
        "current_track_count": {
          "data_source_id": "ds_radar_runtime_001",
          "table": "public.radar_runtime_status",
          "column": "current_track_count",
          "pk_column": "radar_code"
        }
      }
    },
    {
      "id": "R-002",
      "type_key": "Radar",
      "type_label": "雷达",
      "properties": {
        "radar_code": "R-002",
        "status": "online",
        "max_track_capacity": 20,
        "current_track_count": 5,
        "available_capacity": 15,
        "loc": "deployed"
      },
      "_sources": { }
    }
  ],
  "count": 2
}
```

---

### 5. 获取单个对象

```
GET /api/v2/runtime/ontologies/{ontology_id}/objects/{type_key}/{object_key}
```

**说明:** 读取单个对象，所有 bound 属性通过 field binding → transform engine → type casting 解析。
`_sources` 字段追踪每个值的数据库来源。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| type_key | string | path | ObjectType key |
| object_key | string | path | 对象的业务主键值 |

**输出示例 (查询 `Target` / `M-001`):**
```json
{
  "object": {
    "id": "M-001",
    "type_key": "Target",
    "type_label": "目标",
    "properties": {
      "target_code": "M-001",
      "target_type": "incoming_missile",
      "threat_level": "critical",
      "status": "locked",
      "bearing": 45.5,
      "speed": 680
    },
    "_sources": {
      "target_type": {
        "data_source_id": "ds_targets_001",
        "table": "public.ad_targets",
        "column": "target_type",
        "pk_column": "target_code"
      },
      "threat_level": {
        "data_source_id": "ds_targets_001",
        "table": "public.ad_targets",
        "column": "threat_level",
        "pk_column": "target_code"
      },
      "speed": {
        "data_source_id": "ds_targets_001",
        "table": "public.ad_targets",
        "column": "speed",
        "pk_column": "target_code"
      }
    }
  }
}
```

---

### 6. 查询对象

```
POST /api/v2/runtime/ontologies/{ontology_id}/objects/{type_key}/query
```

**说明:** 带过滤和排序的查询。当前支持 exact-match AND 过滤。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| type_key | string | path | ObjectType key |

**请求体 (ObjectQueryRequest):**
| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| filter | dict | {} | 属性过滤，值可为字面量或 `{op, value}` |
| sort | list[dict] | [] | 排序，`{field, direction}` |
| limit | int | 20 | 1-500 |

**支持的 filter op:** `eq`, `neq`, `contains`, `in`, `gt`, `gte`, `lt`, `lte`

**请求示例 — 查询 `Target` 中所有 threat_level 为 `critical` 的目标，按 speed 降序排列:**
```json
{
  "filter": { "threat_level": "critical" },
  "sort": [ { "field": "speed", "direction": "desc" } ],
  "limit": 10
}
```

**输出示例:**
```json
{
  "items": [
    {
      "id": "M-001",
      "type_key": "Target",
      "type_label": "目标",
      "properties": {
        "target_code": "M-001",
        "target_type": "incoming_missile",
        "threat_level": "critical",
        "status": "locked",
        "bearing": 45.5,
        "speed": 680
      },
      "_sources": { }
    },
    {
      "id": "M-003",
      "type_key": "Target",
      "type_label": "目标",
      "properties": {
        "target_code": "M-003",
        "target_type": "ballistic_missile",
        "threat_level": "critical",
        "status": "incoming",
        "bearing": 120.3,
        "speed": 1500
      },
      "_sources": { }
    }
  ],
  "count": 2
}
```

**请求示例 — 使用 op 语法:** 查询速度 > 500 的目标
```json
{
  "filter": { "speed": { "op": "gt", "value": 500 } },
  "limit": 20
}
```

---

### 7. 获取对象关系

```
GET /api/v2/runtime/ontologies/{ontology_id}/objects/{type_key}/{object_key}/relations?relation=TRACKS
```

**说明:** 获取指定对象的所有**出向关系**。支持静态 Link（materialized）和动态 DB link binding。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| type_key | string | path | ObjectType key |
| object_key | string | path | 对象 key |
| relation | string | query | (可选) 按 link type 名称过滤 |

**输出示例 (查询 `Radar` / `R-001` 的关系):**
```json
{
  "relations": [
    {
      "relation": "BELONGS_TO",
      "relation_label": "隶属系统",
      "source_kind": "static_link",
      "source_id": "inst_radar_r001",
      "target_id": "inst_ads_east",
      "target_key": "EADS-001",
      "target_label": "东部防空系统",
      "target_type": "防空系统",
      "target_type_key": "AirDefenseSystem",
      "properties": {},
      "confidence": 1.0
    },
    {
      "relation": "TRACKS",
      "relation_label": "持续跟踪",
      "source_kind": "dynamic_binding",
      "data_source_id": "ds_radar_links_001",
      "table": "public.ad_radar_target_links",
      "source_type": "雷达",
      "source_type_key": "Radar",
      "source_key": "R-001",
      "target_type": "目标",
      "target_type_key": "Target",
      "target_key": "M-001",
      "target_label": "M-001",
      "properties": {
        "status": "active",
        "started_at": "2026-07-16T08:30:00Z",
        "confidence": 0.95
      },
      "confidence": 0.95
    },
    {
      "relation": "TRACKS",
      "relation_label": "持续跟踪",
      "source_kind": "dynamic_binding",
      "data_source_id": "ds_radar_links_001",
      "table": "public.ad_radar_target_links",
      "source_type": "雷达",
      "source_type_key": "Radar",
      "source_key": "R-001",
      "target_type": "目标",
      "target_type_key": "Target",
      "target_key": "UAV-A-003",
      "target_label": "UAV-A-003",
      "properties": {
        "status": "active",
        "started_at": "2026-07-16T08:25:00Z",
        "confidence": 0.78
      },
      "confidence": 0.78
    }
  ]
}
```

---

### 8. 评估规则

```
POST /api/v2/runtime/ontologies/{ontology_id}/rules/evaluate
```

**说明:** 只读评估规则，无副作用。Agent 在执行动作前检查条件。

**请求体 (RuleEvaluateRequest):**
| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| rule_key | string | null | 特定规则名，省略则评估所有 |
| subject_type_key | string | null | ObjectType key |
| subject_id | string | null | 对象业务 key |
| orchestration_run_id | string | null | 可选编排运行 ID |
| context | dict | {} | 额外上下文 |

**请求示例 — 评估 `AirDefenseSystem` (`EADS-001`) 的 `跟踪容量评估` 规则:**
```json
{
  "rule_key": "跟踪容量评估",
  "subject_type_key": "AirDefenseSystem",
  "subject_id": "EADS-001",
  "context": {
    "new_target_count": 5
  }
}
```

**输出示例:**
```json
{
  "matched": true,
  "evaluations": [
    {
      "rule_key": "跟踪容量评估",
      "rule_id": "rule_capacity_001",
      "matched": true,
      "severity": "high",
      "message": "新增目标数(5)超过系统可用容量(3)",
      "details": {
        "new_target_count": 5,
        "available_capacity": 3,
        "total_capacity": 60,
        "current_count": 57
      }
    }
  ],
  "suggested_actions": [
    {
      "action_key": "分配雷达持续跟踪",
      "action_id": "act_assign_radar_001",
      "description": "将新增目标分配给指定雷达进行持续跟踪"
    }
  ]
}
```

**请求示例 — 评估所有规则 (省略 rule_key):**
```json
{
  "subject_type_key": "Radar",
  "subject_id": "R-001"
}
```

**输出示例:**
```json
{
  "matched": true,
  "evaluations": [
    {
      "rule_key": "雷达可用性检查",
      "rule_id": "rule_radar_avail_001",
      "matched": true,
      "severity": "info",
      "message": "雷达 R-001 在线，可用跟踪容量 8",
      "details": {
        "status": "online",
        "available_capacity": 8,
        "max_capacity": 20,
        "current_count": 12
      }
    }
  ],
  "suggested_actions": []
}
```

---

### 9. 执行动作

```
POST /api/v2/runtime/ontologies/{ontology_id}/actions/{action_key}/execute
```

**说明:** 执行动作（可能有副作用）。`dry_run: true` 仅做验证不执行。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| action_key | string | path | Action 的 name_cn 或 id |

**请求体 (ActionExecuteRequest):**
| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| subject_type_key | string | null | ObjectType key |
| subject_id | string | null | 对象业务 key |
| input | dict | {} | 输入数据 |
| dry_run | bool | false | 仅验证，无副作用 |
| idempotency_key | string | null | 幂等 key，防止重复执行 |
| orchestration_run_id | string | null | 可选编排运行 ID |

**请求示例 — 执行 `分配雷达持续跟踪`:**
```json
{
  "subject_type_key": "AirDefenseSystem",
  "subject_id": "EADS-001",
  "input": {
    "data_source_id": "ds_radar_links_001",
    "assignments": [
      { "radar_code": "R-002", "target_code": "M-003", "relation_type": "TRACKS" },
      { "radar_code": "R-002", "target_code": "UAV-A-007", "relation_type": "TRACKS" }
    ]
  },
  "idempotency_key": "assign_track_20260716_001",
  "orchestration_run_id": "orch_run_001"
}
```

**输出示例:**
```json
{
  "status": "done",
  "run_id": "run_abc123",
  "action_key": "分配雷达持续跟踪",
  "message": "成功分配 2 个目标给 R-002",
  "idempotency_key": "assign_track_20260716_001",
  "orchestration_run_id": "orch_run_001",
  "rowcount": 2
}
```

**请求示例 — 执行 `锁定威胁` (dry_run 验证):**
```json
{
  "subject_type_key": "Radar",
  "subject_id": "R-001",
  "input": {
    "target_id": "M-001",
    "launcher_id": "L-001"
  },
  "dry_run": true
}
```

**输出示例 (dry_run):**
```json
{
  "status": "dry_run",
  "action_key": "锁定威胁",
  "action_id": "act_lock_threat_001",
  "message": "Dry run - action would execute",
  "idempotency_key": null,
  "orchestration_run_id": null
}
```

**请求示例 — 带幂等 key 重复调用（返回历史结果）:**
```json
{
  "subject_type_key": "AirDefenseSystem",
  "subject_id": "EADS-001",
  "input": {},
  "idempotency_key": "assign_track_20260716_001"
}
```

**输出示例 (replayed):**
```json
{
  "status": "done",
  "run_id": "run_abc123",
  "idempotency_key": "assign_track_20260716_001",
  "orchestration_run_id": "orch_run_001",
  "replayed": true,
  "result": { "rowcount": 2 },
  "error": null
}
```

---

### 10. 列出动作执行记录

```
GET /api/v2/runtime/ontologies/{ontology_id}/runs?orchestration_run_id=orch_run_001&limit=50
```

**说明:** 查看历史动作执行记录。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| orchestration_run_id | string | query | (可选) 按编排运行过滤 |
| limit | int | query | 1-200，默认 50 |

**输出示例:**
```json
{
  "runs": [
    {
      "id": "run_abc123",
      "ontology_id": "ont_air_defense_001",
      "action_key": "分配雷达持续跟踪",
      "orchestration_run_id": "orch_run_001",
      "idempotency_key": "assign_track_20260716_001",
      "status": "done",
      "request_payload": {
        "subject_type_key": "AirDefenseSystem",
        "subject_id": "EADS-001",
        "input": { "assignments": [...] },
        "dry_run": false,
        "orchestration_run_id": "orch_run_001"
      },
      "result_payload": {
        "status": "done",
        "message": "成功分配 2 个目标给 R-002",
        "rowcount": 2
      },
      "error": null,
      "started_at": "2026-07-16T08:35:00+00:00",
      "completed_at": "2026-07-16T08:35:01+00:00"
    },
    {
      "id": "run_def456",
      "ontology_id": "ont_air_defense_001",
      "action_key": "锁定威胁",
      "orchestration_run_id": "orch_run_001",
      "idempotency_key": null,
      "status": "failed",
      "request_payload": {
        "subject_type_key": "Radar",
        "subject_id": "R-001",
        "input": { "target_id": "M-001", "launcher_id": "L-001" },
        "dry_run": false,
        "orchestration_run_id": "orch_run_001"
      },
      "result_payload": {
        "status": "failed",
        "message": "Action runtime error: 拦截弹 L-001 弹药不足",
        "action_key": "锁定威胁"
      },
      "error": "拦截弹 L-001 弹药不足",
      "started_at": "2026-07-16T08:36:00+00:00",
      "completed_at": "2026-07-16T08:36:00+00:00"
    }
  ]
}
```

---

### 11. 获取单条动作执行记录

```
GET /api/v2/runtime/ontologies/{ontology_id}/runs/{run_id}
```

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| run_id | string | path | 运行记录 ID |

**输出示例:**
```json
{
  "id": "run_abc123",
  "ontology_id": "ont_air_defense_001",
  "action_key": "分配雷达持续跟踪",
  "orchestration_run_id": "orch_run_001",
  "idempotency_key": "assign_track_20260716_001",
  "status": "done",
  "request_payload": {
    "subject_type_key": "AirDefenseSystem",
    "subject_id": "EADS-001",
    "input": { "assignments": [...] },
    "dry_run": false,
    "orchestration_run_id": "orch_run_001"
  },
  "result_payload": {
    "status": "done",
    "message": "成功分配 2 个目标给 R-002",
    "rowcount": 2
  },
  "error": null,
  "started_at": "2026-07-16T08:35:00+00:00",
  "completed_at": "2026-07-16T08:35:01+00:00"
}
```

---

### 12. 创建编排运行

```
POST /api/v2/runtime/ontologies/{ontology_id}/orchestration-runs
```

**说明:** 创建一个编排运行上下文，关联多个动作执行，用于 Agent 工作流追踪。

**请求体 (OrchestrationRunCreateRequest):**
| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| external_run_id | string | null | 外部编排系统的 run ID |
| agent_key | string | null | agent/workflow 标识 |
| input_context | dict | {} | 初始编排上下文快照 |

**请求示例:**
```json
{
  "external_run_id": "agent_orch_20260716_001",
  "agent_key": "threat_response_agent_v1",
  "input_context": {
    "trigger": "new_target_detected",
    "target_code": "M-003",
    "target_type": "ballistic_missile",
    "detected_by": "R-001"
  }
}
```

**输出示例:**
```json
{
  "id": "orch_run_001",
  "ontology_id": "ont_air_defense_001",
  "external_run_id": "agent_orch_20260716_001",
  "agent_key": "threat_response_agent_v1",
  "status": "running",
  "input_context": {
    "trigger": "new_target_detected",
    "target_code": "M-003",
    "target_type": "ballistic_missile",
    "detected_by": "R-001"
  },
  "result_summary": {},
  "error": null,
  "started_at": "2026-07-16T08:34:00+00:00",
  "completed_at": null
}
```

---

### 13. 列出编排运行

```
GET /api/v2/runtime/ontologies/{ontology_id}/orchestration-runs?agent_key=threat_response_agent_v1&status=running&limit=50
```

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| agent_key | string | query | (可选) agent/workflow 过滤 |
| status | string | query | (可选) 状态过滤 |
| limit | int | query | 1-200，默认 50 |

**输出示例:**
```json
{
  "runs": [
    {
      "id": "orch_run_001",
      "ontology_id": "ont_air_defense_001",
      "external_run_id": "agent_orch_20260716_001",
      "agent_key": "threat_response_agent_v1",
      "status": "running",
      "input_context": {
        "trigger": "new_target_detected",
        "target_code": "M-003",
        "target_type": "ballistic_missile",
        "detected_by": "R-001"
      },
      "result_summary": {},
      "error": null,
      "started_at": "2026-07-16T08:34:00+00:00",
      "completed_at": null
    }
  ]
}
```

---

### 14. 获取单条编排运行

```
GET /api/v2/runtime/ontologies/{ontology_id}/orchestration-runs/{run_id}
```

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| run_id | string | path | 编排运行 ID |

**输出示例 (获取 `orch_run_001`):**
```json
{
  "id": "orch_run_001",
  "ontology_id": "ont_air_defense_001",
  "external_run_id": "agent_orch_20260716_001",
  "agent_key": "threat_response_agent_v1",
  "status": "running",
  "input_context": {
    "trigger": "new_target_detected",
    "target_code": "M-003",
    "target_type": "ballistic_missile",
    "detected_by": "R-001"
  },
  "result_summary": {},
  "error": null,
  "started_at": "2026-07-16T08:34:00+00:00",
  "completed_at": null
}
```

---

### 15. 完成编排运行

```
POST /api/v2/runtime/ontologies/{ontology_id}/orchestration-runs/{run_id}/complete
```

**说明:** 标记编排运行为完成/失败/取消。

**请求体 (OrchestrationRunCompleteRequest):**
| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| status | string | "completed" | completed / failed / cancelled |
| result_summary | dict | {} | 最终结果摘要 |
| error | string | null | 错误信息 |

**请求示例:**
```json
{
  "status": "completed",
  "result_summary": {
    "targets_processed": 1,
    "target_code": "M-003",
    "actions_taken": [
      { "action": "跟踪容量评估", "result": "matched" },
      { "action": "分配雷达持续跟踪", "result": "done", "run_id": "run_abc123" }
    ],
    "final_verdict": "已分配 R-002 持续跟踪 M-003"
  }
}
```

**输出示例:**
```json
{
  "id": "orch_run_001",
  "ontology_id": "ont_air_defense_001",
  "external_run_id": "agent_orch_20260716_001",
  "agent_key": "threat_response_agent_v1",
  "status": "completed",
  "input_context": {
    "trigger": "new_target_detected",
    "target_code": "M-003"
  },
  "result_summary": {
    "targets_processed": 1,
    "target_code": "M-003",
    "actions_taken": [
      { "action": "跟踪容量评估", "result": "matched" },
      { "action": "分配雷达持续跟踪", "result": "done", "run_id": "run_abc123" }
    ],
    "final_verdict": "已分配 R-002 持续跟踪 M-003"
  },
  "error": null,
  "started_at": "2026-07-16T08:34:00+00:00",
  "completed_at": "2026-07-16T08:35:30+00:00"
}
```

---

## 二、Manual Runtime Authoring API (`/api/v2/manual`)

**路由文件:** `backend/app/routers/v2/manual/__init__.py`
**用途:** 为 manual 本体提供 Field Binding 和 Link Binding 的 CRUD 管理。

---

### 1. 获取本体摘要

```
GET /api/v2/manual/ontologies/{ontology_id}/summary
```

**说明:** 获取 Manual 本体的概要统计（各类型数量）。

**输出示例:**
```json
{
  "data": {
    "id": "ont_air_defense_001",
    "name": "东部防空反导系统手动本体",
    "domain": "防空反导",
    "status": "active",
    "build_mode": "manual",
    "counts": {
      "object_types": 5,
      "object_instances": 28,
      "link_types": 4,
      "links": 45,
      "rules": 3,
      "actions": 2,
      "field_bindings": 22,
      "link_bindings": 4
    }
  }
}
```

---

### 2. 验证本体

```
POST /api/v2/manual/ontologies/{ontology_id}/validate
```

**说明:** 校验 manual 本体配置是否完整，返回警告列表。

**输出示例 (有警告):**
```json
{
  "data": {
    "valid": true,
    "warnings": [
      {
        "code": "NO_LINK_BINDINGS",
        "message": "No ontology relationships are bound to data relation tables yet."
      }
    ]
  }
}
```

**输出示例 (完全配置):**
```json
{
  "data": {
    "valid": true,
    "warnings": []
  }
}
```

---

### 3. Field Binding CRUD

#### 列出字段绑定
```
GET /api/v2/manual/ontologies/{ontology_id}/field-bindings?object_type_id=ot_radar_001
```

**说明:** 列出字段绑定，可按 object_type_id 过滤。

**输出示例:**
```json
{
  "data": [
    {
      "id": "fb_radar_status",
      "ontology_id": "ont_air_defense_001",
      "object_type_id": "ot_radar_001",
      "property_name": "status",
      "data_source_id": "ds_radar_runtime_001",
      "schema_name": "public",
      "table_name": "radar_runtime_status",
      "column_name": "status",
      "primary_key_column": "radar_code",
      "value_type": "string",
      "direction": "read",
      "transform_expression": "{\"pipeline\": [{\"op\": \"trim\"}, {\"op\": \"lower\"}]}",
      "is_required": false,
      "read_only": true,
      "created_at": "2026-07-15T10:00:00+00:00",
      "updated_at": "2026-07-15T10:00:00+00:00"
    },
    {
      "id": "fb_radar_capacity",
      "ontology_id": "ont_air_defense_001",
      "object_type_id": "ot_radar_001",
      "property_name": "max_track_capacity",
      "data_source_id": "ds_radar_runtime_001",
      "schema_name": "public",
      "table_name": "radar_runtime_status",
      "column_name": "max_track_capacity",
      "primary_key_column": "radar_code",
      "value_type": "number",
      "direction": "read",
      "transform_expression": null,
      "is_required": false,
      "read_only": true,
      "created_at": "2026-07-15T10:00:00+00:00",
      "updated_at": "2026-07-15T10:00:00+00:00"
    }
  ]
}
```

#### 创建字段绑定
```
POST /api/v2/manual/ontologies/{ontology_id}/field-bindings
```

**请求体 (FieldBindingCreate):**
| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| object_type_id | string | - | ObjectType ID |
| property_name | string | - | 属性名 |
| data_source_id | string | null | 数据源 ID |
| schema_name | string | null | 数据库 schema |
| table_name | string | - | 表名 |
| column_name | string | - | 列名 |
| primary_key_column | string | null | 主键列名 |
| value_type | string | "string" | string / number / boolean |
| direction | string | "read" | read / write |
| transform_expression | string | null | 转换表达式 JSON |
| is_required | bool | false | 是否必需 |
| read_only | bool | true | 是否只读 |

**请求示例:**
```json
{
  "object_type_id": "ot_radar_001",
  "property_name": "loc",
  "data_source_id": "ds_radar_runtime_001",
  "schema_name": "public",
  "table_name": "radar_runtime_status",
  "column_name": "loc",
  "primary_key_column": "radar_code",
  "value_type": "string",
  "direction": "read",
  "is_required": false,
  "read_only": true
}
```

**输出:** 同上单条 field binding 对象，status_code 201

#### 更新字段绑定
```
PUT /api/v2/manual/ontologies/{ontology_id}/field-bindings/{binding_id}
```

**请求体:** FieldBindingUpdate（所有字段可选）

**请求示例 (修改 transform):**
```json
{
  "transform_expression": "{\"pipeline\": [{\"op\": \"trim\"}, {\"op\": \"upper\"}]}"
}
```

#### 删除字段绑定
```
DELETE /api/v2/manual/ontologies/{ontology_id}/field-bindings/{binding_id}
```
**状态码:** 204

---

### 4. Link Binding CRUD

#### 列出链接绑定
```
GET /api/v2/manual/ontologies/{ontology_id}/link-bindings?link_type_id=lt_tracks_001
```

**输出示例:**
```json
{
  "data": [
    {
      "id": "lb_tracks_radar_target",
      "ontology_id": "ont_air_defense_001",
      "link_type_id": "lt_tracks_001",
      "data_source_id": "ds_radar_links_001",
      "schema_name": "public",
      "table_name": "ad_radar_target_links",
      "source_object_type_id": "ot_radar_001",
      "source_key_column": "radar_code",
      "target_object_type_id": "ot_target_001",
      "target_key_column": "target_code",
      "direction": "out",
      "relation_filters": {
        "relation_type": "TRACKS",
        "status": "active"
      },
      "property_bindings": {
        "status": "status",
        "started_at": "started_at",
        "confidence": "confidence"
      },
      "transform_expression": null,
      "is_active": true,
      "created_at": "2026-07-15T10:00:00+00:00",
      "updated_at": "2026-07-15T10:00:00+00:00"
    }
  ]
}
```

#### 创建链接绑定
```
POST /api/v2/manual/ontologies/{ontology_id}/link-bindings
```

**请求体 (LinkBindingCreate):**
| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| link_type_id | string | - | 关系类型 ID |
| data_source_id | string | null | 数据源 ID |
| schema_name | string | null | 数据库 schema |
| table_name | string | - | 关系表名 |
| source_object_type_id | string | - | 源 ObjectType ID |
| source_key_column | string | - | 源 key 列名 |
| target_object_type_id | string | - | 目标 ObjectType ID |
| target_key_column | string | - | 目标 key 列名 |
| direction | string | "out" | out / in |
| relation_filters | dict | {} | 额外过滤条件，如 `{"status": "active"}` |
| property_bindings | dict | {} | 关系属性映射，如 `{"confidence": "confidence"}` |
| transform_expression | string | null | 转换表达式 |
| is_active | bool | true | 是否启用 |

**请求示例:**
```json
{
  "link_type_id": "lt_locks_001",
  "data_source_id": "ds_radar_links_001",
  "schema_name": "public",
  "table_name": "ad_radar_target_links",
  "source_object_type_id": "ot_radar_001",
  "source_key_column": "radar_code",
  "target_object_type_id": "ot_target_001",
  "target_key_column": "target_code",
  "direction": "out",
  "relation_filters": {
    "relation_type": "LOCKS",
    "status": "active"
  },
  "property_bindings": {
    "status": "status",
    "started_at": "started_at",
    "confidence": "confidence"
  },
  "is_active": true
}
```

#### 更新链接绑定
```
PUT /api/v2/manual/ontologies/{ontology_id}/link-bindings/{binding_id}
```
**请求体:** LinkBindingUpdate（所有字段可选）

#### 删除链接绑定
```
DELETE /api/v2/manual/ontologies/{ontology_id}/link-bindings/{binding_id}
```
**状态码:** 204

---

## 关键设计约束

1. **仅支持 `build_mode=manual` 的本体**, 其他模式返回 409
2. **Type Key 解析优先级**: `id` → `name_en` → `name_cn`（三选一匹配）
3. **Object Key 解析**: 通过 FieldBinding 的 `primary_key_column` 确定业务主键
4. **Rule 执行**: Python sandbox 执行 `check(context)` 函数，返回 `{"passed": bool, ...}`
5. **Action 执行**: Python sandbox 执行 `execute(context)` 函数，返回 `{"status": "...", ...}`
6. **幂等性**: 通过 `idempotency_key` 实现，同一 key 重复执行直接返回上次结果
7. **编排运行**: 用于关联一组 Action 执行，便于 Agent 工作流追踪
