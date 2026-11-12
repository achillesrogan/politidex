const dataOn = process.env.POLITIDEX_DATA !== "0";
/** @type {import('next').NextConfig} */
export default {
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  env: { POLITIDEX_DATA: dataOn ? "1" : "0" },
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Robots-Tag", value: "noindex, nofollow" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ]}];
  },
  async redirects() {
    return [
      { source: "/research-methodology", destination: "/methodology", permanent: false },
      { source: "/politicians", destination: "/people", permanent: false },
      { source: "/investigate", destination: "/people", permanent: false },
      { source: "/influence-networks", destination: "/connections", permanent: false },
      { source: "/elections-2026", destination: "/", permanent: false },
      { source: "/elect/:slug", destination: "/", permanent: false },
    ];
  },
};
