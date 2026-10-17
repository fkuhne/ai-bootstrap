// The model that answers, and the inputs it accepts (docs/foundations.md#the-chat-view): asked
// once, and again every POLL_MS while it can't be, as when the backend or the model is still
// starting.
import { useCallback, useEffect, useState } from 'react'
import { getModel } from '../api/client'
import type { ModelInfo } from '../api/types'
import { usePolling } from '../polling'

export function useModel(): ModelInfo | null {
  const [model, setModel] = useState<ModelInfo | null>(null)
  const [failed, setFailed] = useState(false)

  const load = useCallback(
    () =>
      getModel()
        .then((loaded) => {
          setModel(loaded)
          setFailed(false)
        })
        .catch(() => setFailed(true)),
    [],
  )

  useEffect(() => {
    void load()
  }, [load])
  usePolling(load, failed)

  return model
}
