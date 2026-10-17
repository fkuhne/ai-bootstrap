// How an answer was made, as the line under it says: the model and its tokens, with more in its
// tooltip. For a module whose stream ends with them.
import type { ViewMessage } from './Message'

export interface Made {
  readonly model?: string | null
  readonly finish_reason?: string | null
  readonly usage?: {
    readonly prompt_tokens: number
    readonly completion_tokens: number
  } | null
}

export function detailsOf(end: Made): ViewMessage['details'] {
  const usage = end.usage
  const summary = end.model == null ? [] : [end.model]
  const breakdown = []
  if (usage != null) {
    summary.push(`${usage.completion_tokens.toLocaleString('en-US')} tokens`)
    breakdown.push(
      `${usage.prompt_tokens.toLocaleString('en-US')} prompt + ${usage.completion_tokens.toLocaleString('en-US')} answer tokens`,
    )
  }
  if (end.finish_reason != null) {
    breakdown.push(`Finished: ${end.finish_reason}`)
  }
  if (summary.length === 0) {
    return null
  }
  return { summary: summary.join(' · '), breakdown: breakdown.join('\n') }
}
