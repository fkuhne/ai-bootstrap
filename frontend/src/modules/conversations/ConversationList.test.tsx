import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { POLL_MS } from '../../polling'
import { callsTo } from '../../test/api'
import { mediaQueries } from '../../test/media'
import { event } from '../../test/streams'
import {
  conversation,
  fakeConversationsApi,
  renderConversations,
  storedMessage,
} from './testing'

// The last answer at that day and hour of October 2026, in the browser's time zone; "now" is 4
// October at 15:00.
function at(day: number, hour: number, month = 9): string {
  return new Date(2026, month, day, hour).toISOString()
}

function summary(id: string, title: string | null, lastAnswer: string) {
  return { id, title, created_at: lastAnswer, updated_at: lastAnswer }
}

const NOTES = summary('c-notes', 'Summarize my notes', at(4, 10))
const SQL = summary('c-sql', 'Write a SQL join', at(4, 9))
const TRIP = summary('c-trip', 'Plan a weekend trip', at(3, 18))
const POEM = summary('c-poem', 'A poem about rain', at(1, 12))
const OLD = summary('c-old', 'What is an LLM?', at(20, 12, 8))
// Started, but its first answer failed: no title.
const EMPTY = summary('c-empty', null, at(4, 11))
const LIST = [EMPTY, NOTES, SQL, TRIP, POEM, OLD]

async function renderAt(path: string) {
  await renderConversations(path)
  // The sidebar, found even while it's a closed drawer, which has no name then.
  return screen.getByRole('navigation', { hidden: true })
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 4, 15, 0))
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  window.matchMedia = mediaQueries(false)
})

test('conversations with a stored turn are listed under the day of their last answer, the open one marked', async () => {
  fakeConversationsApi({
    'GET /api/conversations': () => Response.json(LIST),
    [`GET /api/conversations/${SQL.id}`]: () =>
      Response.json(conversation(SQL.id, [])),
  })

  const nav = await renderAt(`/conversations/${SQL.id}`)

  await within(nav).findByRole('link', { name: NOTES.title! })
  expect(
    within(nav)
      .getAllByRole('heading', { level: 3 })
      .map((heading) => heading.textContent),
  ).toEqual(['Today', 'Yesterday', 'Previous 7 days', 'Older'])
  // The one without a title isn't listed.
  expect(
    within(nav)
      .getAllByRole('listitem')
      .map((item) => item.textContent),
  ).toEqual([NOTES.title, SQL.title, TRIP.title, POEM.title, OLD.title])
  expect(within(nav).getByRole('link', { name: SQL.title! })).toHaveAttribute(
    'aria-current',
    'page',
  )
})

test('with no conversations yet, the list says where they will be', async () => {
  fakeConversationsApi({})

  const nav = await renderAt('/conversations')

  expect(
    await within(nav).findByText('Your conversations will be listed here.'),
  ).toBeInTheDocument()
})

test('deleting asks first, in the row; Cancel and Escape keep the conversation', async () => {
  const fetchMock = fakeConversationsApi({
    'GET /api/conversations': () => Response.json(LIST),
  })
  const nav = await renderAt('/conversations')
  const trash = await within(nav).findByRole('button', {
    name: `Delete “${NOTES.title}”`,
  })

  await userEvent.click(trash)
  const asking = within(nav).getByRole('group', {
    name: `Delete “${NOTES.title}”?`,
  })
  // A stray Enter cancels, not deletes.
  expect(within(asking).getByRole('button', { name: 'Cancel' })).toHaveFocus()

  await userEvent.click(within(asking).getByRole('button', { name: 'Cancel' }))
  const again = within(nav).getByRole('button', {
    name: `Delete “${NOTES.title}”`,
  })
  expect(again).toHaveFocus()

  await userEvent.click(again)
  await userEvent.keyboard('{Escape}')

  expect(
    within(nav).getByRole('link', { name: NOTES.title! }),
  ).toBeInTheDocument()
  expect(
    fetchMock.mock.calls.filter(([, init]) => init?.method === 'DELETE'),
  ).toEqual([])
})

test('a confirmed delete removes the conversation; deleting the open one starts a new chat', async () => {
  let list = LIST
  fakeConversationsApi({
    'GET /api/conversations': () => Response.json(list),
    [`GET /api/conversations/${SQL.id}`]: () =>
      Response.json(conversation(SQL.id, [])),
    [`DELETE /api/conversations/${SQL.id}`]: () => {
      list = list.filter((c) => c.id !== SQL.id)
      return new Response(null, { status: 204 })
    },
  })
  const nav = await renderAt(`/conversations/${SQL.id}`)

  await userEvent.click(
    await within(nav).findByRole('button', { name: `Delete “${SQL.title}”` }),
  )
  await userEvent.click(within(nav).getByRole('button', { name: 'Delete' }))

  await waitFor(() =>
    expect(
      within(nav).queryByRole('link', { name: SQL.title! }),
    ).not.toBeInTheDocument(),
  )
  // The page moves, and the focus with it, once the delete has answered: after the row is gone.
  await waitFor(() =>
    expect(screen.getByTestId('location')).toHaveTextContent(
      /^\/conversations$/,
    ),
  )
  expect(
    within(nav).getByRole('heading', { name: 'Conversations' }),
  ).toHaveFocus()
})

test('a failed delete says why, in its row, and keeps the conversation', async () => {
  fakeConversationsApi({
    'GET /api/conversations': () => Response.json(LIST),
    [`DELETE /api/conversations/${NOTES.id}`]: () =>
      Response.json(
        { detail: 'The database is unavailable.' },
        { status: 503 },
      ),
  })
  const nav = await renderAt('/conversations')

  await userEvent.click(
    await within(nav).findByRole('button', {
      name: `Delete “${NOTES.title}”`,
    }),
  )
  await userEvent.click(within(nav).getByRole('button', { name: 'Delete' }))

  expect(await within(nav).findByRole('alert')).toHaveTextContent(
    'The database is unavailable.',
  )
  expect(within(nav).getByRole('button', { name: 'Delete' })).toBeEnabled()
})

test('a list that fails to load says so, and loads again by itself every 3 seconds', async () => {
  vi.useRealTimers() // to fake the interval as well as the date, which beforeEach faked alone
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
  vi.setSystemTime(new Date(2026, 9, 4, 15, 0))
  let available = false
  const fetchMock = fakeConversationsApi({
    'GET /api/conversations': () =>
      available
        ? Response.json([NOTES])
        : Response.json(
            { detail: 'The database is unavailable.' },
            { status: 503 },
          ),
  })
  const nav = await renderAt('/conversations')

  expect(
    await within(nav).findByText(
      "The conversations couldn't be loaded (The database is unavailable). Trying again every 3 seconds.",
    ),
  ).toBeInTheDocument()
  const lists = () => callsTo(fetchMock, '/api/conversations').length
  const before = lists()
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS))
  expect(lists()).toBe(before + 1)

  available = true
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS))

  expect(
    await within(nav).findByRole('link', { name: NOTES.title! }),
  ).toBeInTheDocument()
  expect(within(nav).queryByText(/couldn't be loaded/)).not.toBeInTheDocument()
  // Loaded, it stops asking.
  const after = lists()
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 3))
  expect(lists()).toBe(after)
})

test('a new conversation is listed once its first answer is stored', async () => {
  const id = 'c-new'
  const question = 'What is a vector database?'
  let list: unknown[] = []
  fakeConversationsApi({
    'GET /api/conversations': () => Response.json(list),
    'POST /api/conversations': () =>
      Response.json(conversation(id, []), { status: 201 }),
    [`POST /api/conversations/${id}/messages/stream`]: () => {
      list = [summary(id, question, at(4, 15))]
      return new Response(
        event('token', { text: 'A store of embeddings.' }) +
          event('done', {
            model: 'local-model',
            finish_reason: 'stop',
            usage: null,
            question_id: 'q1',
            answer_id: 'a1',
          }),
      )
    },
    [`GET /api/conversations/${id}`]: () =>
      Response.json(
        conversation(id, [
          storedMessage('q1', 'user', question),
          storedMessage('a1', 'assistant', 'A store of embeddings.'),
        ]),
      ),
  })
  const nav = await renderAt('/conversations')
  await within(nav).findByText(/will be listed here/)

  await userEvent.type(
    screen.getByRole('textbox', { name: 'Message' }),
    `${question}{Enter}`,
  )

  const link = await within(nav).findByRole('link', { name: question })
  // Marked once the page has moved to it, which may follow the list by a moment.
  await waitFor(() => expect(link).toHaveAttribute('aria-current', 'page'))
})

test('on a narrow screen, choosing a conversation, or a new chat, closes the drawer', async () => {
  window.matchMedia = mediaQueries(true)
  fakeConversationsApi({
    'GET /api/conversations': () => Response.json([NOTES, SQL]),
    [`GET /api/conversations/${NOTES.id}`]: () =>
      Response.json(conversation(NOTES.id, [])),
  })
  const nav = await renderAt('/conversations')

  await userEvent.click(
    screen.getByRole('button', { name: 'Open the sidebar' }),
  )
  await userEvent.click(
    await within(nav).findByRole('link', { name: NOTES.title! }),
  )

  expect(nav).not.toBeVisible()
  expect(screen.getByTestId('location')).toHaveTextContent(
    `/conversations/${NOTES.id}`,
  )

  await userEvent.click(
    screen.getByRole('button', { name: 'Open the sidebar' }),
  )
  await userEvent.click(within(nav).getByRole('link', { name: 'New chat' }))

  expect(nav).not.toBeVisible()
  expect(screen.getByTestId('location')).toHaveTextContent(/^\/conversations$/)
  expect(
    screen.getByRole('heading', { name: 'Hello there' }),
  ).toBeInTheDocument()
})
