// The decision model's page (docs/foundations.md#the-decision-model): a text, typed questions
// about it, and the model's answers as probabilities. It opens with an example of each type.
import { type FormEvent, useState } from 'react'
import { Plus } from 'lucide-react'
import {
  explain,
  type Failure,
  failureOf,
  type Words,
} from '../../api/failures'
import { NotReady } from '../../health/NotReady'
import { useReadiness } from '../../health/useReadiness'
import { Answers } from './Answers'
import { decide } from './api'
import styles from './DecisionPage.module.css'
import { blank, build, type Draft, EXAMPLE_TEXT, example } from './form'
import { QuestionEditor } from './QuestionEditor'
import type { Decision } from './types'

// What the page needs from the backend, and its words for it.
const NEEDED = ['decision']
const READINESS_WORDS = {
  decision:
    "The decision model isn't answering yet. It may be starting, which takes a minute, longer the first time while it downloads.",
}

const FAILURE_WORDS: Words = {
  502: 'The decision model refused the questions.',
  503: "The decision model can't be reached right now. If the app was just started, it may still be loading: try again in a minute.",
  504: "The decision model didn't answer in time.",
}

interface Answered {
  // The questions as they were asked, so editing them doesn't change the answers shown.
  readonly asked: readonly Draft[]
  readonly decision: Decision
  readonly ms: number
}

export function DecisionPage() {
  const [text, setText] = useState(EXAMPLE_TEXT)
  const [drafts, setDrafts] = useState<readonly Draft[]>(example)
  const [problems, setProblems] = useState<readonly string[]>([])
  const [asking, setAsking] = useState(false)
  const [answered, setAnswered] = useState<Answered | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const readiness = useReadiness(NEEDED, asking)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const built = build(text, drafts)
    setProblems(built.problems ?? [])
    if (built.request === undefined) {
      return
    }
    setFailure(null)
    setAsking(true)
    const started = performance.now()
    try {
      const decision = await decide(built.request)
      setAnswered({ asked: drafts, decision, ms: performance.now() - started })
    } catch (error) {
      setFailure(failureOf(error))
      readiness.recheck()
    } finally {
      setAsking(false)
    }
  }

  const explanation = failure === null ? '' : explain(failure, FAILURE_WORDS)
  return (
    <div className={styles.page}>
      <div className={styles.column}>
        <header className={styles.header}>
          <h2>Decide</h2>
          <p>
            Ask typed questions about a text. The decision model answers each
            with probabilities, in a fraction of a second.
          </p>
        </header>
        <NotReady notReady={readiness.notReady} words={READINESS_WORDS} />
        <form
          className={styles.form}
          onSubmit={(event) => void onSubmit(event)}
        >
          <label className={styles.field}>
            Text
            <textarea
              rows={4}
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </label>
          <h3 className={styles.heading}>Questions</h3>
          {drafts.map((draft) => (
            <QuestionEditor
              key={draft.id}
              draft={draft}
              onChange={(changed) =>
                setDrafts((current) =>
                  current.map((other) =>
                    other.id === changed.id ? changed : other,
                  ),
                )
              }
              onRemove={() =>
                setDrafts((current) =>
                  current.filter((other) => other.id !== draft.id),
                )
              }
            />
          ))}
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.add}
              onClick={() =>
                setDrafts((current) => [...current, blank(current)])
              }
            >
              <Plus aria-hidden="true" />
              Add a question
            </button>
            <button type="submit" className={styles.decide} disabled={asking}>
              {asking ? 'Deciding…' : 'Decide'}
            </button>
          </div>
          {problems.length > 0 && (
            <ul className={styles.problems} role="alert">
              {problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          )}
          {failure !== null && (
            <div className={styles.failed} role="alert">
              <p>
                <strong>The questions failed.</strong> {explanation}
              </p>
              {failure.detail !== explanation && (
                <p className={styles.detail}>Details: {failure.detail}</p>
              )}
            </div>
          )}
        </form>
        {answered !== null && <Answers {...answered} />}
      </div>
    </div>
  )
}
