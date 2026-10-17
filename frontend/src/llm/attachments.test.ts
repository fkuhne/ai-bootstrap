import { expect, test } from 'vitest'
import { acceptFor, fileKind, readAttachment } from './attachments'

function file(name: string, type: string, bytes = 'abc') {
  return new File([bytes], name, { type })
}

test('a file is an image, a sound or a video by its media type', () => {
  expect(fileKind(file('a.png', 'image/png'))).toBe('image')
  expect(fileKind(file('a.wav', 'audio/wav'))).toBe('audio')
  expect(fileKind(file('a.mp4', 'video/mp4'))).toBe('video')
  expect(fileKind(file('a.pdf', 'application/pdf'))).toBeNull()
  expect(fileKind(file('a', ''))).toBeNull()
  expect(acceptFor(['image', 'audio'])).toBe('image/*,audio/*')
})

test('an image is sent as a data: URI', async () => {
  expect(await readAttachment(file('a.png', 'image/png'), 'image')).toEqual({
    type: 'image_url',
    image_url: { url: 'data:image/png;base64,YWJj' },
  })
})

test.each([
  ['audio/wav', 'wav'],
  ['audio/x-wav', 'wav'],
  ['audio/vnd.wave', 'wav'],
  ['audio/mpeg', 'mp3'],
  ['audio/ogg', 'ogg'],
])(
  'a %s sound is sent as base64 data in the %s format',
  async (type, format) => {
    expect(await readAttachment(file('a', type), 'audio')).toEqual({
      type: 'input_audio',
      input_audio: { data: 'YWJj', format },
    })
  },
)

test('a video is sent as base64 data with its format', async () => {
  expect(await readAttachment(file('a.mp4', 'video/mp4'), 'video')).toEqual({
    type: 'input_video',
    input_video: { data: 'YWJj', format: 'mp4' },
  })
})
