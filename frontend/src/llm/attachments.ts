// Files attached to a message, read into the content parts the API takes
// (docs/foundations.md#the-chat-view).
import type { MediaPart } from '../api/types'
import type { Kind } from './content'

export interface Attachment {
  readonly id: string
  readonly name: string
  readonly part: MediaPart
}

// The kind of a file, from its media type: null for anything that isn't an image, a sound or a
// video, or when the browser can't tell.
export function fileKind(file: File): Kind | null {
  const [type] = file.type.split('/')
  return type === 'image' || type === 'audio' || type === 'video' ? type : null
}

// What the file picker offers, for the kinds the model takes.
export function acceptFor(kinds: readonly Kind[]): string {
  return kinds.map((kind) => `${kind}/*`).join(',')
}

// The file as a content part: an image as a data: URI; audio and video as base64 data and a
// format, such as wav, mp3 or mp4.
export async function readAttachment(
  file: File,
  kind: Kind,
): Promise<MediaPart> {
  const url = await dataUrl(file)
  if (kind === 'image') {
    return { type: 'image_url', image_url: { url } }
  }
  const media = {
    data: url.slice(url.indexOf(',') + 1),
    format: formatOf(file),
  }
  return kind === 'audio'
    ? { type: 'input_audio', input_audio: media }
    : { type: 'input_video', input_video: media }
}

// A sound's or a video's format, by the names OpenAI-compatible servers use: audio/mpeg is mp3,
// and the WAV types are wav; any other is its subtype, such as ogg or mp4.
function formatOf(file: File): string {
  const subtype = file.type.split('/')[1]?.split(';')[0] ?? ''
  if (subtype === 'mpeg') {
    return 'mp3'
  }
  return /^(x-)?wav(e)?$|^vnd\.wave$/.test(subtype) ? 'wav' : subtype
}

function dataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error ?? new Error('unreadable'))
    reader.readAsDataURL(file)
  })
}
