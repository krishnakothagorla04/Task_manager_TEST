// ==============================================================
// k6 Load Test — Task Service HPA Validation
//
// This script simulates concurrent traffic against the task-service
// to trigger the Horizontal Pod Autoscaler (HPA). It ramps up
// virtual users to generate CPU load, then ramps down to observe
// the cluster scaling back.
//
// Usage:
//   k6 run load-test.js
//
// Prerequisites:
//   - kubectl port-forward svc/task-service 3001:3001 -n taskmanager
//   - or replace BASE_URL with your NodePort/LoadBalancer address
// ==============================================================

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:3001';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // Ramp up to 50 users over 30s
    { duration: '1m',  target: 200 },  // Spike to 200 users for 1 minute
    { duration: '30s', target: 300 },  // Push to 300 users (triggers HPA)
    { duration: '1m',  target: 300 },  // Hold at 300 users
    { duration: '30s', target: 0 },    // Ramp down to 0 (observe scale-in)
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],  // 95th percentile under 2 seconds
    http_req_failed:   ['rate<0.1'],    // Less than 10% failure rate
  },
};

export default function () {
  // Health check endpoint (lightweight, high volume)
  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, {
    'health check returns 200': (r) => r.status === 200,
    'health response is healthy': (r) => JSON.parse(r.body).status === 'healthy',
  });

  // Get all tasks (simulates read-heavy workload)
  const tasksRes = http.get(`${BASE_URL}/tasks`);
  check(tasksRes, {
    'tasks endpoint returns 200': (r) => r.status === 200,
  });

  sleep(0.5);
}
