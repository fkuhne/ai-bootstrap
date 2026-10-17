import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../../App'
import { callsTo, fakeApi } from '../../test/api'
import { DECISION } from '.'

// The decision model's answers to the example's questions, in the shape the backend sends them.
const DECIDED = {
  model: 'laya',
  answers: {
    angry: { type: 'noul', noul: 0.834 },
    team: {
      type: 'choice',
      choice: 'billing',
      probabilities: { shipping: 0.02, billing: 0.973, technical: 0.007 },
      confidence: 0.94,
    },
    urgency: {
      type: 'score',
      score: 1.97,
      legend: {
        '0': 'can wait',
        '1': 'this week',
        '2': 'today',
        '3': 'right now',
      },
      probabilities: { '0': 0.02, '1': 0.2, '2': 0.57, '3': 0.21 },
      confidence: 0.41,
    },
  },
  usage: { input_tokens: 239, output_tokens: 0 },
}

async function renderDecision(routes: Parameters<typeof fakeApi>[0] = {}) {
  const fetchMock = fakeApi(
    { 'POST /api/decide': () => Response.json(DECIDED), ...routes },
    [DECISION.name],
  )
  render(
    <MemoryRouter initialEntries={['/decision']}>
      <App modules={[DECISION]} />
    </MemoryRouter>,
  )
  await screen.findByRole('heading', { name: 'Decide' })
  const sent = () =>
    callsTo(fetchMock, '/decide').map(
      (init) => JSON.parse(init.body as string) as Record<string, unknown>,
    )
  return { sent }
}

beforeEach(() =>
  localStorage.setItem('user-id', '3f2b8c1e-6d4a-4f7e-9b0a-2c5d8e1f4a7b'),
)
afterEach(() => vi.unstubAllGlobals())

test('the page opens with an example, and its answers come back as bars', async () => {
  const { sent } = await renderDecision()

  await userEvent.click(screen.getByRole('button', { name: 'Decide' }))

  const answers = await screen.findByRole('region', { name: 'Answers' })
  const angry = within(answers).getByRole('article', { name: 'angry' })
  expect(angry).toHaveTextContent('Yes83%')
  const team = within(answers).getByRole('article', { name: 'team' })
  // Every option, from the most likely; the chosen one in words.
  expect(
    within(team)
      .getAllByRole('listitem')
      .map((item) => item.textContent),
  ).toEqual(['billing97%', 'shipping2%', 'technical1%'])
  expect(team).toHaveTextContent('Chose billing, with a confidence of 94%.')
  const urgency = within(answers).getByRole('article', { name: 'urgency' })
  expect(urgency).toHaveTextContent(
    'Scored 1.97 on 0 to 3, nearest “today”, with a confidence of 41%.',
  )
  expect(answers).toHaveTextContent('laya · 239 tokens of text')
  expect(sent()[0]).toMatchObject({
    questions: { angry: { type: 'noul' }, team: { type: 'choice' } },
  })
})

test('a question is added, made a choice, and sent with its options', async () => {
  const user = userEvent.setup()
  const { sent } = await renderDecision()

  await user.click(screen.getByRole('button', { name: 'Add a question' }))
  const question = screen.getByRole('group', { name: 'Question “question 4”' })
  await user.selectOptions(
    within(question).getByRole('combobox', { name: 'Type' }),
    'One of options',
  )
  await user.type(
    within(question).getByRole('textbox', { name: 'Instructions' }),
    'Which language is it in?',
  )
  await user.type(
    within(question).getByRole('textbox', { name: 'Option 1' }),
    'English',
  )
  await user.type(
    within(question).getByRole('textbox', { name: 'Option 2' }),
    'Portuguese',
  )
  await user.click(screen.getByRole('button', { name: 'Decide' }))

  await waitFor(() => expect(sent()).toHaveLength(1))
  expect(sent()[0]).toMatchObject({
    questions: {
      'question 4': {
        type: 'choice',
        instructions: 'Which language is it in?',
        criteria: { English: null, Portuguese: null },
      },
    },
  })
})

test('what the backend would refuse is said, and nothing is sent', async () => {
  const user = userEvent.setup()
  const { sent } = await renderDecision()
  const angry = screen.getByRole('group', { name: 'Question “angry”' })

  await user.clear(within(angry).getByRole('textbox', { name: 'Name' }))
  await user.click(screen.getByRole('button', { name: 'Decide' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Each question needs a name.',
  )
  expect(sent()).toEqual([])
})

test('a failure is explained, with the backend message as a detail', async () => {
  await renderDecision({
    'POST /api/decide': () =>
      Response.json(
        { detail: "The decision endpoint can't be reached." },
        { status: 503 },
      ),
  })

  await userEvent.click(screen.getByRole('button', { name: 'Decide' }))

  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent("The decision model can't be reached")
  expect(alert).toHaveTextContent(
    "Details: The decision endpoint can't be reached.",
  )
})

test('the page needs only the decision model, and says when it is not ready', async () => {
  await renderDecision({
    'GET /api/health/ready': () =>
      Response.json(
        {
          status: 'unavailable',
          checks: { llm: 'unavailable', decision: 'unavailable' },
        },
        { status: 503 },
      ),
  })

  const notice = await within(screen.getByRole('main')).findByRole('status')
  expect(notice).toHaveTextContent("The decision model isn't answering yet.")
  expect(notice).not.toHaveTextContent('The model isn')
})
