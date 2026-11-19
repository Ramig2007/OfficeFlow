import http from 'k6/http';
import { check, sleep } from 'k6';

const host = __ENV.BASE_URL || 'http://localhost:8080';
export const options = {
  scenarios: {
    baseline: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.TARGET_RPS || 100),
      timeUnit: '1s', duration: __ENV.DURATION || '2m',
      preAllocatedVUs: 120, maxVUs: 300,
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<200'],
    http_req_failed: ['rate<0.001'],
  },
};
export default function () {
  // Public liveness path: a first-stage baseline. Authenticated booking flows
  // need a prepared user session and a separate dedicated k6 script.
  const res = http.get(`${host}/health/live/`);
  check(res, { 'HTTP 200': r => r.status === 200 });
  sleep(0.01);
}
