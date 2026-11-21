// OfficeFlow: mixed authenticated read + booking lifecycle workload.
// Independent browser and booking-cycle arrivals model the planned 80/20 mix.
// Peak: 79 HTML GET/s + 7 booking cycles/s x 3 writes = 100 HTTP RPS.
// The target is sustained for the configured duration after VU warm-up.
// This is a lighter, realistic MIX than the failed 25 lifecycle/s (75% writes)
// profile in CI #137; do not present that older stress profile as passed.
// Run ONLY against a disposable DEBUG=1 database with loadtest users and a test room.
import http from 'k6/http';
import { check, fail, sleep } from 'k6';
import { Counter } from 'k6/metrics';

const baseURL = (__ENV.BASE_URL || 'http://proxy').replace(/\/+$/, '');
const password = __ENV.K6_PASSWORD || '';
const userPrefix = __ENV.K6_USER_PREFIX || 'loadtest';
const roomId = Number(__ENV.K6_ROOM_ID || 0);
const timezoneOffset = __ENV.K6_TIMEZONE_OFFSET || '+03:00';

const reads = new Counter('officeflow_mixed_reads');
const createdCount = new Counter('officeflow_mixed_bookings_created');
const editedCount = new Counter('officeflow_mixed_bookings_edited');
const cancelledCount = new Counter('officeflow_mixed_bookings_cancelled');
const loginFailures = new Counter('officeflow_mixed_login_failures');

let session = null;

const readRate = Number(__ENV.READ_RPS || 79);
const bookingCyclesRate = Number(__ENV.BOOKING_CYCLES_RPS || 7);
const testDuration = __ENV.DURATION || '5m';

export const options = {
  scenarios: {
    browsing: {
      executor: 'constant-arrival-rate',
      exec: 'readOnly',
      rate: readRate,
      timeUnit: '1s',
      duration: testDuration,
      preAllocatedVUs: 40,
      maxVUs: 160,
      gracefulStop: '30s',
    },
    booking_cycles: {
      executor: 'constant-arrival-rate',
      exec: 'writeLifecycle',
      rate: bookingCyclesRate,
      timeUnit: '1s',
      duration: testDuration,
      preAllocatedVUs: 30,
      maxVUs: 100,
      gracefulStop: '30s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<200', 'p(99)<500'],
    http_req_failed: ['rate<0.001'],
    checks: ['rate>0.999'],
    dropped_iterations: ['count==0'],
    officeflow_mixed_reads: ['count>0'],
    officeflow_mixed_bookings_created: ['count>0'],
    officeflow_mixed_bookings_edited: ['count>0'],
    officeflow_mixed_bookings_cancelled: ['count>0'],
    officeflow_mixed_login_failures: ['count==0'],
  },
};

function authenticate() {
  if (!password || !roomId) {
    loginFailures.add(1);
    return null;
  }

  const username = userPrefix + String(__VU).padStart(2, '0');
  const loginURL = baseURL + '/accounts/login/';
  const loginPage = http.get(loginURL, {
    redirects: 0,
    tags: { phase: 'login_page' },
  });
  if (loginPage.status !== 200) {
    loginFailures.add(1);
    return null;
  }

  const tokenMatch = loginPage.body.match(/name=["']csrfmiddlewaretoken["']\s+value=["']([^"']+)["']/);
  if (!tokenMatch) {
    loginFailures.add(1);
    return null;
  }

  const login = http.post(
    loginURL,
    { username, password, csrfmiddlewaretoken: tokenMatch[1] },
    {
      redirects: 0,
      headers: { Referer: loginURL },
      tags: { phase: 'login_submit' },
    },
  );
  if (login.status !== 302) {
    loginFailures.add(1);
    return null;
  }

  const cookies = http.cookieJar().cookiesForURL(baseURL + '/');
  const sessionId = cookies.sessionid && cookies.sessionid[0];
  const csrfToken = cookies.csrftoken && cookies.csrftoken[0];
  if (!sessionId || !csrfToken) {
    loginFailures.add(1);
    return null;
  }
  return { sessionId, csrfToken };
}

export function readOnly() {
  if (!session) {
    session = authenticate();
    if (!session) {
      fail('Could not authenticate the isolated mixed-load read VU.');
    }
  }

  const readPaths = ['/rooms/', '/schedule/', '/my-bookings/'];
  const readPath = readPaths[Math.floor(Math.random() * readPaths.length)];
  // Keep the CSRF cookie alongside the session cookie. A rendered Django
  // page can issue a new CSRF cookie if the GET omits it; keeping only the
  // session cookie made subsequent POSTs use an outdated X-CSRFToken (403).
  const readResponse = http.get(baseURL + readPath, {
    redirects: 0,
    headers: {
      Cookie: 'sessionid=' + session.sessionId + '; csrftoken=' + session.csrfToken,
    },
    tags: { operation: 'read', route: readPath },
  });
  const freshCookies = http.cookieJar().cookiesForURL(baseURL + '/');
  if (freshCookies.csrftoken && freshCookies.csrftoken[0]) {
    session.csrfToken = freshCookies.csrftoken[0];
  }
  if (!check(readResponse, {
    'mixed authenticated read returns HTTP 200': (response) => response.status === 200,
  })) {
    console.error('Mixed read failed: HTTP ' + readResponse.status);
    return;
  }
  reads.add(1);
}

export function writeLifecycle() {
  if (!session) {
    session = authenticate();
    if (!session) {
      fail('Could not authenticate the isolated mixed-load writer VU.');
    }
  }

  const dayOffset = 30 + Math.floor((__VU - 1) / 9);
  const hour = 9 + ((__VU - 1) % 9);
  const day = new Date(Date.now() + dayOffset * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const startsAt = day + 'T' + String(hour).padStart(2, '0') + ':00:00' + timezoneOffset;
  const endsAt = day + 'T' + String(hour + 1).padStart(2, '0') + ':00:00' + timezoneOffset;
  const title = 'k6-mixed-' + __VU + '-' + __ITER + '-' + Date.now();

  const headers = {
    'Content-Type': 'application/json',
    Cookie: 'sessionid=' + session.sessionId + '; csrftoken=' + session.csrfToken,
    'X-CSRFToken': session.csrfToken,
    Referer: baseURL + '/',
  };

  const created = http.post(
    baseURL + '/api/v1/bookings/',
    JSON.stringify({
      room: roomId,
      title,
      notes: 'Disposable mixed read/write k6 workload',
      starts_at: startsAt,
      ends_at: endsAt,
    }),
    { headers, redirects: 0, tags: { operation: 'booking_create' } },
  );

  if (!check(created, {
    'mixed booking create returns HTTP 201': (response) => response.status === 201,
  })) {
    console.error('Mixed create failed: HTTP ' + created.status + '; body=' + created.body);
    return;
  }

  const bookingId = created.json('id');
  if (!bookingId) {
    fail('Mixed create returned HTTP 201 without a booking id.');
  }
  createdCount.add(1);

  const bookingURL = baseURL + '/api/v1/bookings/' + bookingId + '/';
  const editedTitle = 'k6-mixed-edited-' + __VU + '-' + __ITER;
  const edited = http.patch(
    bookingURL,
    JSON.stringify({ title: editedTitle, notes: 'Updated by mixed load test' }),
    { headers, redirects: 0, tags: { operation: 'booking_edit' } },
  );

  if (check(edited, {
    'mixed booking edit returns HTTP 200': (response) => response.status === 200,
    'mixed booking edit persists title': (response) => response.json('title') === editedTitle,
  })) {
    editedCount.add(1);
  } else {
    console.error('Mixed edit failed: HTTP ' + edited.status + '; body=' + edited.body);
  }

  const cancelled = http.post(
    baseURL + '/api/v1/bookings/' + bookingId + '/cancel/',
    JSON.stringify({}),
    { headers, redirects: 0, tags: { operation: 'booking_cancel' } },
  );
  if (check(cancelled, {
    'mixed booking cancel returns HTTP 200': (response) => response.status === 200,
    'mixed booking status is cancelled': (response) => response.json('status') === 'cancelled',
  })) {
    cancelledCount.add(1);
  } else {
    console.error('Mixed cancel failed: HTTP ' + cancelled.status + '; body=' + cancelled.body);
  }

  // Three API writes per lifecycle; keep each account below the 120/minute API throttle.
  sleep(2);
}
