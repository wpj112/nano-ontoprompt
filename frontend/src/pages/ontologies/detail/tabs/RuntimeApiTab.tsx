import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Copy, Play } from 'lucide-react'
import { ontologyApi } from '@/api/ontologies'

export default function RuntimeApiTab({ ontologyId }: { ontologyId: string }) {
  const [typeKey, setTypeKey] = useState('')
  const [objectKey, setObjectKey] = useState('')
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const { data: metadata } = useQuery({
    queryKey: ['runtime-metadata', ontologyId],
    queryFn: () => ontologyApi.getRuntimeMetadata(ontologyId) as Promise<any>,
  })

  const data = (metadata as any)?.data || metadata || {}
  const objectTypes = data.object_types || []
  const bindings = data.field_bindings || []
  const selectedType = objectTypes.find((t: any) => t.id === typeKey || t.name_en === typeKey || t.name_cn === typeKey)
  const endpoint = `/api/v2/runtime/ontologies/${ontologyId}/objects/${typeKey || ':type_key'}/${objectKey || ':object_key'}`

  async function fetchObject() {
    setError('')
    setResult(null)
    try {
      const res = await ontologyApi.getRuntimeObject(ontologyId, typeKey, objectKey)
      setResult(res)
    } catch (e: any) {
      setError(String(e?.detail || e?.message || e))
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="font-semibold text-gray-900">Runtime API</h3>
        <p className="text-sm text-gray-500 mt-0.5">第三方智能体编排系统通过这些接口读取已绑定的本体对象。</p>
      </div>

      <div className="bg-white border rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="font-mono text-xs bg-gray-50 border rounded-lg px-3 py-2 flex-1 overflow-auto">GET {endpoint}</div>
          <button onClick={() => navigator.clipboard?.writeText(endpoint)} className="px-3 py-2 border rounded-lg text-xs flex items-center gap-1 text-gray-600 hover:bg-gray-50">
            <Copy size={13} /> 复制
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">ObjectType</label>
            <select value={typeKey} onChange={e => setTypeKey(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm">
              <option value="">选择类型</option>
              {objectTypes.map((t: any) => <option key={t.id} value={t.name_en || t.id}>{t.name_cn}{t.name_en ? ` · ${t.name_en}` : ''}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">业务主键</label>
            <input value={objectKey} onChange={e => setObjectKey(e.target.value)} placeholder="例如 SUP-001" className="w-full border rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="flex items-end">
            <button onClick={fetchObject} disabled={!typeKey || !objectKey} className="w-full px-4 py-2 bg-black text-white rounded-lg text-sm flex items-center justify-center gap-2 disabled:opacity-40">
              <Play size={14} /> 调用
            </button>
          </div>
        </div>
        {selectedType && (
          <p className="text-xs text-gray-500">已绑定字段：{bindings.filter((b: any) => b.object_type_id === selectedType.id).length}</p>
        )}
        {error && <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>}
        {result && <pre className="text-xs bg-gray-950 text-green-300 rounded-lg p-4 overflow-auto max-h-96">{JSON.stringify(result, null, 2)}</pre>}
      </div>

      <div className="bg-white border rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b text-sm font-medium text-gray-800">Runtime Metadata</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-5 text-sm">
          <div className="border rounded-lg p-3"><p className="text-xs text-gray-400">ObjectTypes</p><p className="font-semibold">{objectTypes.length}</p></div>
          <div className="border rounded-lg p-3"><p className="text-xs text-gray-400">Field Bindings</p><p className="font-semibold">{bindings.length}</p></div>
          <div className="border rounded-lg p-3"><p className="text-xs text-gray-400">Rules</p><p className="font-semibold">{(data.rules || []).length}</p></div>
          <div className="border rounded-lg p-3"><p className="text-xs text-gray-400">Actions</p><p className="font-semibold">{(data.actions || []).length}</p></div>
        </div>
      </div>
    </div>
  )
}
