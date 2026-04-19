/** @type {import('next').NextConfig} */
const BACKEND = process.env.BACKEND_URL || 'http://localhost:5005';

const nextConfig = {
  async rewrites() {
    return [
      { source: '/status',            destination: `${BACKEND}/status` },
      { source: '/api/:path*',        destination: `${BACKEND}/api/:path*` },
      { source: '/login',             destination: `${BACKEND}/login` },
      { source: '/app',               destination: `${BACKEND}/app` },
      { source: '/planner',           destination: `${BACKEND}/planner` },
      { source: '/privacy',           destination: `${BACKEND}/privacy` },
      { source: '/maez_hero.html',    destination: `${BACKEND}/maez_hero.html` },
      { source: '/maez_analytics.js', destination: `${BACKEND}/maez_analytics.js` },
    ];
  },

  webpack(config, { isServer }) {
    if (isServer) {
      config.externals = [...(config.externals || []), 'three'];
    }
    return config;
  },
};

export default nextConfig;
