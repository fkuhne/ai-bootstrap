// A chat whose conversation the browser keeps, until the page is reloaded or a new chat starts
// (docs/foundations.md#chat-whole-or-streamed): each question goes with the conversation so far,
// and only complete answers join it.
import { useEffect } from 'react'
import type {
  ChatMessage,
  Content,
  Parameters,
  StreamEnd,
} from '../../api/types'
import { newUuid } from '../../api/userId'
import { NotReady } from '../../health/NotReady'
import { useReadiness } from '../../health/useReadiness'
import { ChatView } from '../../llm/ChatView'
import { detailsOf } from '../../llm/details'
import { isStreaming, useStreamedAnswer } from '../../llm/useStreamedAnswer'
import { chatStream } from './api'
import { useChat } from './context'

// What the page needs from the backend: the LLM alone.
const NEEDED = ['llm']

export function ChatPage() {
  const { messages, add, cleared } = useChat()
  const { answer, ask, stop, reset } = useStreamedAnswer<StreamEnd>()
  const readiness = useReadiness(NEEDED, isStreaming(answer.phase))

  // A new chat drops the answer on the page too.
  useEffect(reset, [cleared, reset])

  async function onSend(content: Content, parameters: Parameters) {
    const sent: ChatMessage[] = [
      ...messages
        // An answer with no text, as when a model only reasons, can't be sent back.
        .filter((message) => message.content !== '')
        .map(({ role, content: said }) => ({ role, content: said })),
      { role: 'user', content },
    ]
    const completed = await ask(content, (signal) =>
      chatStream(sent, parameters, signal),
    )
    if (completed === null || readiness.notReady.length > 0) {
      readiness.recheck()
    }
    if (completed !== null) {
      add(
        { id: newUuid(), role: 'user', content },
        {
          id: newUuid(),
          role: 'assistant',
          content: completed.text,
          reasoning: completed.reasoning || null,
          details: detailsOf(completed.done),
        },
      )
      reset()
    }
  }

  return (
    <ChatView
      messages={messages}
      answer={answer}
      onSend={(content, parameters) => void onSend(content, parameters)}
      onStop={stop}
      error={null}
      notice={<NotReady notReady={readiness.notReady} />}
      unkept="It's left out of the conversation."
    />
  )
}
