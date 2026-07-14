import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ontologyApi } from '@/api/ontologies'
import SimpleLlmOntologyPage from './modes/SimpleLlmOntologyPage'
import ManualOntologyPage from './modes/ManualOntologyPage'
import PipelineMappingOntologyPage from './modes/PipelineMappingOntologyPage'

export default function OntologyDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()

  const { data: ontology, isLoading } = useQuery({
    queryKey: ['ontology', id],
    queryFn: () => ontologyApi.get(id!) as any,
    enabled: !!id,
  })

  if (isLoading) return <div className="p-6 text-gray-400">{t('common.loading')}</div>
  if (!ontology) return <div className="p-6 text-red-500">Ontology not found</div>

  if ((ontology as any).build_mode === 'manual') {
    return <ManualOntologyPage ontology={ontology} />
  }

  if ((ontology as any).build_mode === 'pipeline_mapping') {
    return <PipelineMappingOntologyPage ontology={ontology} />
  }

  return <SimpleLlmOntologyPage ontology={ontology} />
}

