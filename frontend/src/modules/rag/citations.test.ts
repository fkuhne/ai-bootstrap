import { expect, test } from 'vitest'
import { citedIn } from './citations'

test('the numbers an answer cites, alone, listed or side by side', () => {
  expect([...citedIn('Within a week [1]. Abroad, longer [2, 3][5].')]).toEqual([
    1, 2, 3, 5,
  ])
})

test('an answer without citations cites nothing, nor do other brackets', () => {
  expect(
    citedIn("The documents don't say. See [the page](x) or [a].").size,
  ).toBe(0)
})
