import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export for Firebase Hosting (CDN delivery, no Node.js server required)
  output: "export",

  // Required when using 'output: export' — Next.js Image Optimization
  // needs a server runtime which static exports don't have.
  images: {
    unoptimized: true,
  },

  // Pass API URL through at build time so the client bundle can reach Cloud Run.
  // Override in CI/CD with the actual Cloud Run URL.
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080",
  },

  // Trailing slashes produce index.html files per route — required for
  // Firebase Hosting's single-page app routing to work correctly.
  trailingSlash: true,
};

export default nextConfig;
