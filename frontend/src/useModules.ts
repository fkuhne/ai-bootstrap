// The modules the backend has on (docs/foundations.md#modules): asked once, and again every
// POLL_MS while it can't be, as when the backend is still starting.
import { useCallback, useEffect, useState } from 'react'
import { getModules } from './api/client'
import { usePolling } from './polling'

export interface ModulesOn {
  // Their names; null until the backend has answered.
  readonly names: readonly string[] | null
  // The last ask failed: the backend can't be reached yet.
  readonly failed: boolean
}

export function useModules(): ModulesOn {
  const [names, setNames] = useState<readonly string[] | null>(null)
  const [failed, setFailed] = useState(false)

  const load = useCallback(
    () =>
      getModules()
        .then((list) => {
          setNames(list.modules.map((module) => module.name))
          setFailed(false)
        })
        .catch(() => setFailed(true)),
    [],
  )

  useEffect(() => {
    void load()
  }, [load])
  usePolling(load, failed)

  return { names, failed }
}
