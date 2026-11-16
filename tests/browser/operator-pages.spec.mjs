// Issue #684 — headless Chromium JS gate for the six shipped Sea Speed pages.
//
// Each test loads a real shipped page from the local fixture server
// (tests/browser/fixture-server.mjs) which answers every request with the
// production CSP as a real response header, so the browser enforces the policy
// the deploy actually ships. Listeners for console errors, uncaught exceptions,
// CSP violations, failed requests and script responses are registered BEFORE
// navigation; each page must then reach its own readiness condition AND have
// every one of its <script src> answered with 200.
//
// CDN stubbing: the shipped HTML loads hls.js from
// https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js. `page.route`
// fulfils exactly that URL with HLS_STUB_SOURCE, and any other
// cdn.jsdelivr.net request is aborted (a leaked request surfaces as a
// `requestfailed`, i.e. a test failure). The fixture server strips that tag's
// `integrity`/`crossorigin` attributes because a synthetic stub cannot satisfy
// the shipped SRI digest; the absolute CDN URL itself is preserved and asserted.

import { test, expect } from "@playwright/test";
import {
  CONTENT_SECURITY_POLICY,
  FIXTURE_PORT,
  HLS_CDN_URL,
  HLS_STUB_SOURCE,
  startFixtureServer,
} from "./fixture-server.mjs";

const ORIGIN = `http://127.0.0.1:${FIXTURE_PORT}`;

/** origin + pathname, so request/response/DOM URL shapes compare evenly. */
function urlKey(rawUrl) {
  const parsed = new URL(rawUrl);
  return `${parsed.origin}${parsed.pathname}`;
}

/** Resolve a fixture path (or absolute URL) to its origin + pathname key. */
function keyFor(target) {
  return urlKey(new URL(target, ORIGIN).href);
}

/**
 * Register every observation listener and route BEFORE navigation.
 * Playwright matches routes last-registered-first, so the catch-all CDN abort is
 * registered first and the exact hls.js fulfil wins.
 */
async function instrumentPage(page) {
  const observed = {
    consoleErrors: [],
    pageErrors: [],
    cspViolations: [],
    failedRequests: [],
    scriptStatus: new Map(),
  };

  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    observed.consoleErrors.push(text);
    if (/content security policy|refused to (execute|load|apply|connect)/i.test(text)) {
      observed.cspViolations.push(text);
    }
  });
  page.on("pageerror", (error) => {
    observed.pageErrors.push(error?.message ?? String(error));
  });
  page.on("requestfailed", (request) => {
    observed.failedRequests.push(
      `${request.resourceType()} ${urlKey(request.url())} ${request.failure()?.errorText ?? "unknown"}`,
    );
  });
  page.on("response", (response) => {
    if (response.request().resourceType() === "script") {
      observed.scriptStatus.set(urlKey(response.url()), response.status());
    }
  });

  // No internet at test time: any CDN request we did not stub is aborted.
  await page.route("https://cdn.jsdelivr.net/**", (route) => route.abort("blockedbyclient"));
  await page.route(HLS_CDN_URL, (route) =>
    route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/javascript; charset=utf-8",
        "Cache-Control": "no-store",
        "Content-Security-Policy": CONTENT_SECURITY_POLICY,
      },
      body: HLS_STUB_SOURCE,
    }),
  );

  return observed;
}

/** Navigate and prove the document itself carried the production CSP header. */
async function openPage(page, pathname) {
  const observed = await instrumentPage(page);
  const response = await page.goto(pathname, { waitUntil: "load" });
  expect(response, `no document response for ${pathname}`).not.toBeNull();
  expect(response.headers()["content-security-policy"], `CSP response header for ${pathname}`).toBe(
    CONTENT_SECURITY_POLICY,
  );
  return observed;
}

/**
 * Console-error allow-list: intentionally EMPTY for all six pages.
 * No shipped page script calls console.* at all, every resource the pages
 * request is answered 200 by the fixture, and the hls.js stub never requests
 * media — so nothing benign is expected to log. An entry here would have to be
 * justified per page, never used to paper over a real failure.
 */
const ALLOWED_CONSOLE_ERRORS = [];

function expectCleanBrowserState(observed, allowedConsoleErrors = ALLOWED_CONSOLE_ERRORS) {
  expect(observed.pageErrors, "uncaught page errors").toEqual([]);
  expect(observed.cspViolations, "Content Security Policy violations").toEqual([]);
  const unexpected = observed.consoleErrors.filter(
    (text) => !allowedConsoleErrors.some((pattern) => pattern.test(text)),
  );
  expect(unexpected, "console errors outside the allow-list").toEqual([]);
  expect(observed.failedRequests, "failed network requests").toEqual([]);
}

/** Every <script src> in the served document must exist and must have returned 200. */
async function expectAllScriptsLoaded(page, observed, expectedScripts) {
  const inDocument = await page.locator("script[src]").evaluateAll((elements) => elements.map((element) => element.src));
  const expectedKeys = expectedScripts.map(keyFor).sort();
  expect(inDocument.map(urlKey).sort(), "script tags in the served document").toEqual(expectedKeys);
  for (const key of expectedKeys) {
    expect(observed.scriptStatus.get(key), `script response status for ${key}`).toBe(200);
  }
}

/** login-popup.js exports an object (not a function) with these members. */
async function expectSeaSpeedAuth(page) {
  await expect
    .poll(
      () =>
        page.evaluate(() => ({
          auth: typeof window.SeaSpeedAuth,
          openLogin: typeof window.SeaSpeedAuth?.openLogin,
          showOverlay: typeof window.SeaSpeedAuth?.showOverlay,
        })),
      { timeout: 5_000, message: "window.SeaSpeedAuth must be live" },
    )
    .toEqual({ auth: "object", openLogin: "function", showOverlay: "function" });
}

test.describe("#684 operator pages under the production CSP", () => {
  let fixture;

  test.beforeAll(async () => {
    fixture = await startFixtureServer();
  });

  test.afterAll(async () => {
    await fixture?.close();
  });

  test("root page (/): login button and SeaSpeedAuth are live", async ({ page }) => {
    const observed = await openPage(page, "/");

    await expect(page.locator("#loginBtn")).toBeVisible();
    await expectSeaSpeedAuth(page);

    await expectAllScriptsLoaded(page, observed, ["/login-popup.js"]);
    expectCleanBrowserState(observed);
  });

  test("water page (/sea-speed/): authenticated session and live-sync module", async ({ page }) => {
    const scripts = [
      HLS_CDN_URL,
      "/sea-speed/crossing-line.js",
      "/sea-speed/overlay-canvas.js",
      "/login-popup.js",
      "/sea-speed/main.js",
      "/sea-speed/live-sync.js",
    ];
    const observed = await openPage(page, "/sea-speed/");

    await expect(page.locator("#sessionUser")).toHaveText("operator");
    await expect
      .poll(
        () =>
          page.evaluate(() => ({
            liveSync: typeof window.SeaSpeedLiveSync,
            bracketForMedia: typeof window.SeaSpeedLiveSync?.bracketForMedia,
          })),
        { timeout: 5_000, message: "window.SeaSpeedLiveSync must be live" },
      )
      .toEqual({ liveSync: "object", bracketForMedia: "function" });
    await expectSeaSpeedAuth(page);

    await expectAllScriptsLoaded(page, observed, scripts);
    expectCleanBrowserState(observed);
  });

  test("objects page (/sea-speed/objects/): registry boots with domain scope", async ({ page }) => {
    const scripts = ["/sea-speed/objects/crossings.js", "/login-popup.js", "/sea-speed/objects/registry.js"];
    const observed = await openPage(page, "/sea-speed/objects/");

    await expect(page.locator("#sessionUser")).toHaveText("operator");
    await expect(page.locator("#domainInput")).toHaveValue("water");
    // registry.js loadObjects() rendered its empty state -> /sea-speed/api/objects answered 200.
    await expect(page.locator("#objectsGrid")).toContainText("объектов нет");
    await expectSeaSpeedAuth(page);

    await expectAllScriptsLoaded(page, observed, scripts);
    expectCleanBrowserState(observed);
  });

  test("cameras page (/sea-speed/cameras/): both camera players present", async ({ page }) => {
    const scripts = [HLS_CDN_URL, "/login-popup.js", "/sea-speed/cameras/cameras.js"];
    const observed = await openPage(page, "/sea-speed/cameras/");

    await expect(page.locator("#cameraGrid")).toBeVisible();
    await expect(page.locator("#cameraGrid article.card")).toHaveCount(2);
    await expect(page.locator("#sessionUser")).toHaveText("operator");
    await expectSeaSpeedAuth(page);

    await expectAllScriptsLoaded(page, observed, scripts);
    expectCleanBrowserState(observed);
  });

  test("road page (/sea-speed/road/): crossing stats wired and session live", async ({ page }) => {
    const scripts = [
      "/sea-speed/road/config.js",
      HLS_CDN_URL,
      "/sea-speed/live-sync.js",
      "/sea-speed/overlay-canvas.js",
      "/login-popup.js",
      "/sea-speed/road/main.js",
    ];
    const observed = await openPage(page, "/sea-speed/road/");

    await expect(page.locator("#cxStatsRows")).toBeVisible();
    // road/main.js boot fills the date filter with today's Vladivostok date.
    await expect(page.locator("#cxFrom")).not.toHaveValue("");
    await expect(page.locator("#sessionUser")).toHaveText("operator");
    await expectSeaSpeedAuth(page);

    await expectAllScriptsLoaded(page, observed, scripts);
    expectCleanBrowserState(observed);
  });

  test("unavailable page (/sea-speed/unavailable.html): retry button is wired", async ({ page }) => {
    const observed = await openPage(page, "/sea-speed/unavailable.html");

    await expect(page.locator("#retry-button")).toBeVisible();
    await expectAllScriptsLoaded(page, observed, ["/sea-speed/unavailable.js"]);
    expectCleanBrowserState(observed);

    // unavailable.js wires #retry-button to location.reload(); observing the
    // reload proves the shipped script executed (an unwired button does nothing).
    const reloaded = page.waitForEvent("framenavigated", {
      predicate: (frame) => frame === page.mainFrame(),
      timeout: 10_000,
    });
    await page.locator("#retry-button").click();
    await reloaded;
    await page.waitForLoadState("load");

    await expect(page.locator("#retry-button")).toBeVisible();
    expectCleanBrowserState(observed);
  });

  test("hls.js is loaded from the local stub, not the internet", async ({ page }) => {
    const observed = await openPage(page, "/sea-speed/");

    const hls = await page.evaluate(() => {
      const element = document.querySelector('script[src*="hls.js"]');
      return {
        src: element?.src ?? null,
        integrity: element ? element.getAttribute("integrity") : undefined,
        supported: typeof window.Hls?.isSupported === "function" ? window.Hls.isSupported() : null,
      };
    });

    expect(hls.src, "DOM keeps the shipped absolute CDN URL").toBe(HLS_CDN_URL);
    expect(hls.integrity, "SRI digest cannot match a synthetic stub, so it is stripped").toBeNull();
    expect(hls.supported, "the served hls.js stub executed under CSP").toBe(true);
    expect(observed.scriptStatus.get(keyFor(HLS_CDN_URL))).toBe(200);
    expectCleanBrowserState(observed);
  });

  test("the served CSP header is really enforced by the browser", async ({ page }) => {
    const observed = await instrumentPage(page);
    const response = await page.goto("/", { waitUntil: "load" });
    expect(response.headers()["content-security-policy"]).toBe(CONTENT_SECURITY_POLICY);

    const violation = page.waitForEvent("console", {
      predicate: (message) => /content security policy|refused to execute inline/i.test(message.text()),
      timeout: 5_000,
    });
    const executed = await page.evaluate(() => {
      const script = document.createElement("script");
      script.textContent = "window.__seaSpeedCspInlineProbe = true;";
      document.head.appendChild(script);
      return window.__seaSpeedCspInlineProbe === true;
    });

    expect(executed, "inline script must be blocked by script-src 'self'").toBe(false);
    const message = await violation;
    expect(message.text()).toMatch(/content security policy/i);

    // This deliberate violation is the only noise this test tolerates.
    expect(observed.pageErrors).toEqual([]);
    expect(observed.failedRequests).toEqual([]);
  });
});
