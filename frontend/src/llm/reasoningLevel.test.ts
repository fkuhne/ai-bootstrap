import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { levelOf, parametersFor, useReasoningLevel } from './reasoningLevel'

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

test.each([
  ['auto', {}],
  ['none', { reasoning_effort: 'none' }],
  ['low', { reasoning_effort: 'low' }],
  ['medium', { reasoning_effort: 'medium' }],
  // The highest value every provider documents.
  ['max', { reasoning_effort: 'high' }],
] as const)('%s sends %o', (level, parameters) => {
  expect(parametersFor(level)).toEqual(parameters)
})

test('anything else read back is Auto', () => {
  expect(levelOf('medium')).toBe('medium')
  expect(levelOf('extreme')).toBe('auto')
  expect(levelOf(null)).toBe('auto')
})

test('the level chosen is kept in the browser', () => {
  const { result, unmount } = renderHook(() => useReasoningLevel())
  expect(result.current[0]).toBe('auto')

  act(() => result.current[1]('low'))
  unmount()

  expect(renderHook(() => useReasoningLevel()).result.current[0]).toBe('low')
})

test('without storage, the level lasts for the visit', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new DOMException('blocked', 'SecurityError')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('blocked', 'SecurityError')
  })
  const { result } = renderHook(() => useReasoningLevel())

  act(() => result.current[1]('none'))

  expect(result.current[0]).toBe('none')
})
