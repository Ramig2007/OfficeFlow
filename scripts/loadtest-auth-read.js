// OfficeFlow: read-only authenticated workload for Django + PostgreSQL.
// Does NOT create, edit, approve or cancel bookings.
// The 100 RPS acceptance profile matches the stated project target; route-level
// Trends make a slow HTML page visible instead of hiding it in the aggregate.
import http from 'k6/http';
import { check, fail } from 'k6';
import { Trend } from 'k6/metrics';

const baseURL = (__ENV.BASE_URL || 'http://proxy').replace(/\/+$/, '');
const username = __ENV.K6_USERNAME || '';
const password = __ENV.K6_PASSWORD || '';

const routeDurations = {
  '/rooms/': new Trend('rooms_page_duration', true),
  '/schedule/': new Trend('schedule_page_duration', true),
  '/my-bookings/': new Trend('my_bookings_page_duration', true),
};

export const options = {
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  scenarios: {
    read_pages: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.TARGET_RPS || 100),
      timeUnit: '1s',
      duration: __ENV.DURATION || '15s',
      preAllocatedVUs: 120,
      maxVUs: 250,
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<200', 'p(99)<500'],
    rooms_page_duration: ['p(95)<200', 'p(99)<500'],
    schedule_page_duration: ['p(95)<200', 'p(99)<500'],
    my_bookings_page_duration: ['p(95)<200', 'p(99)<500'],
    http_req_failed: ['rate<0.001'],
    checks: ['rate>0.999'],
    dropped_iterations: ['count==0'],
  },
};

export function setup() {
  if (!username || !password) {
    fail('Set K6_USERNAME and K6_PASSWORD in the Docker container environment.');
  }
  const loginURL = `${baseURL}/accounts/login/`;
  const page = http.get(loginURL, { redirects: 0, tags: { phase: 'login' } });
  if (page.status !== 200) {
    fail(`Login page is not available: HTTP ${page.status}`);
  }
  const match = page.body.match(/name=["']csrfmiddlewaretoken["']\\s+value=["']([^"']+)["']/);
  if (!match) {
    fail('Could not find csrfmiddlewaretoken on login page.');
  }
  const login = http.post(
    loginURL,
    {
      username,
      password,
      csrfmiddlewaretoken: match[1],
    },
    {
      redirects: 0,
      headers: { Referer: loginURL },
      tags: { phase: 'login' },
    },
  );
  if (login.status !== 302) {
    fail(`Login failed: HTTP ${login.status}. Check credentials and CSRF setup.`);
  }
  const cookies = http.cookieJar().cookiesForURL(`${baseURL}/`);
  const sessionID = cookies.sessionid && cookies.sessionid[0];
  if (!sessionID) {
    fail('Login succeeded but no sessionid cookie was returned.');
  }
  return { sessionID };
}

export default function (state) {
  // Each route requires Django authentication and reads from PostgreSQL.
  const paths = ['/rooms/', '/schedule/', '/my-bookings/'];
  const path = paths[Math.floor(Math.random() * paths.length)];
  const response = http.get(`${baseURL}${path}`, {
    redirects: 0,
    headers: { Cookie: `sessionid=${state.sessionID}` },
    tags: { route: path, phase: 'workload' },
  });
  routeDurations[path].add(response.timings.duration);
  check(response, {
    'Authenticated HTML 200': (r) => r.status === 200,
  });
}
