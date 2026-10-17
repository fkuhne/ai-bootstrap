// Doing something again every few seconds while something isn't right
// (docs/foundations.md#the-web-ui).
import { useEffect } from 'react'

// How often the page checks again: the backend, what a page needs, and what a module lists.
// Short, so a service that has finished starting is noticed at once; a check is one small request.
export const POLL_MS = 3_000

// Runs `task` every POLL_MS while `active`, never two at a time: a check that outlasts the
// interval, such as readiness waiting for a busy model, is waited for, not piled up on. `task`
// must be stable, such as a `useCallback`, or the interval starts over at every render.
export function usePolling(
  task: () => Promise<unknown>,
  active: boolean,
): void {
  useEffect(() => {
    if (!active) {
      return
    }
    let running = false
    const timer = setInterval(() => {
      if (running) {
        return
      }
      running = true
      void task().finally(() => {
        running = false
      })
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [task, active])
}
