// The decision module's page (docs/foundations.md#the-decision-model): typed questions about a
// text, answered with probabilities.
import { Scale } from 'lucide-react'
import type { UiModule } from '../../uiModule'
import { DecisionPage } from './DecisionPage'
import { PATH } from './paths'

export const DECISION: UiModule = {
  name: 'decision',
  title: 'Decide',
  icon: Scale,
  path: PATH.slice(1),
  Page: DecisionPage,
}
