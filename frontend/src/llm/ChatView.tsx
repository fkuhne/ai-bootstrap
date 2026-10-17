// A chat with the model, as a page lays it out (docs/foundations.md#the-chat-view): the messages,
// the answer being streamed, and the message form with the model's name and how much it reasons.
// While it's empty, a greeting and the form sit in the middle of the page, as in llama.cpp's web
// UI. The page that uses it keeps the messages, and says where answers come from.
import { useEffect, useRef, type ReactNode } from 'react'
import type { Words } from '../api/failures'
import type { Content, Input, Parameters } from '../api/types'
import styles from './ChatView.module.css'
import { Composer } from './Composer'
import { inWords, type Kind } from './content'
import {
  AssistantMessage,
  StreamingAnswer,
  UserMessage,
  type ViewMessage,
} from './Message'
import { parametersFor, useReasoningLevel } from './reasoningLevel'
import { useModel } from './useModel'
import { isStreaming, type StreamedAnswer } from './useStreamedAnswer'

const TEXT_ONLY: readonly Input[] = ['text']

interface Props {
  readonly messages: readonly ViewMessage[]
  readonly answer: StreamedAnswer
  readonly onSend: (content: Content, parameters: Parameters) => void
  readonly onStop: () => void
  // A problem to show under the messages, such as a conversation that can't be opened.
  readonly error: string | null
  // What isn't ready, shown above the form.
  readonly notice: ReactNode
  // Messages still loading: neither the empty page nor the messages yet.
  readonly loading?: boolean
  // What a stopped or failed answer leaves behind, and the page's words for a failure's status.
  readonly unkept?: string
  readonly words?: Words
  // What the page shows under the answer being streamed, as a message's `extra` under it.
  readonly answerExtra?: ReactNode
}

export function ChatView({
  messages,
  answer,
  onSend,
  onStop,
  error,
  notice,
  loading = false,
  unkept,
  words,
  answerExtra,
}: Props) {
  const model = useModel()
  const [reasoning, setReasoning] = useReasoningLevel()
  const end = useRef<HTMLDivElement>(null)

  // Keep the newest text in view as it arrives.
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' })
  }, [messages, answer.phase, answer.text, answer.reasoning])

  const inputs = model?.inputs ?? TEXT_ONLY
  const empty = !loading && messages.length === 0 && answer.phase === 'idle'
  const composer = (
    <Composer
      inputs={inputs}
      model={model?.model ?? null}
      reasoning={reasoning}
      onReasoning={setReasoning}
      busy={isStreaming(answer.phase)}
      onSend={(content) => onSend(content, parametersFor(reasoning))}
      onStop={onStop}
    />
  )
  const failed = error !== null && (
    <p className={styles.error} role="alert">
      {error}
    </p>
  )

  if (empty) {
    return (
      <div className={styles.page}>
        <div className={styles.centered}>
          {error === null && <Greeting inputs={inputs} />}
          {failed}
          {notice}
          {composer}
        </div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.scroller}>
        <div className={styles.column}>
          {loading && (
            <p className={styles.loading}>Loading the conversation…</p>
          )}
          <ol className={styles.messages} aria-label="Conversation">
            {messages.map((message) => (
              <li key={message.id}>
                {message.role === 'user' ? (
                  <UserMessage content={message.content} />
                ) : (
                  <AssistantMessage message={message} />
                )}
              </li>
            ))}
            {answer.phase !== 'idle' && (
              <>
                <li>
                  <UserMessage content={answer.question} />
                </li>
                <li>
                  <StreamingAnswer
                    answer={answer}
                    unkept={unkept}
                    words={words}
                  />
                  {answerExtra}
                </li>
              </>
            )}
          </ol>
          {failed}
          <div ref={end} />
        </div>
      </div>
      <div className={styles.bottom}>
        <div className={styles.column}>
          {notice}
          {composer}
        </div>
      </div>
    </div>
  )
}

function Greeting({ inputs }: { inputs: readonly Input[] }) {
  const kinds = inputs.filter((input): input is Kind => input !== 'text')
  return (
    <div className={styles.greeting}>
      <h2>Hello there</h2>
      <p>
        {kinds.length === 0
          ? 'Type a message to get started'
          : `Type a message, or attach ${inWords(kinds)}, to get started`}
      </p>
    </div>
  )
}
