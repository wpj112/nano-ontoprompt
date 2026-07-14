import { useState, useMemo } from 'react'
import { ChevronDown, ChevronRight, Plus, Trash2, Code, Wand2 } from 'lucide-react'

// ── Select mode definitions ──────────────────────────────

interface SelectMode {
  key: string
  label: string
  desc: string
  needsOp?: boolean
  needsOrderBy?: boolean
  hint?: string
}

const SELECT_MODES: SelectMode[] = [
  { key: 'value',    label: '直接取列',     desc: 'WHERE pk = key 取单列值（默认）' },
  { key: 'aggregate', label: '聚合取值',     desc: 'max / min / avg / sum',         needsOp: true },
  { key: 'latest',   label: '按时间取最近',  desc: 'ORDER BY time_col DESC LIMIT 1', needsOrderBy: true, hint: 'value_column 和 order_by 都需要填' },
  { key: 'earliest', label: '按时间取最早',  desc: 'ORDER BY time_col ASC LIMIT 1',  needsOrderBy: true, hint: 'value_column 和 order_by 都需要填' },
  { key: 'columns',  label: '多列组合',      desc: 'SELECT c1, c2 ... 返回 dict，配合 concat pipeline 使用' },
  { key: 'count',    label: '计数',          desc: 'SELECT COUNT(*) ...' },
]

const AGG_OPS = ['max', 'min', 'avg', 'sum', 'count']

// ── Pipeline op definitions ──────────────────────────────

interface PipeOp {
  key: string
  label: string
  params?: { name: string; label: string; type: string; placeholder?: string }[]
}

const PIPE_OPS: PipeOp[] = [
  { key: 'trim',       label: '去首尾空格' },
  { key: 'lower',      label: '转小写' },
  { key: 'upper',      label: '转大写' },
  { key: 'title',      label: '首字母大写' },
  { key: 'replace',    label: '替换',       params: [{ name: 'src', label: '查找', type: 'text' }, { name: 'dst', label: '替换为', type: 'text' }] },
  { key: 'substring',  label: '截取',       params: [{ name: 'start', label: '起始', type: 'number' }, { name: 'length', label: '长度(可选)', type: 'number' }] },
  { key: 'split',      label: '分割取第N项', params: [{ name: 'delimiter', label: '分隔符', type: 'text', placeholder: ',' }, { name: 'index', label: '索引(0开始)', type: 'number' }] },
  { key: 'join',       label: '拼接',       params: [{ name: 'delimiter', label: '分隔符', type: 'text', placeholder: ',' }] },
  { key: 'concat',     label: '模板拼接',   params: [{ name: 'template', label: '模板', type: 'text', placeholder: '前缀{value}后缀' }] },
  { key: 'default',    label: '空值默认',   params: [{ name: 'val', label: '默认值', type: 'text' }] },
  { key: 'regex_replace', label: '正则替换', params: [{ name: 'pattern', label: '正则', type: 'text' }, { name: 'repl', label: '替换为', type: 'text' }] },
  { key: 'to_number',  label: '转数字' },
  { key: 'to_string',  label: '转字符串' },
  { key: 'to_bool',    label: '转布尔' },
  { key: 'to_date',    label: '转日期',     params: [{ name: 'fmt', label: '格式', type: 'text', placeholder: '%Y-%m-%d' }] },
  { key: 'round',      label: '数字取整',   params: [{ name: 'digits', label: '小数位', type: 'number' }] },
]

// ── Types ────────────────────────────────────────────────

interface SelectConfig {
  mode?: string
  column?: string
  columns?: string[]
  value_column?: string
  order_by?: string
  op?: string
  limit?: number
}

interface PipelineStep {
  op: string
  [key: string]: any
}

interface TransformConfig {
  // eslint-disable-next-line @typescript-eslint/no-redundant-type-constituents
  version?: string | number
  select?: SelectConfig
  pipeline?: PipelineStep[]
}

// ── Props ────────────────────────────────────────────────

interface Props {
  value: string
  onChange: (json: string) => void
  sourceColumns: Array<{ name: string; type: string }>
  /** The ObjectType's property_schema keys (for informative hints) */
  propertySchemaKeys: string[]
}

// ── Helpers ──────────────────────────────────────────────

function parseConfig(raw: string): TransformConfig {
  try { return JSON.parse(raw) || {} } catch { return {} }
}

function buildJSON(cfg: TransformConfig): string {
  const out: any = {}
  if (cfg.select && cfg.select.mode && cfg.select.mode !== 'value') {
    const s: any = {}
    for (const [k, v] of Object.entries(cfg.select)) {
      if (v !== undefined && v !== '' && v !== null && (!Array.isArray(v) || v.length > 0)) {
        s[k] = v
      }
    }
    if (Object.keys(s).length > 0) out.select = s
  }
  if (cfg.pipeline && cfg.pipeline.length > 0) {
    out.pipeline = cfg.pipeline
  }
  return Object.keys(out).length > 0 ? JSON.stringify(out, null, 2) : ''
}

// ── Component ────────────────────────────────────────────

export default function TransformEditor({ value, onChange, sourceColumns, propertySchemaKeys }: Props) {
  const [rawMode, setRawMode] = useState(false)
  const [rawText, setRawText] = useState(value || '{}')
  const [expanded, setExpanded] = useState(true)

  const config = useMemo(() => parseConfig(value), [value])
  const select = config.select || {}
  const pipeline: PipelineStep[] = config.pipeline || []

  function updateConfig(patch: (cfg: TransformConfig) => TransformConfig) {
    const newCfg = patch(structuredClone(parseConfig(value)))
    onChange(buildJSON(newCfg))
  }

  function updateSelect(patch: Partial<SelectConfig>) {
    updateConfig(cfg => {
      cfg.select = { ...cfg.select, ...patch }
      if (cfg.select.mode === 'value' && !cfg.select.column && !cfg.select.columns) {
        delete (cfg as any).select
      }
      return cfg
    })
  }

  function updatePipeline(steps: PipelineStep[]) {
    updateConfig(cfg => { cfg.pipeline = steps; return cfg })
  }

  function addPipeStep() {
    updatePipeline([...pipeline, { op: 'trim' }])
  }

  function removePipeStep(index: number) {
    const next = pipeline.filter((_, i) => i !== index)
    updatePipeline(next)
  }

  function updatePipeStep(index: number, step: PipelineStep) {
    const next = pipeline.map((s, i) => i === index ? step : s)
    updatePipeline(next)
  }

  function toggleRawMode() {
    if (!rawMode) {
      setRawText(value || '{}')
    } else {
      try {
        const parsed = JSON.parse(rawText)
        onChange(JSON.stringify(parsed, null, 2))
      } catch {
        // keep old raw text
      }
    }
    setRawMode(!rawMode)
  }

  const selectedMode = SELECT_MODES.find(m => m.key === select.mode)
  const hasConfig = select.mode || pipeline.length > 0

  return (
    <div className="border rounded-lg">
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b">
        <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-black">
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <span className="font-medium">转换规则{hasConfig ? ' (已配置)' : ''}</span>
        </button>
        <button onClick={toggleRawMode}
          className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs ${rawMode ? 'bg-black text-white' : 'border text-gray-500 hover:bg-gray-100'}`}>
          <Code size={11} /> {rawMode ? '可视化' : '高级 JSON'}
        </button>
      </div>

      {expanded && (
        <div className="p-3 space-y-4">
          {rawMode ? (
            // Raw JSON mode
            <div>
              <textarea
                value={rawText}
                onChange={e => { setRawText(e.target.value); try { JSON.parse(e.target.value); onChange(e.target.value) } catch {} }}
                rows={10}
                placeholder='{"select": {...}, "pipeline": [...]}'
                className="w-full border rounded-lg px-3 py-2 text-xs font-mono"
              />
              <p className="text-[10px] text-gray-400 mt-1">编辑 JSON 后自动实时保存，格式错误时不会丢失数据</p>
            </div>
          ) : (
            <>
              {/* ── Select mode ── */}
              <div>
                <label className="block text-[10px] font-medium text-gray-500 uppercase mb-1">取值方式</label>
                <select
                  value={select.mode || 'value'}
                  onChange={e => updateSelect({ mode: e.target.value || 'value', op: undefined, order_by: undefined, value_column: undefined })}
                  className="w-full border rounded-lg px-2.5 py-1.5 text-xs"
                >
                  {SELECT_MODES.map(m => (
                    <option key={m.key} value={m.key}>{m.label} — {m.desc}</option>
                  ))}
                </select>

                {/* Aggregate params */}
                {selectedMode?.needsOp && (
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <div>
                      <label className="block text-[10px] text-gray-400 mb-0.5">聚合操作</label>
                      <select value={select.op || 'max'} onChange={e => updateSelect({ op: e.target.value })}
                        className="w-full border rounded px-2 py-1.5 text-xs">
                        {AGG_OPS.map(o => <option key={o} value={o}>{o.toUpperCase()}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] text-gray-400 mb-0.5">目标列</label>
                      <select value={select.column || ''}
                        onChange={e => updateSelect({ column: e.target.value })}
                        className="w-full border rounded px-2 py-1.5 text-xs">
                        <option value="">选列</option>
                        {sourceColumns.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                      </select>
                    </div>
                  </div>
                )}

                {/* Latest/earliest params */}
                {selectedMode?.needsOrderBy && (
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <div>
                      <label className="block text-[10px] text-gray-400 mb-0.5">取值列 (value_column)</label>
                      <select value={select.value_column || ''}
                        onChange={e => updateSelect({ value_column: e.target.value })}
                        className="w-full border rounded px-2 py-1.5 text-xs">
                        <option value="">选列</option>
                        {sourceColumns.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] text-gray-400 mb-0.5">排序列 (order_by)</label>
                      <select value={select.order_by || ''}
                        onChange={e => updateSelect({ order_by: e.target.value })}
                        className="w-full border rounded px-2 py-1.5 text-xs">
                        <option value="">选列</option>
                        {sourceColumns.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                      </select>
                    </div>
                  </div>
                )}
              </div>

              {/* ── Pipeline steps ── */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[10px] font-medium text-gray-500 uppercase">格式处理 (<span data-testid="pipeline-count">{pipeline.length}</span>)</label>
                  <button onClick={addPipeStep}
                    className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] border text-gray-500 hover:bg-gray-50">
                    <Plus size={10} /> 添加步骤
                  </button>
                </div>
                {pipeline.length === 0 ? (
                  <p className="text-[10px] text-gray-400 bg-gray-50 rounded px-2 py-2 text-center">无格式处理，直接返回原值</p>
                ) : (
                  <div className="space-y-1.5">
                    {pipeline.map((step, i) => {
                      const opDef = PIPE_OPS.find(o => o.key === step.op)
                      return (
                        <div key={i} className="flex items-start gap-1.5 bg-gray-50 rounded-lg p-2">
                          <span className="text-[10px] text-gray-400 font-mono mt-1.5 shrink-0">{i + 1}</span>
                          <div className="flex-1 space-y-1">
                            <select value={step.op}
                              onChange={e => {
                                const newOp = e.target.value
                                const params: any = { op: newOp }
                                // carry over compatible params
                                updatePipeStep(i, { op: newOp })
                              }}
                              className="w-full border rounded px-2 py-1 text-xs">
                              {PIPE_OPS.map(o => (
                                <option key={o.key} value={o.key}>{o.label}</option>
                              ))}
                            </select>
                            {opDef?.params?.map(p => (
                              <input key={p.name}
                                type={p.type === 'number' ? 'number' : 'text'}
                                value={step[p.name] || ''}
                                onChange={e => {
                                  const val = p.type === 'number' ? Number(e.target.value) || undefined : e.target.value
                                  updatePipeStep(i, { ...step, [p.name]: val || undefined })
                                }}
                                placeholder={p.placeholder || p.label}
                                className="w-full border rounded px-2 py-1 text-[10px]"
                              />
                            ))}
                          </div>
                          <button onClick={() => removePipeStep(i)} className="text-gray-300 hover:text-red-500 shrink-0 mt-1">
                            <Trash2 size={12} />
                          </button>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* ── JSON preview ── */}
              {hasConfig && (
                <details className="text-[10px]">
                  <summary className="text-gray-400 cursor-pointer hover:text-gray-600">JSON 预览</summary>
                  <pre className="mt-1 bg-gray-100 rounded p-2 overflow-x-auto text-[10px] font-mono text-gray-600">
                    {JSON.stringify(parseConfig(value), null, 2)}
                  </pre>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
