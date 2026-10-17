// The sources an answer cites: the numbers it writes in square brackets, as `[1]`, `[1, 3]` or
// `[2][3]`, as the prompt asks the model to.
const CITATION = /\[(\d+(?:\s*,\s*\d+)*)\]/g

export function citedIn(answer: string): ReadonlySet<number> {
  const cited = new Set<number>()
  for (const [, numbers] of answer.matchAll(CITATION)) {
    for (const number of numbers?.split(',') ?? []) {
      cited.add(Number(number))
    }
  }
  return cited
}
