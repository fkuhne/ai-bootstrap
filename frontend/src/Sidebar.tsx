// The sidebar: the app's name, a button that closes it, and what it holds: the modules' entries, and
// the open module's own content (App.tsx). On a narrow screen it's a drawer over the page, closed
// by Escape too.
import type { ReactNode, Ref } from 'react'
import { Link } from 'react-router'
import { PanelLeftClose } from 'lucide-react'
import { APP_NAME } from './config'
import styles from './Sidebar.module.css'

interface Props {
  readonly id: string
  readonly headingRef: Ref<HTMLHeadingElement>
  readonly open: boolean
  // Open as a drawer, over the page.
  readonly drawer: boolean
  readonly onClose: () => void
  readonly children?: ReactNode
}

export function Sidebar({
  id,
  headingRef,
  open,
  drawer,
  onClose,
  children,
}: Props) {
  return (
    <nav
      id={id}
      className={drawer ? `${styles.sidebar} ${styles.drawer}` : styles.sidebar}
      aria-labelledby={`${id}-heading`}
      hidden={!open}
      onKeyDown={(event) => {
        if (drawer && event.key === 'Escape') {
          onClose()
        }
      }}
    >
      <div className={styles.top}>
        <h1
          id={`${id}-heading`}
          ref={headingRef}
          tabIndex={-1}
          className={styles.name}
        >
          <Link to="/">{APP_NAME}</Link>
        </h1>
        <button
          type="button"
          className="icon-button"
          aria-label="Close the sidebar"
          aria-controls={id}
          aria-expanded={true}
          onClick={onClose}
        >
          <PanelLeftClose aria-hidden="true" />
        </button>
      </div>
      {children}
    </nav>
  )
}
