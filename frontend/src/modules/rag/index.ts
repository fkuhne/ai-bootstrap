// The RAG module's page (docs/foundations.md#rag): questions answered from the stored documents,
// each answer with its sources.
import { BookOpen } from 'lucide-react'
import type { UiModule } from '../../uiModule'
import { DocumentList, DocumentsPage, DocumentsProvider } from './parts'
import { PATH } from './paths'

export const RAG: UiModule = {
  name: 'rag',
  title: 'Documents',
  icon: BookOpen,
  path: PATH.slice(1),
  Page: DocumentsPage,
  Sidebar: DocumentList,
  Provider: DocumentsProvider,
}
