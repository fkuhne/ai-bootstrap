import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { body, event } from '../test/streams'
import { postStream, type StreamEvent } from './stream'

const ID = '6c685ab5-5d6c-4212-9095-ae6d5c696214'
const USER = '3f2b8c1e-6d4a-4f7e-9b0a-2c5d8e1f4a7b'
const DONE = {
  model: 'local',
  finish_reason: 'stop',
  usage: { prompt_tokens: 12, completion_tokens: 3, total_tokens: 15 },
}
type Done = typeof DONE
const PATH = `/things/${ID}/stream`

// A streamed POST, as a module makes one: its path and body, any parameters within.
function ask(
  content: unknown,
  parameters: Record<string, unknown>,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent<Done>> {
  return postStream<Done>(PATH, { content, parameters }, signal)
}

function streams(chunks: string[], options: { stayOpen?: boolean } = {}) {
  const fetchMock = vi.fn<typeof fetch>((_url, init) =>
    Promise.resolve(
      new Response(body(chunks, { signal: init?.signal, ...options }), {
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function collect(
  events: AsyncGenerator<StreamEvent<Done>>,
): Promise<StreamEvent<Done>[]> {
  const found: StreamEvent<Done>[] = []
  for await (const received of events) {
    found.push(received)
  }
  return found
}

beforeEach(() => localStorage.setItem('user-id', USER))
afterEach(() => vi.unstubAllGlobals())

test('the answer streams as typed events, in order', async () => {
  const fetchMock = streams([
    event('reasoning', { text: 'A greeting.' }),
    ': ping\n\n',
    event('token', { text: 'Hel' }),
    event('token', { text: 'lo' }),
    event('done', DONE),
  ])

  const found = await collect(ask('Hi', {}))

  expect(found.map((e) => e.type)).toEqual([
    'reasoning',
    'token',
    'token',
    'done',
  ])
  expect(found[3]).toEqual({ type: 'done', data: DONE })
  const [url, init] = fetchMock.mock.calls[0] ?? []
  expect(url).toBe(`/api${PATH}`)
  expect(new Headers(init?.headers).get('Accept')).toBe('text/event-stream')
  expect(new Headers(init?.headers).get('X-User-Id')).toBe(USER)
  expect(JSON.parse(init?.body as string)).toEqual({
    content: 'Hi',
    parameters: {},
  })
})

test("a module's own events pass when it names them, and others are dropped", async () => {
  streams([
    event('sources', { sources: [{ number: 1 }] }),
    event('unknown', { anything: true }),
    event('token', { text: 'Hi' }),
    event('done', DONE),
  ])
  type Sources = { type: 'sources'; data: { sources: { number: number }[] } }

  const found: StreamEvent<Done, Sources>[] = []
  for await (const received of postStream<Done, Sources>(PATH, {}, undefined, [
    'sources',
  ])) {
    found.push(received)
  }

  expect(found.map((e) => e.type)).toEqual(['sources', 'token', 'done'])
  expect(found[0]).toEqual({
    type: 'sources',
    data: { sources: [{ number: 1 }] },
  })
  // Without the name, the same stream holds only the core's events.
  streams([event('sources', { sources: [] }), event('done', DONE)])
  expect((await collect(ask('Hi', {}))).map((e) => e.type)).toEqual(['done'])
})

test('content with parts, and parameters, are sent as they are', async () => {
  const fetchMock = streams([event('done', DONE)])
  const content = [
    { type: 'text' as const, text: 'What color?' },
    {
      type: 'image_url' as const,
      image_url: { url: 'data:image/png;base64,AAAA' },
    },
  ]

  await collect(ask(content, { reasoning_effort: 'low' }))

  expect(JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)).toEqual({
    content,
    parameters: { reasoning_effort: 'low' },
  })
})

test('an error event ends the stream', async () => {
  streams([
    event('token', { text: 'Hel' }),
    event('error', {
      status: 503,
      detail: "The LLM endpoint can't be reached.",
    }),
  ])

  const found = await collect(ask('Hi', {}))

  expect(found.at(-1)).toEqual({
    type: 'error',
    data: { status: 503, detail: "The LLM endpoint can't be reached." },
  })
})

test('a stream that closes without its outcome was cut off', async () => {
  streams([event('token', { text: 'Hel' })])

  await expect(collect(ask('Hi', {}))).rejects.toMatchObject({
    status: 0,
    message: 'The answer was cut off before it ended.',
  })
})

test('stopping ends the stream quietly, and closes the request', async () => {
  const fetchMock = streams(
    [event('reasoning', { text: 'Hm.' }), event('token', { text: 'Hel' })],
    { stayOpen: true },
  )
  const controller = new AbortController()
  const found: StreamEvent<Done>[] = []

  for await (const received of ask('Hi', {}, controller.signal)) {
    found.push(received)
    if (received.type === 'token') {
      controller.abort() // the user presses stop
    }
  }

  expect(found.map((e) => e.type)).toEqual(['reasoning', 'token'])
  expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true)
})

test('a request refused before streaming fails with its status', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        Response.json({ detail: `No conversation ${ID}.` }, { status: 404 }),
      ),
    ),
  )

  await expect(collect(ask('Hi', {}))).rejects.toMatchObject({
    status: 404,
    message: `No conversation ${ID}.`,
  })
})

test('a backend that cannot be reached is status 0', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
  )

  await expect(collect(ask('Hi', {}))).rejects.toMatchObject({
    status: 0,
  })
})

test('a connection lost mid-answer is reported as such', async () => {
  const broken = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(
        new TextEncoder().encode(event('token', { text: 'Hel' })),
      )
      controller.error(new TypeError('network error'))
    },
  })
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(new Response(broken))),
  )

  await expect(collect(ask('Hi', {}))).rejects.toMatchObject({
    status: 0,
    message: 'The connection to the backend was lost.',
  })
})
