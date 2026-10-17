// The answer being streamed, as React state (docs/foundations.md#the-chat-view): a question goes
// through waiting, reasoning and writing, then done, stopped or failed. The page says where the
// answer comes from: it passes a stream, and gets the stream's `done` data back.
import { useCallback, useEffect, useReducer, useRef } from 'react'
import { type Failure, failureOf } from '../api/failures'
import type { StreamEvent } from '../api/stream'
import type { Content } from '../api/types'

export type Phase =
  | 'idle' // nothing asked yet
  | 'waiting' // asked; nothing has come yet
  | 'reasoning' // the model's reasoning is arriving
  | 'writing' // the answer is arriving
  | 'done' // answered
  | 'stopped' // the user stopped it
  | 'failed' // an error ended it

export interface StreamedAnswer {
  readonly phase: Phase
  readonly question: Content
  readonly reasoning: string
  readonly text: string
  readonly failure: Failure | null
}

type Action =
  | { readonly type: 'asked'; readonly question: Content }
  | { readonly type: 'reasoning'; readonly text: string }
  | { readonly type: 'token'; readonly text: string }
  | { readonly type: 'done' }
  | { readonly type: 'stopped' }
  | { readonly type: 'failed'; readonly failure: Failure }
  | { readonly type: 'reset' }

export const IDLE: StreamedAnswer = {
  phase: 'idle',
  question: '',
  reasoning: '',
  text: '',
  failure: null,
}

export function reduce(answer: StreamedAnswer, action: Action): StreamedAnswer {
  switch (action.type) {
    case 'asked':
      return { ...IDLE, phase: 'waiting', question: action.question }
    case 'reasoning':
      return {
        ...answer,
        phase: 'reasoning',
        reasoning: answer.reasoning + action.text,
      }
    case 'token':
      return { ...answer, phase: 'writing', text: answer.text + action.text }
    case 'done':
      return { ...answer, phase: 'done' }
    case 'stopped':
      return { ...answer, phase: 'stopped' }
    case 'failed':
      return { ...answer, phase: 'failed', failure: action.failure }
    case 'reset':
      return IDLE
  }
}

export function isStreaming(phase: Phase): boolean {
  return phase === 'waiting' || phase === 'reasoning' || phase === 'writing'
}

// Where an answer comes from: a stream, opened with the signal that stops it.
export type Source<Done> = (
  signal: AbortSignal,
) => AsyncIterable<StreamEvent<Done>>

// A complete answer: its text and reasoning, as they streamed, and the stream's `done` data.
export interface Completed<Done> {
  readonly text: string
  readonly reasoning: string
  readonly done: Done
}

export interface AnswerStream<Done> {
  readonly answer: StreamedAnswer
  // Asks, and resolves with the answer once it's complete; null if it was stopped or failed.
  readonly ask: (
    question: Content,
    source: Source<Done>,
  ) => Promise<Completed<Done> | null>
  // Stops the answer: the backend stops the model.
  readonly stop: () => void
  // Clears the answer, once the page shows it as complete, or when leaving it.
  readonly reset: () => void
}

export function useStreamedAnswer<Done>(): AnswerStream<Done> {
  const [answer, dispatch] = useReducer(reduce, IDLE)
  const running = useRef<AbortController | null>(null)

  const ask = useCallback(
    async (
      question: Content,
      source: Source<Done>,
    ): Promise<Completed<Done> | null> => {
      running.current?.abort() // one answer at a time
      const controller = new AbortController()
      running.current = controller
      // A newer question replaces this one: from then on, this stream's events are ignored.
      const send = (action: Action) => {
        if (running.current === controller) {
          dispatch(action)
        }
      }
      send({ type: 'asked', question })
      let text = ''
      let reasoning = ''
      try {
        for await (const event of source(controller.signal)) {
          switch (event.type) {
            case 'reasoning':
              reasoning += event.data.text
              send({ type: 'reasoning', text: event.data.text })
              break
            case 'token':
              text += event.data.text
              send({ type: 'token', text: event.data.text })
              break
            case 'done':
              send({ type: 'done' })
              return { text, reasoning, done: event.data }
            case 'error':
              send({ type: 'failed', failure: event.data })
              return null
          }
        }
        send({ type: 'stopped' }) // the stream only ends quietly when it's stopped
        return null
      } catch (error) {
        send({ type: 'failed', failure: failureOf(error) })
        return null
      } finally {
        if (running.current === controller) {
          running.current = null
        }
      }
    },
    [],
  )

  const stop = useCallback(() => running.current?.abort(), [])
  const reset = useCallback(() => {
    running.current?.abort()
    running.current = null
    dispatch({ type: 'reset' })
  }, [])

  // Leaving the view stops an answer still streaming.
  useEffect(() => () => running.current?.abort(), [])

  return { answer, ask, stop, reset }
}
