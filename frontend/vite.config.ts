import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiUrl = env.VITE_API_URL || 'http://localhost:8000';
  const ccremoteUrl = env.VITE_CCREMOTE_URL || 'http://localhost:3000';

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/ccremote': {
          target: ccremoteUrl,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/ccremote/, ''),
        },
        '/api': {
          target: apiUrl,
          changeOrigin: true,
        },
      },
    },
  };
});
