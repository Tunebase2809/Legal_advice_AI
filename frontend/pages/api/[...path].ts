import type { NextApiRequest, NextApiResponse } from 'next';
import httpProxy from 'http-proxy';

// Create proxy instance outside of request handler to avoid memory leaks
const proxy = httpProxy.createProxyServer({
  target: 'http://127.0.0.1:5000',
  changeOrigin: true,
  // Tăng thời gian chờ lên 5 phút (300,000 ms) để đợi AI Gemini xử lý xong
  proxyTimeout: 300000,
  timeout: 300000,
});

// IMPORTANT: Tell Next.js not to parse the body automatically
// This is necessary so the proxy can handle streaming, file uploads, and multipart forms correctly.
export const config = {
  api: {
    bodyParser: false,
    externalResolver: true,
  },
};

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  return new Promise((resolve, reject) => {
    proxy.web(req, res, {}, (err) => {
      if (err) {
        console.error('Lỗi Custom Proxy:', err);
        if (!res.headersSent) {
          res.status(500).json({ error: 'Proxy Error', details: err.message });
        }
        return reject(err);
      }
      resolve(true);
    });
  });
}
