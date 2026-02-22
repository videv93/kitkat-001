/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  base: '/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // ConnectKit's family dependency needs Node.js events polyfill
      events: 'events',
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
