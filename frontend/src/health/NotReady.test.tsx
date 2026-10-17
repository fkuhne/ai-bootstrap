import { act, render, renderHook, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { POLL_MS } from '../polling'
import { fakeApi, READY } from '../test/api'
import { NotReady } from './NotReady'
import { useReadiness } from './useReadiness'

const LOADING = {
  status: 'unavailable',
  checks: { llm: 'unavailable', search: 'ok' },
}
const LLM = ['llm']

beforeEach(() => vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] }))
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

// A page that needs the given checks, with its own words for some, as a module's page is.
function Page({
  needed = LLM,
  words,
}: {
  needed?: readonly string[]
  words?: Record<string, string>
}) {
  const readiness = useReadiness(needed, false)
  return (
    <main>
      <NotReady notReady={readiness.notReady} words={words} />
    </main>
  )
}

function renderApp() {
  render(<Page />)
}

test('a model still loading is named, and the notice goes once it answers', async () => {
  let ready = false
  fakeApi({
    'GET /api/health/ready': () =>
      Response.json(ready ? READY : LOADING, { status: ready ? 200 : 503 }),
  })
  renderApp()

  const notice = await within(screen.getByRole('main')).findByRole('status')
  expect(notice).toHaveTextContent("The model isn't answering yet.")
  expect(notice).toHaveTextContent('Checking again every 3 seconds.')

  ready = true
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS))

  expect(
    within(screen.getByRole('main')).queryByRole('status'),
  ).not.toBeInTheDocument()
})

test('a backend that cannot be reached is said to be unreachable', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
  )
  renderApp()

  expect(
    await within(screen.getByRole('main')).findByRole('status'),
  ).toHaveTextContent("The backend can't be reached.")
})

test("each check the page needs has its own sentence; others aren't the page's concern", async () => {
  fakeApi({
    'GET /api/health/ready': () =>
      Response.json(
        {
          status: 'unavailable',
          checks: {
            llm: 'ok',
            store: 'unavailable',
            search: 'unavailable',
            other: 'unavailable',
          },
        },
        { status: 503 },
      ),
  })
  render(
    <Page
      needed={['llm', 'store', 'search']}
      words={{ store: "The store can't be reached." }}
    />,
  )

  const notice = await within(screen.getByRole('main')).findByRole('status')
  expect(notice).toHaveTextContent("The store can't be reached.")
  // A check the page has no sentence for is still named.
  expect(notice).toHaveTextContent("The search isn't ready.")
  // Another module's check, which the page doesn't need, isn't shown.
  expect(notice).not.toHaveTextContent('other')
  expect(notice).not.toHaveTextContent("The model isn't answering")
})

test('nothing is checked while an answer streams: a busy single-slot model would look unavailable', async () => {
  const fetchMock = fakeApi({
    'GET /api/health/ready': () => Response.json(LOADING, { status: 503 }),
  })
  const { result, rerender } = renderHook(
    ({ paused }) => useReadiness(LLM, paused),
    { initialProps: { paused: false } },
  )
  await act(() => vi.advanceTimersByTimeAsync(0))
  expect(result.current.notReady).toEqual(['llm'])
  const checks = () =>
    fetchMock.mock.calls.filter(([url]) => (url as string).includes('/ready'))
      .length
  const before = checks()

  rerender({ paused: true })
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 3))
  expect(checks()).toBe(before)

  rerender({ paused: false })
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS))
  expect(checks()).toBe(before + 1)
})

test('a backend that was not up yet is noticed within 3 seconds of coming up', async () => {
  let up = false
  fakeApi({
    'GET /api/health/ready': () =>
      up
        ? Response.json(READY)
        : Promise.reject(new TypeError('Failed to fetch')),
  })
  renderApp()
  expect(
    await within(screen.getByRole('main')).findByRole('status'),
  ).toHaveTextContent("The backend can't be reached.")

  // The page didn't wait for the backend, and doesn't ask for a button to look again.
  up = true
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS))

  expect(
    within(screen.getByRole('main')).queryByRole('status'),
  ).not.toBeInTheDocument()
})

test('a check is never started while the one before it is still waiting', async () => {
  let checks = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(() => {
      checks += 1
      // The first answers at once; the model's ping then outlasts every interval.
      return checks === 1
        ? Promise.resolve(Response.json(LOADING, { status: 503 }))
        : new Promise<Response>(() => undefined)
    }),
  )
  renderHook(() => useReadiness(LLM, false))
  await act(() => vi.advanceTimersByTimeAsync(0))
  expect(checks).toBe(1)

  await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 5))

  expect(checks).toBe(2) // one tick started a check; the later ticks waited for it
})

test('an older check that answers late does not overwrite a newer one', async () => {
  const answers: Array<(response: Response) => void> = []
  vi.stubGlobal(
    'fetch',
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          answers.push(resolve)
        }),
    ),
  )
  const { result } = renderHook(() => useReadiness(LLM, true)) // the first check, still waiting
  act(() => result.current.recheck()) // a second, newer one

  await act(async () => answers[1]?.(Response.json(READY)))
  await act(async () => answers[0]?.(Response.json(LOADING, { status: 503 })))

  expect(result.current.notReady).toEqual([])
})
