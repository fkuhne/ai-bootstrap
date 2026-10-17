import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import type { Input } from '../api/types'
import { Composer } from './Composer'

function renderComposer({
  inputs = ['text'],
  busy = false,
  model = 'local-model',
}: { inputs?: Input[]; busy?: boolean; model?: string | null } = {}) {
  const onSend = vi.fn()
  const onStop = vi.fn()
  const onReasoning = vi.fn()
  render(
    <Composer
      inputs={inputs}
      model={model}
      reasoning="auto"
      onReasoning={onReasoning}
      busy={busy}
      onSend={onSend}
      onStop={onStop}
    />,
  )
  return {
    onSend,
    onStop,
    onReasoning,
    box: screen.getByRole('textbox', { name: 'Message' }),
  }
}

const PNG = new File(['abc'], 'red.png', { type: 'image/png' })

test('Enter sends the message, and clears the box', async () => {
  const { onSend, box } = renderComposer()

  await userEvent.type(box, 'What is an LLM?{Enter}')

  expect(onSend).toHaveBeenCalledWith('What is an LLM?')
  expect(box).toHaveValue('')
})

test('Shift+Enter starts a new line instead', async () => {
  const { onSend, box } = renderComposer()

  await userEvent.type(box, 'First line{Shift>}{Enter}{/Shift}second line')

  expect(onSend).not.toHaveBeenCalled()
  expect(box).toHaveValue('First line\nsecond line')
})

test('a blank message cannot be sent', async () => {
  const { onSend, box } = renderComposer()

  await userEvent.type(box, '   {Enter}')

  expect(onSend).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
})

test('while an answer is written, the round button stops it', async () => {
  const { onStop } = renderComposer({ busy: true })

  await userEvent.click(screen.getByRole('button', { name: 'Stop' }))

  expect(onStop).toHaveBeenCalled()
  expect(screen.queryByRole('button', { name: 'Send' })).not.toBeInTheDocument()
})

test('the model is named, and a text-only model offers no attachments', () => {
  renderComposer()

  expect(screen.getByText('local-model')).toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: /^Attach/ }),
  ).not.toBeInTheDocument()
})

test('an image attached is shown, and sent after the text', async () => {
  const { onSend, box } = renderComposer({ inputs: ['text', 'image'] })
  expect(screen.getByRole('button', { name: 'Attach images' })).toBeVisible()

  await userEvent.upload(screen.getByTestId('attach'), PNG)
  const attached = await screen.findByRole('list', { name: 'Attached' })
  expect(
    within(attached).getByRole('img', { name: 'red.png' }),
  ).toHaveAttribute('src', 'data:image/png;base64,YWJj')
  await userEvent.type(box, 'What color?{Enter}')

  expect(onSend).toHaveBeenCalledWith([
    { type: 'text', text: 'What color?' },
    { type: 'image_url', image_url: { url: 'data:image/png;base64,YWJj' } },
  ])
  expect(
    screen.queryByRole('list', { name: 'Attached' }),
  ).not.toBeInTheDocument()
})

test('an attachment alone can be sent, and one can be removed first', async () => {
  const { onSend } = renderComposer({ inputs: ['text', 'image', 'audio'] })
  const sound = new File(['abc'], 'tone.wav', { type: 'audio/wav' })

  await userEvent.upload(screen.getByTestId('attach'), [PNG, sound])
  await screen.findByRole('button', { name: 'Remove tone.wav' })
  await userEvent.click(screen.getByRole('button', { name: 'Remove red.png' }))
  await userEvent.click(screen.getByRole('button', { name: 'Send' }))

  expect(onSend).toHaveBeenCalledWith([
    { type: 'input_audio', input_audio: { data: 'YWJj', format: 'wav' } },
  ])
})

test('a file the model does not take is refused, saying what it takes', async () => {
  const user = userEvent.setup({ applyAccept: false })
  renderComposer({ inputs: ['text', 'image', 'video'] })

  await user.upload(
    screen.getByTestId('attach'),
    new File(['abc'], 'notes.pdf', { type: 'application/pdf' }),
  )

  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent(
      "notes.pdf can't be sent: the model takes images or video.",
    ),
  )
  expect(
    screen.queryByRole('list', { name: 'Attached' }),
  ).not.toBeInTheDocument()
})

test('the reasoning level is chosen beside the model, Auto until then', async () => {
  const { onReasoning } = renderComposer()
  const level = screen.getByRole('combobox', { name: 'Reasoning' })

  expect(level).toHaveValue('auto')
  expect(
    Array.from((level as HTMLSelectElement).options, (option) => option.text),
  ).toEqual(['None', 'Auto', 'Low', 'Medium', 'Max'])

  await userEvent.selectOptions(level, 'Low')

  expect(onReasoning).toHaveBeenCalledWith('low')
})
