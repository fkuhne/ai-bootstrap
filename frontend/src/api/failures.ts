// What a failed answer means to the user, by its HTTP status (docs/foundations.md#the-chat-view). A
// request that failed and a stream that ended with an error read the same: the stream's error
// carries the status the request would have answered.
import { ApiError } from './client'

export interface Failure {
  // 0 when the backend couldn't be reached, or the connection broke.
  readonly status: number
  // The backend's own message, shown as a detail.
  readonly detail: string
}

export function failureOf(error: unknown): Failure {
  if (error instanceof ApiError) {
    return { status: error.status, detail: error.message }
  }
  return {
    status: 0,
    detail: error instanceof Error ? error.message : String(error),
  }
}

// Words a page gives for a status, in place of the core's own, such as a conversation's page for a
// conversation deleted meanwhile.
export type Words = Readonly<Partial<Record<number, string>>>

// One plain sentence for the statuses the backend, or nginx before it, answers with when
// something fails; for any other status, the backend's message says it best.
const WORDS: Words = {
  413: 'The message is too large to send: attach fewer or smaller files.',
  429: "The model's provider is limiting how often it answers. Wait a minute, then try again.",
  502: 'The backend, or the model behind it, returned an error.',
  503: "The model can't be reached right now. If the app was just started, it may still be loading: try again in a minute.",
  504: "The model didn't answer in time. Try again; on a slow computer, a shorter message helps.",
}

export function explain(
  { status, detail }: Failure,
  words: Words = {},
): string {
  return words[status] ?? WORDS[status] ?? detail
}
