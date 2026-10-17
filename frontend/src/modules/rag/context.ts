// The conversation, kept in the browser for as long as the page isn't reloaded: shared by the
// module's page, which adds to it, and its sidebar, which starts a new one.
import { createContext, useContext } from 'react'
import type { ViewMessage } from '../../llm/Message'

export interface DocumentsChat {
  readonly messages: readonly ViewMessage[]
  readonly add: (...messages: ViewMessage[]) => void
  readonly clear: () => void
  // How many times it was cleared, so the page drops an answer still on it too.
  readonly cleared: number
}

export const DocumentsContext = createContext<DocumentsChat | null>(null)

export function useDocumentsChat(): DocumentsChat {
  const chat = useContext(DocumentsContext)
  if (chat === null) {
    throw new Error('The conversation is read inside DocumentsProvider.')
  }
  return chat
}
