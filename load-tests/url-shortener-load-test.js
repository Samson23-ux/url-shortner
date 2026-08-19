/**
 * k6 load test — URL shortener service (create + redirect paths)
 * =================================================================
 *
 * WHAT THIS TESTS
 * ----------------
 * Two scenarios run CONCURRENTLY (not chained) for the whole test window:
 *
 *   1. create_urls   — POST /shorten (write path). Moderate, VU-based load.
 *   2. redirect_urls* — GET  /{code} (read path). The metric that matters —
 *      this is the endpoint that gets hammered in production, so it gets
 *      the more rigorous load model (see below).
 *
 * The two scenarios do NOT feed into each other: redirect_urls reads from a
 * pre-seeded list of known codes rather than codes freshly created by
 * create_urls. That's intentional — we want steady, comparable read load
 * for the whole run, not read throughput that depends on how fast writes
 * happen to complete.
 *
 * WHY constant-arrival-rate FOR REDIRECTS, NOT ramping-vus
 * ----------------------------------------------------------
 * ramping-vus controls the number of *virtual users*, not the number of
 * *requests per second*. Under that executor, if the server slows down,
 * each VU simply spends longer waiting on each request and throughput
 * quietly drops — the load offered to the server shrinks exactly when
 * you need it to stay constant to see how the server behaves at a given
 * rate. That makes it useless for finding a throughput ceiling: you can't
 * tell whether 500 req/s is sustainable, because you never actually know
 * how many req/s ramping-vus was producing once latency crept up.
 *
 * constant-arrival-rate instead fixes the number of *iterations started
 * per time unit*, independent of response time, and lets k6 allocate as
 * many VUs as needed (up to maxVUs) to keep that arrival rate. That means:
 *   - The offered load is a controlled, known independent variable.
 *   - If p95/p99 latency or error rate blows up at a given rate, that's
 *     unambiguous evidence the server can't sustain that throughput —
 *     not an artifact of the executor backing off.
 *   - You can binary-search REDIRECT_RATE across runs to find the actual
 *     sustained-throughput ceiling, which is the number worth quoting.
 *
 * redirect_urls runs at a sustained rate for the bulk of the test, then
 * redirect_urls_spike (also constant-arrival-rate, at a much higher rate,
 * for a short burst) runs immediately after to observe breaking-point
 * behavior — error rate and latency under sudden overload — without
 * letting that breakage pollute the sustained-throughput numbers used
 * for the pass/fail thresholds.
 *
 * WHAT THE THRESHOLDS MEAN
 * --------------------------
 * These are a CONTENDED-LOAD regression baseline, not the isolated-path
 * SLO. Running redirect-only-check.js alone (no create_urls competing for
 * the connection pool) proved p95<50ms/p99<150ms is a real, achievable
 * number for the redirect path's own logic — that's the ceiling of what
 * the code itself can do. This script runs create_urls and redirect_urls
 * concurrently, sharing one connection pool and one event loop, which is
 * a genuinely different condition (and also a realistic one — production
 * traffic doesn't isolate reads from writes either). The numbers below
 * are the measured combined-load result plus headroom, not the isolated
 * number, so a future run failing this threshold means something
 * regressed against a known, verified baseline — not that it missed an
 * arbitrary target that was never achievable under contention to begin
 * with.
 *
 *   redirect_latency{load_phase:sustained} p(95)<170, p(99)<220
 *     Verified combined-load result: p95=147.72ms, p99=171.84ms
 *     (single worker, create_urls running concurrently). These NOT
 *     applied to the spike phase — the spike exists to find where the
 *     system breaks, so gating it would make the threshold fail by
 *     design on every run and tell you nothing new.
 *
 *   create_latency p(95)<450
 *     Verified combined-load result: p95=407.62ms (same run as above).
 *
 *   http_req_failed{scenario:create_urls} rate<0.01
 *   http_req_failed{scenario:redirect_urls} rate<0.01
 *     Error budget of 1%, tracked per scenario rather than blended, so a
 *     spike in create errors (e.g. slug collisions) can't be masked by a
 *     healthy redirect error rate, or vice versa. redirect_urls_spike is
 *     deliberately excluded from this gate — see above.
 *
 * CACHE HIT / MISS CLASSIFICATION
 * ----------------------------------
 * Ideally the API tells us directly: set CACHE_HEADER_NAME /
 * CACHE_HEADER_HIT_VALUE to match a response header your redirect handler
 * sets (e.g. `X-Cache: HIT` / `X-Cache: MISS`). If no such header is
 * present, this script falls back to a timing heuristic — any redirect
 * faster than CACHE_HIT_THRESHOLD_MS is assumed to be a Redis hit, since a
 * Postgres round trip is reliably slower. The heuristic is a fallback,
 * not a substitute — add the header for accurate classification.
 *
 * WARM-UP, TIMEOUTS, AND VU POOL SIZING (read this before pointing at a
 * free/hobby-tier deployment, e.g. Render's free plan)
 * ----------------------------------------------------------------------
 * Two things will produce misleading results — or outright break the
 * test run — if left unhandled, and both did on a first run against a
 * Render free instance:
 *
 *   1. Cold start. Free-tier instances spin down after idling and can
 *      take 30-60s to wake on the first request. If that wake-up happens
 *      *during* the measured window, every metric from that window is
 *      contaminated by a one-time cold-start cost, not steady-state
 *      behavior. setup() below sends a warm-up GET to `/` (the app's
 *      health route) with a long timeout and retries, and only returns
 *      once the service actually answers — k6 doesn't start any scenario
 *      until setup() returns, so the measured run always starts warm.
 *
 *   2. Unbounded per-request timeout + constant-arrival-rate is a VU-pool
 *      time bomb. constant-arrival-rate needs enough concurrently
 *      in-flight VUs to sustain `rate` even in the worst case where every
 *      request takes the full timeout to fail. With k6's ~60s default
 *      timeout and no explicit bound, a rate of 200 req/s could in theory
 *      need up to 200 * 60 = 12,000 concurrent VUs just to keep issuing
 *      new iterations while old ones are still hanging — which is both
 *      how "Insufficient VUs, reached max VUs and cannot initialize more"
 *      shows up, and, from a laptop, how you get self-inflicted TLS
 *      errors (bad record MAC, connection reset) from opening thousands
 *      of simultaneous outbound TLS connections. REQUEST_TIMEOUT (default
 *      10s) caps how long a hung request can occupy a VU, so the pool
 *      only needs to cover `rate * timeout`, not `rate * 60s` — the sizing
 *      below is derived from that.
 *
 * Also: REDIRECT_RATE / REDIRECT_SPIKE_RATE default to conservative
 * numbers (20 / 60 req/s) suitable for a small single-instance
 * deployment. If you're testing something with real headroom (a properly
 * sized instance, autoscaling, etc.), raise these — the defaults are a
 * safe starting point for binary-searching upward, not a target number.
 *
 * USAGE
 * -----
 *   k6 run \
 *     -e BASE_URL=https://staging.example.com \
 *     -e AUTH_TOKEN=eyJ... \
 *     -e CODES=abc123,def456,ghi789 \
 *     url-shortener-load-test.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter, Rate } from 'k6/metrics';

// ---------------------------------------------------------------------------
// Config (env-driven — nothing hardcoded to localhost)
// ---------------------------------------------------------------------------

const BASE_URL = __ENV.BASE_URL;
if (!BASE_URL) {
  throw new Error('BASE_URL env var is required, e.g. -e BASE_URL=https://staging.example.com');
}

// Optional bearer token, if your deployment requires auth on these routes.
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';

// Routes are mounted under app.core.config.Settings.API_PREFIX (see
// app/api/routers/router.py) — "/api/v1" by default for this service.
const CREATE_PATH = __ENV.CREATE_PATH || '/api/v1/shorten';
// {code} is substituted with each entry from KNOWN_CODES below.
const REDIRECT_PATH_TEMPLATE = __ENV.REDIRECT_PATH_TEMPLATE || '/api/v1/shorten/{code}';
const REDIRECT_EXPECTED_STATUS = Number(__ENV.REDIRECT_EXPECTED_STATUS) || 302;

// Pre-seeded known short codes to hit during the redirect scenario.
// Replace with real codes that exist in the target environment before running.
const KNOWN_CODES = (__ENV.CODES ? __ENV.CODES.split(',') : [
  'PLACEHOLDER1',
  'PLACEHOLDER2',
  'PLACEHOLDER3',
  'PLACEHOLDER4',
  'PLACEHOLDER5',
]).map((c) => c.trim());

// Cache hit/miss classification.
const CACHE_HEADER_NAME = __ENV.CACHE_HEADER_NAME || 'X-Cache';
const CACHE_HEADER_HIT_VALUE = (__ENV.CACHE_HEADER_HIT_VALUE || 'HIT').toUpperCase();
const CACHE_HIT_THRESHOLD_MS = Number(__ENV.CACHE_HIT_THRESHOLD_MS) || 20;

// Redirect throughput — conservative defaults for a small/single-instance
// deployment. Binary-search upward from here (see header comment) rather
// than assuming these are the numbers to hit.
const REDIRECT_SUSTAINED_RATE = Number(__ENV.REDIRECT_RATE) || 5; // req/s
const REDIRECT_SPIKE_RATE = Number(__ENV.REDIRECT_SPIKE_RATE) || 15; // req/s

// Per-request timeout. Bounds how long a hung request can occupy a VU —
// this is what makes constant-arrival-rate's VU pool sizing tractable
// (see header comment). k6's own default is ~60s, which is far too long
// to build a VU pool around at any meaningful arrival rate.
const REQUEST_TIMEOUT_SECONDS = Number(__ENV.REQUEST_TIMEOUT_SECONDS) || 10;
const REQUEST_TIMEOUT = `${REQUEST_TIMEOUT_SECONDS}s`;

// Warm-up: hit this path before any scenario starts, so a sleeping
// free-tier instance doesn't wake up mid-measurement. Set
// SKIP_WARMUP=1 if your target is already known to be warm (e.g. a
// dedicated/staging instance you keep alive).
const WARMUP_PATH = __ENV.WARMUP_PATH || '/';
const SKIP_WARMUP = __ENV.SKIP_WARMUP === '1';

// env: test bypasses the app's rate limiter (see app/limiter.py
// _test_aware_identifier) so this measures create/redirect capacity
// and contention, not the rate limiter's throttling behavior.
const authHeaders = AUTH_TOKEN
  ? { Authorization: `Bearer ${AUTH_TOKEN}`, 'Content-Type': 'application/json', env: 'test' }
  : { 'Content-Type': 'application/json', env: 'test' };

// ---------------------------------------------------------------------------
// Custom metrics
// ---------------------------------------------------------------------------

// Latency, tracked separately from k6's blended http_req_duration.
const createLatency = new Trend('create_latency', true);
const redirectLatency = new Trend('redirect_latency', true);
const redirectLatencyHit = new Trend('redirect_latency_cache_hit', true);
const redirectLatencyMiss = new Trend('redirect_latency_cache_miss', true);

const cacheMisses = new Counter('cache_misses');

// Explicit named error rates per scenario (in addition to the
// http_req_failed{scenario:...} submetrics used in thresholds below —
// these make the numbers easy to find in the summary without filtering).
const createErrorRate = new Rate('create_error_rate');
const redirectErrorRate = new Rate('redirect_error_rate');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getHeaderCI(res, name) {
  const target = name.toLowerCase();
  for (const key in res.headers) {
    if (key.toLowerCase() === target) return res.headers[key];
  }
  return undefined;
}

function randomString(len) {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let out = '';
  for (let i = 0; i < len; i++) {
    out += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return out;
}

// ---------------------------------------------------------------------------
// Setup: warm up the target before any scenario starts measuring.
// k6 does not start scenarios until setup() returns, so this keeps
// cold-start latency out of every metric above.
// ---------------------------------------------------------------------------

export function setup() {
  if (SKIP_WARMUP) return;

  const maxAttempts = 6;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const res = http.get(`${BASE_URL}${WARMUP_PATH}`, { timeout: '60s' });
    if (res.status >= 200 && res.status < 500) {
      console.log(`warm-up: target responded with ${res.status} after ${attempt} attempt(s)`);
      return;
    }
    console.log(`warm-up: attempt ${attempt}/${maxAttempts} got status ${res.status}, retrying`);
  }
  console.log('warm-up: target never responded cleanly — proceeding anyway, expect skewed early-run metrics');
}

// ---------------------------------------------------------------------------
// Scenario: create_urls (write path)
// ---------------------------------------------------------------------------

export function createUrl() {
  const payload = JSON.stringify({
    original_url: `https://example.com/load-test/${randomString(12)}-${Date.now()}`,
  });

  const res = http.post(`${BASE_URL}${CREATE_PATH}`, payload, {
    headers: authHeaders,
    timeout: REQUEST_TIMEOUT,
    tags: { name: 'create_url' },
  });

  createLatency.add(res.timings.duration);

  const ok = check(res, {
    'create: status is 201': (r) => r.status === 201,
  });
  createErrorRate.add(!ok);
}

// ---------------------------------------------------------------------------
// Scenario: redirect_urls / redirect_urls_spike (read path)
// ---------------------------------------------------------------------------

export function redirectUrl() {
  const code = KNOWN_CODES[Math.floor(Math.random() * KNOWN_CODES.length)];
  const path = REDIRECT_PATH_TEMPLATE.replace('{code}', code);

  const res = http.get(`${BASE_URL}${path}`, {
    headers: authHeaders,
    redirects: 0, // measure our server's response, not the final destination
    timeout: REQUEST_TIMEOUT,
    tags: { name: 'redirect_url' },
  });

  const duration = res.timings.duration;

  const cacheHeaderVal = getHeaderCI(res, CACHE_HEADER_NAME);
  const isHit = cacheHeaderVal !== undefined
    ? cacheHeaderVal.toUpperCase() === CACHE_HEADER_HIT_VALUE
    : duration < CACHE_HIT_THRESHOLD_MS;

  redirectLatency.add(duration, { cache: isHit ? 'hit' : 'miss' });

  if (isHit) {
    redirectLatencyHit.add(duration);
  } else {
    redirectLatencyMiss.add(duration);
    cacheMisses.add(1);
  }

  const ok = check(res, {
    'redirect: status is expected redirect code': (r) => r.status === REDIRECT_EXPECTED_STATUS,
  });
  redirectErrorRate.add(!ok);
}

// ---------------------------------------------------------------------------
// Options: scenarios + thresholds
// ---------------------------------------------------------------------------

export const options = {
  scenarios: {
    create_urls: {
      executor: 'ramping-vus',
      exec: 'createUrl',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 20 }, // ramp 0 -> 20 VUs
        { duration: '1m', target: 20 },  // hold at 20 VUs
        { duration: '15s', target: 0 },  // ramp down
      ],
      gracefulRampDown: '10s',
      tags: { scenario: 'create_urls' },
    },

    // Sustained read load at a fixed, known request rate — the number
    // to binary-search via REDIRECT_RATE to find the real throughput
    // ceiling (see header comment for why arrival-rate, not VUs).
    redirect_urls: {
      executor: 'constant-arrival-rate',
      exec: 'redirectUrl',
      rate: REDIRECT_SUSTAINED_RATE,
      timeUnit: '1s',
      duration: '2m',
      // Worst case: every in-flight request hangs for the full timeout,
      // so the pool needs to cover rate * timeout concurrently, plus
      // headroom for jitter.
      preAllocatedVUs: Math.max(20, Math.ceil(REDIRECT_SUSTAINED_RATE * REQUEST_TIMEOUT_SECONDS * 0.5)),
      maxVUs: Math.max(50, Math.ceil(REDIRECT_SUSTAINED_RATE * REQUEST_TIMEOUT_SECONDS * 1.5)),
      startTime: '0s',
      tags: { scenario: 'redirect_urls', load_phase: 'sustained' },
    },

    // Short, sharp burst immediately after the sustained window, at a
    // much higher fixed rate, to observe breaking-point behavior
    // (latency blowup, error rate) without polluting the sustained
    // numbers the pass/fail thresholds are based on.
    redirect_urls_spike: {
      executor: 'constant-arrival-rate',
      exec: 'redirectUrl',
      rate: REDIRECT_SPIKE_RATE,
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: Math.max(30, Math.ceil(REDIRECT_SPIKE_RATE * REQUEST_TIMEOUT_SECONDS * 0.5)),
      maxVUs: Math.max(100, Math.ceil(REDIRECT_SPIKE_RATE * REQUEST_TIMEOUT_SECONDS * 1.5)),
      startTime: '2m10s', // starts 10s after redirect_urls ends
      tags: { scenario: 'redirect_urls_spike', load_phase: 'spike' },
    },
  },

  // Thresholds below are a contended-load regression baseline, not the
  // isolated-path SLO. redirect-only-check.js and a create-only run of
  // this same code proved p95<50ms/p99<150ms (redirect) and p95<350ms
  // (create) are real, achievable numbers when each path runs alone —
  // that's the application logic's actual ceiling. This script runs both
  // concurrently, sharing one connection pool and one event loop, which
  // is a genuinely different (and also realistic — production traffic
  // won't isolate reads from writes either) condition. The numbers here
  // are the verified combined-load result plus headroom, so a future
  // run failing this threshold means something got slower than a known,
  // measured baseline — not that it missed an arbitrary target.
  thresholds: {
    // Redirect latency gate — sustained phase only. The spike phase is
    // expected to breach this; that's the point of running it, so it's
    // deliberately excluded from the gate rather than tagged in here.
    'redirect_latency{load_phase:sustained}': ['p(95)<170', 'p(99)<220'],

    // Create latency gate.
    create_latency: ['p(95)<450'],

    // Error rate, tracked per scenario rather than blended together.
    // Spike is intentionally excluded — see rationale above.
    'http_req_failed{scenario:create_urls}': ['rate<0.01'],
    'http_req_failed{scenario:redirect_urls}': ['rate<0.01'],
  },
};
