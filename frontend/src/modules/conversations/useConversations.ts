// The user's conversations, for the sidebar (docs/foundations.md#the-conversation-list): loaded
// once, again whenever an answer is stored, and without one once it's deleted. A load that failed
// is tried again every POLL_MS, by itself: the backend may still be starting.
import { useCallback, useEffect, useRef, useState } from 'react'
import { failureMessage } from '../../api/client'
import { deleteConversation, listConversations } from './api'
import type { ConversationSummary } from './types'
import { usePolling } from '../../polling'

export interface Conversations {
  // Null until the first load answers.
  readonly list: readonly ConversationSummary[] | null
  // When the list was loaded: the day the sidebar's "Today" means.
  readonly loadedAt: Date | null
  readonly error: string | null
  readonly refresh: () => void
  // Rejects with the failure, for the row that asked to show it.
  readonly remove: (id: string) => Promise<void>
}

export function useConversations(): Conversations {
  const [list, setList] = useState<readonly ConversationSummary[] | null>(null)
  const [loadedAt, setLoadedAt] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Only the newest load counts: an older one may answer after it.
  const latest = useRef(0)

  const load = useCallback(() => {
    const mine = ++latest.current
    return listConversations()
      .then((loaded) => {
        if (mine === latest.current) {
          setList(loaded)
          setLoadedAt(new Date())
          setError(null)
        }
      })
      .catch((failure: unknown) => {
        if (mine === latest.current) {
          setError(failureMessage(failure))
        }
      })
  }, [])

  const refresh = useCallback(() => {
    void load()
  }, [load])

  useEffect(refresh, [refresh])
  usePolling(load, error !== null)

  const remove = useCallback(
    async (id: string) => {
      await deleteConversation(id)
      setList((current) => current?.filter((c) => c.id !== id) ?? null)
      refresh() // and a load started before the delete no longer counts
    },
    [refresh],
  )

  return { list, loadedAt, error, refresh, remove }
}
