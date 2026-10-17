// A notice naming what can't answer yet (docs/foundations.md#the-web-ui). Asking still works: a
// model busy with another answer can look not ready. The core has words for the backend and the
// LLM; a page gives its own for the checks of the modules it uses.
import { TriangleAlert } from 'lucide-react'
import { POLL_MS } from '../polling'
import styles from './NotReady.module.css'

const MESSAGES: Readonly<Record<string, string>> = {
  backend: "The backend can't be reached.",
  llm: "The model isn't answering yet. It may be starting, which takes a minute or two, longer the first time while it downloads, or busy with another answer.",
}

export function NotReady({
  notReady,
  words = {},
}: {
  notReady: readonly string[]
  // The page's words for its modules' checks, by the check's name.
  words?: Readonly<Record<string, string>>
}) {
  if (notReady.length === 0) {
    return null
  }
  return (
    <div className={styles.notice} role="status">
      <TriangleAlert className={styles.icon} aria-hidden="true" />
      <div>
        {notReady.map((name) => (
          <p key={name}>
            {words[name] ?? MESSAGES[name] ?? `The ${name} isn't ready.`}
          </p>
        ))}
        <p className={styles.again}>
          Checking again every {POLL_MS / 1000} seconds.
        </p>
      </div>
    </div>
  )
}
