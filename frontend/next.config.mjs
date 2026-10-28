/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Self-contained server bundle for the Docker image (node .next/standalone/server.js)
  output: "standalone",
  experimental: {
    typedRoutes: false,
  },
};

export default nextConfig;
