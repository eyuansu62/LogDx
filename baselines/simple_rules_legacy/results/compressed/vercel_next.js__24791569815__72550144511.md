# CI Log (compressed)

**Sections:** 27 total, 1 with failures

## Failures

### ❌ _between_groups `[js-build]` (orig 770 lines, id=s_b1807377)
```
[17:03:50] Finished ncc_mswjs_interceptors in 129ms
[17:03:50] Starting ncc_rsc_poison_packages
[17:03:50] Finished ncc_rsc_poison_packages in 3ms
[17:03:50] Starting ncc_modelcontextprotocol_sdk
ncc: Version 0.34.0
ncc: Compiling file mcp.js into CJS
ncc: Version 0.34.0
ncc: Compiling file streamableHttp.js into CJS
[17:03:51] Finished ncc_modelcontextprotocol_sdk in 780ms
[17:03:51] Starting ncc_vercel_routing_utils
ncc: Version 0.34.0
ncc: Compiling file superstatic.js into CJS
[17:03:51] Finished ncc_vercel_routing_utils in 61ms
[17:03:51] Finished ncc in 45.37s
Error: Command failed with exit code 128 (Unknown system error -128): git push origin update/react/19.3.0-canary-142cfde8-20260422
    at makeError (/home/runner/work/next.js/next.js/node_modules/.pnpm/execa@2.0.3/node_modules/execa/lib/error.js:58:11)
    at handlePromise (/home/runner/work/next.js/next.js/node_modules/.pnpm/execa@2.0.3/node_modules/execa/index.js:112:26)
    at process.processTicksAndRejections (node:internal/process/task_queues:95:5)
    at async main (/home/runner/work/next.js/next.js/scripts/sync-react.js:645:5) {
  command: 'git push origin update/react/19.3.0-canary-142cfde8-20260422',
  exitCode: 128,
  exitCodeName: 'Unknown system error -128',
  stdout: '',
  stderr: 'remote: Permission to vercel/next.js.git denied to nextjs-bot.\n' +
    "fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL returned error: 403",
  all: 'remote: Permission to vercel/next.js.git denied to nextjs-bot.\n' +
    "fatal: unable to access 'https://github.com/vercel/next.js/': The requested URL returned error: 403",
  failed: true,
  timedOut: false,
  isCanceled: false,
  killed: false,
  signal: undefined
}
 ELIFECYCLE  Command failed with exit code 1.
##[error]Process completed with exit code 1.
Post job cleanup.
[command]/usr/bin/git version
git version 2.53.0
Temporarily overriding HOME='/home/runner/work/_temp/eb5f4af6-002d-496f-bf7f-8341f3749ac9' before making global git config changes
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
- **Run actions/checkout@v4** `[generic]` (17 lines → 17 kept, id=s_0b57da8f)
- **_between_groups** `[generic]` (1 lines → 1 kept, id=s_e9b655f7)
- **Getting Git version info** `[generic]` (3 lines → 3 kept, id=s_c0d79239)
- **_between_groups** `[generic]` (4 lines → 4 kept, id=s_516a890d)
- **Initializing the repository** `[generic]` (16 lines → 16 kept, id=s_20cb754e)
- **Disabling automatic garbage collection** `[generic]` (1 lines → 1 kept, id=s_950b35af)
- **Setting up auth** `[generic]` (7 lines → 7 kept, id=s_d335bf33)
- **Fetching the repository** `[generic]` (3 lines → 3 kept, id=s_cdbdee1d)
- **_between_groups** `[generic]` (2 lines → 2 kept, id=s_5261c17f)
- **Checking out the ref** `[generic]` (51 lines → 31 kept, id=s_87086def)
- **_between_groups** `[generic]` (2 lines → 2 kept, id=s_10c1230e)
- **Run git config user.name "nextjs-bot"** `[generic]` (6 lines → 6 kept, id=s_92759e1d)
- **Run actions/setup-node@v4** `[generic]` (8 lines → 8 kept, id=s_783dfee3)
- **_between_groups** `[generic]` (3 lines → 3 kept, id=s_7b9dd958)
- **Environment details** `[generic]` (3 lines → 3 kept, id=s_193e4100)
- **Run npm i -g corepack@0.31** `[generic]` (6 lines → 6 kept, id=s_6325fab9)
- **_between_groups** `[generic]` (2 lines, elided)
- **Run pnpm install --filter .** `[npm-install]` (5 lines → 1 kept, id=s_e9311f2e)
- **_between_groups** `[generic]` (41 lines → 31 kept, id=s_89edd8de)
- **Run pnpm sync-react --actor "eps1lon" --commit --create-pull --version ""** `[generic]` (6 lines → 6 kept, id=s_674da545)