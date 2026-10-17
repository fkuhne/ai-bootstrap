// The message form, as in llama.cpp's web UI: a rounded box with the text, what's attached, a
// button that attaches images, audio or video when the model takes them, the model's name, how
// much it reasons, and a round button that sends, or stops the answer being written.
import {
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import {
  ArrowUp,
  Lightbulb,
  LightbulbOff,
  Paperclip,
  Square,
  X,
} from 'lucide-react'
import type { Content, Input } from '../api/types'
import { newUuid } from '../api/userId'
import {
  type Attachment,
  acceptFor,
  fileKind,
  readAttachment,
} from './attachments'
import styles from './Composer.module.css'
import { contentOf, inWords, type Kind } from './content'
import { MediaView } from './MediaView'
import { LABELS, LEVELS, levelOf, type ReasoningLevel } from './reasoningLevel'

interface Props {
  // What the model takes: text, and the kinds of files it can be sent.
  readonly inputs: readonly Input[]
  // The model's name, when it's known.
  readonly model: string | null
  // How much the model reasons, sent with each message.
  readonly reasoning: ReasoningLevel
  readonly onReasoning: (level: ReasoningLevel) => void
  // An answer is being written: the round button stops it instead of sending.
  readonly busy: boolean
  readonly onSend: (content: Content) => void
  readonly onStop: () => void
}

export function Composer({
  inputs,
  model,
  reasoning,
  onReasoning,
  busy,
  onSend,
  onStop,
}: Props) {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState<readonly Attachment[]>([])
  const [problem, setProblem] = useState<string | null>(null)
  const box = useRef<HTMLTextAreaElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const hint = useId()
  const kinds = inputs.filter((input): input is Kind => input !== 'text')
  const content = contentOf(
    text,
    attachments.map((attachment) => attachment.part),
  )

  // The box grows with its text, up to the height its CSS allows.
  useLayoutEffect(() => {
    const element = box.current
    if (element !== null) {
      element.style.height = 'auto'
      element.style.height = `${element.scrollHeight}px`
    }
  }, [text])

  function send() {
    if (content === null || busy) {
      return
    }
    onSend(content)
    setText('')
    setAttachments([])
    setProblem(null)
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    send()
  }

  // Enter sends, Shift+Enter starts a new line; Enter that confirms an input method's
  // composition, as for Japanese, sends nothing.
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === 'Enter' &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault()
      send()
    }
  }

  async function attach(files: readonly File[]) {
    setProblem(null)
    for (const file of files) {
      const kind = fileKind(file)
      if (kind === null || !kinds.includes(kind)) {
        setProblem(
          `${file.name} can't be sent: the model takes ${inWords(kinds)}.`,
        )
        continue
      }
      try {
        const part = await readAttachment(file, kind)
        setAttachments((current) => [
          ...current,
          { id: newUuid(), name: file.name, part },
        ])
      } catch {
        setProblem(`${file.name} couldn't be read.`)
      }
    }
  }

  return (
    <form className={styles.form} onSubmit={onSubmit}>
      <div className={styles.box}>
        {attachments.length > 0 && (
          <ul className={styles.attachments} aria-label="Attached">
            {attachments.map((attachment) => (
              <li key={attachment.id} className={styles.attachment}>
                <MediaView part={attachment.part} name={attachment.name} />
                <button
                  type="button"
                  className={styles.remove}
                  aria-label={`Remove ${attachment.name}`}
                  onClick={() =>
                    setAttachments((current) =>
                      current.filter((other) => other.id !== attachment.id),
                    )
                  }
                >
                  <X aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <textarea
          ref={box}
          className={styles.input}
          aria-label="Message"
          aria-describedby={hint}
          placeholder="Type a message"
          rows={1}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <p id={hint} className="sr-only">
          Enter sends; Shift+Enter starts a new line.
        </p>
        <div className={styles.actions}>
          {kinds.length > 0 && (
            <>
              <button
                type="button"
                className="icon-button"
                aria-label={`Attach ${inWords(kinds)}`}
                title={`Attach ${inWords(kinds)}`}
                onClick={() => picker.current?.click()}
              >
                <Paperclip aria-hidden="true" />
              </button>
              <input
                ref={picker}
                type="file"
                className={styles.picker}
                data-testid="attach"
                tabIndex={-1}
                aria-hidden="true"
                multiple
                accept={acceptFor(kinds)}
                onChange={(event) => {
                  const files = Array.from(event.target.files ?? [])
                  event.target.value = '' // the same file can be chosen again
                  void attach(files)
                }}
              />
            </>
          )}
          {model !== null && (
            <span className={styles.model} title="The model that answers">
              {model}
            </span>
          )}
          <label
            className={styles.reasoning}
            title="How much the model reasons before it answers. Auto leaves it to the model."
          >
            {reasoning === 'none' ? (
              <LightbulbOff aria-hidden="true" />
            ) : (
              <Lightbulb aria-hidden="true" />
            )}
            <select
              aria-label="Reasoning"
              value={reasoning}
              onChange={(event) => onReasoning(levelOf(event.target.value))}
            >
              {LEVELS.map((level) => (
                <option key={level} value={level}>
                  {LABELS[level]}
                </option>
              ))}
            </select>
          </label>
          {busy ? (
            <button
              type="button"
              className={styles.stop}
              aria-label="Stop"
              title="Stop"
              onClick={onStop}
            >
              <Square aria-hidden="true" />
            </button>
          ) : (
            <button
              type="submit"
              className={styles.send}
              aria-label="Send"
              title="Send"
              disabled={content === null}
            >
              <ArrowUp aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
      {problem !== null && (
        <p className={styles.problem} role="alert">
          {problem}
        </p>
      )}
    </form>
  )
}
