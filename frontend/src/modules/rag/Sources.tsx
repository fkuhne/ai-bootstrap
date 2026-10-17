// The sources an answer was given, by their numbers: each one's title, document and similarity to
// the question, its text folded below. Those the answer cites are marked, so a reader can check
// what it says against them (docs/foundations.md#rag).
import { ChevronDown } from 'lucide-react'
import { citedIn } from './citations'
import styles from './Sources.module.css'
import type { RagSource } from './types'

export function Sources({
  sources,
  answer,
}: {
  sources: readonly RagSource[]
  answer: string
}) {
  if (sources.length === 0) {
    return null
  }
  const cited = citedIn(answer)
  return (
    <section className={styles.sources} aria-label="Sources">
      <ol className={styles.list}>
        {sources.map(({ number, chunk, similarity }) => (
          <li key={number}>
            <details className={styles.source}>
              <summary className={styles.summary}>
                <span
                  className={
                    cited.has(number)
                      ? `${styles.number} ${styles.cited}`
                      : styles.number
                  }
                >
                  {number}
                </span>
                <span className={styles.title}>
                  {chunk.title ?? chunk.source}
                </span>
                <span className={styles.meta}>
                  {chunk.title != null && `${chunk.source} · `}similarity{' '}
                  {similarity.toFixed(2)}
                  {cited.has(number) && ' · cited'}
                </span>
                <ChevronDown className={styles.chevron} aria-hidden="true" />
              </summary>
              <p className={styles.text}>{chunk.text}</p>
            </details>
          </li>
        ))}
      </ol>
    </section>
  )
}
