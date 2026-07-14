import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Columns3, Database, Edit2, Loader2, Plus, RefreshCw, Save, Table2, Trash2, XCircle } from 'lucide-react'
import { ontologyApi } from '@/api/ontologies'

interface DbConfig {
  db_type: string
  host: string
  port: number
  user: string
  password: string
  database: string
}

interface DataSourceItem {
  id: string
  name: string
  db_config?: Partial<DbConfig>
  registered_table?: string | null
  created_at?: string
  updated_at?: string
}

interface ColumnInfo {
  name: string
  type: string
}

const emptyConfig: DbConfig = {
  db_type: 'mysql',
  host: '',
  port: 3306,
  user: '',
  password: '',
  database: '',
}

const emptyForm = {
  name: '',
  registered_table: '',
  schema_name: '',
  db_config: emptyConfig,
}

function normalizeList(payload: any): any[] {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.data)) return payload.data
  return []
}

function sourceLabel(source: DataSourceItem) {
  const cfg = source.db_config || {}
  const db = cfg.database || 'database'
  const host = cfg.host || 'host'
  return `${cfg.db_type || 'db'}://${host}/${db}`
}

export default function DataSourcesTab({ ontologyId }: { ontologyId: string }) {
  const qc = useQueryClient()
  const [form, setForm] = useState(emptyForm)
  const [editId, setEditId] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [tables, setTables] = useState<string[]>([])
  const [columns, setColumns] = useState<ColumnInfo[]>([])
  const [selectedTable, setSelectedTable] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loadingTables, setLoadingTables] = useState(false)
  const [loadingColumns, setLoadingColumns] = useState(false)

  const { data: sources = [], isLoading } = useQuery({
    queryKey: ['data-sources', ontologyId],
    queryFn: () => ontologyApi.listDataSources(ontologyId).then(normalizeList) as Promise<DataSourceItem[]>,
  })

  const saveMut = useMutation({
    mutationFn: (payload: any) => editId
      ? ontologyApi.updateDataSource(ontologyId, editId, payload)
      : ontologyApi.createDataSource(ontologyId, payload),
    onSuccess: (saved: any) => {
      qc.invalidateQueries({ queryKey: ['data-sources', ontologyId] })
      const savedId = saved?.id || editId
      if (savedId) setSelectedId(savedId)
      setMessage(editId ? '数据源已更新。' : '数据源已保存。')
      setError('')
      if (!editId) resetForm()
    },
    onError: (e: any) => setError(readError(e)),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => ontologyApi.deleteDataSource(ontologyId, id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['data-sources', ontologyId] })
      if (selectedId === id) {
        setSelectedId(null)
        setTables([])
        setColumns([])
        setSelectedTable('')
      }
      if (editId === id) resetForm()
    },
    onError: (e: any) => setError(readError(e)),
  })

  const selectedSource = (sources as DataSourceItem[]).find(s => s.id === selectedId) || null

  useEffect(() => {
    if (!selectedSource) return
    setSelectedTable(selectedSource.registered_table || '')
  }, [selectedSource?.id])

  function readError(e: any) {
    return String(e?.response?.data?.detail || e?.detail || e?.message || e)
  }

  function resetForm() {
    setForm(emptyForm)
    setEditId(null)
    setError('')
  }

  function updateConfig(patch: Partial<DbConfig>) {
    setForm(prev => ({ ...prev, db_config: { ...prev.db_config, ...patch } }))
  }

  function startCreate() {
    resetForm()
    setMessage('')
  }

  function startEdit(source: DataSourceItem) {
    const cfg = { ...emptyConfig, ...(source.db_config || {}) }
    setEditId(source.id)
    setSelectedId(source.id)
    setForm({
      name: source.name || '',
      registered_table: source.registered_table || '',
      schema_name: '',
      db_config: cfg,
    })
    setMessage('')
    setError('')
  }

  function save() {
    if (!form.name.trim()) {
      setError('请填写数据源名称。')
      return
    }
    if (!form.db_config.host.trim() || !form.db_config.database.trim() || !form.db_config.user.trim()) {
      setError('请填写主机、数据库名和用户名。')
      return
    }
    saveMut.mutate({
      name: form.name.trim(),
      db_config: form.db_config,
      registered_table: form.registered_table.trim() || null,
    })
  }

  async function testSource(sourceId: string) {
    setMessage('')
    setError('')
    try {
      const res: any = await ontologyApi.testDataSource(ontologyId, sourceId)
      setMessage(res?.message || '连接测试成功。')
    } catch (e: any) {
      setError(readError(e))
    }
  }

  async function loadTables(sourceId = selectedId, schemaName = form.schema_name) {
    if (!sourceId) return
    setLoadingTables(true)
    setMessage('')
    setError('')
    try {
      const res: any = await ontologyApi.listDataSourceTables(ontologyId, sourceId, schemaName || undefined)
      const payload = res?.data || res
      setTables(payload?.tables || [])
      setColumns([])
    } catch (e: any) {
      setError(readError(e))
      setTables([])
    } finally {
      setLoadingTables(false)
    }
  }

  async function loadColumns(tableName: string, sourceId = selectedId, schemaName = form.schema_name) {
    if (!sourceId || !tableName) return
    setSelectedTable(tableName)
    setLoadingColumns(true)
    setMessage('')
    setError('')
    try {
      const res: any = await ontologyApi.listDataSourceColumns(ontologyId, sourceId, tableName, schemaName || undefined)
      const payload = res?.data || res
      setColumns(payload?.columns || [])
    } catch (e: any) {
      setError(readError(e))
      setColumns([])
    } finally {
      setLoadingColumns(false)
    }
  }

  function useTableAsDefault(tableName: string) {
    if (!selectedSource) return
    ontologyApi.updateDataSource(ontologyId, selectedSource.id, { registered_table: tableName })
      .then(() => {
        qc.invalidateQueries({ queryKey: ['data-sources', ontologyId] })
        setMessage(`默认表已切换为 ${tableName}。字段绑定仍可单独选择其他表。`)
      })
      .catch((e: any) => setError(readError(e)))
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">数据源</h3>
          <p className="text-sm text-gray-500 mt-0.5">管理手动本体可访问的外部数据库连接。这里保存连接和默认表，字段绑定页负责绑定具体列。</p>
        </div>
        <button onClick={startCreate} className="px-3 py-1.5 border rounded-lg text-xs flex items-center gap-1 text-gray-600 hover:bg-gray-50">
          <Plus size={13} /> 新建数据源
        </button>
      </div>

      {(message || error) && (
        <div className={`border rounded-xl px-4 py-3 text-sm flex items-center gap-2 ${error ? 'border-red-200 bg-red-50 text-red-700' : 'border-green-200 bg-green-50 text-green-700'}`}>
          {error ? <XCircle size={15} /> : <CheckCircle2 size={15} />}
          <span>{error || message}</span>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[390px_1fr] gap-5">
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-800">
            <Database size={15} /> {editId ? '编辑数据源' : '新建数据源'}
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">名称</label>
              <input value={form.name} onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))} placeholder="crm.customers" className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">数据库类型</label>
                <select value={form.db_config.db_type} onChange={e => updateConfig({ db_type: e.target.value, port: e.target.value === 'postgres' ? 5432 : 3306 })} className="w-full border rounded-lg px-3 py-2 text-sm">
                  <option value="mysql">MySQL</option>
                  <option value="postgres">PostgreSQL</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">端口</label>
                <input type="number" value={form.db_config.port} onChange={e => updateConfig({ port: Number(e.target.value) })} className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">主机</label>
              <input value={form.db_config.host} onChange={e => updateConfig({ host: e.target.value })} placeholder="localhost" className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">数据库名</label>
                <input value={form.db_config.database} onChange={e => updateConfig({ database: e.target.value })} placeholder="business_db" className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">用户名</label>
                <input value={form.db_config.user} onChange={e => updateConfig({ user: e.target.value })} placeholder="readonly_user" className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">密码</label>
              <input type="password" value={form.db_config.password} onChange={e => updateConfig({ password: e.target.value })} className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">默认 Schema</label>
                <input value={form.schema_name} onChange={e => setForm(prev => ({ ...prev, schema_name: e.target.value }))} placeholder="public" className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">默认表</label>
                <input value={form.registered_table} onChange={e => setForm(prev => ({ ...prev, registered_table: e.target.value }))} placeholder="customers" className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
            </div>
          </div>

          <div className="flex gap-2 pt-2">
            <button onClick={save} disabled={saveMut.isPending} className="px-4 py-2 bg-black text-white rounded-lg text-sm flex items-center gap-1 disabled:opacity-40">
              {saveMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} 保存
            </button>
            {editId && <button onClick={resetForm} className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-gray-50">取消编辑</button>}
          </div>
        </div>

        <div className="space-y-5">
          <div className="bg-white border rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-medium text-gray-800">
                <Database size={15} /> 已保存数据源 ({(sources as DataSourceItem[]).length})
              </div>
              {isLoading && <Loader2 size={14} className="animate-spin text-gray-400" />}
            </div>

            {(sources as DataSourceItem[]).length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-gray-500">还没有数据源。先在左侧保存一个连接，后面字段绑定就可以复用它。</div>
            ) : (
              <div className="divide-y">
                {(sources as DataSourceItem[]).map(source => (
                  <div key={source.id} className={`p-4 hover:bg-gray-50 ${selectedId === source.id ? 'bg-green-50/60' : ''}`}>
                    <div className="flex items-start justify-between gap-3">
                      <button onClick={() => { setSelectedId(source.id); setSelectedTable(source.registered_table || ''); setColumns([]) }} className="min-w-0 text-left">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm text-gray-900">{source.name}</span>
                          {source.registered_table && <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">默认表 {source.registered_table}</span>}
                        </div>
                        <p className="text-xs text-gray-500 mt-1">{sourceLabel(source)}</p>
                      </button>
                      <div className="flex items-center gap-1">
                        <button onClick={() => testSource(source.id)} className="px-2.5 py-1.5 border rounded-lg text-xs text-gray-600 hover:bg-white">重测</button>
                        <button onClick={() => { setSelectedId(source.id); loadTables(source.id) }} className="px-2.5 py-1.5 border rounded-lg text-xs text-gray-600 hover:bg-white flex items-center gap-1">
                          <Table2 size={12} /> 表
                        </button>
                        <button onClick={() => startEdit(source)} className="p-1.5 text-gray-500 hover:text-gray-800" title="编辑"><Edit2 size={14} /></button>
                        <button onClick={() => { if (confirm('删除这个数据源？字段绑定中引用它的配置也会失效。')) deleteMut.mutate(source.id) }} className="p-1.5 text-red-500 hover:text-red-700" title="删除"><Trash2 size={14} /></button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {selectedSource && (
            <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-5">
              <div className="bg-white border rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-800">表清单</span>
                  <button onClick={() => loadTables()} disabled={loadingTables} className="text-gray-500 hover:text-gray-800 disabled:opacity-40">
                    <RefreshCw size={14} className={loadingTables ? 'animate-spin' : ''} />
                  </button>
                </div>
                {tables.length === 0 ? (
                  <div className="px-4 py-8 text-center text-xs text-gray-500">点击“表”或刷新按钮读取该数据源的表。</div>
                ) : (
                  <div className="max-h-80 overflow-auto divide-y">
                    {tables.map(table => (
                      <button key={table} onClick={() => loadColumns(table)} className={`w-full px-4 py-2.5 text-left text-xs flex items-center gap-2 hover:bg-gray-50 ${selectedTable === table ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700'}`}>
                        <Table2 size={12} /> <span className="truncate">{table}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-white border rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-medium text-gray-800">
                    <Columns3 size={15} /> {selectedTable || selectedSource.registered_table || '选择表查看列'}
                  </div>
                  {selectedTable && (
                    <button onClick={() => useTableAsDefault(selectedTable)} className="px-2.5 py-1.5 bg-green-600 text-white rounded-lg text-xs">
                      设为默认表
                    </button>
                  )}
                </div>
                {loadingColumns ? (
                  <div className="px-5 py-10 text-center text-sm text-gray-500"><Loader2 size={16} className="animate-spin inline mr-2" />正在读取列</div>
                ) : columns.length === 0 ? (
                  <div className="px-5 py-10 text-center text-sm text-gray-500">选择左侧表后会显示列名和数据库类型。</div>
                ) : (
                  <div className="overflow-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 text-xs text-gray-500">
                        <tr>
                          <th className="text-left font-medium px-4 py-2">列名</th>
                          <th className="text-left font-medium px-4 py-2">类型</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {columns.map(col => (
                          <tr key={col.name}>
                            <td className="px-4 py-2 font-mono text-xs text-gray-800">{col.name}</td>
                            <td className="px-4 py-2 text-xs text-gray-500">{col.type}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
