import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { Markdown } from './Markdown'

test('Markdown is rendered, tables included', () => {
  const { container } = render(
    <Markdown
      text={'Use **bold**.\n\n| Key | Value |\n|---|---|\n| a | 1 |\n'}
    />,
  )

  expect(screen.getByText('bold').tagName).toBe('STRONG')
  expect(container.querySelector('table td')).toHaveTextContent('a')
})

test('raw HTML stays text, and is never run', () => {
  const { container } = render(
    <Markdown text={'Hi <img src=x onerror="alert(1)"> there'} />,
  )

  expect(container.querySelector('img')).toBeNull()
})

test('a <br> in a table cell is a line break', () => {
  const { container } = render(
    <Markdown text={'| Steps |\n|---|\n| one<br>two |\n'} />,
  )

  expect(container.querySelector('td')?.innerHTML).toMatch(/^one<br>\s*two$/)
})

test('a link opens in a new tab', () => {
  render(<Markdown text="[the docs](https://example.com/docs)" />)

  const link = screen.getByRole('link', { name: 'the docs' })
  expect(link).toHaveAttribute('href', 'https://example.com/docs')
  expect(link).toHaveAttribute('target', '_blank')
  expect(link).toHaveAttribute('rel', 'noreferrer')
})
