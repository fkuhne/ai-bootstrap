// The conversations module's calls (docs/foundations.md#conversations): the user's conversations,
// and an answer streamed in one, stored once it's complete.
import { request } from '../../api/client'
import { postStream, type StreamEvent } from '../../api/stream'
import type { Content, Parameters } from '../../api/types'
import type {
  AskRequest,
  ConversationDoneEvent,
  ConversationSummary,
  ConversationWithMessages,
} from './types'

export function listConversations(): Promise<ConversationSummary[]> {
  return request('/conversations')
}

export function startConversation(): Promise<ConversationSummary> {
  return request('/conversations', { method: 'POST' })
}

export function openConversation(
  id: string,
): Promise<ConversationWithMessages> {
  return request(`/conversations/${encodeURIComponent(id)}`)
}

export function deleteConversation(id: string): Promise<void> {
  return request(`/conversations/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}

// Asks in the conversation, which adds its stored history, and yields the answer's events. Stopped
// or failed, nothing is stored.
export function askStream(
  conversationId: string,
  content: Content,
  parameters: Parameters,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent<ConversationDoneEvent>> {
  const body: AskRequest = { content, parameters }
  return postStream(
    `/conversations/${encodeURIComponent(conversationId)}/messages/stream`,
    body,
    signal,
  )
}
