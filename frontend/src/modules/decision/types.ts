// Short names for the decision module's models, generated from the backend's OpenAPI schema
// (docs/foundations.md#the-decision-model).
import type { components } from '../../api/schema'

type Models = components['schemas']

export type DecisionRequest = Models['DecisionRequest']
export type Decision = Models['Decision']
export type Question = DecisionRequest['questions'][string]
export type NoulAnswer = Models['NoulAnswer']
export type ChoiceAnswer = Models['ChoiceAnswer']
export type ScoreAnswer = Models['ScoreAnswer']
