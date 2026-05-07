# CI Log (compressed)

**Sections:** 47 total, 1 with failures

## Failures

### ❌ _between_groups `[js-build]` (orig 9875 lines, id=s_1920eaf4)
```
e509d2f90ff6: Pull complete
05844576d180: Pull complete
ef1757ad0520: Pull complete
Digest: sha256:e30a602d8c77682be8159343e7421cd80f600d54a391b6a3c07d5469ccc9319d
Status: Downloaded newer image for mcr.microsoft.com/playwright:v1.35.1-focal
  Configuration
> Version:  v20.20.2 (resolved from v20)
> Prefix:   /usr/local
> Platform: linux
> Arch:     x64
> Tarball URL: https://nodejs.org/dist/v20.20.2/node-v20.20.2-linux-x64.tar.gz
> Installing Node.js, please wait…
✓ Done
v20.20.2
fatal: detected dubious ownership in repository at '/work'
To add an exception for this directory, call:
	git config --global --add safe.directory /work
Running tests with concurrency: 2 in test mode start
Test profile:
  os=linux
  branch=
  sha=
  node=20
  type=examples
  NEXT_TEST_MODE=start
  Ignored: NEXT_TEST_JOB
  Caching: disabled
[... 9059 lines elided ...]
Cleaning test files at /work/examples/with-jest-babel/__tests__
Starting examples/with-jest-babel/__tests__/index.test.tsx retry 2/2
❌ examples/with-jest/__tests__/index.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+325 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-jest/__tests__/index.test.tsx - 0 matches
end of examples/with-jest/__tests__/index.test.tsx output
examples/with-jest/__tests__/index.test.tsx failed due to Error: failed with code: 1
examples/with-jest/__tests__/index.test.tsx failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-jest/__tests__/index.test.tsx.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 1)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-jest/__tests__/index.test.tsx.results.json'
}
Starting examples/with-jest/app/blog/[slug]/page.test.tsx retry 0/2
❌ examples/with-jest-babel/__tests__/index.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+349 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-jest-babel/__tests__/index.test.tsx - 0 matches
end of examples/with-jest-babel/__tests__/index.test.tsx output
examples/with-jest-babel/__tests__/index.test.tsx failed due to Error: failed with code: 1
examples/with-jest-babel/__tests__/index.test.tsx failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-jest-babel/__tests__/index.test.tsx.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 0)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-jest-babel/__tests__/index.test.tsx.results.json'
}
Starting examples/with-jest/app/counter.test.tsx retry 0/2
❌ examples/with-jest/app/blog/[slug]/page.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=undefined TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NA ... [+350 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
[... 51 lines elided ...]
Cleaning test files at /work/examples/with-jest/app
Starting examples/with-jest/app/counter.test.tsx retry 2/2
❌ examples/with-jest/app/blog/[slug]/page.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+345 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-jest/app/blog/[slug]/page.test.tsx - 0 matches
end of examples/with-jest/app/blog/[slug]/page.test.tsx output
examples/with-jest/app/blog/[slug]/page.test.tsx failed due to Error: failed with code: 1
examples/with-jest/app/blog/[slug]/page.test.tsx failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-jest/app/blog/[slug]/page.test.tsx.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 2)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-jest/app/blog/[slug]/page.test.tsx.results.json'
}
Starting examples/with-jest/app/page.test.tsx retry 0/2
❌ examples/with-jest/app/counter.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+309 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-jest/app/counter.test.tsx - 0 matches
end of examples/with-jest/app/counter.test.tsx output
examples/with-jest/app/counter.test.tsx failed due to Error: failed with code: 1
examples/with-jest/app/counter.test.tsx failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-jest/app/counter.test.tsx.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 3)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-jest/app/counter.test.tsx.results.json'
}
Starting examples/with-jest/app/utils/add.test.ts retry 0/2
❌ examples/with-jest/app/page.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=undefined TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NA ... [+302 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
[... 51 lines elided ...]
Cleaning test files at /work/examples/with-jest/app/utils
Starting examples/with-jest/app/utils/add.test.ts retry 2/2
❌ examples/with-jest/app/utils/add.test.ts output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+313 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-jest/app/utils/add.test.ts - 0 matches
end of examples/with-jest/app/utils/add.test.ts output
examples/with-jest/app/utils/add.test.ts failed due to Error: failed with code: 1
examples/with-jest/app/utils/add.test.ts failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-jest/app/utils/add.test.ts.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 5)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-jest/app/utils/add.test.ts.results.json'
}
Starting examples/with-mocha/test/index.test.js retry 0/2
❌ examples/with-jest/app/page.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=examples_with-jest_app_page.test.tsx JEST_SUITE_NAME=start:examples:examples/with-jest/app/page.test.tsx /work/node_modules/.bin/jest '--runInBand' '--forceExit' '--no-cache' '--verbose' '--json' '--outputFile=examples/with-jest/app/page.test.tsx.results.json' 'examples/with-jest/app/page.test.tsx'
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-jest/app/page.test.tsx - 0 matches
end of examples/with-jest/app/page.test.tsx output
examples/with-jest/app/page.test.tsx failed due to Error: failed with code: 1
examples/with-jest/app/page.test.tsx failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-jest/app/page.test.tsx.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 4)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-jest/app/page.test.tsx.results.json'
}
Starting examples/with-typescript-graphql/test/index.test.tsx retry 0/2
❌ examples/with-mocha/test/index.test.js output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=undefined TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NA ... [+310 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
[... 51 lines elided ...]
Cleaning test files at /work/examples/with-typescript-graphql
Starting examples/with-typescript-graphql/test/index.test.tsx retry 2/2
❌ examples/with-mocha/test/index.test.js output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+305 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-mocha/test/index.test.js - 0 matches
end of examples/with-mocha/test/index.test.js output
examples/with-mocha/test/index.test.js failed due to Error: failed with code: 1
examples/with-mocha/test/index.test.js failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-mocha/test/index.test.js.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 6)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-mocha/test/index.test.js.results.json'
}
Starting examples/with-vitest/__tests__/Home.test.tsx retry 0/2
❌ examples/with-typescript-graphql/test/index.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+361 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-typescript-graphql/test/index.test.tsx - 0 matches
end of examples/with-typescript-graphql/test/index.test.tsx output
examples/with-typescript-graphql/test/index.test.tsx failed due to Error: failed with code: 1
examples/with-typescript-graphql/test/index.test.tsx failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-typescript-graphql/test/index.test.tsx.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 7)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-typescript-graphql/test/index.test.tsx.results.json'
}
Starting examples/with-vitest/app/blog/[slug]/page.test.tsx retry 0/2
❌ examples/with-vitest/__tests__/Home.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=undefined TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NA ... [+334 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
[... 51 lines elided ...]
Cleaning test files at /work/examples/with-vitest/app/blog/[slug]
Starting examples/with-vitest/app/blog/[slug]/page.test.tsx retry 2/2
❌ examples/with-vitest/__tests__/Home.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+329 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-vitest/__tests__/Home.test.tsx - 0 matches
end of examples/with-vitest/__tests__/Home.test.tsx output
examples/with-vitest/__tests__/Home.test.tsx failed due to Error: failed with code: 1
examples/with-vitest/__tests__/Home.test.tsx failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-vitest/__tests__/Home.test.tsx.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 8)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-vitest/__tests__/Home.test.tsx.results.json'
}
Starting examples/with-vitest/app/counter.test.tsx retry 0/2
❌ examples/with-vitest/app/blog/[slug]/page.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+353 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-vitest/app/blog/[slug]/page.test.tsx - 0 matches
end of examples/with-vitest/app/blog/[slug]/page.test.tsx output
examples/with-vitest/app/blog/[slug]/page.test.tsx failed due to Error: failed with code: 1
examples/with-vitest/app/blog/[slug]/page.test.tsx failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-vitest/app/blog/[slug]/page.test.tsx.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 9)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-vitest/app/blog/[slug]/page.test.tsx.results.json'
}
Starting examples/with-vitest/app/page.test.tsx retry 0/2
❌ examples/with-vitest/app/counter.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=undefined TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NA ... [+322 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
[... 51 lines elided ...]
Cleaning test files at /work/examples/with-vitest/app
Starting examples/with-vitest/app/page.test.tsx retry 2/2
❌ examples/with-vitest/app/counter.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+317 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-vitest/app/counter.test.tsx - 0 matches
end of examples/with-vitest/app/counter.test.tsx output
examples/with-vitest/app/counter.test.tsx failed due to Error: failed with code: 1
examples/with-vitest/app/counter.test.tsx failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-vitest/app/counter.test.tsx.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 10)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-vitest/app/counter.test.tsx.results.json'
}
Starting examples/with-vitest/app/utils/add.test.ts retry 0/2
❌ examples/with-vitest/app/page.test.tsx output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+305 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-vitest/app/page.test.tsx - 0 matches
end of examples/with-vitest/app/page.test.tsx output
examples/with-vitest/app/page.test.tsx failed due to Error: failed with code: 1
examples/with-vitest/app/page.test.tsx failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-vitest/app/page.test.tsx.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 11)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-vitest/app/page.test.tsx.results.json'
}
Starting examples/with-zones/home/test/next-config.test.ts retry 0/2
❌ examples/with-vitest/app/utils/add.test.ts output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=undefined TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NA ... [+326 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
[... 51 lines elided ...]
Cleaning test files at /work/examples/with-zones/home
Starting examples/with-zones/home/test/next-config.test.ts retry 2/2
❌ examples/with-zones/home/test/next-config.test.ts output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+349 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-zones/home/test/next-config.test.ts - 0 matches
end of examples/with-zones/home/test/next-config.test.ts output
examples/with-zones/home/test/next-config.test.ts failed due to Error: failed with code: 1
examples/with-zones/home/test/next-config.test.ts failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-zones/home/test/next-config.test.ts.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 13)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-zones/home/test/next-config.test.ts.results.json'
}
❌ examples/with-vitest/app/utils/add.test.ts output
HEADLESS=true NEXT_TELEMETRY_DISABLED=1 CI= NEXT_TEST_CI=undefined IS_RETRY=true TRACE_PLAYWRIGHT=true CIRCLECI= GITHUB_ACTIONS= CONTINUOUS_INTEGRATION= RUN_ID= BUILD_NUMBER= JEST_JUNIT_OUTPUT_NAME=ex ... [+321 chars elided]
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /work/test
  14634 files checked.
  roots: /work/test, /work/packages/next/src, /work/packages/next-codemod, /work/packages/eslint-plugin-internal, /work/packages/font/src, /work/packages/next-routing - 14634 matches
  testMatch: **/*.test.js, **/*.test.ts, **/*.test.jsx, **/*.test.tsx - 1861 matches
  testPathIgnorePatterns: /node_modules/, /.next/ - 14634 matches
  testRegex:  - 0 matches
Pattern: examples/with-vitest/app/utils/add.test.ts - 0 matches
end of examples/with-vitest/app/utils/add.test.ts output
examples/with-vitest/app/utils/add.test.ts failed due to Error: failed with code: 1
examples/with-vitest/app/utils/add.test.ts failed to pass within 2 retries
Failed to load test output Error: ENOENT: no such file or directory, open 'examples/with-vitest/app/utils/add.test.ts.results.json'
    at async open (node:internal/fs/promises:637:25)
    at async Object.readFile (node:internal/fs/promises:1249:14)
    at async runTest (/work/run-tests.js:927:29)
    at async /work/run-tests.js:991:9
    at async Promise.allSettled (index 12)
    at async main (/work/run-tests.js:975:19) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'examples/with-vitest/app/utils/add.test.ts.results.json'
}
Some tests failed
exiting with code 1
##[error]Process completed with exit code 1.
Post job cleanup.
[command]/usr/bin/git version
git version 2.53.0
Temporarily overriding HOME='/home/runner/work/_temp/e6390356-c93f-4e52-9727-41f9ec061786' before making global git config changes
Adding repository directory to the temporary git global config as a safe directory
[command]/usr/bin/git config --global --add safe.directory /home/runner/work/next.js/next.js
[command]/usr/bin/git config --local --name-only --get-regexp core\.sshCommand
[command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :"
[command]/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
http.https://github.com/.extraheader
[command]/usr/bin/git config --local --unset-all http.https://github.com/.extraheader
[command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
[command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
[command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
Cleaning up orphan processes
```

## Passing sections (summarized)

- **_preamble** `[generic]` (1 lines → 1 kept, id=s_b8f696d3)
- **Runner Image Provisioner** `[generic]` (6 lines → 6 kept, id=s_e7f4a387)
- **Operating System** `[generic]` (3 lines → 3 kept, id=s_1c324472)
- **Runner Image** `[generic]` (4 lines → 4 kept, id=s_970d65fd)
- **GITHUB_TOKEN Permissions** `[generic]` (17 lines → 17 kept, id=s_2d8f09c2)
- **_between_groups** `[generic]` (7 lines → 7 kept, id=s_39f4d20f)
- **Run actions/checkout@v4** `[generic]` (16 lines → 16 kept, id=s_0b57da8f)
- **_between_groups** `[generic]` (1 lines → 1 kept, id=s_e336bb1b)
- **Getting Git version info** `[generic]` (3 lines → 3 kept, id=s_17bf0e1b)
- **_between_groups** `[generic]` (4 lines → 4 kept, id=s_d042e513)
- **Initializing the repository** `[generic]` (16 lines → 16 kept, id=s_498b19b5)
- **Disabling automatic garbage collection** `[generic]` (1 lines → 1 kept, id=s_963d3163)
- **Setting up auth** `[generic]` (7 lines → 7 kept, id=s_142f0763)
- **Fetching the repository** `[generic]` (3 lines → 3 kept, id=s_b144b05e)
- **_between_groups** `[generic]` (2 lines → 2 kept, id=s_dde991aa)
- **Checking out the ref** `[generic]` (53 lines → 31 kept, id=s_1028748c)
- **_between_groups** `[generic]` (2 lines → 2 kept, id=s_41878d9d)
- **Run sudo ethtool -K eth0 tx off rx off** `[generic]` (4 lines → 4 kept, id=s_d6ccff9c)
- **_between_groups** `[generic]` (6 lines → 6 kept, id=s_aa8b9d35)
- **Run actions/setup-node@v4** `[generic]` (7 lines → 7 kept, id=s_18fe925d)
- **_between_groups** `[generic]` (3 lines → 3 kept, id=s_e7bb029e)
- **Environment details** `[generic]` (3 lines → 3 kept, id=s_e0f5e176)
- **Run npm i -g corepack@0.31** `[generic]` (5 lines → 5 kept, id=s_b04edc1a)
- **_between_groups** `[generic]` (2 lines, elided)
- **Run pnpm install** `[npm-install]` (4 lines → 1 kept, id=s_9ddc75e7)
- **_between_groups** `[js-build]` (238 lines → 31 kept, id=s_ff212e99)
- **Run pnpm build** `[generic]` (4 lines → 4 kept, id=s_64626860)
- **_between_groups** `[generic]` (16 lines → 10 kept, id=s_4ed83efd)
- **@next/polyfill-module:build** `[generic]` (8 lines → 6 kept, id=s_db83508a)
- **@next/react-refresh-utils:build** `[js-build]` (6 lines → 4 kept, id=s_0ae249ec)
- **@next/eslint-plugin-next:build** `[js-build]` (10 lines → 6 kept, id=s_fe84a62b)
- **@next/playwright:build** `[js-build]` (6 lines → 4 kept, id=s_fed6e909)
- **@next/codemod:build** `[js-build]` (5 lines → 3 kept, id=s_c4754b1c)
- **eslint-config-next:build** `[js-build]` (10 lines → 6 kept, id=s_d2e7f4c7)
- **@vercel/devlow-bench:build** `[js-build]` (5 lines → 3 kept, id=s_2ba990a1)
- **@next/env:build** `[js-build]` (23 lines → 15 kept, id=s_1c4cfd33)
- **@next/routing:build** `[js-build]` (23 lines → 15 kept, id=s_33f36c6a)
- **@next/bundle-analyzer-ui:build** `[generic]` (25 lines → 18 kept, id=s_cc7029de)
- **@next/font:build** `[js-build]` (14 lines → 10 kept, id=s_f10d58d6)
- **@next/polyfill-nomodule:build** `[generic]` (8 lines → 6 kept, id=s_e5b93b45)
- **create-next-app:build** `[generic]` (250 lines → 31 kept, id=s_7c49580c)
- **next:build** `[js-build]` (191 lines → 31 kept, id=s_d37d2c3c)
- **@vercel/turbopack-next:build** `[js-build]` (9 lines → 5 kept, id=s_ceaea9a5)
- **@next/third-parties:build** `[js-build]` (6 lines → 4 kept, id=s_4403573c)
- **_between_groups** `[generic]` (6 lines → 4 kept, id=s_8564b482)
- **Run docker run --rm -v $(pwd):/work mcr.microsoft.com/playwright:v1.35.1-focal /bin/bash -c "cd /work && curl -s https://install-node.vercel.app/v20 | FORCE=1 bash && node -v && corepack enable > /dev/null && NEXT_TEST_JOB=1 NEXT_TEST_MODE=start xvfb-run node run-tests.js --type examples >> /proc/1/fd/1"** `[generic]` (4 lines → 4 kept, id=s_bc757602)