// The RAG module's calls (docs/foundations.md#rag): a question, with the conversation so far,
// answered from the stored chunks and streamed, its sources first; and the stored documents.
import { request } from '../../api/client'
import { postStream, type StreamEvent } from '../../api/stream'
import type { ChatMessage, Parameters } from '../../api/types'
import type {
  RagDoneEvent,
  RagQuestion,
  RagSourcesEvent,
  SourceList,
} from './types'

// How many chunks an answer is given, the most the page shows under it.
const LIMIT = 5

// The event that comes before the answer: the chunks the model is given, numbered.
export interface SourcesEvent {
  readonly type: 'sources'
  readonly data: RagSourcesEvent
}

export function askStream(
  messages: readonly ChatMessage[],
  parameters: Parameters,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent<RagDoneEvent, SourcesEvent>> {
  const body: RagQuestion = {
    messages: [...messages],
    parameters,
    limit: LIMIT,
  }
  return postStream('/rag/ask/stream', body, signal, ['sources'])
}

export function listSources(): Promise<SourceList> {
  return request('/rag/sources')
}
