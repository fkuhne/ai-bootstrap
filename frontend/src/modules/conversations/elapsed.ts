// How an answer was made, in words, for the line under it.
import type { AnswerDetails } from './types'

// A time for people: "606 ms", "1.4 s", "37 s", "2 min 52 s".
export function elapsed(ms: number): string {
  if (ms < 999.5) {
    return `${Math.round(ms)} ms`
  }
  if (ms < 9_950) {
    return `${(Math.round(ms / 100) / 10).toFixed(1)} s`
  }
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) {
    return `${seconds} s`
  }
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest === 0 ? `${minutes} min` : `${minutes} min ${rest} s`
}

// The model, the answer's tokens and its time. No speed: reasoning counts among the tokens, and
// a cloud provider may send its answer in bursts, so one would mislead.
export function summary(details: AnswerDetails): string {
  const parts = [details.model]
  const tokens = details.usage?.completion_tokens
  if (tokens !== undefined) {
    parts.push(`${tokens.toLocaleString('en-US')} tokens`)
  }
  parts.push(elapsed(details.total_ms))
  return parts.join(' · ')
}

// Where the time went, one line each, for the tooltip.
export function breakdown(details: AnswerDetails): string {
  const lines = []
  if (details.first_token_ms != null) {
    lines.push(`First piece after ${elapsed(details.first_token_ms)}`)
  }
  lines.push(`Answered in ${elapsed(details.total_ms)}`)
  if (details.usage != null) {
    const { prompt_tokens: prompt, completion_tokens: answer } = details.usage
    lines.push(
      `${prompt.toLocaleString('en-US')} prompt + ${answer.toLocaleString('en-US')} answer tokens`,
    )
  }
  if (details.finish_reason != null) {
    lines.push(`Finished: ${details.finish_reason}`)
  }
  return lines.join('\n')
}
