/**
 * vite.config.ts — Vite build configuration for the Chrome Extension
 *
 * Why is this different from a normal Vite app?
 *   A regular Vite app produces index.html + JS bundles.
 *   A Chrome extension needs a specific folder structure with a manifest.json,
 *   content scripts, service workers, etc.
 *
 *   @crxjs/vite-plugin bridges this gap:
 *     - It reads manifest.json as the root entry point
 *     - It finds all referenced JS/CSS files (content scripts, popup, etc.)
 *     - It compiles them correctly and outputs a proper extension folder
 *     - In dev mode (--watch), it even supports hot-reloading the extension
 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { crx } from '@crxjs/vite-plugin'
import manifest from './manifest.json'

export default defineConfig({
  plugins: [
    react(),          // Adds JSX/TSX support
    crx({ manifest }), // Handles Chrome extension output format
  ],
  build: {
    outDir: 'dist',   // The built extension will be in extension/dist/
    emptyOutDir: true,
  },
})
