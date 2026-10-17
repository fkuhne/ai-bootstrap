import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { getModel, getModules, getReadiness } from './client'

const USER = '3f2b8c1e-6d4a-4f7e-9b0a-2c5d8e1f4a7b'

function answers(status: number, body?: unknown, statusText = '') {
  const fetchMock = vi.fn<typeof fetch>(() =>
    Promise.resolve(
      new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        statusText,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

beforeEach(() => localStorage.setItem('user-id', USER))
afterEach(() => vi.unstubAllGlobals())

test('every call carries the user id', async () => {
  const fetchMock = answers(200, {})

  await getModel()

  const [url, init] = fetchMock.mock.calls[0] ?? []
  expect(url).toBe('/api/llm/model')
  expect(new Headers(init?.headers).get('X-User-Id')).toBe(USER)
})

test('the modules that are on are asked for', async () => {
  const modules = { modules: [{ name: 'chat' }] }
  const fetchMock = answers(200, modules)

  await expect(getModules()).resolves.toEqual(modules)
  expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/modules')
})

test('readiness is asked for as JSON, with no body', async () => {
  const fetchMock = answers(200, { status: 'ok', checks: { llm: 'ok' } })

  await getReadiness()

  const [url, init] = fetchMock.mock.calls[0] ?? []
  expect(url).toBe('/api/health/ready')
  const headers = new Headers(init?.headers)
  expect(headers.get('Accept')).toBe('application/json')
  expect(headers.get('Content-Type')).toBeNull()
})

test('readiness answers even while a dependency is down', async () => {
  const body = { status: 'unavailable', checks: { llm: 'unavailable' } }
  answers(503, body)

  await expect(getReadiness()).resolves.toEqual(body)
})

test("a failure carries the status and the backend's message", async () => {
  answers(500, { detail: 'Something broke.' })

  await expect(getReadiness()).rejects.toMatchObject({
    name: 'ApiError',
    status: 500,
    message: 'Something broke.',
  })
})

test('an invalid request lists what is wrong', async () => {
  answers(422, {
    detail: [{ msg: 'Field required' }, { msg: 'Input should be a UUID' }],
  })

  await expect(getReadiness()).rejects.toMatchObject({
    status: 422,
    message: 'Field required Input should be a UUID',
  })
})

test('a failure without a JSON body falls back to the status line', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        new Response('<html>', { status: 502, statusText: 'Bad Gateway' }),
      ),
    ),
  )

  await expect(getReadiness()).rejects.toMatchObject({
    status: 502,
    message: '502 Bad Gateway',
  })
})

test('a backend that cannot be reached is status 0', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
  )

  await expect(getReadiness()).rejects.toMatchObject({
    status: 0,
    message: "The backend can't be reached.",
  })
})
