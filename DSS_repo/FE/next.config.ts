import type { NextConfig } from 'next';
import { resolve } from 'node:path';

const frontendRoot = resolve(__dirname);
const config: NextConfig = {
  turbopack: {root: frontendRoot},
  outputFileTracingRoot: frontendRoot,
  async redirects() {
    return [{source: '/training', destination: '/evaluation', permanent: false}];
  },
  async rewrites() {
    return [
      {source: '/api/:path*', destination: `${process.env.API_URL || 'http://127.0.0.1:4000'}/api/:path*`},
      {source: '/legacy-api/:path*', destination: `${process.env.LEGACY_API_URL || 'http://127.0.0.1:8000'}/:path*`},
    ];
  },
};
export default config;
