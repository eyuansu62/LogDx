# CI Log (compressed)

**Sections:** 2 total, 2 with failures

## Failures

### ❌ go test -race ./... `[go-test]` (orig 25 lines, id=s_f6764ab3)
```
WARNING: DATA RACE
Read at 0x00c00012c050 by goroutine 13:
  github.com/acme/service/internal/cache.(*Cache).Get()
      /home/runner/work/service/service/internal/cache/cache.go:87 +0x4a
  github.com/acme/service/internal/cache_test.TestConcurrentGet.func1()
      /home/runner/work/service/service/internal/cache/cache_test.go:142 +0x5b
Previous write at 0x00c00012c050 by goroutine 12:
  github.com/acme/service/internal/cache.(*Cache).Set()
      /home/runner/work/service/service/internal/cache/cache.go:103 +0x8c
--- FAIL: TestConcurrentGet (0.42s)
    testing.go:1446: race detected during execution of test
FAIL
FAIL	github.com/acme/service/internal/cache	0.527s
FAIL
```

### ❌ _between_groups `[generic]` (orig 1 lines, id=s_3d172f6a)
```
##[error]Process completed with exit code 1.
```
