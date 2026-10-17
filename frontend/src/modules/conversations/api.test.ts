import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { body, event } from '../../test/streams'
import {
  askStream,
  deleteConversation,
  listConversations,
  openConversation,
  startConversation,
} from './api'

const USER = '3f2b8c1e-6d4a-4f7e-9b0a-2c5d8e1f4a7b'
const ID = '6c685ab5-5d6c-4212-9095-ae6d5c696214'

function answers(status: number, responseBody?: unknown) {
  const fetchMock = vi.fn<typeof fetch>(() =>
    Promise.resolve(
      new Response(
        responseBody === undefined ? null : JSON.stringify(responseBody),
        { status, headers: { 'Content-Type': 'application/json' } },
      ),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

beforeEach(() => localStorage.setItem('user-id', USER))
afterEach(() => vi.unstubAllGlobals())

test('each endpoint is called with its method and path', async () => {
  const fetchMock = answers(200, {})

  await listConversations()
  await startConversation()
  await openConversation(ID)

  const calls = fetchMock.mock.calls.map(([url, init]) => [
    init?.method ?? 'GET',
    url,
  ])
  expect(calls).toEqual([
    ['GET', '/api/conversations'],
    ['POST', '/api/conversations'],
    ['GET', `/api/conversations/${ID}`],
  ])
})

test('a deleted conversation answers nothing', async () => {
  const fetchMock = answers(204)

  await expect(deleteConversation(ID)).resolves.toBeUndefined()
  const [url, init] = fetchMock.mock.calls[0] ?? []
  expect([init?.method, url]).toEqual(['DELETE', `/api/conversations/${ID}`])
})

test('a question is asked in its conversation, with its parameters, and streamed', async () => {
  const done = { model: 'm', question_id: 'q', answer_id: 'a' }
  const fetchMock = vi.fn<typeof fetch>(() =>
    Promise.resolve(new Response(body([event('done', done)]))),
  )
  vi.stubGlobal('fetch', fetchMock)

  const found = []
  for await (const received of askStream(ID, 'Hi', { reasoning_effort: 'low' }))
    found.push(received)

  expect(found).toEqual([{ type: 'done', data: done }])
  const [url, init] = fetchMock.mock.calls[0] ?? []
  expect(url).toBe(`/api/conversations/${ID}/messages/stream`)
  expect(JSON.parse(init?.body as string)).toEqual({
    content: 'Hi',
    parameters: { reasoning_effort: 'low' },
  })
})
