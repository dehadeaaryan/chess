import { defineConfig, loadEnv } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
export default defineConfig(({ mode }) => ({
  plugins: [svelte()],
  server: { proxy: { '/api': loadEnv(mode, '.', 'CHESS_').CHESS_API_URL || 'http://127.0.0.1:8000' } },
}));
