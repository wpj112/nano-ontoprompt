"""
Runtime API — Agent Orchestration Demo
=======================================
军事态势感知场景：智能体通过本体语义 API 完成从探测到拦截的完整链路

Ontology: 防空态势感知
Types:   雷达站(RadarStation), 导弹发射车(MissileLauncher), 威胁目标(Threat), 指挥中心(CommandCenter)
Relations: DETECTS(雷达→目标), ASSIGNED_TO(发射车→指挥中心), TARGETS(发射车→目标)
Rules:   威胁等级评估, 战备状态检查
Actions: 锁定威胁, 发射拦截弹

授权: Authorization: Bearer <token>
Base URL: /api/v2/runtime/ontologies/{ontology_id}
"""

# ═══════════════════════════════════════════════════════════
# Step 1: METADATA — 能力发现
# ═══════════════════════════════════════════════════════════
"""
#!/bin/bash
# 智能体启动时第一步：发现本体中有什么

curl -X GET "http://localhost:18020/api/v2/runtime/ontologies/{ontology_id}/metadata" \
  -H "Authorization: Bearer <token>"

# 返回:
{
  "ontology": {
    "id": "8786faf6-...",
    "name": "防空态势感知 a3a4",
    "domain": "军事",
    "version": "v0.1"
  },
  "object_types": [
    {
      "key": "Threat",
      "label": "威胁目标",
      "id": "2491e33f-...",
      "properties": [
        {"name": "名称", "type": "string"},
        {"name": "威胁类型", "type": "string"},
        {"name": "速度", "type": "number", "unit": "km/h"},
        {"name": "高度", "type": "number", "unit": "m"},
        {"name": "航向", "type": "number", "unit": "°"},
        {"name": "距离", "type": "number", "unit": "km"},
        {"name": "状态", "type": "string"},
        {"name": "探测来源", "type": "string"}
      ]
    },
    ... (RadarStation, MissileLauncher, CommandCenter)
  ],
  "relations": [
    {"key": "DETECTS", "label": "探测"},
    {"key": "ASSIGNED_TO", "label": "隶属"},
    {"key": "TARGETS", "label": "瞄准"}
  ],
  "rules": [
    {"key": "威胁等级评估", "id": "6534e79b-...", "target_type_id": "b09732b9-..."},
    {"key": "战备状态检查", "id": "ae58e523-...", "target_type_id": "753c1216-..."}
  ],
  "actions": [
    {"key": "锁定威胁", "id": "fe5a1c7c-...", "description": null},
    {"key": "发射拦截弹", "id": "d3b2a1c8-...", "description": null}
  ]
}

# 智能体决策依据:
# - 能查 4 类对象: 雷达站, 发射车, 威胁, 指挥中心
# - 有 3 种关系: DETECTS, ASSIGNED_TO, TARGETS
# - 可评估 2 条规则
# - 可执行 2 种动作
"""


# ═══════════════════════════════════════════════════════════
# Step 2: OBJECT READ — 读取单个目标数据（含实时 DB 查询）
# ═══════════════════════════════════════════════════════════
"""
curl -X GET "http://localhost:18020/api/v2/runtime/ontologies/{id}/objects/Threat/T-004" \
  -H "Authorization: Bearer <token>"

# 返回:
{
  "object": {
    "id": "T-004",
    "type_key": "Threat",
    "type_label": "威胁目标",
    "properties": {
      "名称": "不明飞行器 D",
      "威胁类型": "fighter",
      "速度": 1500,           # ← 从 threats 表实时读取
      "高度": 1000,            # ← 字段绑定: SELECT altitude FROM threats WHERE code='T-004'
      "航向": 315,
      "距离": 80,              # ← 80km —— 极近！
      "状态": "warning",
      "探测来源": "R-003"
    },
    "_sources": {
      "速度": {"data_source_id": "...", "table": "threats", "column": "speed", "pk_column": "code"},
      "高度": {"data_source_id": "...", "table": "threats", "column": "altitude", "pk_column": "code"},
      ...
    }
  }
}

# 智能体理解:
# - T-004 是战斗机，速度 1500 km/h，高度 1000m，距离仅 80km
# - 数据来自 threats 表的实时查询
# - 不关心表结构、SQL、字段绑定 —— 只拿本体属性
"""


# ═══════════════════════════════════════════════════════════
# Step 3: LIST OBJECTS — 轮询所有威胁
# ═══════════════════════════════════════════════════════════
"""
curl -X GET "http://localhost:18020/api/v2/runtime/ontologies/{id}/objects/Threat" \
  -H "Authorization: Bearer <token>"

# 返回 {items: [T-001, T-002, T-003, T-004, T-005], count: 5}
# 智能体拿到所有威胁列表，逐个评估
"""


# ═══════════════════════════════════════════════════════════
# Step 4: RULE EVALUATION — 评估威胁等级
# ═══════════════════════════════════════════════════════════
"""
curl -X POST "http://localhost:18020/api/v2/runtime/ontologies/{id}/rules/evaluate" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_key": "威胁等级评估",
    "subject_type_key": "Threat",
    "subject_id": "T-004"
  }'

# 返回:
{
  "matched": true,
  "evaluations": [
    {
      "rule_key": "威胁等级评估",
      "matched": true,
      "severity": "critical",
      "message": "威胁评分: 11 (critical威胁)",
      "details": {
        "threat_score": 11,
        "reasons": ["高速目标 (>1000km/h)", "超低空飞行 (<2000m)", "极近距离 (80km)", "战斗机目标"],
        "suggest_engage": true
      }
    }
  ],
  "suggested_actions": ["锁定威胁", "发射拦截弹"]
}

# 智能体决策:
# - threat_score=11 → critical → 必须交战
# - 原因: 高速 + 超低空 + 极近 + 战斗机
# - 建议执行: 锁定威胁 → 发射拦截弹
"""


# ═══════════════════════════════════════════════════════════
# Step 5: CHECK LAUNCHER READINESS — 找到可用的发射车
# ═══════════════════════════════════════════════════════════
"""
curl -X POST "http://localhost:18020/api/v2/runtime/ontologies/{id}/rules/evaluate" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_key": "战备状态检查",
    "subject_type_key": "MissileLauncher",
    "subject_id": "M-001"
  }'

# 返回:
{
  "matched": true,
  "evaluations": [{
    "rule_key": "战备状态检查",
    "matched": true,
    "message": "发射车待命: missiles=8, status=standby",
    "details": {"missiles_available": 8, "can_engage": true}
  }]
}

# 智能体确认: M-001 可用，8枚备弹
"""


# ═══════════════════════════════════════════════════════════
# Step 6: WALK RELATIONS — 确认雷达覆盖
# ═══════════════════════════════════════════════════════════
"""
# 查询 T-004 被哪个雷达探测到
curl -X GET "http://localhost:18020/api/v2/runtime/ontologies/{id}/objects/Threat/T-004/relations?relation=DETECTS" \
  -H "Authorization: Bearer <token>"

# 目前返回空（DETECTS 关系在 T-004 实例上不存在，因为 Link 创建有 warning）
# 
# 但理想流程是:
# {
#   "relations": [{
#     "relation": "DETECTS",
#     "source_id": "<radar_instance_id>",
#     "target_id": "<T-004_id>",
#     "target_label": "西部防空雷达",
#     "target_type": "雷达站"
#   }]
# }
"""


# ═══════════════════════════════════════════════════════════
# Step 7: EXECUTE ACTION — 锁定威胁
# ═══════════════════════════════════════════════════════════
"""
curl -X POST "http://localhost:18020/api/v2/runtime/ontologies/{id}/actions/锁定威胁/execute" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "subject_type_key": "MissileLauncher",
    "subject_id": "M-001",
    "input": {"target_id": "T-004", "launcher_id": "M-001"},
    "dry_run": false
  }'

# 返回:
{
  "status": "done",
  "message": "已锁定威胁目标，拦截方案已生成",
  "target_locked": true,
  "target_id": "T-004",
  "launcher_id": "M-001",
  "intercept_plan": {
    "method": "动能拦截",
    "estimated_impact": "3分钟内",
    "probability": 0.85
  }
}

# 智能体: 锁定成功，拦截方案已生成
"""


# ═══════════════════════════════════════════════════════════
# Step 8: EXECUTE ACTION — 发射拦截弹
# ═══════════════════════════════════════════════════════════
"""
curl -X POST "http://localhost:18020/api/v2/runtime/ontologies/{id}/actions/发射拦截弹/execute" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "subject_type_key": "MissileLauncher",
    "subject_id": "M-001",
    "input": {"target_id": "T-004"},
    "dry_run": false
  }'

# 返回:
{
  "status": "done",
  "message": "拦截弹已发射",
  "missiles_remaining": 7,
  "engagement_id": "ENG-2026-001"
}
"""


# ═══════════════════════════════════════════════════════════
# 智能体编排总结
# ═══════════════════════════════════════════════════════════
"""
完整的 agent 决策流程:

  1. GET  /metadata                → 发现能力（类型/属性/规则/动作）
  2. GET  /objects/Threat          → 列出所有威胁
  3. GET  /objects/Threat/T-004    → 读取 T-004 实时属性
  4. POST /rules/evaluate          → 评估威胁等级 → critical
  5. POST /rules/evaluate          → 检查 M-001 战备 → ready
  6. GET  /objects/.../relations   → 确认雷达覆盖
  7. POST /actions/锁定威胁/execute → 锁定制导
  8. POST /actions/发射拦截弹/execute → 发射拦截

智能体不关心中间细节:
  - 不写 SQL
  - 不认识表名 (threats, launchers, radars)
  - 不处理 trim/upper/聚合
  - 不懂 exec() 沙箱
  - 不操作 Link/LinkType 表

只通过语义层:
  类型 → 对象 → 属性 → 关系 → 规则 → 动作
"""

# ═══════════════════════════════════════════════════════════
# API 契约总结
# ═══════════════════════════════════════════════════════════
"""
Endpoints:

# 能力发现
  GET  /metadata                                                → 本体 Schema
  GET  /types                                                   → 列出类型
  GET  /types/{type_key}                                       → 类型详情

# 对象访问
  GET  /objects/{type_key}                                      → 列出对象
  GET  /objects/{type_key}/{object_key}                         → 读对象 + 实时属性
  POST /objects/{type_key}/query                                → 查询过滤

# 关系遍历
  GET  /objects/{type_key}/{object_key}/relations               → 全部出链
  GET  /objects/{type_key}/{object_key}/relations?relation=X    → 按类型过滤

# 规则评估 (只读无副作用)
  POST /rules/evaluate                                          → 评估规则

# 动作执行 (可能有副作用)
  POST /actions/{action_key}/execute                            → 执行动作
"""
