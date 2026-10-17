import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router'
import { PanelLeftOpen } from 'lucide-react'
import styles from './App.module.css'
import { NotReady } from './health/NotReady'
import { MODULES } from './modules'
import { Sidebar } from './Sidebar'
import { type UiModule, visibleModules } from './uiModule'
import { useMediaQuery } from './useMediaQuery'
import { type ModulesOn, useModules } from './useModules'

// Below this width the sidebar is a drawer over the page. The CSS modules use the same width.
const NARROW = '(max-width: 767px)'

// The page's frame, laid out as llama.cpp's web UI is (docs/foundations.md#the-web-ui): the sidebar,
// and beside it the page of the module that's open. It shows the modules the backend has on, from
// `modules`, the app's list unless a test gives its own: their entries and the open one's sidebar
// content, their pages under their paths; `/` goes to the first.
export default function App({
  modules = MODULES,
}: {
  modules?: readonly UiModule[]
}) {
  const on = useModules()
  const visible = on.names === null ? [] : visibleModules(modules, on.names)
  const { pathname } = useLocation()
  const opened = visible.find(
    (module) =>
      pathname === `/${module.path}` || pathname.startsWith(`/${module.path}/`),
  )
  const ModuleSidebar = opened?.Sidebar
  const narrow = useMediaQuery(NARROW)
  // Open on a wide screen, and closed on a narrow one, until the user says otherwise.
  const [openWide, setOpenWide] = useState(true)
  const [openNarrow, setOpenNarrow] = useState(false)
  const open = narrow ? openNarrow : openWide
  const drawer = narrow && open
  const heading = useRef<HTMLHeadingElement>(null)
  const opener = useRef<HTMLButtonElement>(null)
  // Where the focus goes once the user has opened or closed the sidebar.
  const moved = useRef<'opened' | 'closed' | null>(null)

  // On a narrow screen, choosing something in the sidebar closes the drawer.
  function choose() {
    if (narrow) {
      show(false)
    }
  }

  function show(next: boolean) {
    moved.current = next ? 'opened' : 'closed'
    if (narrow) {
      setOpenNarrow(next)
    } else {
      setOpenWide(next)
    }
  }

  // Opened, the sidebar takes the focus; closed, the button that opens it does.
  useEffect(() => {
    if (moved.current === 'opened') {
      heading.current?.focus()
    } else if (moved.current === 'closed') {
      opener.current?.focus()
    }
    moved.current = null
  }, [open])

  return withProviders(
    visible,
    <div className={styles.app}>
      <Sidebar
        id="sidebar"
        headingRef={heading}
        open={open}
        drawer={drawer}
        onClose={() => show(false)}
      >
        {visible.length > 1 && (
          <ModuleEntries modules={visible} onChoose={choose} />
        )}
        {ModuleSidebar !== undefined && <ModuleSidebar onChoose={choose} />}
      </Sidebar>
      {/* While the drawer is open, the page behind it is inert: no focus, no clicks. */}
      <main className={styles.main} inert={drawer}>
        {!open && (
          <button
            ref={opener}
            type="button"
            className={`icon-button ${styles.opener}`}
            aria-label="Open the sidebar"
            aria-controls="sidebar"
            aria-expanded={false}
            onClick={() => show(true)}
          >
            <PanelLeftOpen aria-hidden="true" />
          </button>
        )}
        <Pages on={on} visible={visible} />
      </main>
      {drawer && (
        <div
          className={styles.backdrop}
          aria-hidden="true"
          onClick={() => show(false)}
        />
      )}
    </div>,
  )
}

// Each module's provider, around the shell, so its page and its sidebar share its state.
function withProviders(modules: readonly UiModule[], shell: ReactNode) {
  return modules.reduceRight(
    (children, { name, Provider }) =>
      Provider === undefined ? (
        children
      ) : (
        <Provider key={name}>{children}</Provider>
      ),
    shell,
  )
}

// An entry per module, when there's more than one to choose from.
function ModuleEntries({
  modules,
  onChoose,
}: {
  modules: readonly UiModule[]
  onChoose: () => void
}) {
  return (
    <ul className={styles.entries} aria-label="Pages">
      {modules.map(({ name, title, icon: Icon, path }) => (
        <li key={name}>
          <NavLink to={`/${path}`} className="sidebar-row" onClick={onChoose}>
            <Icon aria-hidden="true" />
            {title}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}

// The modules' pages, under their paths. Until the backend says which are on, there's none to
// show: while it can't be reached, a notice says so, and it's asked again.
function Pages({
  on,
  visible,
}: {
  on: ModulesOn
  visible: readonly UiModule[]
}) {
  const [first] = visible
  if (on.names === null) {
    return (
      on.failed && (
        <div className={styles.notice}>
          <NotReady notReady={['backend']} />
        </div>
      )
    )
  }
  if (first === undefined) {
    return (
      <p className={styles.empty}>
        No module with a page is on. Turn one on in the backend's settings.
      </p>
    )
  }
  return (
    <Routes>
      {visible.map(({ name, path, Page }) => (
        <Route key={name} path={`${path}/*`} element={<Page />} />
      ))}
      <Route path="*" element={<Navigate to={`/${first.path}`} replace />} />
    </Routes>
  )
}
