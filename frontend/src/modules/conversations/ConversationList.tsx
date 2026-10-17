// The sidebar's conversations, as in llama.cpp's web UI: a new chat at the top, then the user's
// conversations, newest first under the day of their last answer. Open one, or delete it after a
// confirmation in its row (docs/foundations.md#the-conversation-list).
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useMatch, useNavigate } from 'react-router'
import { SquarePen, Trash2 } from 'lucide-react'
import { failureMessage } from '../../api/client'
import type { ConversationSummary } from './types'
import { POLL_MS } from '../../polling'
import styles from './ConversationList.module.css'
import { groupByDay } from './days'
import { PATH } from './paths'
import type { Conversations } from './useConversations'

interface Props {
  readonly conversations: Conversations
  // A conversation, or a new chat, was chosen: a drawer closes.
  readonly onChoose: () => void
}

export function ConversationList({ conversations, onChoose }: Props) {
  const { list, loadedAt, error, remove } = conversations
  const current = useMatch(`${PATH}/:conversationId`)?.params.conversationId
  const navigate = useNavigate()
  const heading = useRef<HTMLHeadingElement>(null)
  // Only conversations with a stored turn: one whose first answer failed or was stopped has no
  // title, and stays open where it was made.
  const listed = (list ?? []).filter(
    (conversation) => conversation.title !== null,
  )

  async function onDelete(conversationId: string) {
    await remove(conversationId)
    if (conversationId === current) {
      void navigate(PATH)
    }
    heading.current?.focus() // the row that had it is gone
  }

  return (
    <div className={styles.conversations}>
      <Link to={PATH} className={styles.row} onClick={onChoose}>
        <SquarePen aria-hidden="true" />
        New chat
      </Link>
      <h2 ref={heading} tabIndex={-1} className="sr-only">
        Conversations
      </h2>
      <div className={styles.scroll}>
        {error !== null && (
          <p className={styles.note} role="status">
            The conversations couldn't be loaded ({error.replace(/\.$/, '')}).
            Trying again every {POLL_MS / 1000} seconds.
          </p>
        )}
        {list !== null && listed.length === 0 && error === null && (
          <p className={styles.note}>Your conversations will be listed here.</p>
        )}
        {groupByDay(listed, loadedAt ?? new Date(0)).map((group) => (
          <section key={group.label} aria-labelledby={`day-${group.label}`}>
            <h3 id={`day-${group.label}`} className={styles.day}>
              {group.label}
            </h3>
            <ul className={styles.list}>
              {group.conversations.map((conversation) => (
                <Entry
                  key={conversation.id}
                  conversation={conversation}
                  onOpen={onChoose}
                  onDelete={onDelete}
                />
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
}

interface EntryProps {
  readonly conversation: ConversationSummary
  readonly onOpen: () => void
  readonly onDelete: (id: string) => Promise<void>
}

// One conversation: a link to it, and a button that asks, in place, before deleting it.
function Entry({ conversation, onOpen, onDelete }: EntryProps) {
  const title = conversation.title ?? ''
  const [phase, setPhase] = useState<'idle' | 'confirming' | 'deleting'>('idle')
  const [error, setError] = useState<string | null>(null)
  const cancel = useRef<HTMLButtonElement>(null)
  const trash = useRef<HTMLButtonElement>(null)
  const backToTrash = useRef(false)

  // Asking, the focus goes to Cancel, so a stray Enter deletes nothing; cancelled, back to the
  // button that asked.
  useEffect(() => {
    if (phase === 'confirming') {
      cancel.current?.focus()
    } else if (phase === 'idle' && backToTrash.current) {
      backToTrash.current = false
      trash.current?.focus()
    }
  }, [phase])

  async function confirm() {
    setPhase('deleting')
    setError(null)
    try {
      await onDelete(conversation.id)
    } catch (failure) {
      setError(failureMessage(failure))
      setPhase('confirming')
    }
  }

  function back() {
    backToTrash.current = true
    setPhase('idle')
    setError(null)
  }

  if (phase !== 'idle') {
    return (
      <li>
        <div
          className={styles.confirm}
          role="group"
          aria-label={`Delete “${title}”?`}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.stopPropagation() // cancels the delete, not the drawer
              back()
            }
          }}
        >
          <span>Delete this conversation?</span>
          <span className={styles.actions}>
            <button
              type="button"
              className={styles.danger}
              disabled={phase === 'deleting'}
              onClick={() => void confirm()}
            >
              Delete
            </button>
            <button
              type="button"
              ref={cancel}
              className={styles.cancel}
              disabled={phase === 'deleting'}
              onClick={back}
            >
              Cancel
            </button>
          </span>
          {error !== null && (
            <span className={styles.rowError} role="alert">
              {error}
            </span>
          )}
        </div>
      </li>
    )
  }

  return (
    <li className={styles.entry}>
      <NavLink
        to={`${PATH}/${conversation.id}`}
        className={({ isActive }) =>
          isActive ? `${styles.link} ${styles.active}` : styles.link
        }
        title={`${title}\nLast answer: ${WHEN.format(new Date(conversation.updated_at))}`}
        onClick={onOpen}
      >
        {title}
      </NavLink>
      <button
        type="button"
        ref={trash}
        className={styles.delete}
        aria-label={`Delete “${title}”`}
        onClick={() => setPhase('confirming')}
      >
        <Trash2 aria-hidden="true" />
      </button>
    </li>
  )
}

const WHEN = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})
