// Short names for the core's models. `npm run api:types` generates them into schema.d.ts from
// the backend's OpenAPI schema, which is never edited by hand (docs/foundations.md#the-web-ui).
// Each module names its own models in its folder.
import type { components } from './schema'

type Models = components['schemas']

export type Readiness = Models['Readiness']
export type ModelInfo = Models['ModelInfo']
export type Input = ModelInfo['inputs'][number]
export type ModuleList = Models['ModuleList']

// A message to the LLM, as the LLM port takes it: the schema always holds it, whichever modules
// are on. Its content is text, or parts with text, images, audio and video.
export type ChatMessage = Models['ChatMessage']
export type Content = ChatMessage['content']
export type TextPart = Models['TextPart']
export type ImagePart = Models['ImagePart']
export type AudioPart = Models['AudioPart']
export type VideoPart = Models['VideoPart']
export type MediaPart = ImagePart | AudioPart | VideoPart

// Generation parameters, such as reasoning_effort, sent as given.
export type Parameters = Readonly<Record<string, unknown>>

// The data of a streamed answer's events; each module's stream ends with its own `done`.
export type ReasoningDelta = Models['ReasoningDelta']
export type ContentDelta = Models['ContentDelta']
export type StreamEnd = Models['StreamEnd']
export type ErrorEvent = Models['ErrorEvent']
