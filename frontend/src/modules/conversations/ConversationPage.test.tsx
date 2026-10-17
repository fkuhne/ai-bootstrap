import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { callsTo } from '../../test/api'
import { controlledBody, event } from '../../test/streams'
import {
  conversation,
  fakeConversationsApi,
  renderConversations,
  storedMessage,
} from './testing'

const ID = '6c685ab5-5d6c-4212-9095-ae6d5c696214'
const STREAM = `POST /api/conversations/${ID}/messages/stream`
const OPEN = `GET /api/conversations/${ID}`
const DONE = {
  model: 'local-model',
  finish_reason: 'stop',
  usage: { prompt_tokens: 12, completion_tokens: 40, total_tokens: 52 },
  question_id: 'q1',
  answer_id: 'a1',
}
const IMAGE = {
  type: 'image_url',
  image_url: { url: 'data:image/png;base64,YWJj' },
}

const renderAt = renderConversations

async function send(message: string) {
  await userEvent.type(
    await screen.findByRole('textbox', { name: 'Message' }),
    `${message}{Enter}`,
  )
}

// A new conversation whose answer the test streams, event by event.
function newConversation(
  stored: unknown[] = [],
  routes: Parameters<typeof fakeConversationsApi>[0] = {},
) {
  let body: ReturnType<typeof controlledBody> | undefined
  const fetchMock = fakeConversationsApi({
    ...routes,
    'POST /api/conversations': () =>
      Response.json(conversation(ID, []), { status: 201 }),
    [STREAM]: (init) => {
      body = controlledBody(init?.signal)
      return new Response(body.stream)
    },
    [OPEN]: () => Response.json(conversation(ID, stored)),
  })
  // Waits for the page to ask, then sends the events.
  async function stream(...events: string[]) {
    await waitFor(() => expect(body).toBeDefined())
    events.forEach((text) => body?.send(text))
  }
  return { fetchMock, stream, close: () => body?.close() }
}

beforeEach(() =>
  localStorage.setItem('user-id', '3f2b8c1e-6d4a-4f7e-9b0a-2c5d8e1f4a7b'),
)
afterEach(() => vi.unstubAllGlobals())

test('a first message starts its conversation, streams the reasoning and the answer, then shows them stored', async () => {
  const { stream, close } = newConversation([
    storedMessage('q1', 'user', 'Hi there'),
    storedMessage('a1', 'assistant', 'Hello **you**', 'Greet back.'),
  ])
  await renderAt('/conversations')

  await send('Hi there')

  // The URL moves to the new conversation, and the answer is awaited.
  await waitFor(() =>
    expect(screen.getByTestId('location')).toHaveTextContent(
      `/conversations/${ID}`,
    ),
  )
  expect(screen.getByText('Hi there')).toBeInTheDocument()
  expect(await screen.findByRole('status')).toHaveTextContent('Processing…')
  expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()

  await stream(
    event('reasoning', { text: 'Greet ' }),
    event('reasoning', { text: 'back.' }),
  )
  const reasoning = await screen.findByText('Greet back.')
  expect(screen.getByText('Reasoning…')).toBeInTheDocument()
  expect(reasoning.closest('details')).toHaveAttribute('open')

  await stream(
    event('token', { text: 'Hello **yo' }),
    event('token', { text: 'u**' }),
  )
  // Markdown, rendered as it arrives; the reasoning folds away.
  await waitFor(() => expect(screen.getByText('you').tagName).toBe('STRONG'))
  expect(reasoning.closest('details')).not.toHaveAttribute('open')

  await stream(event('done', DONE))
  close()
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument(),
  )
  // Once stored, the turn shows once, as the backend holds it, with how it was made.
  expect(screen.getAllByText('Hi there')).toHaveLength(1)
  expect(
    screen.getByText('local-model · 40 tokens · 2.3 s'),
  ).toBeInTheDocument()
})

test('stopping keeps what was written, and says nothing was stored', async () => {
  const { stream, fetchMock } = newConversation()
  await renderAt('/conversations')
  await send('Tell me a story')
  await stream(event('token', { text: 'Once upon' }))
  await screen.findByText('Once upon')

  await userEvent.click(screen.getByRole('button', { name: 'Stop' }))

  expect(
    await screen.findByText('Stopped. Nothing was stored.'),
  ).toBeInTheDocument()
  expect(screen.getByText('Once upon')).toBeInTheDocument()
  expect(callsTo(fetchMock, '/stream')[0]?.signal?.aborted).toBe(true)
})

test('a failure is explained by its status, with the backend message as a detail', async () => {
  const { stream, close } = newConversation()
  await renderAt('/conversations')
  await send('Hi')

  await stream(
    event('error', {
      status: 503,
      detail: "The LLM endpoint can't be reached.",
    }),
  )
  close()

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The answer failed.')
  expect(alert).toHaveTextContent("The model or the database can't be reached")
  expect(alert).toHaveTextContent("Details: The LLM endpoint can't be reached.")
})

test('a first answer that fails at once keeps its explanation as the page moves to its conversation', async () => {
  // The whole stream answers with the request, so it can end before React moves the page.
  fakeConversationsApi({
    'POST /api/conversations': () =>
      Response.json(conversation(ID, []), { status: 201 }),
    [STREAM]: () =>
      new Response(
        event('error', { status: 504, detail: "The LLM didn't answer." }),
      ),
    [OPEN]: () => Response.json(conversation(ID, [])),
  })
  await renderAt('/conversations')

  await send('Hi')

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent("The model didn't answer in time.")
  await waitFor(() =>
    expect(screen.getByTestId('location')).toHaveTextContent(
      `/conversations/${ID}`,
    ),
  )
  expect(screen.getByRole('alert')).toBe(alert)
})

test('a stored conversation opens with its media, and its reasoning folded', async () => {
  fakeConversationsApi({
    [OPEN]: () =>
      Response.json(
        conversation(ID, [
          storedMessage('q1', 'user', [
            { type: 'text', text: 'What color is this?' },
            IMAGE,
          ]),
          storedMessage('a1', 'assistant', 'Red.', 'A red square.'),
        ]),
      ),
  })
  await renderAt(`/conversations/${ID}`)

  const list = await screen.findByRole('list', { name: 'Conversation' })
  expect(within(list).getByText('What color is this?')).toBeInTheDocument()
  expect(within(list).getByRole('img')).toHaveAttribute(
    'src',
    'data:image/png;base64,YWJj',
  )
  expect(within(list).getByText('Red.')).toBeInTheDocument()
  expect(
    within(list).getByText('Reasoning').closest('details'),
  ).not.toHaveAttribute('open')
})

test('a conversation that cannot be opened says why', async () => {
  fakeConversationsApi({
    [OPEN]: () =>
      Response.json({ detail: `No conversation ${ID}.` }, { status: 404 }),
  })
  await renderAt(`/conversations/${ID}`)

  expect(await screen.findByRole('alert')).toHaveTextContent(
    `No conversation ${ID}.`,
  )
})

test('a conversation that cannot be started says why, and nothing is sent', async () => {
  const fetchMock = fakeConversationsApi({
    'POST /api/conversations': () =>
      Response.json(
        { detail: 'The database is unavailable.' },
        { status: 503 },
      ),
  })
  await renderAt('/conversations')

  await send('Hi')

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'The database is unavailable.',
  )
  expect(screen.getByTestId('location')).toHaveTextContent(/^\/conversations$/)
  expect(callsTo(fetchMock, '/stream')).toEqual([])
})

test('when the model takes images, the greeting says so, and an image is sent with the text', async () => {
  const { fetchMock } = newConversation([], {
    'GET /api/llm/model': () =>
      Response.json({ model: 'vision', inputs: ['text', 'image'] }),
  })
  await renderAt('/conversations')

  expect(
    await screen.findByText('Type a message, or attach images, to get started'),
  ).toBeInTheDocument()
  await userEvent.upload(
    screen.getByTestId('attach'),
    new File(['abc'], 'red.png', { type: 'image/png' }),
  )
  await screen.findByRole('img', { name: 'red.png' })
  await send('What color?')

  await waitFor(() => expect(callsTo(fetchMock, '/stream')).toHaveLength(1))
  expect(JSON.parse(callsTo(fetchMock, '/stream')[0]?.body as string)).toEqual({
    content: [{ type: 'text', text: 'What color?' }, IMAGE],
    parameters: {},
  })
})

test('the reasoning level chosen is sent with each message, and kept for the next visit', async () => {
  localStorage.removeItem('reasoning-level')
  const { fetchMock } = newConversation()
  await renderAt('/conversations')
  const level = screen.getByRole('combobox', { name: 'Reasoning' })
  expect(level).toHaveValue('auto')

  await userEvent.selectOptions(level, 'Max')
  await send('Is 1001 a prime number?')

  await waitFor(() => expect(callsTo(fetchMock, '/stream')).toHaveLength(1))
  expect(
    JSON.parse(callsTo(fetchMock, '/stream')[0]?.body as string),
  ).toMatchObject({ parameters: { reasoning_effort: 'high' } })
  expect(localStorage.getItem('reasoning-level')).toBe('max')
})
