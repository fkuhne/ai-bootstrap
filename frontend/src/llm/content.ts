// A message's content as the API carries it: text, or parts with text, images, audio and video
// (docs/foundations.md#every-parameter-and-input).
import type { Content, Input, MediaPart, TextPart } from '../api/types'

export type Kind = Exclude<Input, 'text'>

// The text of a message: its text parts joined, as the backend joins them.
export function textOf(content: Content): string {
  if (typeof content === 'string') {
    return content
  }
  return content
    .filter((part): part is TextPart => part.type === 'text')
    .map((part) => part.text)
    .join(' ')
}

export function mediaOf(content: Content): readonly MediaPart[] {
  if (typeof content === 'string') {
    return []
  }
  return content.filter((part): part is MediaPart => part.type !== 'text')
}

// What to send: the text alone when nothing is attached, or the text, if any, then the media;
// null when there's nothing to send.
export function contentOf(
  text: string,
  media: readonly MediaPart[],
): Content | null {
  const blank = text.trim() === ''
  if (media.length === 0) {
    return blank ? null : text
  }
  return blank ? [...media] : [{ type: 'text', text }, ...media]
}

export function kindOf(part: MediaPart): Kind {
  switch (part.type) {
    case 'image_url':
      return 'image'
    case 'input_audio':
      return 'audio'
    case 'input_video':
      return 'video'
  }
}

// Where the browser can show or play a part: its URL, or its data as a data: URI.
export function sourceOf(part: MediaPart): string {
  if (part.type === 'image_url') {
    return part.image_url.url
  }
  const media =
    part.type === 'input_audio' ? part.input_audio : part.input_video
  if (media.url) {
    return media.url
  }
  const kind = kindOf(part)
  const format = media.format ?? (kind === 'audio' ? 'wav' : 'mp4')
  // mp3's media type is audio/mpeg.
  const subtype = format === 'mp3' ? 'mpeg' : format
  return `data:${kind}/${subtype};base64,${media.data ?? ''}`
}

// The kinds a model takes, in words: "images", "images or video", "images, audio or video".
export function inWords(kinds: readonly Kind[]): string {
  const words = kinds.map((kind) => (kind === 'image' ? 'images' : kind))
  if (words.length <= 1) {
    return words.join('')
  }
  return `${words.slice(0, -1).join(', ')} or ${words.at(-1)}`
}
