# Browser JS gate (issue #684)

Chromium-only Playwright suite over the six shipped operator pages: `npm ci && npx playwright install chromium && npm run test:browser`.
`fixture-server.mjs` serves the real `frontend/**` HTML/JS on `127.0.0.1:8131` with the production CSP as a real response
header, deterministic `/sea-speed/api/**` JSON and an `hls.js` stub served through `page.route` (no network); any other
CDN request is aborted. For every page the spec asserts: every `<script src>` returned 200, no uncaught page errors, no CSP
violations, no console errors (allow-list intentionally empty) and a page-specific readiness condition.
It proves browser enforcement of the supplied policy for the shipped assets. It does NOT prove the deployed nginx header
inheritance or the real CDN payload — those stay separate runtime probes. Note: the fixture strips the `integrity`/`crossorigin`
attributes of the hls.js tag (SRI cannot match a synthetic stub); the absolute CDN URL itself is preserved and asserted.
