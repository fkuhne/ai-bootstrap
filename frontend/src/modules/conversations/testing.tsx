// What the module's page tests share: the fake backend with the module on, the app with it, and
// stored conversations and messages as the backend answers them.
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import App from '../../App'
import { fakeApi } from '../../test/api'
import { Location } from '../../test/Location'
import { CONVERSATIONS } from '.'

// The fake backend, with the module on and no conversations yet, unless a test gives its own.
export function fakeConversationsApi(routes: Parameters<typeof fakeApi>[0]) {
  return fakeApi(
    { 'GET /api/conversations': () => Response.json([]), ...routes },
    [CONVERSATIONS.name],
  )
}

// The app with this module alone, at the path, once the backend has said it's on; the path the
// page is at shows in `location`.
export async function renderConversations(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App modules={[CONVERSATIONS]} />
      <Location />
    </MemoryRouter>,
  )
  // The sidebar's new chat comes with the module, even in a closed drawer.
  await screen.findByRole('link', { name: 'New chat', hidden: true })
}

export const NOW = '2026-10-04T12:00:00Z'

export const DETAILS = {
  model: 'local-model',
  finish_reason: 'stop',
  usage: { prompt_tokens: 12, completion_tokens: 40, total_tokens: 52 },
  first_token_ms: 300,
  total_ms: 2300,
}

export function storedMessage(
  id: string,
  role: 'user' | 'assistant',
  content: unknown,
  reasoning: string | null = null,
) {
  return {
    id,
    parent_id: null,
    role,
    content,
    reasoning,
    created_at: NOW,
    details: role === 'assistant' ? DETAILS : null,
  }
}

export function conversation(id: string, messages: unknown[]) {
  return {
    id,
    title: messages.length > 0 ? 'A question' : null,
    created_at: NOW,
    updated_at: NOW,
    messages,
  }
}
