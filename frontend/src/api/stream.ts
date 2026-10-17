// An answer streamed from the backend (docs/foundations.md#the-web-ui): its reasoning and its text
// as they're written, then its outcome, `done`, whose data each endpoint gives, or an error. A
// module's endpoint may send events of its own, such as RAG's `sources`, which pass when named.
import { ApiError, BASE, failure, headers, unreachable } from './client'
import { readEvents } from './sse'
import type { ContentDelta, ErrorEvent, ReasoningDelta } from './types'

// An event of a module's own: its name, and its data.
export interface ModuleEvent {
  readonly type: string
  readonly data: unknown
}

export type StreamEvent<Done, Extra extends ModuleEvent = never> =
  | { readonly type: 'reasoning'; readonly data: ReasoningDelta }
  | { readonly type: 'token'; readonly data: ContentDelta }
  | { readonly type: 'done'; readonly data: Done }
  | { readonly type: 'error'; readonly data: ErrorEvent }
  | Extra

const TYPES: ReadonlySet<string> = new Set([
  'reasoning',
  'token',
  'done',
  'error',
])

// POSTs the body to the path, under /api, and yields the answer's events as they arrive, with
// those of the module's own events `extra` names; any other event is skipped. Aborting `signal`
// ends it quietly: the backend sees the connection close, and stops the model.
export async function* postStream<Done, Extra extends ModuleEvent = never>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
  extra: readonly Extra['type'][] = [],
): AsyncGenerator<StreamEvent<Done, Extra>> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: headers('text/event-stream', true),
      body: JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) {
      return
    }
    throw unreachable(error)
  }
  if (!response.ok || response.body === null) {
    throw await failure(response)
  }

  let ended = false
  try {
    for await (const { event, data } of readEvents(response.body)) {
      if (TYPES.has(event) || extra.includes(event)) {
        const parsed = { type: event, data: JSON.parse(data) as unknown }
        ended = event === 'done' || event === 'error'
        yield parsed as StreamEvent<Done, Extra>
      }
    }
  } catch (error) {
    if (signal?.aborted) {
      return
    }
    throw new ApiError(0, 'The connection to the backend was lost.', error)
  }
  if (!ended && !signal?.aborted) {
    // The stream closed without its outcome, as when a proxy cuts it: not a complete answer.
    throw new ApiError(0, 'The answer was cut off before it ended.')
  }
}
