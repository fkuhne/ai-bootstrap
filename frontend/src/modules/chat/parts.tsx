// What the module gives the shell: its provider, which keeps the conversation, its page and its
// sidebar content.
import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { SquarePen } from 'lucide-react'
import type { ViewMessage } from '../../llm/Message'
import type { SidebarProps } from '../../uiModule'
import { ChatContext, useChat } from './context'

export { ChatPage } from './ChatPage'

export function ChatProvider({ children }: { children: ReactNode }) {
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
  return <ChatContext value={chat}>{children}</ChatContext>
}

export function ChatSidebar({ onChoose }: SidebarProps) {
  const { clear } = useChat()
  return (
    <button
      type="button"
      className="sidebar-row"
      onClick={() => {
        clear()
        onChoose()
      }}
    >
      <SquarePen aria-hidden="true" />
      New chat
    </button>
  )
}
