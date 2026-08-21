/**
 * k6 load test — URL shortener create path, ISOLATED (no concurrent reads)
 * ==========================================================================
 *
 * Companion to redirect-only-check.js, testing the other half of the same
 * question: url-shortener-load-test.js runs create_urls and redirect_urls
 * concurrently, sharing one connection pool and one event loop — the
 * combined-load thresholds in that script (create p95<450ms) were
 * recalibrated to that contended reality once it was confirmed real.
 *
 * This script isolates the write path to verify what its own ceiling
 * actually is with no reads competing for the pool: p95<200ms was the
 * original, aspirational target before any of this was measured. Run
 * this alone to find out whether that number is genuinely achievable
 * for the create path's own logic, the same way redirect-only-check.js
 * proved p95<50ms/p99<150ms was real for the redirect path.
 *
 * Same config knobs and metric names as url-shortener-load-test.js's
 * create_urls scenario — results are directly comparable between the two.
 *
 * Uses constant-arrival-rate (WRITE_RATE req/s) rather than ramping-vus,
 * for the same reason redirect-only-check.js does: a fixed VU count is
 * an emergent, not controlled, request rate — once latency moves under
 * load, the actual req/s a given VU count produces moves with it. A
 * fixed arrival rate is what makes binary-searching for the real
 * throughput ceiling possible.
 *
 * USAGE
 * -----
 *   k6 run \
 *     -e BASE_URL=http://localhost:8000 \
 *     -e AUTH_TOKEN=eyJ... \
 *     -e WRITE_RATE=5 \
 *     -e DEPLOYED=1 \
 *     load-tests/write-only-check.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate } from 'k6/metrics';

// ---------------------------------------------------------------------------
// Config (env-driven — nothing hardcoded to localhost)
// ---------------------------------------------------------------------------

const BASE_URL = __ENV.BASE_URL;
if (!BASE_URL) {
  throw new Error('BASE_URL env var is required, e.g. -e BASE_URL=http://localhost:8000');
}

const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const CREATE_PATH = __ENV.CREATE_PATH || '/api/v1/shorten';

// Write throughput — conservative default. Binary-search upward via
// WRITE_RATE to find the real ceiling, the same way REDIRECT_RATE is
// used for the read path, rather than reading it off an emergent VU
// ramp (which stops being a controlled variable once request latency
// itself moves under load).
const WRITE_RATE = Number(__ENV.WRITE_RATE) || 5; // req/s

// Selects which threshold set to gate on (see options.thresholds below).
// Deployed's own network RTT to Oregon is ~300ms before the app does
// anything, so a threshold calibrated to local measurements will always
// fail there regardless of app behavior. Set -e DEPLOYED=1 when pointing
// BASE_URL at the deployed instance.
const DEPLOYED = __ENV.DEPLOYED === '1';

const REQUEST_TIMEOUT_SECONDS = Number(__ENV.REQUEST_TIMEOUT_SECONDS) || 10;
const REQUEST_TIMEOUT = `${REQUEST_TIMEOUT_SECONDS}s`;

const WARMUP_PATH = __ENV.WARMUP_PATH || '/';
const SKIP_WARMUP = __ENV.SKIP_WARMUP === '1';

// env: test bypasses the app's rate limiter (see app/limiter.py
// _test_aware_identifier) so this measures the create path's own
// capacity, not the rate limiter's throttling behavior.
const authHeaders = AUTH_TOKEN
  ? { Authorization: `Bearer ${AUTH_TOKEN}`, 'Content-Type': 'application/json', env: 'test' }
  : { 'Content-Type': 'application/json', env: 'test' };

// ---------------------------------------------------------------------------
// Custom metrics — same names as the combined script for direct comparison
// ---------------------------------------------------------------------------

const createLatency = new Trend('create_latency', true);
const createErrorRate = new Rate('create_error_rate');

function randomString(len) {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let out = '';
  for (let i = 0; i < len; i++) {
    out += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return out;
}

// ---------------------------------------------------------------------------
// Setup: same warm-up as the combined and redirect-only scripts
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
// Scenario: create_urls only — no reads running
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
// Options: create scenario only, isolated-path SLO (not the contended-load
// baseline from url-shortener-load-test.js)
// ---------------------------------------------------------------------------

export const options = {
  scenarios: {
    create_urls: {
      executor: 'constant-arrival-rate',
      exec: 'createUrl',
      rate: WRITE_RATE,
      timeUnit: '1s',
      duration: '1m30s',
      // Worst case: every in-flight request hangs for the full timeout,
      // so the pool needs to cover rate * timeout concurrently.
      preAllocatedVUs: Math.max(20, Math.ceil(WRITE_RATE * REQUEST_TIMEOUT_SECONDS * 0.5)),
      maxVUs: Math.max(50, Math.ceil(WRITE_RATE * REQUEST_TIMEOUT_SECONDS * 1.5)),
      tags: { scenario: 'create_urls' },
    },
  },

  thresholds: DEPLOYED
    ? {
        // Calibrated against the deployed Render free-tier instance with
        // Postgres/Redis/app all in Frankfurt (EU-Central). At the default
        // 5 req/s, p95 ranged 264ms-1.17s across runs, 0% errors every
        // time — still real run-to-run variance, just a much lower floor
        // than Oregon (was 425-713ms *there*, i.e. a higher floor with
        // less spread). 10 req/s was tried too and no longer fails
        // outright the way it did on Oregon (0% errors both times), but
        // it's consistently much slower (p95 2.15s-5.87s) — so these
        // thresholds still only describe the 5 req/s point; 10 req/s is
        // "doesn't break" territory, not "fast" territory.
        create_latency: ['p(95)<1500'],
        http_req_failed: ['rate<0.02'],
      }
    : {
        create_latency: ['p(95)<200'],
        http_req_failed: ['rate<0.01'],
      },
};
