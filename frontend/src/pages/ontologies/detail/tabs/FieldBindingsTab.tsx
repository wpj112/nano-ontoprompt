import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Columns3, Database, Link2, Plus, RefreshCw, Save, Table2, Trash2 } from 'lucide-react'
import { ontologyApi } from '@/api/ontologies'
import type { ObjectType } from '@/types/ontology'
import TransformEditor from '@/components/TransformEditor'

interface BindingForm {
  object_type_id: string
  property_name: string
  data_source_id: string
  schema_name: string
  table_name: string
  column_name: string
  primary_key_column: string
  value_type: string
  direction: string
  transform_expression: string
  is_required: boolean
  read_only: boolean
}

const emptyForm: BindingForm = {
  object_type_id: '',
  property_name: '',
  data_source_id: '',
  schema_name: '',
  table_name: '',
  column_name: '',
  primary_key_column: '',
  value_type: 'string',
  direction: 'read',
  transform_expression: '',
  is_required: false,
  read_only: true,
}

export default function FieldBindingsTab({ ontologyId }: { ontologyId: string }) {
  const qc = useQueryClient()
  const [form, setForm] = useState<BindingForm>(emptyForm)
  const [editId, setEditId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [sourceMsg, setSourceMsg] = useState('')
  const [sourceTables, setSourceTables] = useState<string[]>([])
  const [sourceColumns, setSourceColumns] = useState<Array<{ name: string; type: string }>>([])
  const [loadingTables, setLoadingTables] = useState(false)
  const [loadingColumns, setLoadingColumns] = useState(false)
  const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set())
  const [batchProgress, setBatchProgress] = useState('')

  const { data: types = [] } = useQuery({
    queryKey: ['object-types', ontologyId],
    queryFn: () => ontologyApi.listObjectTypes(ontologyId) as Promise<ObjectType[]>,
  })
  const { data: sources = [] } = useQuery({
    queryKey: ['data-sources', ontologyId],
    queryFn: () => ontologyApi.listDataSources(ontologyId) as Promise<any[]>,
  })
  const { data: bindings = [] } = useQuery({
    queryKey: ['field-bindings', ontologyId],
    queryFn: () => ontologyApi.listFieldBindings(ontologyId).then((r: any) => Array.isArray(r) ? r : r?.data || []),
  })

  const selectedType = (types as ObjectType[]).find(t => t.id === form.object_type_id)
  const propertyOptions = useMemo(() => Object.keys(selectedType?.property_schema || {}), [selectedType])
  const selectedSource = (sources as any[]).find(s => s.id === form.data_source_id)
  const existingBindings = (bindings as any[]) || []

  useEffect(() => {
    if (!form.data_source_id) {
      setSourceTables([])
      setSourceColumns([])
      return
    }
    loadTables(form.data_source_id, form.schema_name)
  }, [form.data_source_id])

  useEffect(() => {
    if (!form.data_source_id || !form.table_name) {
      setSourceColumns([])
      return
    }
    loadColumns(form.data_source_id, form.table_name, form.schema_name)
  }, [form.data_source_id, form.table_name])

  const saveMut = useMutation({
    mutationFn: (payload: any) => editId
      ? ontologyApi.updateFieldBinding(ontologyId, editId, payload)
      : ontologyApi.createFieldBinding(ontologyId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['field-bindings', ontologyId] })
      setForm(emptyForm)
      setEditId(null)
      setError('')
      setSelectedColumns(new Set())
    },
    onError: (e: any) => setError(String(e?.detail || e?.message || e)),
  })

  const batchSaveMut = useMutation({
    mutationFn: async (columns: string[]) => {
      const results: { column: string; ok: boolean; error?: string }[] = []
      for (const col of columns) {
        try {
          const colInfo = sourceColumns.find(c => c.name === col)
          const t = colInfo?.type?.toLowerCase() || ''
          const inferredType = t.includes('int') || t.includes('float') || t.includes('double') || t.includes('numeric') || t.includes('decimal') ? 'number' : t.includes('bool') ? 'boolean' : t.includes('date') || t.includes('time') ? 'datetime' : 'string'
          await ontologyApi.createFieldBinding(ontologyId, {
            object_type_id: form.object_type_id,
            property_name: col,
            data_source_id: form.data_source_id || null,
            schema_name: form.schema_name || null,
            table_name: form.table_name,
            column_name: col,
            primary_key_column: form.primary_key_column || null,
            value_type: inferredType,
            direction: form.direction,
            transform_expression: form.transform_expression || null,
            is_required: form.is_required,
            read_only: form.read_only,
          })
          results.push({ column: col, ok: true })
        } catch (e: any) {
          results.push({ column: col, ok: false, error: String(e?.detail || e?.message || e) })
        }
      }
      return results
    },
    onSuccess: (results) => {
      const ok = results.filter(r => r.ok).length
      const fail = results.filter(r => !r.ok).length
      const failNames = results.filter(r => !r.ok).map(r => r.column)
      setBatchProgress(`完成：成功 ${ok} 个${fail > 0 ? `，失败 ${fail} 个（${failNames.join(', ')}）` : ''}`)
      qc.invalidateQueries({ queryKey: ['field-bindings', ontologyId] })
      setSelectedColumns(new Set())
    },
    onError: (e: any) => setError(String(e?.detail || e?.message || e)),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => ontologyApi.deleteFieldBinding(ontologyId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['field-bindings', ontologyId] }),
  })

  function update(patch: Partial<BindingForm>) {
    setForm(prev => ({ ...prev, ...patch }))
  }

  async function loadTables(sourceId = form.data_source_id, schemaName = form.schema_name) {
    if (!sourceId) return
    setLoadingTables(true)
    setSourceMsg('')
    try {
      const res: any = await ontologyApi.listDataSourceTables(ontologyId, sourceId, schemaName || undefined)
      const payload = res?.data || res
      setSourceTables(payload?.tables || [])
    } catch (e: any) {
      setSourceMsg(String(e?.detail || e?.message || e))
      setSourceTables([])
    } finally {
      setLoadingTables(false)
    }
  }

  async function loadColumns(sourceId = form.data_source_id, tableName = form.table_name, schemaName = form.schema_name) {
    if (!sourceId || !tableName) return
    setLoadingColumns(true)
    setSourceMsg('')
    try {
      const res: any = await ontologyApi.listDataSourceColumns(ontologyId, sourceId, tableName, schemaName || undefined)
      const payload = res?.data || res
      setSourceColumns(payload?.columns || [])
    } catch (e: any) {
      setSourceMsg(String(e?.detail || e?.message || e))
      setSourceColumns([])
    } finally {
      setLoadingColumns(false)
    }
  }

  async function testSelectedSource() {
    if (!form.data_source_id) return
    setSourceMsg('')
    try {
      const res: any = await ontologyApi.testDataSource(ontologyId, form.data_source_id)
      setSourceMsg(res?.message || JSON.stringify(res))
    } catch (e: any) {
      setSourceMsg(String(e?.detail || e?.message || e))
    }
  }

  function startEdit(binding: any) {
    setEditId(binding.id)
    setForm({
      object_type_id: binding.object_type_id || '',
      property_name: binding.property_name || '',
      data_source_id: binding.data_source_id || '',
      schema_name: binding.schema_name || '',
      table_name: binding.table_name || '',
      column_name: binding.column_name || '',
      primary_key_column: binding.primary_key_column || '',
      value_type: binding.value_type || 'string',
      direction: binding.direction || 'read',
      transform_expression: binding.transform_expression || '',
      is_required: !!binding.is_required,
      read_only: binding.read_only !== false,
    })
    setSelectedColumns(new Set(binding.column_name ? [binding.column_name] : []))
  }

  function save() {
    if (!form.object_type_id || !form.table_name) {
      setError('请选择本体类型，并填写表名。')
      return
    }
    if (editId) {
      saveMut.mutate({
        ...form,
        data_source_id: form.data_source_id || null,
        schema_name: form.schema_name || null,
        primary_key_column: form.primary_key_column || null,
        transform_expression: form.transform_expression || null,
      })
    } else {
      if (selectedColumns.size === 0) {
        setError('请至少选择一列。')
        return
      }
      batchSaveMut.mutate([...selectedColumns])
    }
  }

  function toggleColumn(colName: string) {
    setSelectedColumns(prev => {
      const next = new Set(prev)
      next.has(colName) ? next.delete(colName) : next.add(colName)
      return next
    })
  }

  function resetForm() {
    setForm(emptyForm)
    setEditId(null)
    setError('')
    setSelectedColumns(new Set())
    setBatchProgress('')
    setSourceColumns([])
    setSourceTables([])
  }

  function typeName(typeId: string) {
    return (types as ObjectType[]).find(t => t.id === typeId)?.name_cn || typeId.slice(0, 8)
  }

  function sourceName(sourceId?: string) {
    if (!sourceId) return '未指定数据源'
    return (sources as any[]).find(s => s.id === sourceId)?.name || sourceId.slice(0, 8)
  }

  const alreadyBoundColumns = useMemo(() => {
    const set = new Set<string>()
    existingBindings.forEach((b: any) => {
      if (editId) return
      if (b.object_type_id === form.object_type_id && b.table_name === form.table_name) {
        set.add(b.column_name)
      }
    })
    return set
  }, [existingBindings, form.object_type_id, form.table_name, editId])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">字段绑定</h3>
          <p className="text-sm text-gray-500 mt-0.5">将本体属性映射到外部数据库表字段，供 runtime API 读取和执行规则动作。</p>
        </div>
        <button onClick={resetForm} className="px-3 py-1.5 border rounded-lg text-xs flex items-center gap-1 text-gray-600 hover:bg-gray-50">
          <Plus size={13} /> {editId ? '取消编辑' : '新建绑定'}
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[420px_1fr] gap-5">
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-800">
            <Link2 size={15} /> {editId ? '编辑绑定' : '新建绑定（选择多列可一次创建多个）'}
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">本体类型</label>
              <select value={form.object_type_id} onChange={e => {
                update({ object_type_id: e.target.value, property_name: '' })
                setSelectedColumns(new Set())
              }} className="w-full border rounded-lg px-3 py-2 text-sm">
                <option value="">选择 ObjectType</option>
                {(types as ObjectType[]).map(t => <option key={t.id} value={t.id}>{t.name_cn}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">本体属性</label>
              <select value={form.property_name} onChange={e => update({ property_name: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm" disabled={!form.object_type_id}>
                <option value="">选择 property_schema 字段</option>
                {propertyOptions.map(name => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">数据源</label>
              <div className="flex gap-2">
                <select value={form.data_source_id} onChange={e => {
                  const source = (sources as any[]).find(s => s.id === e.target.value)
                  update({ data_source_id: e.target.value, table_name: source?.registered_table || '' })
                  setSelectedColumns(new Set())
                }} className="min-w-0 flex-1 border rounded-lg px-3 py-2 text-sm">
                  <option value="">不指定数据源</option>
                  {(sources as any[]).map(s => <option key={s.id} value={s.id}>{s.name}{s.registered_table ? ` · ${s.registered_table}` : ''}</option>)}
                </select>
                <button type="button" onClick={testSelectedSource} disabled={!form.data_source_id} className="px-3 py-2 border rounded-lg text-xs text-gray-600 disabled:opacity-40">重测</button>
              </div>
              {selectedSource && <p className="text-[10px] text-gray-400 mt-1">{selectedSource.db_config?.db_type || 'db'}://{selectedSource.db_config?.host || 'host'}/{selectedSource.db_config?.database || 'database'}</p>}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Schema</label>
                <input value={form.schema_name} onChange={e => update({ schema_name: e.target.value })} onBlur={() => form.data_source_id && loadTables(form.data_source_id, form.schema_name)} placeholder="public" className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">表名</label>
                <div className="flex gap-2">
                  {form.data_source_id && sourceTables.length > 0 ? (
                    <select value={form.table_name} onChange={e => {
                      update({ table_name: e.target.value })
                      setSelectedColumns(new Set())
                    }} className="min-w-0 flex-1 border rounded-lg px-3 py-2 text-sm">
                      <option value="">选择表</option>
                      {sourceTables.map(table => <option key={table} value={table}>{table}</option>)}
                    </select>
                  ) : (
                    <input value={form.table_name} onChange={e => update({ table_name: e.target.value })} placeholder="suppliers" className="min-w-0 flex-1 border rounded-lg px-3 py-2 text-sm" />
                  )}
                  <button type="button" onClick={() => loadTables()} disabled={!form.data_source_id || loadingTables} className="px-2.5 py-2 border rounded-lg text-gray-500 disabled:opacity-40" title="刷新表列表">
                    {loadingTables ? <RefreshCw size={13} className="animate-spin" /> : <Table2 size={13} />}
                  </button>
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">
                {editId ? '列名' : `选择列（${selectedColumns.size}/${sourceColumns.length} 已选）`}
                {!editId && alreadyBoundColumns.size > 0 && <span className="text-amber-600 ml-2">（已绑定的列灰色显示）</span>}
              </label>
              {editId ? (
                // 编辑模式：单列选择
                <div className="flex gap-2">
                  {form.data_source_id && sourceColumns.length > 0 ? (
                    <select value={form.column_name} onChange={e => {
                      const col = sourceColumns.find(c => c.name === e.target.value)
                      const t = col?.type?.toLowerCase() || ''
                      update({ column_name: e.target.value, value_type: t.includes('int') || t.includes('float') || t.includes('double') || t.includes('numeric') || t.includes('decimal') ? 'number' : t.includes('bool') ? 'boolean' : t.includes('date') || t.includes('time') ? 'datetime' : form.value_type })
                    }} className="min-w-0 flex-1 border rounded-lg px-3 py-2 text-sm">
                      <option value="">选择列</option>
                      {sourceColumns.map(col => <option key={col.name} value={col.name}>{col.name} · {col.type}</option>)}
                    </select>
                  ) : (
                    <input value={form.column_name} onChange={e => update({ column_name: e.target.value })} placeholder="credit_level" className="min-w-0 flex-1 border rounded-lg px-3 py-2 text-sm" />
                  )}
                  <button type="button" onClick={() => loadColumns()} disabled={!form.data_source_id || !form.table_name || loadingColumns} className="px-2.5 py-2 border rounded-lg text-gray-500 disabled:opacity-40" title="刷新列列表">
                    {loadingColumns ? <RefreshCw size={13} className="animate-spin" /> : <Columns3 size={13} />}
                  </button>
                </div>
              ) : sourceColumns.length > 0 ? (
                <div className="border rounded-lg divide-y max-h-48 overflow-y-auto">
                  {sourceColumns.map(col => {
                    const alreadyBound = alreadyBoundColumns.has(col.name)
                    return (
                      <label key={col.name}
                        className={`flex items-center gap-2 px-3 py-2 text-sm cursor-pointer transition-colors ${alreadyBound ? 'bg-gray-50 text-gray-400' : selectedColumns.has(col.name) ? 'bg-blue-50' : 'hover:bg-gray-50'}`}>
                        <input type="checkbox" checked={selectedColumns.has(col.name)} disabled={alreadyBound}
                          onChange={() => toggleColumn(col.name)} className="rounded" />
                        <span className="font-mono">{col.name}</span>
                        <span className="text-xs text-gray-400 ml-auto">{col.type}</span>
                        {alreadyBound && <span className="text-xs text-amber-500 ml-1">已绑定</span>}
                      </label>
                    )
                  })}
                </div>
              ) : (
                <p className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-3 text-center">
                  {!form.data_source_id ? '请先选择数据源' : !form.table_name ? '请先选择表' : '点击刷新加载列列表'}
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">主键列</label>
                {form.data_source_id && sourceColumns.length > 0 ? (
                  <select value={form.primary_key_column} onChange={e => update({ primary_key_column: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm">
                    <option value="">选择主键列</option>
                    {sourceColumns.map(col => <option key={col.name} value={col.name}>{col.name}</option>)}
                  </select>
                ) : (
                  <input value={form.primary_key_column} onChange={e => update({ primary_key_column: e.target.value })} placeholder="id" className="w-full border rounded-lg px-3 py-2 text-sm" />
                )}
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">方向</label>
                <select value={form.direction} onChange={e => update({ direction: e.target.value, read_only: e.target.value === 'read' })} className="w-full border rounded-lg px-3 py-2 text-sm">
                  <option value="read">read</option>
                  <option value="write">write</option>
                  <option value="read_write">read_write</option>
                </select>
              </div>
            </div>

            <div>
              <TransformEditor
                value={form.transform_expression}
                onChange={(json: string) => update({ transform_expression: json })}
                sourceColumns={sourceColumns}
                propertySchemaKeys={propertyOptions}
              />
            </div>

            <div className="flex items-center gap-4 text-xs text-gray-600">
              <label className="flex items-center gap-1"><input type="checkbox" checked={form.is_required} onChange={e => update({ is_required: e.target.checked })} /> 必填</label>
              <label className="flex items-center gap-1"><input type="checkbox" checked={form.read_only} onChange={e => update({ read_only: e.target.checked })} /> 只读</label>
            </div>
          </div>

          {sourceMsg && <p className="text-xs text-gray-500 bg-gray-50 border rounded-lg px-3 py-2">{sourceMsg}</p>}
          {error && <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>}
          {batchProgress && <p className="text-xs text-green-600 bg-green-50 border border-green-100 rounded-lg px-3 py-2">{batchProgress}</p>}

          <button onClick={save} disabled={saveMut.isPending || batchSaveMut.isPending} className="w-full px-4 py-2 bg-black text-white rounded-lg text-sm flex items-center justify-center gap-2 disabled:opacity-40">
            {(saveMut.isPending || batchSaveMut.isPending) ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
            {editId ? '保存修改' : `创建绑定 (${selectedColumns.size || ''}列)`}
          </button>
        </div>

        <div className="bg-white border rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b flex items-center gap-2 text-sm font-medium text-gray-800">
            <Database size={15} /> 已绑定字段 ({(bindings as any[]).length})
          </div>
          {(bindings as any[]).length === 0 ? (
            <div className="px-5 py-10 text-center text-sm text-gray-400">暂无字段绑定</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b text-xs text-gray-500">
                  <tr>
                    <th className="px-4 py-2 text-left">本体属性</th>
                    <th className="px-4 py-2 text-left">数据源</th>
                    <th className="px-4 py-2 text-left">数据库列</th>
                    <th className="px-4 py-2 text-left">方向</th>
                    <th className="px-4 py-2 text-left">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {(bindings as any[]).map(binding => (
                    <tr key={binding.id} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-2">
                        <p className="font-medium text-gray-800">{typeName(binding.object_type_id)}</p>
                        <p className="text-xs text-gray-500 font-mono">{binding.property_name}</p>
                      </td>
                      <td className="px-4 py-2 text-gray-600">{sourceName(binding.data_source_id)}</td>
                      <td className="px-4 py-2 font-mono text-xs text-gray-600">
                        {[binding.schema_name, binding.table_name, binding.column_name].filter(Boolean).join('.')}
                        {binding.primary_key_column && <span className="text-gray-400"> · pk:{binding.primary_key_column}</span>}
                      </td>
                      <td className="px-4 py-2"><span className="px-1.5 py-0.5 rounded border text-xs text-gray-600">{binding.direction}</span></td>
                      <td className="px-4 py-2">
                        <div className="flex gap-2">
                          <button onClick={() => startEdit(binding)} className="text-blue-600 hover:underline text-xs">编辑</button>
                          <button onClick={() => { if (confirm('删除此字段绑定？')) deleteMut.mutate(binding.id) }} className="text-red-600 hover:text-red-700"><Trash2 size={13} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
