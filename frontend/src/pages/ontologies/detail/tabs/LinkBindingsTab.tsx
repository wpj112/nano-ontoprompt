import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { GitBranch, Plus, RefreshCw, Save, Table2, Trash2 } from 'lucide-react'
import { ontologyApi } from '@/api/ontologies'
import type { LinkTypeItem, ObjectType } from '@/types/ontology'

interface LinkBindingForm {
  link_type_id: string
  data_source_id: string
  schema_name: string
  table_name: string
  source_object_type_id: string
  source_key_column: string
  target_object_type_id: string
  target_key_column: string
  relation_filters: string
  property_bindings: string
  is_active: boolean
}

const emptyForm: LinkBindingForm = {
  link_type_id: '',
  data_source_id: '',
  schema_name: '',
  table_name: '',
  source_object_type_id: '',
  source_key_column: '',
  target_object_type_id: '',
  target_key_column: '',
  relation_filters: '{}',
  property_bindings: '{}',
  is_active: true,
}

function normalize(payload: any): any[] {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.data)) return payload.data
  return []
}

function parseJson(value: string, fallback: any) {
  if (!value.trim()) return fallback
  return JSON.parse(value)
}

export default function LinkBindingsTab({ ontologyId }: { ontologyId: string }) {
  const qc = useQueryClient()
  const [form, setForm] = useState<LinkBindingForm>(emptyForm)
  const [editId, setEditId] = useState<string | null>(null)
  const [tables, setTables] = useState<string[]>([])
  const [columns, setColumns] = useState<Array<{ name: string; type: string }>>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loadingTables, setLoadingTables] = useState(false)
  const [loadingColumns, setLoadingColumns] = useState(false)

  const { data: linkTypes = [] } = useQuery({ queryKey: ['link-types', ontologyId], queryFn: () => ontologyApi.listLinkTypes(ontologyId) as Promise<LinkTypeItem[]> })
  const { data: objectTypes = [] } = useQuery({ queryKey: ['object-types', ontologyId], queryFn: () => ontologyApi.listObjectTypes(ontologyId) as Promise<ObjectType[]> })
  const { data: sources = [] } = useQuery({ queryKey: ['data-sources', ontologyId], queryFn: () => ontologyApi.listDataSources(ontologyId).then(normalize) })
  const { data: bindings = [] } = useQuery({ queryKey: ['link-bindings', ontologyId], queryFn: () => ontologyApi.listLinkBindings(ontologyId).then(normalize) })

  useEffect(() => {
    if (form.data_source_id) loadTables(form.data_source_id, form.schema_name)
  }, [form.data_source_id])

  useEffect(() => {
    if (form.data_source_id && form.table_name) loadColumns(form.data_source_id, form.table_name, form.schema_name)
  }, [form.data_source_id, form.table_name])

  const saveMut = useMutation({
    mutationFn: (payload: any) => editId ? ontologyApi.updateLinkBinding(ontologyId, editId, payload) : ontologyApi.createLinkBinding(ontologyId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['link-bindings', ontologyId] })
      setMessage(editId ? '关系绑定已更新。' : '关系绑定已创建。')
      reset()
    },
    onError: (e: any) => setError(String(e?.detail || e?.message || e)),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => ontologyApi.deleteLinkBinding(ontologyId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['link-bindings', ontologyId] }),
    onError: (e: any) => setError(String(e?.detail || e?.message || e)),
  })

  function update(patch: Partial<LinkBindingForm>) {
    setForm(prev => ({ ...prev, ...patch }))
  }

  function reset() {
    setForm(emptyForm)
    setEditId(null)
    setError('')
  }

  async function loadTables(sourceId = form.data_source_id, schemaName = form.schema_name) {
    if (!sourceId) return
    setLoadingTables(true)
    try {
      const res: any = await ontologyApi.listDataSourceTables(ontologyId, sourceId, schemaName || undefined)
      setTables((res?.data || res)?.tables || [])
    } catch (e: any) {
      setError(String(e?.detail || e?.message || e))
      setTables([])
    } finally {
      setLoadingTables(false)
    }
  }

  async function loadColumns(sourceId = form.data_source_id, tableName = form.table_name, schemaName = form.schema_name) {
    if (!sourceId || !tableName) return
    setLoadingColumns(true)
    try {
      const res: any = await ontologyApi.listDataSourceColumns(ontologyId, sourceId, tableName, schemaName || undefined)
      setColumns((res?.data || res)?.columns || [])
    } catch (e: any) {
      setError(String(e?.detail || e?.message || e))
      setColumns([])
    } finally {
      setLoadingColumns(false)
    }
  }

  function save() {
    try {
      if (!form.link_type_id || !form.data_source_id || !form.table_name || !form.source_key_column || !form.target_key_column) {
        setError('请选择关系类型、数据源、表、源 key 列和目标 key 列。')
        return
      }
      saveMut.mutate({
        link_type_id: form.link_type_id,
        data_source_id: form.data_source_id,
        schema_name: form.schema_name || null,
        table_name: form.table_name,
        source_object_type_id: form.source_object_type_id,
        source_key_column: form.source_key_column,
        target_object_type_id: form.target_object_type_id,
        target_key_column: form.target_key_column,
        relation_filters: parseJson(form.relation_filters, {}),
        property_bindings: parseJson(form.property_bindings, {}),
        is_active: form.is_active,
      })
    } catch (e: any) {
      setError('JSON 配置不合法：' + String(e?.message || e))
    }
  }

  function startEdit(item: any) {
    setEditId(item.id)
    setForm({
      link_type_id: item.link_type_id || '',
      data_source_id: item.data_source_id || '',
      schema_name: item.schema_name || '',
      table_name: item.table_name || '',
      source_object_type_id: item.source_object_type_id || '',
      source_key_column: item.source_key_column || '',
      target_object_type_id: item.target_object_type_id || '',
      target_key_column: item.target_key_column || '',
      relation_filters: JSON.stringify(item.relation_filters || {}, null, 2),
      property_bindings: JSON.stringify(item.property_bindings || {}, null, 2),
      is_active: item.is_active !== false,
    })
  }

  const selectedLinkType = (linkTypes as any[]).find(t => t.id === form.link_type_id)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">关系绑定</h3>
          <p className="text-sm text-gray-500 mt-0.5">将本体关系类型绑定到数据库关系表，例如 Radar TRACKS Target 来自 radar_target_links。</p>
        </div>
        <button onClick={reset} className="px-3 py-1.5 border rounded-lg text-xs flex items-center gap-1 text-gray-600 hover:bg-gray-50"><Plus size={13} /> 新建关系绑定</button>
      </div>

      {(message || error) && <div className={`border rounded-xl px-4 py-3 text-sm ${error ? 'border-red-200 bg-red-50 text-red-700' : 'border-green-200 bg-green-50 text-green-700'}`}>{error || message}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-[430px_1fr] gap-5">
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-800"><GitBranch size={15} /> {editId ? '编辑关系绑定' : '新建关系绑定'}</div>
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">关系类型</label>
              <select value={form.link_type_id} onChange={e => {
                const lt: any = (linkTypes as any[]).find(x => x.id === e.target.value)
                update({ link_type_id: e.target.value, source_object_type_id: lt?.source_object_type_id || '', target_object_type_id: lt?.target_object_type_id || '' })
              }} className="w-full border rounded-lg px-3 py-2 text-sm">
                <option value="">选择 LinkType</option>
                {(linkTypes as any[]).map(t => <option key={t.id} value={t.id}>{t.name_cn || t.name_en}</option>)}
              </select>
              {selectedLinkType && <p className="text-[10px] text-gray-400 mt-1">{selectedLinkType.name_en || selectedLinkType.id}</p>}
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">数据源</label>
              <select value={form.data_source_id} onChange={e => {
                const s: any = (sources as any[]).find(x => x.id === e.target.value)
                update({ data_source_id: e.target.value, table_name: s?.registered_table || '' })
              }} className="w-full border rounded-lg px-3 py-2 text-sm">
                <option value="">选择数据源</option>
                {(sources as any[]).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">源类型</label>
                <select value={form.source_object_type_id} onChange={e => update({ source_object_type_id: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm">
                  <option value="">选择类型</option>
                  {(objectTypes as ObjectType[]).map(t => <option key={t.id} value={t.id}>{t.name_cn}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">目标类型</label>
                <select value={form.target_object_type_id} onChange={e => update({ target_object_type_id: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm">
                  <option value="">选择类型</option>
                  {(objectTypes as ObjectType[]).map(t => <option key={t.id} value={t.id}>{t.name_cn}</option>)}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Schema</label>
                <input value={form.schema_name} onChange={e => update({ schema_name: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="public" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">关系表</label>
                <div className="flex gap-2">
                  {tables.length > 0 ? <select value={form.table_name} onChange={e => update({ table_name: e.target.value, source_key_column: '', target_key_column: '' })} className="min-w-0 flex-1 border rounded-lg px-3 py-2 text-sm"><option value="">选择表</option>{tables.map(t => <option key={t} value={t}>{t}</option>)}</select> : <input value={form.table_name} onChange={e => update({ table_name: e.target.value })} className="min-w-0 flex-1 border rounded-lg px-3 py-2 text-sm" />}
                  <button onClick={() => loadTables()} disabled={!form.data_source_id || loadingTables} className="px-2.5 py-2 border rounded-lg text-gray-500 disabled:opacity-40">{loadingTables ? <RefreshCw size={13} className="animate-spin" /> : <Table2 size={13} />}</button>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {(['source_key_column', 'target_key_column'] as const).map(key => <div key={key}>
                <label className="block text-xs text-gray-500 mb-1">{key === 'source_key_column' ? '源 key 列' : '目标 key 列'}</label>
                {columns.length > 0 ? <select value={form[key]} onChange={e => update({ [key]: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm"><option value="">选择列</option>{columns.map(c => <option key={c.name} value={c.name}>{c.name} · {c.type}</option>)}</select> : <input value={form[key]} onChange={e => update({ [key]: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm" />}
              </div>)}
            </div>
            <button onClick={() => loadColumns()} disabled={!form.data_source_id || !form.table_name || loadingColumns} className="px-3 py-1.5 border rounded-lg text-xs text-gray-600 disabled:opacity-40">{loadingColumns ? '读取列中...' : '刷新列列表'}</button>
            <div>
              <label className="block text-xs text-gray-500 mb-1">过滤条件 JSON</label>
              <textarea value={form.relation_filters} onChange={e => update({ relation_filters: e.target.value })} rows={3} className="w-full border rounded-lg px-3 py-2 text-xs font-mono" placeholder='{"relation_type":"TRACKS","status":"active"}' />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">关系属性映射 JSON</label>
              <textarea value={form.property_bindings} onChange={e => update({ property_bindings: e.target.value })} rows={3} className="w-full border rounded-lg px-3 py-2 text-xs font-mono" placeholder='{"confidence":"confidence","started_at":"started_at"}' />
            </div>
            <label className="flex items-center gap-2 text-xs text-gray-600"><input type="checkbox" checked={form.is_active} onChange={e => update({ is_active: e.target.checked })} /> 启用</label>
          </div>
          <button onClick={save} disabled={saveMut.isPending} className="px-4 py-2 bg-black text-white rounded-lg text-sm flex items-center gap-1 disabled:opacity-40"><Save size={14} /> 保存关系绑定</button>
        </div>

        <div className="bg-white border rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b bg-gray-50 flex items-center gap-2 text-sm font-medium text-gray-800"><GitBranch size={15} /> 已绑定关系 ({(bindings as any[]).length})</div>
          {(bindings as any[]).length === 0 ? <div className="px-5 py-10 text-center text-sm text-gray-500">还没有关系绑定。</div> : <div className="divide-y">
            {(bindings as any[]).map(item => <div key={item.id} className="p-4 hover:bg-gray-50">
              <div className="flex items-start justify-between gap-3">
                <button onClick={() => startEdit(item)} className="text-left min-w-0">
                  <div className="font-medium text-sm text-gray-900">{(linkTypes as any[]).find(t => t.id === item.link_type_id)?.name_cn || item.link_type_id}</div>
                  <div className="text-xs text-gray-500 mt-1">{item.table_name}: {item.source_key_column}{' -> '}{item.target_key_column}</div>
                  <div className="text-[10px] text-gray-400 mt-1">filters {JSON.stringify(item.relation_filters || {})}</div>
                </button>
                <button onClick={() => { if (confirm('删除此关系绑定？')) deleteMut.mutate(item.id) }} className="text-red-600 hover:text-red-700"><Trash2 size={14} /></button>
              </div>
            </div>)}
          </div>}
        </div>
      </div>
    </div>
  )
}
