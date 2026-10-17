// The stored documents, for the sidebar: loaded once, and again after each answer, so a document
// stored meanwhile shows. A load that failed is tried again every POLL_MS: the backend, or
// Qdrant, may still be starting.
import { useCallback, useEffect, useRef, useState } from 'react'
import { failureMessage } from '../../api/client'
import { usePolling } from '../../polling'
import { listSources } from './api'
import type { SourceSummary } from './types'

export interface StoredDocuments {
  // Null until the first load answers.
  readonly list: readonly SourceSummary[] | null
  readonly error: string | null
}

export function useStoredDocuments(answers: number): StoredDocuments {
  const [list, setList] = useState<readonly SourceSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Only the newest load counts: an older one may answer after it.
  const latest = useRef(0)

  const load = useCallback(() => {
    const mine = ++latest.current
    return listSources()
      .then((loaded) => {
        if (mine === latest.current) {
          setList(loaded.sources)
          setError(null)
        }
      })
      .catch((failure: unknown) => {
        if (mine === latest.current) {
          setError(failureMessage(failure))
        }
      })
  }, [])

  useEffect(() => {
    void load()
  }, [load, answers])
  usePolling(load, error !== null)

  return { list, error }
}
