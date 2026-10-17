// The conversations module's pages (docs/foundations.md#conversations): a chat whose conversations
// the backend stores, listed in the sidebar. It asks the model itself, so it replaces chat's page,
// which forgets, when both modules are on.
import { MessagesSquare } from 'lucide-react'
import type { UiModule } from '../../uiModule'
import {
  ConversationsPage,
  ConversationsProvider,
  ConversationsSidebar,
} from './parts'
import { PATH } from './paths'

export const CONVERSATIONS: UiModule = {
  name: 'conversations',
  title: 'Chat',
  icon: MessagesSquare,
  path: PATH.slice(1),
  Page: ConversationsPage,
  Sidebar: ConversationsSidebar,
  Provider: ConversationsProvider,
  replaces: ['chat'],
}
