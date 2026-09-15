/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ['*.ngrok-free.dev', '*.ngrok.io'],
  // Removed rewrites to use custom pages/api proxy for higher timeout
};

export default nextConfig;
