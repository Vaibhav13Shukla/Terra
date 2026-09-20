import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export -> ./out. The app has no API routes, middleware or server
  // actions (auth and data both talk to Cognito / the Terra API straight from
  // the browser), so it can be hosted as plain files on Amplify Hosting, S3 +
  // CloudFront, or any static host — no Node server to run or pay for.
  output: "export",
};

export default nextConfig;
