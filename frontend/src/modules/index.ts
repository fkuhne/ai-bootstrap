// The web UI's modules: each one's pages, which the shell shows while the backend has the module
// on (docs/foundations.md#modules). To add one, add its line; to remove one, delete its line and
// its folder, with the backend's module.
import type { UiModule } from '../uiModule'
import { CHAT } from './chat'
import { CONVERSATIONS } from './conversations'
import { DECISION } from './decision'
import { RAG } from './rag'

export const MODULES: readonly UiModule[] = [CONVERSATIONS, CHAT, RAG, DECISION]
