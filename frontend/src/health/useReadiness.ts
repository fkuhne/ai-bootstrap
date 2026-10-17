// Whether the backend can answer a page (docs/foundations.md#the-web-ui): checked when the page
// opens, again when asked (after an answer), and every POLL_MS while something it needs isn't
// ready, the backend itself included. A page needs only some checks: a chat page, the LLM's, and
// not a module's it doesn't call. Never while an answer streams: on a model with one slot, readiness's ping waits
// behind the answer, past its 5 s, and the model would look unavailable when it's only busy.
import { useCallback, useEffect, useRef, useState } from 'react'
import { getReadiness } from '../api/client'
import { usePolling } from '../polling'

export interface Readiness {
  // What isn't ready: the page's checks that failed, such as 'llm', or 'backend' when it can't be
  // reached at all.
  readonly notReady: readonly string[]
  readonly recheck: () => void
}

// `needed` names the backend's checks the page needs; a constant, so it doesn't change between
// renders.
export function useReadiness(
  needed: readonly string[],
  paused: boolean,
): Readiness {
  const [notReady, setNotReady] = useState<readonly string[]>([])
  // Only the newest check counts: an older one may answer after it.
  const latest = useRef(0)

  const check = useCallback(() => {
    const mine = ++latest.current
    const apply = (names: readonly string[]) => {
      if (mine === latest.current) {
        setNotReady(names)
      }
    }
    return getReadiness()
      .then((readiness) =>
        apply(
          Object.entries(readiness.checks)
            .filter(
              ([name, status]) => needed.includes(name) && status !== 'ok',
            )
            .map(([name]) => name),
        ),
      )
      .catch(() => apply(['backend']))
  }, [needed])

  const recheck = useCallback(() => {
    void check()
  }, [check])

  useEffect(recheck, [recheck])
  usePolling(check, !paused && notReady.length > 0)

  return { notReady, recheck }
}
