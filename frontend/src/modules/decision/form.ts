// The page's questions as the user edits them, and the request they make: checked first for what
// the backend would refuse, so the page can say what to fix.
import { newUuid } from '../../api/userId'
import type { DecisionRequest, Question } from './types'

export type Kind = 'noul' | 'choice' | 'score'

export const KINDS: Readonly<Record<Kind, string>> = {
  noul: 'Yes or no',
  choice: 'One of options',
  score: 'A level on a scale',
}

// A scale has from 2 to 10 levels.
export const MIN_LEVELS = 2
export const MAX_LEVELS = 10

export interface Option {
  readonly id: string
  readonly name: string
  readonly description: string
}

export interface Level {
  readonly id: string
  readonly text: string
}

export interface Draft {
  readonly id: string
  readonly name: string
  readonly kind: Kind
  readonly instructions: string
  // A choice's options, and a score's levels, lowest first; both kept while the kind changes.
  readonly options: readonly Option[]
  readonly levels: readonly Level[]
}

export const EXAMPLE_TEXT =
  'Customer message: I was charged twice for my order last week, nobody has answered my emails, and I want my money back today.'

// The decision demo's questions: one of each type.
export function example(): readonly Draft[] {
  return [
    draft('angry', 'noul', 'Is the customer angry?'),
    draft('team', 'choice', 'Which team should handle this message?', {
      options: [
        ['billing', 'Payments, refunds and invoices'],
        ['shipping', 'Deliveries and returns'],
        ['technical', 'The website and the app'],
      ],
    }),
    draft('urgency', 'score', 'How urgent is this message?', {
      levels: ['can wait', 'this week', 'today', 'right now'],
    }),
  ]
}

// A new question, yes or no, named apart from the others.
export function blank(others: readonly Draft[]): Draft {
  const taken = new Set(others.map((other) => other.name))
  let number = others.length + 1
  while (taken.has(`question ${number}`)) {
    number += 1
  }
  return draft(`question ${number}`, 'noul', '', {
    options: [
      ['', ''],
      ['', ''],
    ],
    levels: ['', ''],
  })
}

export function option(): Option {
  return { id: newUuid(), name: '', description: '' }
}

export function level(): Level {
  return { id: newUuid(), text: '' }
}

export type Built =
  | { readonly request: DecisionRequest; readonly problems?: undefined }
  | { readonly request?: undefined; readonly problems: readonly string[] }

// The request, or what's wrong with the questions.
export function build(text: string, drafts: readonly Draft[]): Built {
  const problems: string[] = []
  if (text.trim() === '') {
    problems.push('Write the text the questions are about.')
  }
  if (drafts.length === 0) {
    problems.push('Add a question.')
  }
  const names = drafts.map((d) => d.name.trim())
  if (names.includes('')) {
    problems.push('Each question needs a name.')
  }
  for (const name of new Set(
    names.filter((n, i) => n !== '' && names.indexOf(n) !== i),
  )) {
    problems.push(`Two questions are named “${name}”.`)
  }
  for (const d of drafts) {
    problems.push(...problemsOf(d))
  }
  if (problems.length > 0) {
    return { problems }
  }
  return {
    request: {
      state: text.trim(),
      questions: Object.fromEntries(
        drafts.map((d) => [d.name.trim(), questionOf(d)]),
      ),
    },
  }
}

function problemsOf(d: Draft): string[] {
  const name = d.name.trim() || 'A question'
  const problems = []
  if (d.instructions.trim() === '') {
    problems.push(`“${name}” needs instructions.`)
  }
  if (d.kind === 'choice') {
    const options = d.options.map((o) => o.name.trim())
    if (options.length < 2 || options.includes('')) {
      problems.push(`“${name}” needs at least two options, each with a name.`)
    } else if (new Set(options).size < options.length) {
      problems.push(`“${name}” has two options with the same name.`)
    }
  }
  if (d.kind === 'score') {
    const count = d.levels.length
    if (
      count < MIN_LEVELS ||
      count > MAX_LEVELS ||
      d.levels.some((l) => l.text.trim() === '')
    ) {
      problems.push(
        `“${name}” needs from ${MIN_LEVELS} to ${MAX_LEVELS} levels, each described.`,
      )
    }
  }
  return problems
}

function questionOf(d: Draft): Question {
  const instructions = d.instructions.trim()
  switch (d.kind) {
    case 'noul':
      return { type: 'noul', instructions }
    case 'choice':
      return {
        type: 'choice',
        instructions,
        criteria: Object.fromEntries(
          d.options.map((o) => [o.name.trim(), o.description.trim() || null]),
        ),
      }
    case 'score':
      return {
        type: 'score',
        instructions,
        criteria: d.levels.map((l) => l.text.trim()),
      }
  }
}

function draft(
  name: string,
  kind: Kind,
  instructions: string,
  criteria: {
    options?: readonly (readonly [string, string])[]
    levels?: readonly string[]
  } = {},
): Draft {
  return {
    id: newUuid(),
    name,
    kind,
    instructions,
    options: (
      criteria.options ?? [
        ['', ''],
        ['', ''],
      ]
    ).map(([optionName, description]) => ({
      id: newUuid(),
      name: optionName,
      description,
    })),
    levels: (criteria.levels ?? ['', '']).map((text) => ({
      id: newUuid(),
      text,
    })),
  }
}
