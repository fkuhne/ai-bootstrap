// The chat module's call (docs/foundations.md#chat-whole-or-streamed): the conversation so far,
// sent whole, and the answer streamed. The backend keeps nothing.
import { postStream, type StreamEvent } from '../../api/stream'
import type { ChatMessage, Parameters, StreamEnd } from '../../api/types'
import type { ChatRequest } from './types'

export function chatStream(
  messages: readonly ChatMessage[],
  parameters: Parameters,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent<StreamEnd>> {
  const body: ChatRequest = { messages: [...messages], parameters }
  return postStream('/chat/stream', body, signal)
}
