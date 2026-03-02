import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      // Windows bind-mounts into Docker don't propagate native FS events.
      // Polling ensures Vite detects changes on all platforms.
      usePolling: true,
      interval: 500,
    },
  },
})
