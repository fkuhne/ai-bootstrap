// A conversation's messages, laid out as llama.cpp's web UI does them: the user's in a faint
// bubble on the right, with what they attached above it; the model's as plain text, with its
// reasoning folded above it and how it was made below. A module turns its own messages into
// these, and may add its own below an answer, such as its sources.
import type { ReactNode } from 'react'
import { explain, type Failure, type Words } from '../api/failures'
import type { Content } from '../api/types'
import { mediaOf, textOf } from './content'
import { Markdown } from './Markdown'
import { MediaView } from './MediaView'
import styles from './Message.module.css'
import { Reasoning } from './Reasoning'
import type { StreamedAnswer } from './useStreamedAnswer'

// A message as the view shows it, whichever module keeps it.
export interface ViewMessage {
  readonly id: string
  readonly role: 'user' | 'assistant'
  readonly content: Content
  // The model's reasoning before its answer, when it showed it.
  readonly reasoning?: string | null
  // How the answer was made: a line under it, and more in its tooltip.
  readonly details?: {
    readonly summary: string
    readonly breakdown?: string
  } | null
  // What the module shows under the answer, such as the sources it was given.
  readonly extra?: ReactNode
}

export function UserMessage({ content }: { content: Content }) {
  const media = mediaOf(content)
  const text = textOf(content)
  return (
    <div className={styles.user}>
      {media.length > 0 && (
        <div className={styles.media}>
          {media.map((part, index) => (
            <MediaView key={index} part={part} />
          ))}
        </div>
      )}
      {text.trim() !== '' && <div className={styles.bubble}>{text}</div>}
    </div>
  )
}

export function AssistantMessage({ message }: { message: ViewMessage }) {
  return (
    <div className={styles.assistant}>
      {message.reasoning && <Reasoning text={message.reasoning} />}
      <Markdown text={textOf(message.content)} />
      {message.extra}
      {message.details && (
        <p className={styles.details} title={message.details.breakdown}>
          {message.details.summary}
        </p>
      )}
    </div>
  )
}

interface StreamingProps {
  readonly answer: StreamedAnswer
  // What a stopped or failed answer leaves behind, such as "Nothing was stored."
  readonly unkept?: string
  // The page's own words for a failure's status.
  readonly words?: Words
}

export function StreamingAnswer({ answer, unkept, words }: StreamingProps) {
  switch (answer.phase) {
    case 'idle':
      return null
    case 'waiting':
      return (
        <div className={styles.assistant}>
          <p className={`${styles.status} shimmer`} role="status">
            Processing…
          </p>
        </div>
      )
    case 'failed':
      return <Failed failure={answer.failure} unkept={unkept} words={words} />
    default:
      return (
        <div
          className={styles.assistant}
          aria-busy={answer.phase === 'reasoning' || answer.phase === 'writing'}
        >
          {answer.reasoning !== '' && (
            <Reasoning
              text={answer.reasoning}
              streaming={answer.phase === 'reasoning'}
            />
          )}
          {answer.text !== '' && <Markdown text={answer.text} />}
          {answer.phase === 'stopped' && (
            <p className={styles.note}>
              {unkept === undefined ? 'Stopped.' : `Stopped. ${unkept}`}
            </p>
          )}
        </div>
      )
  }
}

// What went wrong, in plain words, and the backend's own message as a detail.
function Failed({
  failure,
  unkept,
  words,
}: {
  failure: Failure | null
  unkept?: string
  words?: Words
}) {
  const explanation = failure === null ? '' : explain(failure, words)
  return (
    <div className={styles.failed} role="alert">
      <p>
        <strong>The answer failed.</strong> {explanation}{' '}
        {unkept === undefined ? '' : `${unkept} `}You can send it again.
      </p>
      {failure !== null && failure.detail !== explanation && (
        <p className={styles.detail}>Details: {failure.detail}</p>
      )}
    </div>
  )
}
