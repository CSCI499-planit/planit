import process from 'node:process'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

function normalizeBasePath(value) {
  if (!value) return '/'

  const withLeadingSlash = value.startsWith('/') ? value : `/${value}`
  return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`
}

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  if (command === 'build') {
    const required = ['VITE_API_BASE_URL', 'VITE_AZURE_MAPS_KEY']
    const missing = required.filter((key) => !env[key])

    if (missing.length > 0) {
      throw new Error(`Missing required frontend env var(s): ${missing.join(', ')}`)
    }
  }

  return {
    base: normalizeBasePath(env.VITE_BASE_PATH),
    plugins: [react()],
    server: {
      open: true,
    },
  }
})
