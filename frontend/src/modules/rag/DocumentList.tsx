// The sidebar's content: a new chat, then the stored documents the page answers from, each with
// its number of chunks.
import { FileText, SquarePen } from 'lucide-react'
import { POLL_MS } from '../../polling'
import type { SidebarProps } from '../../uiModule'
import { useDocumentsChat } from './context'
import styles from './DocumentList.module.css'
import { useStoredDocuments } from './useStoredDocuments'

export function DocumentList({ onChoose }: SidebarProps) {
  const { messages, clear } = useDocumentsChat()
  const { list, error } = useStoredDocuments(messages.length)

  return (
    <div className={styles.documents}>
      <button
        type="button"
        className="sidebar-row"
        onClick={() => {
          clear()
          onChoose()
        }}
      >
        <SquarePen aria-hidden="true" />
        New chat
      </button>
      <h2 id="stored-documents" className={styles.heading}>
        Documents
      </h2>
      <div className={styles.scroll}>
        {error !== null && (
          <p className={styles.note} role="status">
            The documents couldn't be listed ({error.replace(/\.$/, '')}).
            Trying again every {POLL_MS / 1000} seconds.
          </p>
        )}
        {list !== null && list.length === 0 && error === null && (
          <p className={styles.note}>
            No documents stored yet. Your app stores them through the API;
            <code>docker compose run --rm rag-samples</code> stores samples.
          </p>
        )}
        {list !== null && list.length > 0 && (
          <ul className={styles.list} aria-labelledby="stored-documents">
            {list.map(({ source, chunks }) => (
              <li key={source} className={styles.row} title={source}>
                <FileText aria-hidden="true" />
                <span className={styles.name}>{source}</span>
                <span className={styles.count}>
                  {chunks.toLocaleString('en-US')}
                  <span className="sr-only">
                    {chunks === 1 ? ' chunk' : ' chunks'}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
