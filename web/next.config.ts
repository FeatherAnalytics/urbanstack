import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/urbanstack",
  images: { unoptimized: true },
};

export default nextConfig;
