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
 *   redirect_latency{load_phase:sustained} p(95)<50, p(99)<150
 *     The redirect is a cache-fronted lookup + HTTP redirect — it should
 *     be fast for the overwhelming majority of requests. p95<50ms says
 *     "the typical user experience is snappy"; p99<150ms caps how bad the
 *     long tail (mostly cache misses hitting Postgres) is allowed to get.
 *     These are NOT applied to the spike phase — the spike exists to find
 *     where the system breaks, so gating it would make the threshold fail
 *     by design on every run and tell you nothing new.
 *
 *   create_latency p(95)<200
 *     Writes do more work (slug generation, DB insert, cache/filter
 *     updates) so they get a looser bound than reads, but 200ms still
 *     keeps the create path feeling responsive under moderate load.
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

const CREATE_PATH = __ENV.CREATE_PATH || '/shorten';
// {code} is substituted with each entry from KNOWN_CODES below.
const REDIRECT_PATH_TEMPLATE = __ENV.REDIRECT_PATH_TEMPLATE || '/shorten/{code}';
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

// Redirect throughput — tune these to binary-search the real ceiling.
const REDIRECT_SUSTAINED_RATE = Number(__ENV.REDIRECT_RATE) || 200; // req/s
const REDIRECT_SPIKE_RATE = Number(__ENV.REDIRECT_SPIKE_RATE) || 800; // req/s

const authHeaders = AUTH_TOKEN
  ? { Authorization: `Bearer ${AUTH_TOKEN}`, 'Content-Type': 'application/json' }
  : { 'Content-Type': 'application/json' };

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
// Scenario: create_urls (write path)
// ---------------------------------------------------------------------------

export function createUrl() {
  const payload = JSON.stringify({
    original_url: `https://example.com/load-test/${randomString(12)}-${Date.now()}`,
  });

  const res = http.post(`${BASE_URL}${CREATE_PATH}`, payload, {
    headers: authHeaders,
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
      preAllocatedVUs: Math.max(50, Math.ceil(REDIRECT_SUSTAINED_RATE * 0.5)),
      maxVUs: Math.max(200, REDIRECT_SUSTAINED_RATE * 3),
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
      preAllocatedVUs: Math.max(150, Math.ceil(REDIRECT_SPIKE_RATE * 0.5)),
      maxVUs: Math.max(600, REDIRECT_SPIKE_RATE * 3),
      startTime: '2m10s', // starts 10s after redirect_urls ends
      tags: { scenario: 'redirect_urls_spike', load_phase: 'spike' },
    },
  },

  thresholds: {
    // Redirect latency gate — sustained phase only. The spike phase is
    // expected to breach this; that's the point of running it, so it's
    // deliberately excluded from the gate rather than tagged in here.
    'redirect_latency{load_phase:sustained}': ['p(95)<50', 'p(99)<150'],

    // Create latency gate.
    create_latency: ['p(95)<200'],

    // Error rate, tracked per scenario rather than blended together.
    // Spike is intentionally excluded — see rationale above.
    'http_req_failed{scenario:create_urls}': ['rate<0.01'],
    'http_req_failed{scenario:redirect_urls}': ['rate<0.01'],
  },
};
