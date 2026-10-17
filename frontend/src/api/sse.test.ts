import { expect, test } from 'vitest'
import { body } from '../test/streams'
import { readEvents, type ServerSentEvent } from './sse'

async function read(
  chunks: (string | Uint8Array)[],
): Promise<ServerSentEvent[]> {
  const found: ServerSentEvent[] = []
  for await (const event of readEvents(body(chunks))) {
    found.push(event)
  }
  return found
}

test('events are read with their names and data', async () => {
  expect(
    await read([
      'event: token\ndata: {"text":"Hel"}\n\nevent: token\ndata: {"text":"lo"}\n\n',
    ]),
  ).toEqual([
    { event: 'token', data: '{"text":"Hel"}' },
    { event: 'token', data: '{"text":"lo"}' },
  ])
})

test('an event split anywhere between chunks is read whole', async () => {
  const text = 'event: done\ndata: {"model":"local"}\n\n'
  for (let cut = 1; cut < text.length; cut += 1) {
    expect(await read([text.slice(0, cut), text.slice(cut)])).toEqual([
      { event: 'done', data: '{"model":"local"}' },
    ])
  }
})

test('a character split between chunks is decoded whole', async () => {
  const bytes = new TextEncoder().encode('data: 29 × 37 cm\n\n') // × is two bytes
  const cut = bytes.indexOf(0xc3) + 1

  expect(await read([bytes.slice(0, cut), bytes.slice(cut)])).toEqual([
    { event: 'message', data: '29 × 37 cm' },
  ])
})

test('pings and other comments are ignored', async () => {
  expect(
    await read([': ping\n\n', 'event: token\ndata: {}\n\n', ': ping\n\n']),
  ).toEqual([{ event: 'token', data: '{}' }])
})

test('every kind of line ending works, even split between chunks', async () => {
  expect(
    await read(['event: a\r\ndata: 1\r', '\n\r\nevent: b\rdata: 2\r\r']),
  ).toEqual([
    { event: 'a', data: '1' },
    { event: 'b', data: '2' },
  ])
})

test('several data lines are joined, and an unfinished event is dropped', async () => {
  expect(
    await read([
      'data: first\ndata: second\n\n',
      'event: token\ndata: {"text":"x"}',
    ]),
  ).toEqual([{ event: 'message', data: 'first\nsecond' }])
})

test('a chunk with no line ending in it never ends an event early', async () => {
  expect(await read(['data: a\n', 'data', ': b\n\n'])).toEqual([
    { event: 'message', data: 'a\nb' },
  ])
})
