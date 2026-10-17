import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { postStream } from '../api/stream'
import { body, event } from '../test/streams'
import { useStreamedAnswer } from './useStreamedAnswer'

const ID = '6c685ab5-5d6c-4212-9095-ae6d5c696214'
const DONE = { model: 'local-model', finish_reason: 'stop', usage: null }
type Done = typeof DONE

// Where the answers come from: a page passes its own stream.
const SOURCE = (signal: AbortSignal) =>
  postStream<Done>('/chat/stream', { messages: [] }, signal)

// Each request gets the next body; a body left open stays so until the request is aborted.
function responds(...bodies: { chunks: string[]; stayOpen?: boolean }[]) {
  let call = 0
  const fetchMock = vi.fn<typeof fetch>((_url, init) => {
    const next = bodies[Math.min(call, bodies.length - 1)] ?? { chunks: [] }
    call += 1
    return Promise.resolve(
      new Response(
        body(next.chunks, { signal: init?.signal, stayOpen: next.stayOpen }),
      ),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

beforeEach(() =>
  localStorage.setItem('user-id', '3f2b8c1e-6d4a-4f7e-9b0a-2c5d8e1f4a7b'),
)
afterEach(() => vi.unstubAllGlobals())

test('an answer goes from waiting to reasoning to writing', async () => {
  responds({
    chunks: [
      event('reasoning', { text: 'A greeting; ' }),
      event('reasoning', { text: 'answer in kind.' }),
    ],
    stayOpen: true,
  })
  const { result } = renderHook(() => useStreamedAnswer<Done>())

  act(() => {
    void result.current.ask('Hi', SOURCE)
  })
  expect(result.current.answer).toMatchObject({
    phase: 'waiting',
    question: 'Hi',
  })

  await waitFor(() =>
    expect(result.current.answer.reasoning).toBe('A greeting; answer in kind.'),
  )
  expect(result.current.answer.phase).toBe('reasoning')
})

test('a finished answer holds its outcome, and asking resolves with it', async () => {
  responds({
    chunks: [
      event('reasoning', { text: 'Hm.' }),
      event('token', { text: 'Hel' }),
      event('token', { text: 'lo' }),
      event('done', DONE),
    ],
  })
  const { result } = renderHook(() => useStreamedAnswer<Done>())

  let outcome: unknown
  await act(async () => {
    outcome = await result.current.ask('Hi', SOURCE)
  })

  expect(outcome).toEqual({ text: 'Hello', reasoning: 'Hm.', done: DONE })
  expect(result.current.answer).toMatchObject({
    phase: 'done',
    reasoning: 'Hm.',
    text: 'Hello',
  })
})

test('stopping closes the request, and the answer is marked stopped', async () => {
  const fetchMock = responds({
    chunks: [event('token', { text: 'Hel' })],
    stayOpen: true,
  })
  const { result } = renderHook(() => useStreamedAnswer<Done>())
  let asking: Promise<unknown> = Promise.resolve()
  act(() => {
    asking = result.current.ask('Hi', SOURCE)
  })
  await waitFor(() => expect(result.current.answer.text).toBe('Hel'))

  await act(async () => {
    result.current.stop()
    await asking
  })

  expect(result.current.answer.phase).toBe('stopped')
  expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true)
  await expect(asking).resolves.toBeNull()
})

test('an error event marks the answer failed, with its status', async () => {
  responds({
    chunks: [
      event('token', { text: 'Hel' }),
      event('error', { status: 504, detail: "The LLM didn't answer in time." }),
    ],
  })
  const { result } = renderHook(() => useStreamedAnswer<Done>())

  await act(async () => {
    await result.current.ask('Hi', SOURCE)
  })

  expect(result.current.answer).toMatchObject({
    phase: 'failed',
    failure: { status: 504, detail: "The LLM didn't answer in time." },
  })
})

test('a request refused before streaming marks the answer failed', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        Response.json({ detail: `No conversation ${ID}.` }, { status: 404 }),
      ),
    ),
  )
  const { result } = renderHook(() => useStreamedAnswer<Done>())

  await act(async () => {
    await result.current.ask('Hi', SOURCE)
  })

  expect(result.current.answer).toMatchObject({
    phase: 'failed',
    failure: { status: 404, detail: `No conversation ${ID}.` },
  })
})

test('a new question stops the one still streaming, which then changes nothing', async () => {
  const fetchMock = responds(
    { chunks: [event('token', { text: 'First' })], stayOpen: true },
    { chunks: [], stayOpen: true }, // the second is still waiting
  )
  const { result } = renderHook(() => useStreamedAnswer<Done>())
  act(() => {
    void result.current.ask('first question', SOURCE)
  })
  await waitFor(() => expect(result.current.answer.text).toBe('First'))

  await act(async () => {
    void result.current.ask('second question', SOURCE)
    await new Promise((resolve) => setTimeout(resolve, 20)) // the first stream winds down
  })

  expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true)
  // Not "stopped": that was the first question's end, and it belongs to no one now.
  expect(result.current.answer).toMatchObject({
    phase: 'waiting',
    question: 'second question',
    text: '',
  })
})

test('reset clears the answer and stops it; leaving the view stops it too', async () => {
  const fetchMock = responds({
    chunks: [event('token', { text: 'Hel' })],
    stayOpen: true,
  })
  const { result, unmount } = renderHook(() => useStreamedAnswer<Done>())
  act(() => {
    void result.current.ask('Hi', SOURCE)
  })
  await waitFor(() => expect(result.current.answer.phase).toBe('writing'))

  act(() => result.current.reset())

  expect(result.current.answer.phase).toBe('idle')
  expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true)

  act(() => {
    void result.current.ask('Again', SOURCE)
  })
  unmount()

  expect(fetchMock.mock.calls[1]?.[1]?.signal?.aborted).toBe(true)
})
