// OfficeFlow: 1,000 independent authenticated sessions on a disposable CI stack.
// Each VU owns a unique loadtest account and keeps its Django session alive.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';

const baseURL = (__ENV.BASE_URL || 'http://proxy').replace(/\/+$/, '');
const password = __ENV.K6_PASSWORD || '';
const userPrefix = __ENV.K6_USER_PREFIX || 'loadtest';
const authenticatedUsers = new Counter('officeflow_authenticated_users');
const loginFailures = new Counter('officeflow_login_failures');
const paths = [
  '/api/v1/rooms/',
  '/api/v1/bookings/?mine=1',
  '/api/v1/schedule/',
];
let session = null;

export const options = {
  scenarios: {
    concurrent_authenticated_users: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 100 },
        { duration: '1m', target: 250 },
        { duration: '1m', target: 500 },
        { duration: '1m', target: 750 },
        { duration: '2m', target: 1000 },
        { duration: '3m', target: 1000 },
        { duration: '1m', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
    officeflow_authenticated_users: ['count==1000'],
    officeflow_login_failures: ['count==0'],
  },
};

function authenticate() {
  if (!password) {
    loginFailures.add(1);
    return null;
  }

  const username = userPrefix + String(__VU).padStart(2, '0');
  const loginURL = baseURL + '/accounts/login/';
  const loginPage = http.get(loginURL, {
    redirects: 0,
    tags: { phase: 'login_page' },
  });
  if (!check(loginPage, {
    'login page returns HTTP 200': (response) => response.status === 200,
  })) {
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
    {
      username,
      password,
      csrfmiddlewaretoken: tokenMatch[1],
    },
    {
      redirects: 0,
      headers: { Referer: loginURL },
      tags: { phase: 'login_submit' },
    },
  );
  if (!check(login, {
    'independent user login returns HTTP 302': (response) => response.status === 302,
  })) {
    loginFailures.add(1);
    return null;
  }

  const cookies = http.cookieJar().cookiesForURL(baseURL + '/');
  const sessionId = cookies.sessionid && cookies.sessionid[0];
  if (!sessionId) {
    loginFailures.add(1);
    return null;
  }

  authenticatedUsers.add(1);
  return { sessionId, username };
}

export default function () {
  if (!session) {
    session = authenticate();
    if (!session) {
      sleep(10);
      return;
    }
  }

  const path = paths[(__VU + __ITER) % paths.length];
  const response = http.get(baseURL + path, {
    redirects: 0,
    headers: { Cookie: 'sessionid=' + session.sessionId },
    tags: { phase: 'authenticated_workload', route: path },
  });

  check(response, {
    'authenticated API request returns HTTP 200': (result) => result.status === 200,
  });

  // Keep each independent session alive while 1,000 VUs are held concurrently.
  sleep(10);
}
