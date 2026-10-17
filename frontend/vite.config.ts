import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The app's name, in the page's title and its sidebar: APP_NAME, the API's title too. The image
// passes it in at build time (docs/foundations.md#the-web-ui).
process.env.VITE_APP_NAME ||= 'ai-bootstrap'

// https://vite.dev/config/ and https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // `npm run dev` serves the app on its own port; the API stays on the backend's, so the dev
    // server forwards /api to it, as nginx does in the container.
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
