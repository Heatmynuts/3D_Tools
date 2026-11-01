import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI backend runs on :8000; the dev server forwards /api to it.
// VITE_PORT / API_URL allow a second, isolated instance (e.g. for tests).
export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.VITE_PORT ?? 5180),
    strictPort: true,
    proxy: { '/api': process.env.API_URL ?? 'http://127.0.0.1:8000' },
  },
})
