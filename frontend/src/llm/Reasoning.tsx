// The model's reasoning, in a box folded above its answer, as in llama.cpp's web UI: open while
// it's being written, following its newest line, and closed once the answer starts. A click opens
// it again (docs/foundations.md#reasoning).
import { useLayoutEffect, useRef } from 'react'
import { ChevronDown, Lightbulb } from 'lucide-react'
import styles from './Reasoning.module.css'

export function Reasoning({
  text,
  streaming = false,
}: {
  text: string
  streaming?: boolean
}) {
  const box = useRef<HTMLDivElement>(null)

  // While it's written, the newest line stays in view.
  useLayoutEffect(() => {
    if (streaming && box.current !== null) {
      box.current.scrollTop = box.current.scrollHeight
    }
  }, [text, streaming])

  return (
    <details className={styles.reasoning} open={streaming}>
      <summary className={styles.summary}>
        <Lightbulb className={styles.icon} aria-hidden="true" />
        <span className={streaming ? 'shimmer' : undefined}>
          {streaming ? 'Reasoning…' : 'Reasoning'}
        </span>
        <ChevronDown className={styles.chevron} aria-hidden="true" />
      </summary>
      <div ref={box} className={styles.text}>
        {text}
      </div>
    </details>
  )
}
