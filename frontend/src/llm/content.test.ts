import { expect, test } from 'vitest'
import type { MediaPart } from '../api/types'
import { contentOf, inWords, mediaOf, sourceOf, textOf } from './content'

const IMAGE: MediaPart = {
  type: 'image_url',
  image_url: { url: 'data:image/png;base64,AAAA' },
}
const SOUND: MediaPart = {
  type: 'input_audio',
  input_audio: { data: 'UklG', format: 'mp3' },
}

test('the text of a message is its text parts, joined', () => {
  expect(textOf('Hello')).toBe('Hello')
  expect(
    textOf([
      { type: 'text', text: 'What is' },
      IMAGE,
      { type: 'text', text: 'this?' },
    ]),
  ).toBe('What is this?')
  expect(mediaOf([{ type: 'text', text: 'Hi' }, IMAGE])).toEqual([IMAGE])
  expect(mediaOf('Hi')).toEqual([])
})

test('the content sent is the text alone, or parts with the text first', () => {
  expect(contentOf('Hi', [])).toBe('Hi')
  expect(contentOf('  ', [])).toBeNull()
  expect(contentOf('', [IMAGE])).toEqual([IMAGE])
  expect(contentOf('What color?', [IMAGE, SOUND])).toEqual([
    { type: 'text', text: 'What color?' },
    IMAGE,
    SOUND,
  ])
})

test('media plays from its URL, or from its data as a data: URI', () => {
  expect(sourceOf(IMAGE)).toBe('data:image/png;base64,AAAA')
  expect(sourceOf(SOUND)).toBe('data:audio/mpeg;base64,UklG')
  expect(sourceOf({ type: 'input_video', input_video: { data: 'AAAA' } })).toBe(
    'data:video/mp4;base64,AAAA',
  )
  expect(
    sourceOf({
      type: 'input_audio',
      input_audio: { url: 'https://example.com/a.wav' },
    }),
  ).toBe('https://example.com/a.wav')
})

test('the kinds a model takes read as words', () => {
  expect(inWords(['image'])).toBe('images')
  expect(inWords(['image', 'video'])).toBe('images or video')
  expect(inWords(['image', 'audio', 'video'])).toBe('images, audio or video')
})
