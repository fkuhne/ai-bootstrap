// The anonymous id that keeps what a user stores theirs (docs/foundations.md#users). There's no
// login: the browser makes a random UUID once, keeps it, and sends it as X-User-Id.

const KEY = 'user-id'
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// Where the id lives when the browser won't keep it, such as with storage blocked: for this visit.
let unkept: string | undefined

export function userId(): string {
  const kept = read()
  if (kept !== null && UUID.test(kept)) {
    return kept
  }
  const made = unkept ?? newUuid()
  if (!write(made)) {
    unkept = made
  }
  return made
}

// A random UUID, version 4. crypto.randomUUID exists only on secure pages (HTTPS, localhost);
// on any other plain-HTTP address, it's built from random bytes.
export function newUuid(): string {
  if (typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40 // version 4
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80 // the standard variant
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0'))
  const parts = [
    hex.slice(0, 4),
    hex.slice(4, 6),
    hex.slice(6, 8),
    hex.slice(8, 10),
    hex.slice(10),
  ]
  return parts.map((part) => part.join('')).join('-')
}

function read(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

function write(id: string): boolean {
  try {
    localStorage.setItem(KEY, id)
    return true
  } catch {
    return false
  }
}
