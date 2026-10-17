// The chat module's page (docs/foundations.md#chat-whole-or-streamed): a chat whose conversation
// the browser keeps. Conversations' page, which the backend stores, replaces it when both modules
// are on.
import { MessageSquare } from 'lucide-react'
import type { UiModule } from '../../uiModule'
import { ChatPage, ChatProvider, ChatSidebar } from './parts'
import { PATH } from './paths'

export const CHAT: UiModule = {
  name: 'chat',
  title: 'Chat',
  icon: MessageSquare,
  path: PATH.slice(1),
  Page: ChatPage,
  Sidebar: ChatSidebar,
  Provider: ChatProvider,
}
