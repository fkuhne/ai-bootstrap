// A fake backend for page tests: each request is answered by the handler for its method and path,
// and a request with none fails the test loudly. The modules on are `on`; readiness and the model,
// which the shell and its pages load, are ready and text-only, unless a test gives its own.
import { vi } from 'vitest'

type Handler = (init: RequestInit | undefined) => Response | Promise<Response>

export function fakeApi(
  routes: Record<string, Handler>,
  on: readonly string[] = [],
) {
  const defaults: Record<string, Handler> = {
    ...DEFAULT_ROUTES,
    'GET /api/modules': () =>
      Response.json({ modules: on.map((name) => ({ name })) }),
  }
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const key = `${init?.method ?? 'GET'} ${urlOf(input)}`
    const handler = { ...defaults, ...routes }[key]
    if (handler === undefined) {
      throw new Error(`The fake backend has no route for ${key}`)
    }
    return Promise.resolve(handler(init))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function urlOf(input: RequestInfo | URL): string {
  return typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.href
      : input.url
}

// The requests made to a path ending so, such as '/stream'.
export function callsTo(
  fetchMock: ReturnType<typeof fakeApi>,
  ending: string,
): RequestInit[] {
  return fetchMock.mock.calls
    .filter(([input]) => urlOf(input).endsWith(ending))
    .map(([, init]) => init ?? {})
}

const DEFAULT_ROUTES: Record<string, Handler> = {
  'GET /api/health/ready': () => Response.json(READY),
  'GET /api/llm/model': () => Response.json(TEXT_MODEL),
}

export const TEXT_MODEL = { model: 'local-model', inputs: ['text'] }

export const READY = { status: 'ok', checks: { llm: 'ok' } }
