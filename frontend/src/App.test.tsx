import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createContext, useContext, useState, type ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { FileText, PenLine, Sparkles } from 'lucide-react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'
import { POLL_MS } from './polling'
import { fakeApi } from './test/api'
import { Location } from './test/Location'
import { mediaQueries } from './test/media'
import type { SidebarProps, UiModule } from './uiModule'

// Modules of the tests' own, as an app's would be: notes, with sidebar content and state its page
// shares; drafts, a page alone; and better notes, which replace the notes' page.
const Count = createContext<[number, (count: number) => void]>([0, () => {}])

function CountProvider({ children }: { children: ReactNode }) {
  return <Count value={useState(0)}>{children}</Count>
}

function NotesPage() {
  const [count, setCount] = useContext(Count)
  return (
    <>
      <h2>The notes</h2>
      <button type="button" onClick={() => setCount(count + 1)}>
        Add a note
      </button>
    </>
  )
}

function NotesSidebar({ onChoose }: SidebarProps) {
  const [count] = useContext(Count)
  return (
    <button type="button" onClick={onChoose}>
      {count} notes
    </button>
  )
}

const NOTES: UiModule = {
  name: 'notes',
  title: 'Notes',
  icon: FileText,
  path: 'notes',
  Page: NotesPage,
  Sidebar: NotesSidebar,
  Provider: CountProvider,
}

const DRAFTS: UiModule = {
  name: 'drafts',
  title: 'Drafts',
  icon: PenLine,
  path: 'drafts',
  Page: () => <h2>The drafts</h2>,
}

const BETTER: UiModule = {
  name: 'better',
  title: 'Better notes',
  icon: Sparkles,
  path: 'better',
  Page: () => <h2>The better notes</h2>,
  replaces: ['notes'],
}

const ALL = [NOTES, DRAFTS, BETTER]

afterEach(() => {
  window.matchMedia = mediaQueries(false)
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function renderAt(path: string, on: readonly string[]) {
  fakeApi({}, on)
  render(
    <MemoryRouter initialEntries={[path]}>
      <App modules={ALL} />
      <Location />
    </MemoryRouter>,
  )
}

test('the page names the app, and opens the first module the backend has on', async () => {
  renderAt('/', ['notes', 'drafts'])

  expect(
    screen.getByRole('heading', { level: 1, name: 'ai-bootstrap' }),
  ).toBeInTheDocument()
  expect(
    await screen.findByRole('heading', { name: 'The notes' }),
  ).toBeInTheDocument()
  expect(screen.getByTestId('location')).toHaveTextContent('/notes')
})

test('an unknown path goes to the first module', async () => {
  renderAt('/nowhere', ['drafts'])

  expect(
    await screen.findByRole('heading', { name: 'The drafts' }),
  ).toBeInTheDocument()
})

test("with more than one module on, the sidebar has an entry for each, and the open one's own content", async () => {
  const user = userEvent.setup()
  renderAt('/notes', ['notes', 'drafts'])
  const entries = await screen.findByRole('list', { name: 'Pages' })
  expect(
    within(entries)
      .getAllByRole('link')
      .map((link) => link.textContent),
  ).toEqual(['Notes', 'Drafts'])
  expect(within(entries).getByRole('link', { name: 'Notes' })).toHaveAttribute(
    'aria-current',
    'page',
  )
  expect(screen.getByRole('button', { name: '0 notes' })).toBeInTheDocument()

  await user.click(within(entries).getByRole('link', { name: 'Drafts' }))

  expect(
    screen.getByRole('heading', { name: 'The drafts' }),
  ).toBeInTheDocument()
  // The notes' sidebar content goes with their page.
  expect(
    screen.queryByRole('button', { name: '0 notes' }),
  ).not.toBeInTheDocument()
})

test('a module the backend has off has no entry and no page; one alone needs no entry', async () => {
  renderAt('/notes', ['drafts'])

  expect(
    await screen.findByRole('heading', { name: 'The drafts' }),
  ).toBeInTheDocument()
  expect(screen.queryByRole('list', { name: 'Pages' })).not.toBeInTheDocument()
  expect(screen.getByTestId('location')).toHaveTextContent('/drafts')
})

test("a module replaces another's page when both are on", async () => {
  renderAt('/notes', ['notes', 'drafts', 'better'])

  const entries = await screen.findByRole('list', { name: 'Pages' })
  expect(
    within(entries)
      .getAllByRole('link')
      .map((link) => link.textContent),
  ).toEqual(['Drafts', 'Better notes'])
  expect(
    await screen.findByRole('heading', { name: 'The drafts' }),
  ).toBeInTheDocument()
})

test("a module's provider lets its page and its sidebar share state", async () => {
  const user = userEvent.setup()
  renderAt('/notes', ['notes'])

  await user.click(await screen.findByRole('button', { name: 'Add a note' }))

  expect(screen.getByRole('button', { name: '1 notes' })).toBeInTheDocument()
})

test('with no module on, the page says so', async () => {
  renderAt('/', [])

  expect(
    await screen.findByText(/No module with a page is on/),
  ).toBeInTheDocument()
})

test("while the backend can't be reached, the page says so, and asks again until it answers", async () => {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
  let up = false
  const fetchMock = fakeApi({}, ['drafts'])
  const answer = fetchMock.getMockImplementation()
  fetchMock.mockImplementation((input, init) =>
    up
      ? (answer?.(input, init) ?? Promise.reject(new Error('no fake')))
      : Promise.reject(new TypeError('Failed to fetch')),
  )
  render(
    <MemoryRouter initialEntries={['/']}>
      <App modules={ALL} />
    </MemoryRouter>,
  )

  expect(
    await within(screen.getByRole('main')).findByRole('status'),
  ).toHaveTextContent("The backend can't be reached.")

  up = true
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS))

  expect(
    screen.getByRole('heading', { name: 'The drafts' }),
  ).toBeInTheDocument()
})

test('on a wide screen the sidebar is open, and closes and opens again by its buttons', async () => {
  const user = userEvent.setup()
  renderAt('/', ['notes'])
  await screen.findByRole('heading', { name: 'The notes' })
  const sidebar = screen.getByRole('navigation', { name: 'ai-bootstrap' })
  expect(sidebar).toBeVisible()

  await user.click(screen.getByRole('button', { name: 'Close the sidebar' }))

  expect(sidebar).not.toBeVisible()
  const opener = screen.getByRole('button', { name: 'Open the sidebar' })
  expect(opener).toHaveFocus()

  await user.click(opener)

  expect(sidebar).toBeVisible()
  expect(screen.getByRole('heading', { level: 1 })).toHaveFocus()
  expect(screen.getByRole('main')).not.toHaveAttribute('inert')
})

test('on a narrow screen the sidebar is a drawer: the page behind is inert, Escape closes it, and so does choosing', async () => {
  window.matchMedia = mediaQueries(true)
  const user = userEvent.setup()
  renderAt('/', ['notes'])
  await screen.findByRole('heading', { name: 'The notes' })
  const sidebar = screen.getByRole('navigation', { hidden: true })
  expect(sidebar).not.toBeVisible()

  await user.click(screen.getByRole('button', { name: 'Open the sidebar' }))

  expect(sidebar).toBeVisible()
  expect(screen.getByRole('main')).toHaveAttribute('inert')
  expect(screen.getByRole('heading', { level: 1 })).toHaveFocus()

  await user.keyboard('{Escape}')

  expect(sidebar).not.toBeVisible()
  expect(screen.getByRole('main')).not.toHaveAttribute('inert')
  expect(screen.getByRole('button', { name: 'Open the sidebar' })).toHaveFocus()

  await user.click(screen.getByRole('button', { name: 'Open the sidebar' }))
  await user.click(screen.getByRole('button', { name: '0 notes' }))

  expect(sidebar).not.toBeVisible()
})
