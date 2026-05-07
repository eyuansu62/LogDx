# CI Log (compressed)

**Sections:** 4 total, 2 with failures

## Failures

### ❌ Run playwright test `[generic]` (orig 52 lines, id=s_a1f5527f)
```
✓  [chromium] › e2e/smoke.spec.ts:28:1 › loads homepage (570ms)
  ✓  [chromium] › e2e/smoke.spec.ts:29:1 › loads homepage (580ms)
  ✓  [chromium] › e2e/smoke.spec.ts:30:1 › loads homepage (590ms)
  ✘  [chromium] › e2e/checkout.spec.ts:82:1 › completes payment flow (45s)
  1) [chromium] › e2e/checkout.spec.ts:82:1 › completes payment flow
    TimeoutError: locator.click: Timeout 30000ms exceeded.
    Call log:
      - waiting for locator('button[data-testid="submit-order"]')
      - locator resolved to <button disabled data-testid="submit-order">Place order</button>
      - attempting click action
      - waiting for element to be visible, enabled and stable
      - element is not enabled
      at e2e/checkout.spec.ts:101:32
    attachment #1: screenshot.png (image/png) ────────────────────
[binary/base64 blob, 8204 chars elided]
    ─────────────────────────────────────────────────────────────
  33 passed (58s)
  1 failed
```

### ❌ _between_groups `[generic]` (orig 1 lines, id=s_bfa1c9d9)
```
##[error]Process completed with exit code 1.
```

## Passing sections (summarized)

- **Install dependencies** `[generic]` (356 lines → 4 kept, id=s_21d6eba5)
- **Build** `[js-build]` (123 lines → 31 kept, id=s_19ffd1f5)