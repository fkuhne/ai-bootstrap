// One stored conversation: its messages, the answer being streamed, and the message form. PATH is a
// new conversation, created with its first message; PATH/<id> is a stored one
// (docs/foundations.md#the-chat-view).
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { failureMessage } from '../../api/client'
import type { Words } from '../../api/failures'
import type { Content, Parameters } from '../../api/types'
import { askStream, openConversation, startConversation } from './api'
import { breakdown, summary } from './elapsed'
import { PATH } from './paths'
import type {
  ConversationDoneEvent,
  ConversationWithMessages,
  StoredMessage,
} from './types'
import { NotReady } from '../../health/NotReady'
import { useReadiness } from '../../health/useReadiness'
import { ChatView } from '../../llm/ChatView'
import type { ViewMessage } from '../../llm/Message'
import { isStreaming, useStreamedAnswer } from '../../llm/useStreamedAnswer'

// What the page needs from the backend, and its words for the database's check.
const NEEDED = ['llm', 'conversations']
const READINESS_WORDS = {
  conversations:
    "The database can't be reached: conversations can't be saved or listed.",
}

// Its words for a failed answer: the conversation may have been deleted meanwhile.
const FAILURE_WORDS: Words = {
  404: 'This conversation no longer exists: it was deleted, perhaps in another tab.',
  503: "The model or the database can't be reached right now. If the app was just started, the model may still be loading: try again in a minute.",
}

interface Props {
  // An answer was stored: the list of conversations changes.
  readonly onStored: () => void
}

export function ConversationPage({ onStored }: Props) {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const { answer, ask, stop, reset } =
    useStreamedAnswer<ConversationDoneEvent>()
  const [conversation, setConversation] =
    useState<ConversationWithMessages | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Opening a stored conversation: neither the empty page nor its messages yet.
  const [loading, setLoading] = useState(false)
  // The conversation this page just created, and is moving to: there's nothing to load yet, and its
  // first answer is streaming. The move clears it, whenever React makes it: an answer that fails
  // at once can end before then.
  const created = useRef<string | null>(null)

  // Another conversation, or a new one: stop what was streaming, and load it.
  useEffect(() => {
    if (conversationId !== undefined && conversationId === created.current) {
      created.current = null
      return
    }
    reset()
    setError(null)
    setConversation(null)
    setLoading(conversationId !== undefined)
    if (conversationId === undefined) {
      return
    }
    let current = true
    openConversation(conversationId)
      .then((opened) => current && setConversation(opened))
      .catch((failure: unknown) => current && setError(failureMessage(failure)))
      .finally(() => current && setLoading(false))
    return () => {
      current = false
    }
  }, [conversationId, reset])

  const readiness = useReadiness(NEEDED, isStreaming(answer.phase))

  async function onSend(content: Content, parameters: Parameters) {
    setError(null)
    let id = conversationId
    if (id === undefined) {
      try {
        id = (await startConversation()).id
      } catch (failure) {
        setError(failureMessage(failure))
        readiness.recheck()
        return
      }
      created.current = id
      void navigate(`${PATH}/${id}`)
    }
    const stored = id
    const outcome = await ask(content, (signal) =>
      askStream(stored, content, parameters, signal),
    )
    // It failed, or worked while the notice was up: is the backend ready now?
    if (outcome === null || readiness.notReady.length > 0) {
      readiness.recheck()
    }
    if (outcome !== null) {
      onStored()
      // Show the turn as the backend stored it, in place of the streamed answer.
      try {
        setConversation(await openConversation(stored))
        reset()
      } catch (failure) {
        setError(failureMessage(failure))
      }
    }
  }

  return (
    <ChatView
      messages={(conversation?.messages ?? []).map(viewOf)}
      answer={answer}
      onSend={(content, parameters) => void onSend(content, parameters)}
      onStop={stop}
      error={error}
      notice={
        <NotReady notReady={readiness.notReady} words={READINESS_WORDS} />
      }
      loading={loading}
      unkept="Nothing was stored."
      words={FAILURE_WORDS}
    />
  )
}

// A stored message as the view shows it: how its answer was made comes from the backend's timing.
function viewOf(message: StoredMessage): ViewMessage {
  return {
    ...message,
    details: message.details && {
      summary: summary(message.details),
      breakdown: breakdown(message.details),
    },
  }
}
