import { expect, test } from 'vitest'
import { breakdown, elapsed, summary } from './elapsed'

test.each([
  [12.4, '12 ms'],
  [999.4, '999 ms'],
  [999.6, '1.0 s'],
  [1440, '1.4 s'],
  [9949, '9.9 s'],
  [9950, '10 s'],
  [37_200, '37 s'],
  [120_000, '2 min'],
  [172_400, '2 min 52 s'],
])('%f ms reads as %s', (ms, words) => {
  expect(elapsed(ms)).toBe(words)
})

const DETAILS = {
  model: 'qwen',
  finish_reason: 'stop',
  usage: { prompt_tokens: 1200, completion_tokens: 40, total_tokens: 1240 },
  first_token_ms: 300,
  total_ms: 2300,
}

test('an answer is summed up by its model, tokens and time', () => {
  expect(summary(DETAILS)).toBe('qwen · 40 tokens · 2.3 s')
  expect(breakdown(DETAILS)).toBe(
    [
      'First piece after 300 ms',
      'Answered in 2.3 s',
      '1,200 prompt + 40 answer tokens',
      'Finished: stop',
    ].join('\n'),
  )
})

test('an answer without usage or a first piece says what it can', () => {
  const details = {
    ...DETAILS,
    usage: null,
    first_token_ms: null,
    finish_reason: null,
  }

  expect(summary(details)).toBe('qwen · 2.3 s')
  expect(breakdown(details)).toBe('Answered in 2.3 s')
})
