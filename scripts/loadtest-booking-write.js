// Isolated write workload: each VU logs in as its own demo user,
// creates a unique standard-room booking, then cancels it immediately.
// Run ONLY against a disposable DEBUG=1 demo database.
import http from 'k6/http';
import { check, fail, sleep } from 'k6';

const baseURL = (__ENV.BASE_URL || 'http://proxy').replace(/\/+$/, '');
const password = __ENV.K6_PASSWORD || '';
const userPrefix = __ENV.K6_USER_PREFIX || 'loadtest';
const roomId = Number(__ENV.K6_ROOM_ID || 0);
const timezoneOffset = __ENV.K6_TIMEZONE_OFFSET || '+03:00';
let session = null;

export const options = {
  scenarios: {
    booking_lifecycle: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.TARGET_RPS || 8),
      timeUnit: '1s',
      duration: __ENV.DURATION || '30s',
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 10),
      maxVUs: Number(__ENV.MAX_VUS || 10),
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<1000'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
    dropped_iterations: ['count==0'],
  },
};

function authenticate() {
  if (!password || !roomId) {
    fail('Set K6_PASSWORD and K6_ROOM_ID for the isolated write test.');
  }

  const username = userPrefix + String(__VU).padStart(2, '0');
  const loginURL = baseURL + '/accounts/login/';
  const loginPage = http.get(loginURL, { redirects: 0, tags: { phase: 'login' } });
  if (loginPage.status !== 200) {
    fail('Login page unavailable: HTTP ' + loginPage.status);
  }

  const tokenMatch = loginPage.body.match(/name=["']csrfmiddlewaretoken["']\s+value=["']([^"']+)["']/);
  if (!tokenMatch) {
    fail('Could not find CSRF token on the login page.');
  }

  const login = http.post(
    loginURL,
    { username, password, csrfmiddlewaretoken: tokenMatch[1] },
    { redirects: 0, headers: { Referer: loginURL }, tags: { phase: 'login' } },
  );
  if (login.status !== 302) {
    fail('Login failed for ' + username + ': HTTP ' + login.status);
  }

  // Django rotates the CSRF cookie on login, so read it after the POST.
  const cookies = http.cookieJar().cookiesForURL(baseURL + '/');
  const sessionId = cookies.sessionid && cookies.sessionid[0];
  const csrfToken = cookies.csrftoken && cookies.csrftoken[0];
  if (!sessionId || !csrfToken) {
    fail('Login succeeded for ' + username + ', but session/CSRF cookies are missing.');
  }
  return { sessionId, csrfToken };
}

export default function () {
  if (!session) {
    session = authenticate();
  }

  // Each VU receives a disjoint range of future date/hour slots.
  const slot = (__VU - 1) * 100 + __ITER;
  const dayOffset = 30 + Math.floor(slot / 9);
  const hour = 9 + (slot % 9);
  const day = new Date(Date.now() + dayOffset * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const title = 'k6-' + __VU + '-' + __ITER + '-' + Date.now();

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
      notes: 'Disposable k6 write-load test',
      starts_at: day + 'T' + String(hour).padStart(2, '0') + ':00:00' + timezoneOffset,
      ends_at: day + 'T' + String(hour + 1).padStart(2, '0') + ':00:00' + timezoneOffset,
    }),
    { headers, redirects: 0, tags: { operation: 'booking_create' } },
  );

  const createOk = check(created, {
    'booking create returns HTTP 201': (response) => response.status === 201,
  });
  if (!createOk) {
    console.error('Booking create failed: HTTP ' + created.status + '; body=' + created.body);
    return;
  }

  const booking = created.json();
  if (!booking || !booking.id) {
    fail('Booking create returned HTTP 201 without a booking id.');
  }

  const cancelled = http.post(
    baseURL + '/api/v1/bookings/' + booking.id + '/cancel/',
    JSON.stringify({}),
    { headers, redirects: 0, tags: { operation: 'booking_cancel' } },
  );
  check(cancelled, {
    'booking cancel returns HTTP 200': (response) => response.status === 200,
    'booking status is cancelled': (response) => response.json('status') === 'cancelled',
  });

  // Pace each independent VU so the 8 lifecycles/s arrival rate uses
  // approximately 10 sessions while staying below the 120 API calls/min/user throttle.
  sleep(1.2);
}
