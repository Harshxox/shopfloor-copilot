import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'

// Dev: React on :5173, forwards /api and /media to FastAPI on :8000.
// Phone mode (`npm run phone`): HTTPS + listen on the LAN, because phone browsers only allow
// camera access on HTTPS pages. The phone opens https://<laptop-ip>:5173 and accepts the warning once.
// In Docker the backend is reachable as http://backend:8000 (set via VITE_PROXY_TARGET).
export default defineConfig(({ mode }) => {
  const target = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'
  const phone = mode === 'phone'
  return {
    plugins: [react(), ...(phone ? [basicSsl()] : [])],
    server: {
      port: 5173,
      host: phone ? true : 'localhost',
      proxy: { '/api': target, '/media': target },
    },
  }
})
