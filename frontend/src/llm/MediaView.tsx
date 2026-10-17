// An image, a sound or a video from a message, shown or played in place.
import type { MediaPart } from '../api/types'
import { kindOf, sourceOf } from './content'
import styles from './MediaView.module.css'

export function MediaView({ part, name }: { part: MediaPart; name?: string }) {
  const source = sourceOf(part)
  switch (kindOf(part)) {
    case 'image':
      return (
        <img className={styles.image} src={source} alt={name ?? 'An image'} />
      )
    case 'audio':
      return (
        <audio
          className={styles.audio}
          src={source}
          controls
          aria-label={name ?? 'A sound'}
        />
      )
    case 'video':
      return (
        <video
          className={styles.video}
          src={source}
          controls
          aria-label={name ?? 'A video'}
        />
      )
  }
}
