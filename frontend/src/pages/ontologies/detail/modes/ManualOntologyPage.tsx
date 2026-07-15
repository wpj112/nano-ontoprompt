import type { OntologyDetail } from '@/types/ontology'
import OntologySpaceTab from '../tabs/OntologySpaceTab'
import DataSourcesTab from '../tabs/DataSourcesTab'
import FieldBindingsTab from '../tabs/FieldBindingsTab'
import LinkBindingsTab from '../tabs/LinkBindingsTab'
import RuntimeApiTab from '../tabs/RuntimeApiTab'
import TemplatesTab from '../tabs/TemplatesTab'
import OntologyDetailShell, { GraphPanel, PlaceholderPanel, type DetailTab, type DetailTabItem } from './OntologyDetailShell'

export default function ManualOntologyPage({ ontology }: { ontology: OntologyDetail }) {
  const tabs: DetailTabItem[] = [
    { key: 'ontology-space', label: '本体空间' },
    { key: 'data-sources', label: '数据源' },
    { key: 'database', label: '字段绑定' },
    { key: 'link-bindings', label: '关系绑定' },
    { key: 'runtime-api', label: 'Runtime API' },
    { key: 'runs', label: '执行记录' },
    { key: 'graph', label: '图谱' },
    { key: 'templates', label: '类型模板' },
  ]

  return (
    <OntologyDetailShell
      ontology={ontology}
      tabs={tabs}
      modeLabel="Manual Runtime"
      modeClassName="bg-green-50 border-green-200 text-green-700">
      {(activeTab: DetailTab) => (
        <>
          {activeTab === 'ontology-space' && <OntologySpaceTab ontologyId={ontology.id} />}
          {activeTab === 'data-sources' && <DataSourcesTab ontologyId={ontology.id} />}
          {activeTab === 'database' && <FieldBindingsTab ontologyId={ontology.id} />}
          {activeTab === 'link-bindings' && <LinkBindingsTab ontologyId={ontology.id} />}
          {activeTab === 'runtime-api' && <RuntimeApiTab ontologyId={ontology.id} />}
          {activeTab === 'runs' && (
            <PlaceholderPanel title="执行记录">
              这里会展示规则触发、动作执行、外部 API 调用和错误审计。后续 runtime executor 接入后，这里会读取专用运行日志。
            </PlaceholderPanel>
          )}
          {activeTab === 'graph' && <GraphPanel ontologyId={ontology.id} />}
          {activeTab === 'templates' && <TemplatesTab ontologyId={ontology.id} />}
        </>
      )}
    </OntologyDetailShell>
  )
}

