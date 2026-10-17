import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { Reasoning } from './Reasoning'

function box() {
  return screen.getByText('Weigh the options.').closest('details')
}

test('while the reasoning is written, its box is open', () => {
  render(<Reasoning text="Weigh the options." streaming />)

  expect(box()).toHaveAttribute('open')
  expect(screen.getByText('Reasoning…')).toBeInTheDocument()
})

test('once it is written, the box closes, and a click opens it again', async () => {
  const { rerender } = render(<Reasoning text="Weigh the options." streaming />)

  rerender(<Reasoning text="Weigh the options." />)

  expect(box()).not.toHaveAttribute('open')
  expect(screen.getByText('Reasoning')).toBeInTheDocument()

  await userEvent.click(screen.getByText('Reasoning'))

  expect(box()).toHaveAttribute('open')
})
