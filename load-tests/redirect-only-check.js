/**
 * k6 load test — URL shortener redirect path, ISOLATED (no concurrent writes)
 * ============================================================================
 *
 * Companion to url-shortener-load-test.js, with create_urls removed entirely.
 * The combined script showed redirect_latency_cache_miss clustering at almost
 * exactly 10.00-10.01s for every miss — suspiciously exact, and matching both
 * this script's REQUEST_TIMEOUT and app/database/session.py's pool_timeout=10.0.
 * That's the signature of connection-pool starvation, not slow queries: a
 * cache-miss redirect's Postgres read was waiting behind create_urls' write
 * traffic for a pool connection, timing out instead of completing.
 *
 * This script isolates the redirect path to test that theory directly: with
 * no writes competing for the pool, does the cache-miss tail disappear? If
 * p95/p99 come back clean here, the earlier failure was read/write contention
 * on a shared, undersized pool — not the redirect logic itself being slow.
 * If misses are still slow here, the redirect's own DB query is the problem.
 *
 * Same config knobs, metrics, and thresholds as url-shortener-load-test.js —
 * results are directly comparable between the two runs.
 *
 * USAGE
 * -----
 *   k6 run \
 *     -e BASE_URL=http://localhost:8000 \
 *     -e AUTH_TOKEN=eyJ... \
 *     -e CODES=abc123,def456,ghi789 \
 *     load-tests/redirect-only-check.js
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

const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';

const REDIRECT_PATH_TEMPLATE = __ENV.REDIRECT_PATH_TEMPLATE || '/api/v1/shorten/{code}';
const REDIRECT_EXPECTED_STATUS = Number(__ENV.REDIRECT_EXPECTED_STATUS) || 302;

const KNOWN_CODES = (__ENV.CODES ? __ENV.CODES.split(',') : [
  'PLACEHOLDER1',
  'PLACEHOLDER2',
  'PLACEHOLDER3',
  'PLACEHOLDER4',
  'PLACEHOLDER5',
]).map((c) => c.trim());

const CACHE_HEADER_NAME = __ENV.CACHE_HEADER_NAME || 'X-Cache';
const CACHE_HEADER_HIT_VALUE = (__ENV.CACHE_HEADER_HIT_VALUE || 'HIT').toUpperCase();
const CACHE_HIT_THRESHOLD_MS = Number(__ENV.CACHE_HIT_THRESHOLD_MS) || 20;

// Same defaults as the combined script, so this run is a like-for-like
// comparison against that one.
const REDIRECT_SUSTAINED_RATE = Number(__ENV.REDIRECT_RATE) || 20; // req/s
const REDIRECT_SPIKE_RATE = Number(__ENV.REDIRECT_SPIKE_RATE) || 60; // req/s

const REQUEST_TIMEOUT_SECONDS = Number(__ENV.REQUEST_TIMEOUT_SECONDS) || 10;
const REQUEST_TIMEOUT = `${REQUEST_TIMEOUT_SECONDS}s`;

const WARMUP_PATH = __ENV.WARMUP_PATH || '/';
const SKIP_WARMUP = __ENV.SKIP_WARMUP === '1';

const authHeaders = AUTH_TOKEN
  ? { Authorization: `Bearer ${AUTH_TOKEN}`, 'Content-Type': 'application/json' }
  : { 'Content-Type': 'application/json' };

// ---------------------------------------------------------------------------
// Custom metrics — same names as the combined script for direct comparison
// ---------------------------------------------------------------------------

const redirectLatency = new Trend('redirect_latency', true);
const redirectLatencyHit = new Trend('redirect_latency_cache_hit', true);
const redirectLatencyMiss = new Trend('redirect_latency_cache_miss', true);
const cacheMisses = new Counter('cache_misses');
const redirectErrorRate = new Rate('redirect_error_rate');

function getHeaderCI(res, name) {
  const target = name.toLowerCase();
  for (const key in res.headers) {
    if (key.toLowerCase() === target) return res.headers[key];
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// Setup: same warm-up as the combined script
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
// Scenario: redirect_urls / redirect_urls_spike only — no writes running
// ---------------------------------------------------------------------------

export function redirectUrl() {
  const code = KNOWN_CODES[Math.floor(Math.random() * KNOWN_CODES.length)];
  const path = REDIRECT_PATH_TEMPLATE.replace('{code}', code);

  const res = http.get(`${BASE_URL}${path}`, {
    headers: authHeaders,
    redirects: 0,
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
// Options: redirect scenarios only, same thresholds as the combined script
// ---------------------------------------------------------------------------

export const options = {
  scenarios: {
    redirect_urls: {
      executor: 'constant-arrival-rate',
      exec: 'redirectUrl',
      rate: REDIRECT_SUSTAINED_RATE,
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: Math.max(20, Math.ceil(REDIRECT_SUSTAINED_RATE * REQUEST_TIMEOUT_SECONDS * 0.5)),
      maxVUs: Math.max(50, Math.ceil(REDIRECT_SUSTAINED_RATE * REQUEST_TIMEOUT_SECONDS * 1.5)),
      startTime: '0s',
      tags: { scenario: 'redirect_urls', load_phase: 'sustained' },
    },

    redirect_urls_spike: {
      executor: 'constant-arrival-rate',
      exec: 'redirectUrl',
      rate: REDIRECT_SPIKE_RATE,
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: Math.max(30, Math.ceil(REDIRECT_SPIKE_RATE * REQUEST_TIMEOUT_SECONDS * 0.5)),
      maxVUs: Math.max(100, Math.ceil(REDIRECT_SPIKE_RATE * REQUEST_TIMEOUT_SECONDS * 1.5)),
      startTime: '2m10s',
      tags: { scenario: 'redirect_urls_spike', load_phase: 'spike' },
    },
  },

  thresholds: {
    'redirect_latency{load_phase:sustained}': ['p(95)<50', 'p(99)<150'],
    'http_req_failed{scenario:redirect_urls}': ['rate<0.01'],
  },
};
