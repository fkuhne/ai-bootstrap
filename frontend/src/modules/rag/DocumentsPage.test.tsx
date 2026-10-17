import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../../App'
import { callsTo, fakeApi } from '../../test/api'
import { controlledBody, event } from '../../test/streams'
import { RAG } from '.'

const STREAM = 'POST /api/rag/ask/stream'
const SOURCES = 'GET /api/rag/sources'
const DONE = {
  model: 'local-model',
  finish_reason: 'stop',
  usage: { prompt_tokens: 420, completion_tokens: 12, total_tokens: 432 },
  refused: false,
}
const RETURNS = {
  number: 1,
  chunk: {
    id: 'returns-2',
    source: 'help/returns.md',
    title: 'Refunds',
    text: 'Refunds reach the original payment method within a week.',
    metadata: {},
  },
  similarity: 0.8153,
}
const SHIPPING = {
  number: 2,
  chunk: {
    id: 'shipping-1',
    source: 'help/shipping.md',
    title: null,
    text: 'Parcels arrive in three to five working days.',
    metadata: {},
  },
  similarity: 0.6021,
}
const STORED = {
  sources: [
    { source: 'help/returns.md', chunks: 3 },
    { source: 'help/shipping.md', chunks: 1 },
  ],
}

// The app with the RAG module alone; each answer's stream is the test's to send, event by event.
async function renderDocuments(routes: Parameters<typeof fakeApi>[0] = {}) {
  const bodies: ReturnType<typeof controlledBody>[] = []
  const fetchMock = fakeApi(
    {
      'GET /api/health/ready': () =>
        Response.json({ status: 'ok', checks: { llm: 'ok', rag: 'ok' } }),
      [SOURCES]: () => Response.json(STORED),
      [STREAM]: (init) => {
        const body = controlledBody(init?.signal)
        bodies.push(body)
        return new Response(body.stream)
      },
      ...routes,
    },
    [RAG.name],
  )
  render(
    <MemoryRouter initialEntries={['/documents']}>
      <App modules={[RAG]} />
    </MemoryRouter>,
  )
  await screen.findByRole('textbox', { name: 'Message' })

  // Waits for the page to ask the nth question, then sends its events.
  async function stream(nth: number, ...events: string[]) {
    await waitFor(() => expect(bodies[nth]).toBeDefined())
    events.forEach((text) => bodies[nth]?.send(text))
  }
  function sent(nth: number): unknown {
    return JSON.parse(
      callsTo(fetchMock, '/rag/ask/stream')[nth]?.body as string,
    )
  }
  return {
    fetchMock,
    stream,
    sent,
    close: (nth: number) => bodies[nth]?.close(),
  }
}

async function send(message: string) {
  await userEvent.type(
    screen.getByRole('textbox', { name: 'Message' }),
    `${message}{Enter}`,
  )
}

async function answered() {
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument(),
  )
}

beforeEach(() =>
  localStorage.setItem('user-id', '3f2b8c1e-6d4a-4f7e-9b0a-2c5d8e1f4a7b'),
)
afterEach(() => vi.unstubAllGlobals())

test('the sources show as they arrive, before the answer, and stay under it, the cited ones marked', async () => {
  const { stream, close, sent } = await renderDocuments()

  await send('How long do refunds take?')
  await stream(0, event('sources', { sources: [RETURNS, SHIPPING] }))

  const sources = await screen.findByRole('region', { name: 'Sources' })
  expect(within(sources).getByText('Refunds')).toBeInTheDocument()
  expect(
    within(sources).getByText('help/returns.md · similarity 0.82'),
  ).toBeInTheDocument()
  // A chunk without a title goes by its document.
  expect(within(sources).getByText('help/shipping.md')).toBeInTheDocument()
  expect(within(sources).getByText('similarity 0.60')).toBeInTheDocument()

  await stream(
    0,
    event('token', { text: 'Within a week [1].' }),
    event('done', DONE),
  )
  close(0)
  await answered()

  const conversation = screen.getByRole('list', { name: 'Conversation' })
  expect(
    within(conversation).getByText('Within a week [1].'),
  ).toBeInTheDocument()
  expect(
    within(conversation).getByText('help/returns.md · similarity 0.82 · cited'),
  ).toBeInTheDocument()
  expect(within(conversation).getByText('similarity 0.60')).toBeInTheDocument()
  expect(
    within(conversation).getByText('local-model · 12 tokens'),
  ).toBeInTheDocument()
  // Each source's text is folded below it.
  expect(within(conversation).getByText(RETURNS.chunk.text)).not.toBeVisible()
  expect(sent(0)).toEqual({
    messages: [{ role: 'user', content: 'How long do refunds take?' }],
    parameters: {},
    limit: 5,
  })
})

test('each question goes with the conversation so far, and new sources replace the last ones', async () => {
  const { stream, close, sent } = await renderDocuments()
  await send('How long do refunds take?')
  await stream(
    0,
    event('sources', { sources: [RETURNS] }),
    event('token', { text: 'A week [1].' }),
    event('done', DONE),
  )
  close(0)
  await answered()

  await send('And parcels?')
  await stream(1, event('sources', { sources: [{ ...SHIPPING, number: 1 }] }))

  await waitFor(() =>
    expect(screen.getAllByRole('region', { name: 'Sources' })).toHaveLength(2),
  )
  const [first, second] = screen.getAllByRole('region', { name: 'Sources' })
  expect(within(first!).getByText('Refunds')).toBeInTheDocument()
  expect(within(second!).queryByText('Refunds')).not.toBeInTheDocument()
  expect(sent(1)).toMatchObject({
    messages: [
      { role: 'user', content: 'How long do refunds take?' },
      { role: 'assistant', content: 'A week [1].' },
      { role: 'user', content: 'And parcels?' },
    ],
  })
})

test("when the documents don't say, the page tells why the model wasn't asked", async () => {
  const { stream, close } = await renderDocuments()
  await send('What is the meaning of life?')
  await stream(
    0,
    event('sources', { sources: [] }),
    event('token', { text: "The documents don't say." }),
    event('done', { refused: true }),
  )
  close(0)
  await answered()

  expect(screen.getByText("The documents don't say.")).toBeInTheDocument()
  expect(
    screen.getByText("No chunk was found: the model wasn't asked."),
  ).toBeInTheDocument()
  expect(
    screen.queryByRole('region', { name: 'Sources' }),
  ).not.toBeInTheDocument()
})

test('the sidebar lists the stored documents with their chunks, and again after an answer', async () => {
  const { fetchMock, stream, close } = await renderDocuments()

  const documents = await screen.findByRole('list', { name: 'Documents' })
  expect(within(documents).getByText('help/returns.md')).toBeInTheDocument()
  expect(within(documents).getAllByRole('listitem')[0]).toHaveTextContent(
    'help/returns.md3 chunks',
  )
  expect(within(documents).getAllByRole('listitem')[1]).toHaveTextContent(
    'help/shipping.md1 chunk',
  )
  const loads = callsTo(fetchMock, '/rag/sources').length

  await send('How long do refunds take?')
  await stream(0, event('sources', { sources: [] }), event('done', DONE))
  close(0)
  await answered()

  await waitFor(() =>
    expect(callsTo(fetchMock, '/rag/sources').length).toBeGreaterThan(loads),
  )
})

test('with nothing stored, the sidebar says how to store documents', async () => {
  await renderDocuments({
    [SOURCES]: () => Response.json({ sources: [] }),
  })

  expect(await screen.findByText(/No documents stored yet/)).toBeInTheDocument()
  expect(
    screen.getByText('docker compose run --rm rag-samples'),
  ).toBeInTheDocument()
})

test('a new chat starts over', async () => {
  const { stream, close } = await renderDocuments()
  await send('How long do refunds take?')
  await stream(
    0,
    event('sources', { sources: [RETURNS] }),
    event('token', { text: 'A week [1].' }),
    event('done', DONE),
  )
  close(0)
  await answered()

  await userEvent.click(screen.getByRole('button', { name: 'New chat' }))

  expect(
    screen.queryByRole('list', { name: 'Conversation' }),
  ).not.toBeInTheDocument()
})

test('the page needs RAG as well as the model, and says so in its words', async () => {
  await renderDocuments({
    'GET /api/health/ready': () =>
      Response.json(
        { status: 'unavailable', checks: { llm: 'ok', rag: 'unavailable' } },
        { status: 503 },
      ),
  })

  expect(
    await screen.findByText(/The documents can't be searched yet/),
  ).toBeInTheDocument()
})
