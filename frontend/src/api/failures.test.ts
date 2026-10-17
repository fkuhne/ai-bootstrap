import { expect, test } from 'vitest'
import { ApiError } from './client'
import { explain, failureOf } from './failures'

test.each([
  [413, 'The message is too large to send'],
  [429, "The model's provider is limiting how often it answers."],
  [502, 'The backend, or the model behind it, returned an error.'],
  [503, "The model can't be reached right now."],
  [504, "The model didn't answer in time."],
])('a %i is explained in plain words', (status, sentence) => {
  expect(explain({ status, detail: 'The LLM endpoint said so.' })).toContain(
    sentence,
  )
})

test("a page's own words for a status come first", () => {
  const words = { 404: 'This conversation no longer exists.' }

  expect(explain({ status: 404, detail: 'Not Found' }, words)).toBe(
    'This conversation no longer exists.',
  )
  expect(explain({ status: 504, detail: 'Slow' }, words)).toContain(
    "The model didn't answer in time.",
  )
})

test("any other status is the backend's own message", () => {
  expect(explain({ status: 422, detail: 'Field required' })).toBe(
    'Field required',
  )
  expect(explain({ status: 0, detail: "The backend can't be reached." })).toBe(
    "The backend can't be reached.",
  )
})

test('an error becomes a failure with its status, or 0', () => {
  expect(failureOf(new ApiError(503, 'The database is unavailable.'))).toEqual({
    status: 503,
    detail: 'The database is unavailable.',
  })
  expect(failureOf(new TypeError('Failed to fetch'))).toEqual({
    status: 0,
    detail: 'Failed to fetch',
  })
  expect(failureOf('odd')).toEqual({ status: 0, detail: 'odd' })
})
