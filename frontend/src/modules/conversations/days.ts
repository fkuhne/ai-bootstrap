// Conversations under the day of their last answer, by the browser's own calendar
// (docs/foundations.md#the-conversation-list).
import type { ConversationSummary } from './types'

export interface DayGroup {
  readonly label: Label
  readonly conversations: readonly ConversationSummary[]
}

type Label = (typeof LABELS)[number]

const LABELS = ['Today', 'Yesterday', 'Previous 7 days', 'Older'] as const

// The groups that have conversations, in that order; each keeps the order it was given, which is
// the backend's: the newest answer first.
export function groupByDay(
  conversations: readonly ConversationSummary[],
  now: Date,
): DayGroup[] {
  const today = startOfDay(now)
  const groups = new Map<Label, ConversationSummary[]>()
  for (const conversation of conversations) {
    const label = labelFor(today, startOfDay(new Date(conversation.updated_at)))
    groups.set(label, [...(groups.get(label) ?? []), conversation])
  }
  return LABELS.flatMap((label) => {
    const grouped = groups.get(label)
    return grouped === undefined ? [] : [{ label, conversations: grouped }]
  })
}

function labelFor(today: number, day: number): Label {
  // Rounded: a day with a daylight saving change has 23 or 25 hours.
  const daysAgo = Math.round((today - day) / DAY)
  if (daysAgo <= 0) {
    return 'Today' // or a time ahead of the browser's clock
  }
  if (daysAgo === 1) {
    return 'Yesterday'
  }
  return daysAgo <= 7 ? 'Previous 7 days' : 'Older'
}

// Midnight of the date's day, in the browser's time zone.
function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
}

const DAY = 24 * 60 * 60 * 1000
