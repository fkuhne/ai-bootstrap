// The path the page is at, for a test to read, as the address bar would show it.
import { useLocation } from 'react-router'

export function Location() {
  return <span data-testid="location">{useLocation().pathname}</span>
}
