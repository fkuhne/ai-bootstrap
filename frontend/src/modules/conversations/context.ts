// The user's conversations, shared by the module's page and its sidebar: the page refreshes the
// list once an answer is stored, and the sidebar shows it.
import { createContext, useContext } from 'react'
import type { Conversations } from './useConversations'

export const ConversationsContext = createContext<Conversations | null>(null)

export function useConversationsContext(): Conversations {
  const conversations = useContext(ConversationsContext)
  if (conversations === null) {
    throw new Error('The conversations are read inside ConversationsProvider.')
  }
  return conversations
}
