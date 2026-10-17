// Short names for the conversations module's models, generated from the backend's OpenAPI schema
// (docs/foundations.md#the-web-ui).
import type { components } from '../../api/schema'

type Models = components['schemas']

export type ConversationSummary = Models['ConversationSummary']
export type ConversationWithMessages = Models['ConversationWithMessages']
export type StoredMessage = Models['StoredMessage']
export type AnswerDetails = Models['AnswerDetails']
export type AskRequest = Models['AskRequest']
// The data of a stored answer's `done` event: the ids the question and the answer were stored
// under.
export type ConversationDoneEvent = Models['ConversationDoneEvent']
