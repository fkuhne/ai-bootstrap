// Short names for the RAG module's models, generated from the backend's OpenAPI schema
// (docs/foundations.md#rag).
import type { components } from '../../api/schema'

type Models = components['schemas']

export type RagQuestion = Models['RagQuestion']
export type RagSource = Models['RagSource']
export type RagSourcesEvent = Models['RagSourcesEvent']
export type RagDoneEvent = Models['RagDoneEvent']
export type SourceList = Models['SourceList']
export type SourceSummary = Models['SourceSummary']
