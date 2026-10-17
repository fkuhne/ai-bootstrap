import { expect, test } from 'vitest'
import { groupByDay } from './days'

const NOW = new Date(2026, 9, 4, 15, 0) // 4 October, 15:00, in the browser's time zone

function lastAnswered(id: string, at: Date) {
  const time = at.toISOString()
  return { id, title: id, created_at: time, updated_at: time }
}

test('conversations go under the calendar day of their last answer, in the order given', () => {
  const groups = groupByDay(
    [
      lastAnswered('ahead of the clock', new Date(2026, 9, 4, 16, 0)),
      lastAnswered('just after midnight', new Date(2026, 9, 4, 0, 5)),
      lastAnswered('just before midnight', new Date(2026, 9, 3, 23, 55)),
      lastAnswered('two days ago', new Date(2026, 9, 2, 12, 0)),
      lastAnswered('seven days ago', new Date(2026, 8, 27, 12, 0)),
      lastAnswered('eight days ago', new Date(2026, 8, 26, 12, 0)),
      lastAnswered('last year', new Date(2025, 9, 4, 12, 0)),
    ],
    NOW,
  )

  expect(
    groups.map((group) => [group.label, group.conversations.map((c) => c.id)]),
  ).toEqual([
    ['Today', ['ahead of the clock', 'just after midnight']],
    ['Yesterday', ['just before midnight']],
    ['Previous 7 days', ['two days ago', 'seven days ago']],
    ['Older', ['eight days ago', 'last year']],
  ])
})

test('a day with no conversations has no group', () => {
  const groups = groupByDay(
    [lastAnswered('old', new Date(2026, 0, 1, 12, 0))],
    NOW,
  )

  expect(groups.map((group) => group.label)).toEqual(['Older'])
  expect(groupByDay([], NOW)).toEqual([])
})
