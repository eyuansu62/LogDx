# Cowork 任务说明 (legacy)

**Status: legacy.** This doc describes the old "CI log compressor" workflow,
retained for reproducibility of the `simple_rules_legacy` baseline. The
project has pivoted; see the top-level `README.md` for CILogBench
positioning. Run all commands below from the repo root.

你好 Cowork。这个目录（`cilog-bench/`）是一个 CI 日志压缩的 benchmark 项目。
我希望你帮我在本机把它跑起来并查看结果。请按下面的步骤执行，
遇到每一步失败都先把错误原样告诉我，不要自己发挥。

---

## 前置检查

1. 确认本机有 Python 3.10 或更高版本：`python3 --version`
   如果没有，告诉我，不要自行安装
2. 确认当前工作目录就是 `cilog-bench/`（里面应该有 `cilog/` 和 `README.md`）

---

## 步骤 1：冒烟测试（不需要网络）

先跑一个内置的 synthetic 样本集，确认环境正常：

```bash
PYTHONPATH=baselines/simple_rules_legacy python3 -m cilog.bench --synthetic
```

预期输出最后几行应该显示聚合压缩率在 90% 以上、signal preservation 100%。
如果这一步失败，**停下来告诉我错误**，不要往下走。

跑完后用默认浏览器打开 `results/report.html` 给我看看。

---

## 步骤 2：询问我 GitHub token

在跑真实数据之前，你需要一个 GitHub Personal Access Token。
告诉我："这一步需要 GitHub token，请到
https://github.com/settings/tokens 生成一个 classic token
（只需要 public_repo scope），然后粘贴给我。"

**收到 token 后，把它设到环境变量里**（不要写进任何文件）：

```bash
export GITHUB_TOKEN=<用户粘贴的 token>
```

---

## 步骤 3：跑真实 benchmark

```bash
PYTHONPATH=baselines/simple_rules_legacy python3 -m cilog.bench --samples-per-repo 2
```

这会从 10 个热门开源仓库（pandas, react, tokio 等）各抓 2 个最近失败的
CI job，压缩后对比。大约 3-5 分钟，主要是网络 IO。

跑完后：
1. 再次打开 `results/report.html`
2. 把终端的最后 15 行聚合统计告诉我（包括总 token 减少率和 signal preservation）

---

## 步骤 4（可选，我说要再做）

如果我看完报告后说"再跑一组"，默认行为是：
- 把 `results/raw/` 留着（已经抓过的日志当缓存）
- 加 `--repos <我指定的仓库>` 或调整 `--samples-per-repo`
- 不要覆盖之前的 HTML 报告，重命名成 `report_<时间戳>.html`

---

## 不要做的事

- 不要修改 `cilog/` 目录里的任何代码——这是我主动要改的事情，你别动
- 不要把 GITHUB_TOKEN 写进 `.env`、shell rc、或任何文件
- 不要把 `results/raw/` 里的日志上传到任何地方（可能含敏感信息）
- 不要尝试"优化"输出格式或额外安装其他依赖

---

## 你可能遇到的常见错误

**`ModuleNotFoundError: No module named 'cilog'`**
→ 你可能在错误的目录，`cd` 到有 `cilog/` 子目录的位置再跑

**`ERROR: GITHUB_TOKEN env var required`**
→ 步骤 2 的 token 没设进来，或当前 shell 不是你 export 的那个

**`403 Forbidden` 或 `rate limit`**
→ token 无效或被限流，告诉我，让我决定要不要换 token / 等一会

**tiktoken 下载失败**
→ 没事，代码会 fallback 到字符近似计数。只是 tokenizer 那一行会显示
`chars/3.5 (approx)` 而不是 `cl100k_base (tiktoken)`，这正常
