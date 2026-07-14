import React, { lazy, Suspense, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import StatusBadge from '@/components/StatusBadge'
import type { OntologyDetail } from '@/types/ontology'

const GraphTab = lazy(() => import('../tabs/GraphTabV2'))

export type DetailTab =
  | 'info'
  | 'graph'
  | 'ontology-space'
  | 'entities'
  | 'logic'
  | 'actions'
  | 'files'
  | 'database'
  | 'data-sources'
  | 'curated'
  | 'templates'
  | 'runtime-api'
  | 'runs'

export type DetailTabItem = { key: DetailTab; label: string }

class GraphErrorBoundary extends React.Component<
  { children: React.ReactNode; fallbackLabel?: string },
  { hasError: boolean; error: string }
> {
  constructor(props: any) {
    super(props)
    this.state = { hasError: false, error: '' }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
          <p className="text-red-600 font-medium mb-2">{this.props.fallbackLabel || '图表加载失败'}</p>
          <p className="text-red-400 text-sm font-mono">{this.state.error}</p>
          <button
            onClick={() => this.setState({ hasError: false, error: '' })}
            className="mt-4 px-3 py-1.5 text-sm border border-red-300 text-red-500 rounded-lg hover:bg-red-100">
            重试
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export function GraphPanel({ ontologyId }: { ontologyId: string }) {
  const { t } = useTranslation()
  return (
    <GraphErrorBoundary fallbackLabel="知识图谱渲染失败">
      <Suspense fallback={<div className="text-gray-400 py-8 text-center">{t('common.loading')}</div>}>
        <GraphTab ontologyId={ontologyId} />
      </Suspense>
    </GraphErrorBoundary>
  )
}

export function PlaceholderPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border rounded-xl p-6">
      <h3 className="font-semibold text-gray-900 mb-2">{title}</h3>
      <div className="text-sm text-gray-500 leading-6">{children}</div>
    </div>
  )
}

export default function OntologyDetailShell({
  ontology,
  tabs,
  modeLabel,
  modeClassName,
  children,
}: {
  ontology: OntologyDetail
  tabs: DetailTabItem[]
  modeLabel: string
  modeClassName: string
  children: (activeTab: DetailTab) => React.ReactNode
}) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab') as DetailTab | null
  const defaultTab = tabs.some(tab => tab.key === requestedTab) ? requestedTab! : tabs[0].key
  const [activeTab, setActiveTab] = useState<DetailTab>(defaultTab)

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate('/ontologies')} className="text-gray-500 hover:text-black text-sm">{t('ontology.back')}</button>
        <h2 className="text-xl font-semibold">{ontology.name}</h2>
        <StatusBadge status={ontology.status} />
        <span className="text-gray-400 text-sm">{ontology.domain} · {ontology.version}</span>
        <span className={`text-xs px-2 py-0.5 rounded border ${modeClassName}`}>{modeLabel}</span>
      </div>

      <div className="border-b mb-6 overflow-x-auto">
        <div className="flex gap-1 min-w-max">
          {tabs.map(tab => (
            <button key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-black text-black'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {children(activeTab)}
    </div>
  )
}

