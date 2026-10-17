// Adds DOM matchers such as toBeInTheDocument() to Vitest's expect, unmounts what each test
// rendered, and gives jsdom a matchMedia.
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import { mediaQueries } from './media'

afterEach(cleanup)

// jsdom has no matchMedia: no query matches, as on a wide screen, unless a test stubs it.
window.matchMedia = mediaQueries(false)
