// How much the model reasons before it answers, chosen in the message form
// (docs/foundations.md#reasoning). Auto sends nothing, so the provider's default applies; the
// others are sent as `reasoning_effort`, the parameter OpenAI, Ollama and llama.cpp's server share.
import { useState } from 'react'
import type { Parameters } from '../api/types'

export const LEVELS = ['none', 'auto', 'low', 'medium', 'max'] as const

export type ReasoningLevel = (typeof LEVELS)[number]

export const LABELS: Record<ReasoningLevel, string> = {
  none: 'None',
  auto: 'Auto',
  low: 'Low',
  medium: 'Medium',
  max: 'Max',
}

// Max is `high`, the highest value every provider documents: `max` itself isn't among OpenAI's or
// Ollama's.
const EFFORT: Record<ReasoningLevel, string | null> = {
  none: 'none',
  auto: null,
  low: 'low',
  medium: 'medium',
  max: 'high',
}

export function parametersFor(level: ReasoningLevel): Parameters {
  const effort = EFFORT[level]
  return effort === null ? {} : { reasoning_effort: effort }
}

export function levelOf(value: string | null): ReasoningLevel {
  return LEVELS.find((level) => level === value) ?? 'auto'
}

const KEY = 'reasoning-level'

// The level chosen last, kept in the browser as the user's id is; Auto until one is chosen, or
// when the browser keeps nothing.
export function useReasoningLevel(): [
  ReasoningLevel,
  (level: ReasoningLevel) => void,
] {
  const [level, setLevel] = useState<ReasoningLevel>(() => {
    try {
      return levelOf(localStorage.getItem(KEY))
    } catch {
      return 'auto'
    }
  })
  function choose(chosen: ReasoningLevel) {
    setLevel(chosen)
    try {
      localStorage.setItem(KEY, chosen)
    } catch {
      // Kept for this visit only.
    }
  }
  return [level, choose]
}
