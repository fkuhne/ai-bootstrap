// One question, edited in place: its name, its type, its instructions, and its type's criteria, a
// choice's options or a scale's levels.
import type { ReactNode } from 'react'
import { Plus, X } from 'lucide-react'
import { type Draft, type Kind, KINDS, level, MAX_LEVELS, option } from './form'
import styles from './DecisionPage.module.css'

interface Props {
  readonly draft: Draft
  readonly onChange: (draft: Draft) => void
  readonly onRemove: () => void
}

export function QuestionEditor({ draft, onChange, onRemove }: Props) {
  const name = draft.name.trim() || 'this question'
  const change = (changed: Partial<Draft>) => onChange({ ...draft, ...changed })
  return (
    <fieldset className={styles.question}>
      <legend className="sr-only">{`Question “${name}”`}</legend>
      <div className={styles.row}>
        <label className={styles.field}>
          Name
          <input
            value={draft.name}
            onChange={(event) => change({ name: event.target.value })}
          />
        </label>
        <label className={styles.field}>
          Type
          <select
            value={draft.kind}
            onChange={(event) => change({ kind: event.target.value as Kind })}
          >
            {Object.entries(KINDS).map(([kind, label]) => (
              <option key={kind} value={kind}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="icon-button"
          aria-label={`Remove “${name}”`}
          title="Remove the question"
          onClick={onRemove}
        >
          <X aria-hidden="true" />
        </button>
      </div>
      <label className={styles.field}>
        Instructions
        <input
          value={draft.instructions}
          placeholder="What to decide, such as: Is the customer angry?"
          onChange={(event) => change({ instructions: event.target.value })}
        />
      </label>
      {draft.kind === 'choice' && (
        <Criteria
          label={`Options of “${name}”`}
          rows={draft.options.map((o, index) => (
            <div key={o.id} className={styles.row}>
              <input
                aria-label={`Option ${index + 1}`}
                placeholder="Name"
                value={o.name}
                onChange={(event) =>
                  change({
                    options: draft.options.map((other) =>
                      other.id === o.id
                        ? { ...other, name: event.target.value }
                        : other,
                    ),
                  })
                }
              />
              <input
                aria-label={`Option ${index + 1}'s description`}
                placeholder="Description, if it helps"
                value={o.description}
                onChange={(event) =>
                  change({
                    options: draft.options.map((other) =>
                      other.id === o.id
                        ? { ...other, description: event.target.value }
                        : other,
                    ),
                  })
                }
              />
              <Remove
                label={`Remove option ${index + 1}`}
                onClick={() =>
                  change({
                    options: draft.options.filter((other) => other.id !== o.id),
                  })
                }
              />
            </div>
          ))}
          add="Add an option"
          onAdd={() => change({ options: [...draft.options, option()] })}
        />
      )}
      {draft.kind === 'score' && (
        <Criteria
          label={`Levels of “${name}”, lowest first`}
          rows={draft.levels.map((l, index) => (
            <div key={l.id} className={styles.row}>
              <input
                aria-label={`Level ${index}`}
                placeholder={index === 0 ? 'The lowest, such as: can wait' : ''}
                value={l.text}
                onChange={(event) =>
                  change({
                    levels: draft.levels.map((other) =>
                      other.id === l.id
                        ? { ...other, text: event.target.value }
                        : other,
                    ),
                  })
                }
              />
              <Remove
                label={`Remove level ${index}`}
                onClick={() =>
                  change({
                    levels: draft.levels.filter((other) => other.id !== l.id),
                  })
                }
              />
            </div>
          ))}
          add="Add a level"
          onAdd={
            draft.levels.length < MAX_LEVELS
              ? () => change({ levels: [...draft.levels, level()] })
              : undefined
          }
        />
      )}
    </fieldset>
  )
}

function Criteria({
  label,
  rows,
  add,
  onAdd,
}: {
  label: string
  rows: readonly ReactNode[]
  add: string
  // None once the list is full.
  onAdd?: () => void
}) {
  return (
    <div className={styles.criteria} role="group" aria-label={label}>
      {rows}
      <button
        type="button"
        className={styles.add}
        disabled={onAdd === undefined}
        onClick={onAdd}
      >
        <Plus aria-hidden="true" />
        {add}
      </button>
    </div>
  )
}

function Remove({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      className="icon-button"
      aria-label={label}
      onClick={onClick}
    >
      <X aria-hidden="true" />
    </button>
  )
}
