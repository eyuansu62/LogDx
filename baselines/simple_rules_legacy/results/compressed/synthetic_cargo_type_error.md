# CI Log (compressed)

**Sections:** 2 total, 2 with failures

## Failures

### ❌ cargo build `[generic]` (orig 109 lines, id=s_b5337c20)
```
Compiling myapp v0.1.0 (/home/runner/work/myapp/myapp)  [×15]
error[E0308]: mismatched types
   --> src/pipeline/executor.rs:142:28
    |
140 |       async fn run(&self, cfg: Config) -> Result<Report, ExecError> {
141 |           let handle = self.spawn(cfg.clone()).await?;
142 |           let report = handle.collect().await;
    |                        ^^^^^^^^^^^^^^^^^^^^^^ expected `Result<Report, ExecError>`, found `Report`
    |
    = note: consider wrapping with `Ok(...)`
error: could not compile `myapp` (bin "myapp") due to 1 previous error
```

### ❌ _between_groups `[generic]` (orig 1 lines, id=s_dde991aa)
```
##[error]Process completed with exit code 101.
```
