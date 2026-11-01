import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: the React app runs on :5173 and forwards /api and /media to FastAPI on :8000.
// In Docker the backend is reachable as http://backend:8000 (set via VITE_PROXY_TARGET).
const target = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': target,
      '/media': target,
    },
  },
})
