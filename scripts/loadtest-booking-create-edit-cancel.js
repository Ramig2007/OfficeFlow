// OfficeFlow: mixed authenticated read + booking lifecycle workload.
// Each iteration performs one HTML read plus create -> edit -> cancel.
// At the peak 25 lifecycles/s this is 100 HTTP requests/s (25 reads + 75 writes).
// Run ONLY against a disposable DEBUG=1 database; Compose volumes are destroyed afterwards.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';

const baseURL = (__ENV.BASE_URL || 'http://proxy').replace(/\/+$/, '');
const password = __ENV.K6_PASSWORD || '';
const userPrefix = __ENV.K6_USER_PREFIX || 'loadtest';
const roomId = Number(__ENV.K6_ROOM_ID || 0);
const timezoneOffset = __ENV.K6_TIMEZONE_OFFSET || '+03:00';
const createdCount = new Counter('officeflow_bookings_created');
const editedCount = new Counter('officeflow_bookings_edited');
const cancelledCount = new Counter('officeflow_bookings_cancelled');
const readCount = new Counter('officeflow_mixed_reads');
const loginFailures = new Counter('officeflow_write_login_failures');
let session = null;

export const options = {
  scenarios: {
    booking_create_edit_cancel: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 120,
      stages: [
        { target: 10, duration: '1m' },
        { target: 20, duration: '1m' },
        { target: 25, duration: '2m' },
      ],
      gracefulStop: '30s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<200', 'p(99)<500'],
    http_req_failed: ['rate<0.001'],
    checks: ['rate>0.999'],
    dropped_iterations: ['count==0'],
    officeflow_bookings_created: ['count>0'],
    officeflow_bookings_edited: ['count>0'],
    officeflow_bookings_cancelled: ['count>0'],
    officeflow_mixed_reads: ['count>0'],
    officeflow_write_login_failures: ['count==0'],
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

export default function () {
  if (!session) {
    session = authenticate();
    if (!session) {
      sleep(2);
      return;
    }
  }

  const readPaths = ['/rooms/', '/schedule/', '/my-bookings/'];
  const readPath = readPaths[Math.floor(Math.random() * readPaths.length)];
  const readResponse = http.get(baseURL + readPath, {
    redirects: 0,
    headers: { Cookie: 'sessionid=' + session.sessionId },
    tags: { operation: 'read', route: readPath },
  });
  if (!check(readResponse, {
    'mixed authenticated read returns HTTP 200': (response) => response.status === 200,
  })) {
    console.error('Read failed: HTTP ' + readResponse.status);
    return;
  }
  readCount.add(1);

  // Nine hourly slots per day, unique across VUs and safely inside the 180-day limit.
  const dayOffset = 30 + Math.floor((__VU - 1) / 9);
  const hour = 9 + ((__VU - 1) % 9);
  const day = new Date(Date.now() + dayOffset * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const startsAt = day + 'T' + String(hour).padStart(2, '0') + ':00:00' + timezoneOffset;
  const endsAt = day + 'T' + String(hour + 1).padStart(2, '0') + ':00:00' + timezoneOffset;
  const title = 'k6-create-' + __VU + '-' + __ITER + '-' + Date.now();

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
    'booking create returns HTTP 201': (response) => response.status === 201,
  })) {
    console.error('Create failed: HTTP ' + created.status + '; body=' + created.body);
    return;
  }

  const bookingId = created.json('id');
  if (!bookingId) {
    console.error('Create returned HTTP 201 without a booking id.');
    return;
  }
  createdCount.add(1);

  const bookingURL = baseURL + '/api/v1/bookings/' + bookingId + '/';
  const editedTitle = 'k6-edited-' + __VU + '-' + __ITER;
  const edited = http.patch(
    bookingURL,
    JSON.stringify({
      title: editedTitle,
      notes: 'Updated by isolated write-load test',
    }),
    { headers, redirects: 0, tags: { operation: 'booking_edit' } },
  );

  const editOk = check(edited, {
    'booking edit returns HTTP 200': (response) => response.status === 200,
    'booking edit persists the new title': (response) => response.json('title') === editedTitle,
  });
  if (editOk) {
    editedCount.add(1);
  } else {
    console.error('Edit failed: HTTP ' + edited.status + '; body=' + edited.body);
  }

  // Always attempt cleanup after a successful create, even when the edit assertion fails.
  const cancelled = http.post(
    baseURL + '/api/v1/bookings/' + bookingId + '/cancel/',
    JSON.stringify({}),
    { headers, redirects: 0, tags: { operation: 'booking_cancel' } },
  );
  if (check(cancelled, {
    'booking cancel returns HTTP 200': (response) => response.status === 200,
    'booking status is cancelled': (response) => response.json('status') === 'cancelled',
  })) {
    cancelledCount.add(1);
  } else {
    console.error('Cancel failed: HTTP ' + cancelled.status + '; body=' + cancelled.body);
  }

  // Three API writes plus one HTML read per lifecycle; API write throttling stays below 120/minute per VU.
  sleep(2);
}
