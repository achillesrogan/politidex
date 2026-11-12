import type { MetadataRoute } from "next";
// Pre-launch: block all crawlers. Replace only after the maintainer approves a public launch.
export default function robots(): MetadataRoute.Robots {
  return { rules: [{ userAgent: "*", disallow: "/" }] };
}
