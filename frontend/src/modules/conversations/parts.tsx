// What the module gives the shell: its provider, its page and its sidebar content.
import type { ReactNode } from 'react'
import { Route, Routes } from 'react-router'
import type { SidebarProps } from '../../uiModule'
import { ConversationsContext, useConversationsContext } from './context'
import { ConversationList } from './ConversationList'
import { ConversationPage } from './ConversationPage'
import { useConversations } from './useConversations'

export function ConversationsProvider({ children }: { children: ReactNode }) {
  return (
    <ConversationsContext value={useConversations()}>
      {children}
    </ConversationsContext>
  )
}

// ConversationPage is the parent of both routes, so it's one component across both URLs: a first
// question that moves the URL to its new conversation keeps its stream.
export function ConversationsPage() {
  const { refresh } = useConversationsContext()
  return (
    <Routes>
      <Route element={<ConversationPage onStored={refresh} />}>
        <Route index element={null} />
        <Route path=":conversationId" element={null} />
      </Route>
    </Routes>
  )
}

export function ConversationsSidebar({ onChoose }: SidebarProps) {
  return (
    <ConversationList
      conversations={useConversationsContext()}
      onChoose={onChoose}
    />
  )
}
