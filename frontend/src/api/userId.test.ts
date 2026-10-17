import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { newUuid, userId } from './userId'

const UUID_V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

test('a new browser gets a random id, and keeps it', () => {
  const first = userId()

  expect(first).toMatch(UUID_V4)
  expect(userId()).toBe(first)
  expect(localStorage.getItem('user-id')).toBe(first)
})

test('a kept id is used as it is', () => {
  localStorage.setItem('user-id', '3f2b8c1e-6d4a-4f7e-9b0a-2c5d8e1f4a7b')

  expect(userId()).toBe('3f2b8c1e-6d4a-4f7e-9b0a-2c5d8e1f4a7b')
})

test('anything kept that is not a UUID is replaced', () => {
  localStorage.setItem('user-id', 'alice')

  const id = userId()

  expect(id).toMatch(UUID_V4)
  expect(localStorage.getItem('user-id')).toBe(id)
})

test('without storage, the id lasts for the visit', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new DOMException('blocked', 'SecurityError')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('blocked', 'SecurityError')
  })

  const first = userId()

  expect(first).toMatch(UUID_V4)
  expect(userId()).toBe(first)
})

test('without crypto.randomUUID, as on a plain-HTTP address, the id is still a UUID', () => {
  vi.stubGlobal('crypto', {
    getRandomValues: crypto.getRandomValues.bind(crypto),
  })

  const ids = new Set(Array.from({ length: 20 }, newUuid))

  expect(ids.size).toBe(20)
  for (const id of ids) {
    expect(id).toMatch(UUID_V4)
  }
  vi.unstubAllGlobals()
})
