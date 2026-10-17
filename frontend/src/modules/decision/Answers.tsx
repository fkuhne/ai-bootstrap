// The model's answers, a card per question, in the order they were asked: each probability as a
// bar, with its percentage in words.
import styles from './DecisionPage.module.css'
import type { Draft } from './form'
import type { ChoiceAnswer, Decision, NoulAnswer, ScoreAnswer } from './types'

export function Answers({
  asked,
  decision,
  ms,
}: {
  asked: readonly Draft[]
  decision: Decision
  // How long the answers took, in milliseconds.
  ms: number
}) {
  return (
    <section className={styles.answers} aria-label="Answers">
      {asked.map((draft) => {
        const name = draft.name.trim()
        const answer = decision.answers[name]
        return (
          <article key={draft.id} className={styles.answer} aria-label={name}>
            <h3>{name}</h3>
            <p className={styles.instructions}>{draft.instructions}</p>
            {answer?.type === 'noul' && <Noul answer={answer} />}
            {answer?.type === 'choice' && <Choice answer={answer} />}
            {answer?.type === 'score' && <Score answer={answer} />}
            {answer === undefined && <p>No answer.</p>}
          </article>
        )
      })}
      <p className={styles.usage}>
        {decision.model}
        {decision.usage && ` · ${decision.usage.input_tokens} tokens of text`}
        {` · ${Math.round(ms)} ms`}
      </p>
    </section>
  )
}

function Noul({ answer }: { answer: NoulAnswer }) {
  return (
    <ul className={styles.bars}>
      <Bar label="Yes" value={answer.noul} />
    </ul>
  )
}

function Choice({ answer }: { answer: ChoiceAnswer }) {
  const ranked = Object.entries(answer.probabilities).sort(
    ([, a], [, b]) => b - a,
  )
  return (
    <>
      <ul className={styles.bars}>
        {ranked.map(([option, probability]) => (
          <Bar
            key={option}
            label={option}
            value={probability}
            chosen={option === answer.choice}
          />
        ))}
      </ul>
      <p className={styles.verdict}>
        Chose <strong>{answer.choice}</strong>, with a confidence of{' '}
        {percent(answer.confidence)}.
      </p>
    </>
  )
}

function Score({ answer }: { answer: ScoreAnswer }) {
  const levels = Object.keys(answer.legend).sort(
    (a, b) => Number(a) - Number(b),
  )
  const nearest = answer.legend[String(Math.round(answer.score))] ?? ''
  return (
    <>
      <ul className={styles.bars}>
        {levels.map((index) => (
          <Bar
            key={index}
            label={`${index}. ${answer.legend[index]}`}
            value={answer.probabilities[index] ?? 0}
            chosen={index === String(Math.round(answer.score))}
          />
        ))}
      </ul>
      <p className={styles.verdict}>
        Scored <strong>{answer.score.toFixed(2)}</strong> on 0 to{' '}
        {levels.length - 1}, nearest “{nearest}”, with a confidence of{' '}
        {percent(answer.confidence)}.
      </p>
    </>
  )
}

function Bar({
  label,
  value,
  chosen = false,
}: {
  label: string
  value: number
  chosen?: boolean
}) {
  return (
    <li className={chosen ? `${styles.bar} ${styles.chosen}` : styles.bar}>
      <span className={styles.label}>{label}</span>
      <span className={styles.track} aria-hidden="true">
        <span
          className={styles.fill}
          style={{ width: `${Math.min(Math.max(value, 0), 1) * 100}%` }}
        />
      </span>
      <span className={styles.value}>{percent(value)}</span>
    </li>
  )
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}
