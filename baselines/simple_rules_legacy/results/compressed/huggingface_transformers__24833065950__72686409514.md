# CI Log (compressed)

**Sections:** 8 total, 2 with failures

## Failures

### ❌ Run if [[ "failure" == "success" || "failure" == "skipped" ]] && \ `[generic]` (orig 7 lines, id=s_cd740191)
```
if [[ "failure" == "success" || "failure" == "skipped" ]] && \
   [[ "skipped" == "success" || "skipped" == "skipped" ]]; then
  echo "OK"
else
  exit 1
fi
shell: /usr/bin/bash -e {0}
```

### ❌ _between_groups `[generic]` (orig 2 lines, id=s_970d530f)
```
##[error]Process completed with exit code 1.
Cleaning up orphan processes
```

## Passing sections (summarized)

- **_preamble** `[generic]` (1 lines → 1 kept, id=s_b8f696d3)
- **Runner Image Provisioner** `[generic]` (6 lines → 6 kept, id=s_e7f4a387)
- **Operating System** `[generic]` (3 lines → 3 kept, id=s_1c324472)
- **Runner Image** `[generic]` (4 lines → 4 kept, id=s_970d65fd)
- **GITHUB_TOKEN Permissions** `[generic]` (3 lines → 3 kept, id=s_2d8f09c2)
- **_between_groups** `[generic]` (4 lines → 4 kept, id=s_8a8beb02)