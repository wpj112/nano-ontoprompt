import { useTranslation } from 'react-i18next'
import type { OntologyDetail } from '@/types/ontology'
import InfoTab from '../tabs/InfoTab'
import FilesTab from '../tabs/FilesTab'
import EntitiesTab from '../tabs/EntitiesTab'
import LogicTab from '../tabs/LogicTab'
import ActionsTab from '../tabs/ActionsTab'
import TemplatesTab from '../tabs/TemplatesTab'
import DatabaseTab from '../tabs/DatabaseTab'
import OntologySpaceTab from '../tabs/OntologySpaceTab'
import OntologyDetailShell, { GraphPanel, type DetailTab, type DetailTabItem } from './OntologyDetailShell'

export default function SimpleLlmOntologyPage({ ontology }: { ontology: OntologyDetail }) {
  const { t } = useTranslation()
  const tabs: DetailTabItem[] = [
    { key: 'info', label: t('ontology.tabs.info') },
    { key: 'files', label: t('ontology.tabs.files') },
    { key: 'ontology-space', label: '抽取结果' },
    { key: 'graph', label: t('ontology.tabs.graph') },
    { key: 'entities', label: t('ontology.tabs.entities') },
    { key: 'logic', label: t('ontology.tabs.logic') },
    { key: 'actions', label: t('ontology.tabs.actions') },
    { key: 'templates', label: '类型模板' },
    { key: 'database', label: '数据库' },
  ]

  return (
    <OntologyDetailShell
      ontology={ontology}
      tabs={tabs}
      modeLabel="简易 LLM"
      modeClassName="bg-amber-50 border-amber-200 text-amber-700">
      {(activeTab: DetailTab) => (
        <>
          {activeTab === 'info' && <InfoTab ontology={ontology} />}
          {activeTab === 'files' && <FilesTab ontologyId={ontology.id} />}
          {activeTab === 'ontology-space' && <OntologySpaceTab ontologyId={ontology.id} />}
          {activeTab === 'graph' && <GraphPanel ontologyId={ontology.id} />}
          {activeTab === 'entities' && <EntitiesTab ontologyId={ontology.id} />}
          {activeTab === 'logic' && <LogicTab ontologyId={ontology.id} />}
          {activeTab === 'actions' && <ActionsTab ontologyId={ontology.id} />}
          {activeTab === 'templates' && <TemplatesTab ontologyId={ontology.id} />}
          {activeTab === 'database' && <DatabaseTab ontologyId={ontology.id} />}
        </>
      )}
    </OntologyDetailShell>
  )
}

