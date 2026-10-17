// The decision module's call (docs/foundations.md#the-decision-model): typed questions about a
// text, answered with probabilities.
import { request } from '../../api/client'
import type { Decision, DecisionRequest } from './types'

export function decide(body: DecisionRequest): Promise<Decision> {
  return request('/decide', { method: 'POST', body: JSON.stringify(body) })
}
