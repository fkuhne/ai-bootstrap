// What the module gives the shell: its provider, which keeps the conversation, its page and its
// sidebar content.
import { useCallback, useMemo, useState, type ReactNode } from 'react'
import type { ViewMessage } from '../../llm/Message'
import { DocumentsContext } from './context'

export { DocumentList } from './DocumentList'
export { DocumentsPage } from './DocumentsPage'

export function DocumentsProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<readonly ViewMessage[]>([])
  const [cleared, setCleared] = useState(0)

  const add = useCallback(
    (...added: ViewMessage[]) =>
      setMessages((current) => [...current, ...added]),
    [],
  )
  const clear = useCallback(() => {
    setMessages([])
    setCleared((count) => count + 1)
  }, [])

  const chat = useMemo(
    () => ({ messages, add, clear, cleared }),
    [messages, add, clear, cleared],
  )
  return <DocumentsContext value={chat}>{children}</DocumentsContext>
}
