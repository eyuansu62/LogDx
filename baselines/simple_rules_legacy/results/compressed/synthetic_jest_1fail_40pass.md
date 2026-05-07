# CI Log (compressed)

**Sections:** 2 total, 2 with failures

## Failures

### ❌ Run npm test `[jest]` (orig 173 lines, id=s_d34ae2e8)
```
FAIL  src/api/webhook.test.ts (8.721 s)
  Webhook delivery
    ✓ retries on 500 (12 ms)
    ✓ respects retry-after header (8 ms)
    ✗ deduplicates by idempotency key (2043 ms)
  ● Webhook delivery › deduplicates by idempotency key
    expect(received).toBe(expected) // Object.is equality
    Expected: 1
    Received: 2
      47 |   const key = crypto.randomUUID();
      48 |   await deliver(event, { idempotencyKey: key });
    > 49 |   expect(mockServer.calls.length).toBe(1);
         |                                   ^
      50 | });
      at src/api/webhook.test.ts:49:39
      at node_modules/@jest/expect/build/index.js:133:12
      at node_modules/jest-jasmine2/build/queueRunner.js:45:7
Test Suites: 1 failed, 40 passed, 41 total
Tests:       1 failed, 203 passed, 204 total
Snapshots:   0 total
Time:        52.114 s
[+ 40 test suites passed]
```

### ❌ _between_groups `[generic]` (orig 1 lines, id=s_b097ec93)
```
##[error]Process completed with exit code 1.
```
