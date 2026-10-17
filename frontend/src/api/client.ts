// The backend's API as the app calls it: `request`, which every call goes through, and one function
// per endpoint of the core, typed by the models generated from its OpenAPI schema; each module
// keeps its own calls in its folder (docs/foundations.md#the-web-ui). Every call carries the
// anonymous user's id (docs/foundations.md#users).
import type { ModelInfo, ModuleList, Readiness } from './types'
import { userId } from './userId'

export const BASE = '/api'

// A call that failed: the HTTP status and the backend's message, or status 0 when the backend
// couldn't be reached at all.
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string, cause?: unknown) {
    super(message, { cause })
    this.name = 'ApiError'
    this.status = status
  }
}

// What a failed call says to the user: the backend's message, or the error's own.
export function failureMessage(failure: unknown): string {
  return failure instanceof Error ? failure.message : String(failure)
}

export function getReadiness(): Promise<Readiness> {
  // 503 is an answer too: the body says which dependency isn't ready yet.
  return request<Readiness>('/health/ready', {}, [503])
}

export function getModel(): Promise<ModelInfo> {
  return request('/llm/model')
}

export function getModules(): Promise<ModuleList> {
  return request('/modules')
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
  alsoOk: readonly number[] = [],
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: headers('application/json', init.body !== undefined),
    })
  } catch (error) {
    throw unreachable(error)
  }
  if (!response.ok && !alsoOk.includes(response.status)) {
    throw await failure(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

// The headers of every call: what it accepts, the user's id, and the body's type if it has one.
export function headers(
  accept: string,
  withBody: boolean,
): Record<string, string> {
  return {
    Accept: accept,
    'X-User-Id': userId(),
    ...(withBody ? { 'Content-Type': 'application/json' } : {}),
  }
}

export function unreachable(cause?: unknown): ApiError {
  return new ApiError(0, "The backend can't be reached.", cause)
}

// A failed response as an ApiError, with the backend's own message.
export async function failure(response: Response): Promise<ApiError> {
  return new ApiError(response.status, await message(response))
}

// FastAPI's `detail`: a sentence, or for an invalid request a list of what's wrong.
async function message(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') {
      return body.detail
    }
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((problem: { msg?: string }) => problem.msg ?? 'Invalid request.')
        .join(' ')
    }
  } catch {
    // Not JSON: the status line is all there is.
  }
  return `${response.status} ${response.statusText}`.trim()
}
