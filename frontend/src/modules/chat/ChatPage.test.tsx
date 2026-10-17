import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../../App'
import { callsTo, fakeApi } from '../../test/api'
import { controlledBody, event } from '../../test/streams'
import { CHAT } from '.'

const STREAM = 'POST /api/chat/stream'
const DONE = {
  model: 'local-model',
  finish_reason: 'stop',
  usage: { prompt_tokens: 12, completion_tokens: 40, total_tokens: 52 },
}

// The app with the chat module alone; each answer's stream is the test's to send, event by event.
async function renderChat(routes: Parameters<typeof fakeApi>[0] = {}) {
  const bodies: ReturnType<typeof controlledBody>[] = []
  const fetchMock = fakeApi(
    {
      [STREAM]: (init) => {
        const body = controlledBody(init?.signal)
        bodies.push(body)
        return new Response(body.stream)
      },
      ...routes,
    },
    [CHAT.name],
  )
  render(
    <MemoryRouter initialEntries={['/chat']}>
      <App modules={[CHAT]} />
    </MemoryRouter>,
  )
  await screen.findByRole('textbox', { name: 'Message' })
  // Waits for the page to ask the nth question, then sends its events.
  async function stream(nth: number, ...events: string[]) {
    await waitFor(() => expect(bodies[nth]).toBeDefined())
    events.forEach((text) => bodies[nth]?.send(text))
  }
  function sent(nth: number): unknown {
    return JSON.parse(callsTo(fetchMock, '/chat/stream')[nth]?.body as string)
  }
  return { stream, sent, close: (nth: number) => bodies[nth]?.close() }
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

test('a question streams its answer, which then joins the conversation, with how it was made', async () => {
  const { stream, close, sent } = await renderChat()

  await send('Hi there')
  await stream(
    0,
    event('reasoning', { text: 'Greet back.' }),
    event('token', { text: 'Hello **you**' }),
    event('done', DONE),
  )
  close(0)
  await answered()

  const conversation = screen.getByRole('list', { name: 'Conversation' })
  expect(within(conversation).getByText('Hi there')).toBeInTheDocument()
  expect(within(conversation).getByText('you').tagName).toBe('STRONG')
  expect(within(conversation).getByText('Greet back.')).toBeInTheDocument()
  expect(
    within(conversation).getByText('local-model · 40 tokens'),
  ).toBeInTheDocument()
  expect(sent(0)).toEqual({
    messages: [{ role: 'user', content: 'Hi there' }],
    parameters: {},
  })
})

test('each question goes with the conversation so far', async () => {
  const { stream, close, sent } = await renderChat()
  await send('My name is Ada.')
  await stream(0, event('token', { text: 'Hello, Ada.' }), event('done', DONE))
  close(0)
  await answered()

  await send('What is my name?')

  await waitFor(() => expect(sent(1)).toBeDefined())
  expect(sent(1)).toMatchObject({
    messages: [
      { role: 'user', content: 'My name is Ada.' },
      { role: 'assistant', content: 'Hello, Ada.' },
      { role: 'user', content: 'What is my name?' },
    ],
  })
})

test('a stopped answer is left out of the conversation', async () => {
  const { stream, sent } = await renderChat()
  await send('Count to a hundred.')
  await stream(0, event('token', { text: 'One, two,' }))

  await userEvent.click(await screen.findByRole('button', { name: 'Stop' }))

  expect(
    await screen.findByText("Stopped. It's left out of the conversation."),
  ).toBeInTheDocument()
  await send('Hello?')
  await waitFor(() => expect(sent(1)).toBeDefined())
  expect(sent(1)).toMatchObject({
    messages: [{ role: 'user', content: 'Hello?' }],
  })
})

test('a new chat starts over', async () => {
  const { stream, close } = await renderChat()
  await send('Hi there')
  await stream(0, event('token', { text: 'Hello.' }), event('done', DONE))
  close(0)
  await answered()

  await userEvent.click(screen.getByRole('button', { name: 'New chat' }))

  expect(
    screen.queryByRole('list', { name: 'Conversation' }),
  ).not.toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Hello there' }),
  ).toBeInTheDocument()
})

test("the page needs only the model: another module's check isn't its concern", async () => {
  await renderChat({
    'GET /api/health/ready': () =>
      Response.json(
        { status: 'unavailable', checks: { llm: 'ok', other: 'unavailable' } },
        { status: 503 },
      ),
  })

  // Readiness has answered once the model's name, asked beside it, shows.
  expect(await screen.findByText('local-model')).toBeInTheDocument()
  expect(
    within(screen.getByRole('main')).queryByRole('status'),
  ).not.toBeInTheDocument()
})
