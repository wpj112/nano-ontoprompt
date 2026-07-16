# Runtime API 接口文档

## 概述

Runtime API 是面向**第三方代理编排系统**的语义接口层，基于 `build_mode=manual` 的本体工作。
Agent 通过此 API 以业务语义（ObjectType / Object / Property / Relation / Rule / Action）操作本体，
无需接触底层数据库表、SQL 或 DataSource 连接串。

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
| ontology_id | string | path | 本体 ID |

**输出示例:**
```json
{
  "ontology": { "id": "...", "name": "...", "domain": "军事", "version": "1.0" },
  "object_types": [
    {
      "key": "Radar", "label": "雷达", "id": "...",
      "properties": [
        { "name": "frequency", "type": "number", "unit": "MHz", "bound": true }
      ]
    }
  ],
  "relations": [
    { "key": "DETECTS", "label": "探测", "source_type_id": "...", "target_type_id": "..." }
  ],
  "rules": [
    { "key": "高威胁目标", "id": "...", "description": "...", "target_type_id": "..." }
  ],
  "actions": [
    { "key": "告警", "id": "...", "description": "...", "linked_rule_id": "..." }
  ],
  "runtime_capabilities": {
    "field_bindings": 12,
    "link_bindings": 3,
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

**输出:** `{ "types": [ { "key": "Radar", "label": "雷达", "id": "...", "properties": [...] } ] }`

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

**输出:** `{ "key": "Radar", "label": "雷达", "id": "...", "properties": [...] }`

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
| type_key | string | path | ObjectType key |
| limit | int | query | 限制数量，默认 50，范围 1-500 |

**输出:** `{ "items": [ { "id": "...", "type_key": "Radar", "type_label": "雷达", "properties": {...}, "_sources": {...} } ], "count": N }`

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

**输出:** `{ "object": { "id": "object_key", "type_key": "Radar", "type_label": "雷达", "properties": {"frequency": 3500}, "_sources": {"frequency": {"data_source_id": "...", "table": "public.radars", "column": "freq_mhz", "pk_column": "id"}} } }`

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
```json
{
  "filter": { "risk_level": "high" },
  "sort": [ { "field": "frequency", "direction": "desc" } ],
  "limit": 20
}
```

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| filter | dict | {} | 属性过滤，值可为字面量或 `{op, value}` |
| sort | list[dict] | [] | 排序，`{field, direction}` |
| limit | int | 20 | 1-500 |

**支持的 filter op:** `eq`, `neq`, `contains`, `in`, `gt`, `gte`, `lt`, `lte`

**输出:** `{ "items": [...], "count": N }`

---

### 7. 获取对象关系

```
GET /api/v2/runtime/ontologies/{ontology_id}/objects/{type_key}/{object_key}/relations?relation=DETECTS
```

**说明:** 获取指定对象的所有**出向关系**。支持静态 Link（materialized）和动态 DB link binding。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| type_key | string | path | ObjectType key |
| object_key | string | path | 对象 key |
| relation | string | query | (可选) 按 link type 名称过滤 |

**输出:**
```json
{
  "relations": [
    {
      "relation": "DETECTS", "relation_label": "探测",
      "source_kind": "dynamic_binding",
      "source_key": "radar_001",
      "target_type": "目标", "target_type_key": "Target",
      "target_key": "target_001", "target_label": "target_001",
      "properties": {}, "confidence": 1.0
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
```json
{
  "rule_key": "高威胁目标",
  "subject_type_key": "Target",
  "subject_id": "target_001",
  "context": { "extra_info": "..." },
  "orchestration_run_id": "..."
}
```

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| rule_key | string | null | 特定规则名，省略则评估所有 |
| subject_type_key | string | null | ObjectType key |
| subject_id | string | null | 对象业务 key |
| orchestration_run_id | string | null | 可选编排运行 ID |
| context | dict | {} | 额外上下文 |

**输出:**
```json
{
  "matched": true,
  "evaluations": [
    {
      "rule_key": "高威胁目标", "rule_id": "...",
      "matched": true, "severity": "high",
      "message": "目标速度超过阈值",
      "details": { "speed": 800 }
    }
  ],
  "suggested_actions": [
    { "action_key": "告警", "action_id": "...", "description": "..." }
  ]
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

**输出:**
```json
{
  "status": "done",
  "run_id": "...",
  "action_key": "告警",
  "message": "...",
  "idempotency_key": "...",
  "orchestration_run_id": "..."
}
```

---

### 10. 列出动作执行记录

```
GET /api/v2/runtime/ontologies/{ontology_id}/runs?orchestration_run_id=xxx&limit=50
```

**说明:** 查看历史动作执行记录。

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| orchestration_run_id | string | query | (可选) 按编排运行过滤 |
| limit | int | query | 1-200，默认 50 |

**输出:** `{ "runs": [ { "id": "...", "action_key": "...", "status": "done", "started_at": "...", "completed_at": "...", "request_payload": {...}, "result_payload": {...}, "error": null } ] }`

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

**输出:** 同上单条 `run` 对象。

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

**输出:**
```json
{
  "id": "...", "ontology_id": "...", "external_run_id": "...",
  "agent_key": "...", "status": "running",
  "input_context": {}, "result_summary": {},
  "started_at": "...", "completed_at": null
}
```

---

### 13. 列出编排运行

```
GET /api/v2/runtime/ontologies/{ontology_id}/orchestration-runs?agent_key=xxx&status=running&limit=50
```

**输入参数:**
| 参数 | 类型 | 位置 | 说明 |
|------|------|------|------|
| ontology_id | string | path | 本体 ID |
| agent_key | string | query | (可选) agent/workflow 过滤 |
| status | string | query | (可选) 状态过滤 |
| limit | int | query | 1-200，默认 50 |

**输出:** `{ "runs": [ ... ] }`

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

**输出:** 单条编排运行对象。

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

**输出:** 更新后的编排运行对象。

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

**输出:** `{ "data": { "id": "...", "name": "...", "domain": "...", "status": "...", "build_mode": "manual", "counts": { "object_types": N, "object_instances": N, "link_types": N, "links": N, "rules": N, "actions": N, "field_bindings": N, "link_bindings": N } } }`

---

### 2. 验证本体

```
POST /api/v2/manual/ontologies/{ontology_id}/validate
```

**说明:** 校验 manual 本体配置是否完整，返回警告列表。

**输出:** `{ "data": { "valid": true, "warnings": [ { "code": "NO_OBJECT_TYPES", "message": "..." } ] } }`

---

### 3. Field Binding CRUD

#### 列出字段绑定
```
GET /api/v2/manual/ontologies/{ontology_id}/field-bindings?object_type_id=xxx
```
**说明:** 列出字段绑定，可按 object_type_id 过滤。

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
| value_type | string | "string" | 值类型 |
| direction | string | "read" | read / write |
| transform_expression | string | null | 转换表达式 |
| is_required | bool | false | 是否必需 |
| read_only | bool | true | 是否只读 |

#### 更新字段绑定
```
PUT /api/v2/manual/ontologies/{ontology_id}/field-bindings/{binding_id}
```
**请求体:** FieldBindingUpdate（所有字段可选）

#### 删除字段绑定
```
DELETE /api/v2/manual/ontologies/{ontology_id}/field-bindings/{binding_id}
```
**状态码:** 204

---

### 4. Link Binding CRUD

#### 列出链接绑定
```
GET /api/v2/manual/ontologies/{ontology_id}/link-bindings?link_type_id=xxx
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
| relation_filters | dict | {} | 额外过滤条件 |
| property_bindings | dict | {} | 关系属性映射 |
| transform_expression | string | null | 转换表达式 |
| is_active | bool | true | 是否启用 |

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
