import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Fail the production build clearly when VITE_API_BASE_URL is not set.
 * In development the client falls back to http://127.0.0.1:8000, so the
 * variable is optional locally.
 */
function requireApiBaseUrl(env: Record<string, string>): Plugin {
  return {
    name: 'require-api-base-url',
    apply: 'build',
    configResolved(config) {
      const url = env.VITE_API_BASE_URL || process.env.VITE_API_BASE_URL
      if (config.mode === 'production' && (!url || !url.trim())) {
        throw new Error(
          '[build] VITE_API_BASE_URL is not set.\n' +
            'Set it to the backend URL before building for production, e.g.:\n' +
            '  VITE_API_BASE_URL=https://your-backend.onrender.com npm run build',
        )
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss(), requireApiBaseUrl(env)],
  }
})

