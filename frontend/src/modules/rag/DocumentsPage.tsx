// Questions answered from the stored documents (docs/foundations.md#rag): the conversation, kept
// in the browser as chat's is, goes to RAG's answers, and each answer shows the sources it was
// given, those it cites marked. Only complete answers join the conversation.
import { useEffect, useState } from 'react'
import type { Words } from '../../api/failures'
import type { StreamEvent } from '../../api/stream'
import type { ChatMessage, Content, Parameters } from '../../api/types'
import { newUuid } from '../../api/userId'
import { NotReady } from '../../health/NotReady'
import { useReadiness } from '../../health/useReadiness'
import { ChatView } from '../../llm/ChatView'
import { detailsOf } from '../../llm/details'
import type { ViewMessage } from '../../llm/Message'
import { isStreaming, useStreamedAnswer } from '../../llm/useStreamedAnswer'
import { askStream, type SourcesEvent } from './api'
import { useDocumentsChat } from './context'
import { Sources } from './Sources'
import type { RagDoneEvent, RagSource } from './types'

// What the page needs from the backend: the LLM, and RAG's embedding model and store.
const NEEDED = ['llm', 'rag']

// Its words for RAG's check, and for a failed answer: the search may be what failed.
const READINESS_WORDS = {
  rag: "The documents can't be searched yet: the embedding model or Qdrant may be starting, which takes a minute, longer the first time while the model downloads.",
}
const FAILURE_WORDS: Words = {
  503: "The model or the documents' search can't be reached right now. If the app was just started, they may still be loading: try again in a minute.",
}

export function DocumentsPage() {
  const { messages, add, cleared } = useDocumentsChat()
  const { answer, ask, stop, reset } = useStreamedAnswer<RagDoneEvent>()
  // The sources of the answer being streamed, which come before it.
  const [sources, setSources] = useState<readonly RagSource[]>([])
  const readiness = useReadiness(NEEDED, isStreaming(answer.phase))

  // A new chat drops the answer on the page too.
  useEffect(reset, [cleared, reset])

  async function onSend(content: Content, parameters: Parameters) {
    const sent: ChatMessage[] = [
      ...messages
        .filter((message) => message.content !== '')
        .map(({ role, content: said }) => ({ role, content: said })),
      { role: 'user', content },
    ]
    let given: readonly RagSource[] = []
    setSources(given)
    const completed = await ask(content, (signal) =>
      keepingSources(askStream(sent, parameters, signal), (found) => {
        given = found
        setSources(found)
      }),
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
          details: detailsOfAnswer(completed.done, given),
          extra: <Sources sources={given} answer={completed.text} />,
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
      notice={
        <NotReady notReady={readiness.notReady} words={READINESS_WORDS} />
      }
      unkept="It's left out of the conversation."
      words={FAILURE_WORDS}
      answerExtra={<Sources sources={sources} answer={answer.text} />}
    />
  )
}

// The stream, its `sources` event taken out and handed to `keep`.
async function* keepingSources(
  stream: AsyncIterable<StreamEvent<RagDoneEvent, SourcesEvent>>,
  keep: (sources: readonly RagSource[]) => void,
): AsyncGenerator<StreamEvent<RagDoneEvent>> {
  for await (const event of stream) {
    if (event.type === 'sources') {
      keep(event.data.sources)
    } else {
      yield event
    }
  }
}

// The model and its tokens; or, when the documents couldn't ground an answer, why the model
// wasn't asked.
function detailsOfAnswer(
  done: RagDoneEvent,
  sources: readonly RagSource[],
): ViewMessage['details'] {
  if (done.refused) {
    return {
      summary:
        sources.length === 0
          ? "No chunk was found: the model wasn't asked."
          : "No chunk was close enough: the model wasn't asked.",
    }
  }
  return detailsOf(done)
}
