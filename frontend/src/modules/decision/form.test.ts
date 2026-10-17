import { expect, test } from 'vitest'
import { blank, build, type Draft, EXAMPLE_TEXT, example } from './form'

test('the example makes a request with a question of each type', () => {
  const { request } = build(EXAMPLE_TEXT, example())

  expect(request).toEqual({
    state: EXAMPLE_TEXT,
    questions: {
      angry: { type: 'noul', instructions: 'Is the customer angry?' },
      team: {
        type: 'choice',
        instructions: 'Which team should handle this message?',
        criteria: {
          billing: 'Payments, refunds and invoices',
          shipping: 'Deliveries and returns',
          technical: 'The website and the app',
        },
      },
      urgency: {
        type: 'score',
        instructions: 'How urgent is this message?',
        criteria: ['can wait', 'this week', 'today', 'right now'],
      },
    },
  })
})

test('an option without a description is sent as null, and names are trimmed', () => {
  const [, team] = example()
  const edited: Draft = {
    ...team!,
    name: ' team ',
    options: team!.options.map((o) => ({ ...o, description: '' })),
  }

  const { request } = build('A text', [edited])

  expect(request?.questions).toEqual({
    team: expect.objectContaining({
      criteria: { billing: null, shipping: null, technical: null },
    }),
  })
})

test('a new question is named apart from the others', () => {
  const first = blank([])
  const second = blank([first])

  expect([first.name, second.name]).toEqual(['question 1', 'question 2'])
  expect(blank([{ ...first, name: 'question 2' }]).name).toBe('question 3')
})

test.each([
  ['no text', '', example(), 'Write the text the questions are about.'],
  ['no questions', 'A text', [], 'Add a question.'],
  [
    'a question without a name',
    'A text',
    [{ ...example()[0]!, name: ' ' }],
    'Each question needs a name.',
  ],
  [
    'two questions with one name',
    'A text',
    [example()[0]!, { ...example()[0]!, id: 'other' }],
    'Two questions are named “angry”.',
  ],
  [
    'a question without instructions',
    'A text',
    [{ ...example()[0]!, instructions: '' }],
    '“angry” needs instructions.',
  ],
  [
    'a choice with one option',
    'A text',
    [{ ...example()[1]!, options: example()[1]!.options.slice(0, 1) }],
    '“team” needs at least two options, each with a name.',
  ],
  [
    'a choice with two options of one name',
    'A text',
    [
      {
        ...example()[1]!,
        options: example()[1]!.options.map((o) => ({ ...o, name: 'same' })),
      },
    ],
    '“team” has two options with the same name.',
  ],
  [
    'a scale with an empty level',
    'A text',
    [
      {
        ...example()[2]!,
        levels: [...example()[2]!.levels, { id: 'empty', text: '' }],
      },
    ],
    '“urgency” needs from 2 to 10 levels, each described.',
  ],
])('%s is said, and nothing is built', (_case, text, drafts, problem) => {
  const built = build(text, drafts)

  expect(built.request).toBeUndefined()
  expect(built.problems).toContain(problem)
})
