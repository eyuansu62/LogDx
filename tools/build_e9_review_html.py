"""
Build a self-contained HTML labeling UI for an E9 batch.

The output is a single HTML file with all items embedded inline. No server
required — open it in your browser via file://. Features:

  - Auto-saves every change to localStorage (per batch_id)
  - Sticky progress bar + sidebar item list (color-coded complete/incomplete)
  - Side-by-side rendering for pairwise items
  - Keyboard navigation (arrow left/right between items)
  - One-click download of `reviewer_<id>.jsonl` ready for the validator
  - Reviewer-id validation refuses model-shaped names

Anti-leakage: only items.jsonl is embedded. manifest.json is NOT read,
so the blind method map never reaches the page.

Usage:
    python3 tools/build_e9_review_html.py \
        --batch-id e9_v1_3_hybrid_vs_grep_human_001 \
        --reviewer-id human_a
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CILogBench E9 review · __BATCH_ID__</title>
<style>
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, "Helvetica Neue", Arial, sans-serif;
  color: #1f2328;
  background: #f6f8fa;
  min-height: 100vh;
}
button { font: inherit; }
input, select, textarea { font: inherit; color: inherit; }

.topbar {
  position: sticky; top: 0; z-index: 10;
  background: #fff; border-bottom: 1px solid #d0d7de;
  display: flex; align-items: center; gap: 16px;
  padding: 10px 20px;
}
.brand { font-weight: 600; font-size: 14px; }
.brand .batch { color: #656d76; font-weight: 400; font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 12px; }
.reviewer-block { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.reviewer-block input { padding: 4px 8px; border: 1px solid #d0d7de; border-radius: 6px; width: 140px; }
.progress-block { flex: 1; min-width: 200px; }
.progress-text { font-size: 12px; color: #656d76; margin-bottom: 4px; font-family: ui-monospace, monospace; }
.progress-bar { background: #eaeef2; height: 6px; border-radius: 3px; overflow: hidden; }
.progress-fill { background: #1a7f37; height: 100%; transition: width 0.2s ease; width: 0%; }
.btn { padding: 6px 14px; border: 1px solid #d0d7de; background: #fff; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn:hover:not(:disabled) { background: #f6f8fa; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn.primary { background: #1f883d; color: #fff; border-color: #1f883d; }
.btn.primary:hover:not(:disabled) { background: #1a7f37; }
.btn.danger { color: #d1242f; }

main {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: calc(100vh - 100px);
}
.sidebar { background: #fff; border-right: 1px solid #d0d7de; overflow-y: auto; max-height: calc(100vh - 100px); position: sticky; top: 50px; }
.sidebar-header { padding: 10px 12px; font-size: 11px; text-transform: uppercase; color: #656d76; letter-spacing: 0.5px; border-bottom: 1px solid #f6f8fa; }
.item-btn { display: block; width: 100%; text-align: left; padding: 5px 12px; border: none; background: transparent; cursor: pointer; font-family: ui-monospace, monospace; font-size: 12px; color: #1f2328; border-left: 3px solid transparent; }
.item-btn:hover { background: #f6f8fa; }
.item-btn.current { background: #ddf4ff; border-left-color: #0969da; }
.item-btn.complete { color: #1a7f37; }
.item-btn.complete::before { content: "✓ "; font-weight: 700; }
.item-btn.incomplete::before { content: "○ "; color: #d1242f; opacity: 0.6; }

.panel { padding: 20px 28px; max-width: 1200px; }
.case-header { margin-bottom: 16px; }
.case-header h1 { font-family: ui-monospace, monospace; font-size: 16px; margin: 0 0 6px; }
.case-header .badge-row { display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; }
.badge { padding: 2px 8px; border-radius: 3px; font-family: ui-monospace, monospace; }
.badge.split { background: #ddf4ff; color: #0969da; text-transform: uppercase; }
.badge.case { background: #fff8c5; color: #7d4e00; }
.badge.meta { background: #f6f8fa; color: #656d76; }
.badge.kind { background: #cfe9ce; color: #1a4f1c; text-transform: uppercase; font-weight: 600; }

.card { background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px; }
.card h3 { margin: 0 0 10px; font-size: 12px; text-transform: uppercase; color: #656d76; letter-spacing: 0.5px; }
.gt-text { font-size: 14px; line-height: 1.55; margin: 0; }
details > summary { cursor: pointer; font-size: 12px; color: #0969da; margin-top: 10px; user-select: none; }
details > pre { background: #f6f8fa; padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 11px; line-height: 1.4; max-height: 400px; }

.diag-grid { display: grid; gap: 14px; margin-bottom: 14px; }
.diag-grid.pair { grid-template-columns: 1fr 1fr; }
.diag-card { background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 14px 18px; }
.diag-card h3 { margin: 0 0 10px; font-size: 12px; text-transform: uppercase; color: #656d76; letter-spacing: 0.5px; display: flex; justify-content: space-between; align-items: center; }
.diag-card h3 .ab-tag { background: #f6f8fa; color: #1f2328; font-family: ui-monospace, monospace; padding: 2px 8px; border-radius: 3px; }
.d-summary { font-weight: 500; margin: 0 0 10px; }
.d-meta { display: flex; gap: 8px; margin-bottom: 10px; font-size: 12px; flex-wrap: wrap; }
.d-meta .cat { background: #ddf4ff; color: #0969da; padding: 1px 6px; border-radius: 3px; font-family: ui-monospace, monospace; }
.d-meta .conf { color: #656d76; font-family: ui-monospace, monospace; }
.d-section { margin-bottom: 8px; font-size: 13px; }
.d-section strong { color: #656d76; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 2px; font-weight: 600; }
.d-section code { background: #f6f8fa; padding: 1px 4px; border-radius: 3px; font-size: 12px; }
.d-section ul { padding-left: 18px; margin: 4px 0; }
.d-section li { margin-bottom: 6px; }
.d-section .reason { color: #656d76; font-style: italic; font-size: 12px; display: block; margin-top: 2px; }

.form-card { background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px; }
.form-card h3 { margin: 0 0 12px; font-size: 12px; text-transform: uppercase; color: #656d76; letter-spacing: 0.5px; }
.form-row { display: grid; grid-template-columns: 220px 1fr; gap: 14px; padding: 10px 0; align-items: start; border-bottom: 1px solid #f6f8fa; }
.form-row:last-child { border-bottom: none; }
.form-label { font-weight: 500; font-size: 13px; padding-top: 4px; }
.form-label .help { display: block; font-weight: 400; font-size: 11px; color: #656d76; margin-top: 2px; }
.score-buttons { display: flex; gap: 6px; flex-wrap: wrap; }
.score-btn { border: 1px solid #d0d7de; background: #fff; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-family: ui-monospace, monospace; min-width: 36px; font-size: 13px; }
.score-btn:hover { background: #f6f8fa; }
.score-btn.selected { background: #0969da; color: #fff; border-color: #0969da; }
.score-btn.severity.selected { background: #d1242f; border-color: #d1242f; } /* hallucination_severity: red, since higher = worse */
select, textarea {
  width: 100%; max-width: 600px;
  padding: 6px 10px; border: 1px solid #d0d7de; border-radius: 6px;
}
textarea { resize: vertical; min-height: 50px; font-family: inherit; }
.winner-row { display: flex; gap: 8px; flex-wrap: wrap; }
.winner-btn { border: 1px solid #d0d7de; background: #fff; padding: 8px 18px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; }
.winner-btn:hover { background: #f6f8fa; }
.winner-btn.selected { background: #1f883d; color: #fff; border-color: #1f883d; }
.winner-btn[data-pick="A"].selected, .winner-btn[data-pick="B"].selected { background: #0969da; border-color: #0969da; }
.winner-btn[data-pick="tie"].selected { background: #8250df; border-color: #8250df; }
.winner-btn[data-pick="both_bad"].selected { background: #d1242f; border-color: #d1242f; }

.bottombar {
  position: sticky; bottom: 0; z-index: 10;
  background: #fff; border-top: 1px solid #d0d7de;
  padding: 10px 20px;
  display: flex; align-items: center; gap: 16px;
}
.status { flex: 1; font-size: 12px; color: #656d76; font-family: ui-monospace, monospace; }
.status.complete { color: #1a7f37; }
.status.incomplete { color: #d1242f; }

.toast {
  position: fixed; bottom: 80px; right: 24px; z-index: 20;
  background: #1f2328; color: #fff; padding: 10px 16px; border-radius: 8px;
  font-size: 13px; opacity: 0; pointer-events: none;
  transition: opacity 0.2s, transform 0.2s; transform: translateY(8px);
}
.toast.show { opacity: 1; transform: translateY(0); }

.disclosure {
  background: #fff8c5; color: #7d4e00; border: 1px solid #d4ac0d;
  border-radius: 8px; padding: 12px 16px; margin: 14px 0;
  font-size: 13px; line-height: 1.5;
}
.disclosure strong { color: #5a3700; }

.help-modal { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 20px; }
.help-modal[hidden] { display: none; }
.help-modal-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,0.4); }
.help-modal-card { position: relative; background: #fff; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.18); max-width: 760px; width: 100%; max-height: 88vh; overflow-y: auto; }
.help-modal-header { position: sticky; top: 0; background: #fff; padding: 16px 24px; border-bottom: 1px solid #d0d7de; display: flex; align-items: center; justify-content: space-between; }
.help-modal-header h2 { margin: 0; font-size: 18px; }
.help-modal-body { padding: 16px 24px 24px; line-height: 1.65; }
.help-modal-body h3 { margin: 18px 0 8px; font-size: 14px; color: #1f2328; padding-bottom: 4px; border-bottom: 1px solid #f6f8fa; }
.help-modal-body p { margin: 8px 0; font-size: 13px; }
.help-modal-body ul { padding-left: 20px; margin: 6px 0; font-size: 13px; }
.help-modal-body li { margin-bottom: 4px; }
.help-modal-body code { background: #f6f8fa; padding: 1px 5px; border-radius: 3px; font-size: 12px; font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }
.help-modal-body kbd { background: #f6f8fa; border: 1px solid #d0d7de; border-bottom-width: 2px; padding: 1px 6px; border-radius: 4px; font-family: ui-monospace, monospace; font-size: 11px; }
.help-table { width: 100%; border-collapse: collapse; margin: 8px 0 12px; font-size: 12px; }
.help-table th, .help-table td { border: 1px solid #d0d7de; padding: 8px 10px; text-align: left; vertical-align: top; }
.help-table th { background: #f6f8fa; font-weight: 600; }
.help-table code { font-size: 11px; }

@media (max-width: 1000px) {
  main { grid-template-columns: 1fr; }
  .sidebar { display: none; }
  .diag-grid.pair { grid-template-columns: 1fr; }
  .form-row { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<header class="topbar">
  <div class="brand">CILogBench E9 评审<br><span class="batch">__BATCH_ID__</span></div>
  <div class="reviewer-block">
    评审者：
    <input id="reviewer-id" value="__REVIEWER_ID__" placeholder="human_a">
  </div>
  <div class="progress-block">
    <div class="progress-text" id="progress-text">0 / 0 已完成</div>
    <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
  </div>
  <button class="btn" id="help-btn" title="打开评分指南">？说明</button>
  <button class="btn" id="reset-btn" title="清空本 batch 所有 label">清空</button>
  <button class="btn primary" id="download-btn">下载 JSONL</button>
</header>

<main>
  <nav class="sidebar" id="sidebar">
    <div class="sidebar-header">条目列表</div>
    <div id="item-list"></div>
  </nav>
  <section class="panel" id="panel"></section>
</main>

<footer class="bottombar">
  <button class="btn" id="prev-btn">← 上一条</button>
  <div class="status" id="status">—</div>
  <button class="btn" id="next-btn">下一条 →</button>
</footer>

<div class="toast" id="toast"></div>

<div class="help-modal" id="help-modal" hidden>
  <div class="help-modal-backdrop"></div>
  <div class="help-modal-card">
    <div class="help-modal-header">
      <h2>评分指南</h2>
      <button class="btn" id="help-close-btn">关闭</button>
    </div>
    <div class="help-modal-body">
      <h3>单条评分（absolute · 32 条）</h3>
      <p>每条诊断对照 <strong>Ground truth 总结</strong>（页面左上的引用框），打 6 个 0–4 的整数分：</p>
      <table class="help-table">
        <thead><tr><th>维度</th><th>0 分（最差）</th><th>4 分（最好）</th></tr></thead>
        <tbody>
          <tr><td><code>root_cause_correctness</code><br>根本原因正确性</td><td>完全错</td><td>完全命中 GT 真原因</td></tr>
          <tr><td><code>evidence_support</code><br>证据支持</td><td>quote 是编的或没有</td><td>quote 来自原 log 且支持原因</td></tr>
          <tr><td><code>localization_quality</code><br>定位质量</td><td>没说 file / test / step</td><td>准确点到 file:line</td></tr>
          <tr><td><code>actionability</code><br>可执行性</td><td>无法拿来修</td><td>不知情工程师能直接修</td></tr>
          <tr><td><code>hallucination_severity</code><br>幻觉严重程度<br><strong style="color:#d1242f;">越高越糟</strong></td><td>没编任何东西</td><td>编了多个大事</td></tr>
          <tr><td><code>overall_usefulness</code><br>整体有用性</td><td>没用</td><td>会直接交付给 oncall</td></tr>
        </tbody>
      </table>

      <p><strong>弃权（abstention）三选一：</strong></p>
      <ul>
        <li><code>appropriate</code> — 模型说 unknown，证据确实不够（少见）</li>
        <li><code>not_appropriate</code> — 模型说 unknown，但证据其实很清楚（应该答而未答）</li>
        <li><code>not_applicable</code> — 模型没弃权，正常给了诊断（<strong>最常见</strong>）</li>
      </ul>

      <p><strong>备注（notes）：</strong>可选。打 0 或 4 分时建议写一句解释。<strong style="color:#d1242f;">绝对不要写方法名</strong>（<code>raw / tail / grep / rtk-* / llm-summary-* / hybrid-*</code>）—— validator 会拒绝。</p>

      <h3>两两对比（pairwise · 16 条）</h3>
      <p>同一 case 给出 A、B 两条诊断，选一个：</p>
      <ul>
        <li><strong>A 更好 / B 更好</strong> — 一条明显胜出</li>
        <li><strong>平局</strong> — 都同样好</li>
        <li><strong>都不行</strong> — 两条都不及格</li>
        <li><strong>信息不足</strong> — 看不出来谁赢</li>
      </ul>
      <p><strong>平局打破顺序：</strong>根本原因 → 证据支持 → 定位 → 可执行性 → 不幻觉 → 合理弃权。</p>

      <h3>自盲贴士</h3>
      <ul>
        <li><strong>不要打开 <code>manifest.json</code></strong>（含方法名映射）</li>
        <li>每条先读 GT，再读诊断</li>
        <li>不要回头改之前的分（容易引入修正 bias）</li>
        <li>不要去想哪条是 hybrid 哪条是 grep</li>
        <li>评分实时存到 localStorage，关闭浏览器再开还在</li>
        <li>下载只导出已填完整的条目，不完整的会提示跳过多少条</li>
      </ul>

      <h3>键盘快捷键</h3>
      <ul>
        <li><kbd>←</kbd> / <kbd>→</kbd> — 上一条 / 下一条</li>
        <li><kbd>Esc</kbd>（在文本框中）— 取消聚焦</li>
      </ul>
    </div>
  </div>
</div>

<script>
const ITEMS = __ITEMS_JSON__;
const SPLITS = __SPLITS_JSON__;
const BATCH_ID = "__BATCH_ID__";
const STORAGE_KEY = "cilogbench_e9_" + BATCH_ID + "_labels";
const REVIEWER_KEY = "cilogbench_e9_" + BATCH_ID + "_reviewer";

const ABS_REQUIRED = ["root_cause_correctness","evidence_support","localization_quality","actionability","hallucination_severity","overall_usefulness","abstention_appropriateness"];
const ABS_AXES = [
  ["root_cause_correctness", "根本原因正确性",        "0 = 完全错；4 = 完全命中 GT 真原因"],
  ["evidence_support",       "证据支持",              "0 = quote 是编的或没有；4 = quote 来自原 log 且支持原因"],
  ["localization_quality",   "定位质量",              "0 = 没说 file / test / step；4 = 准确点到 file:line"],
  ["actionability",          "可执行性",              "0 = 无法拿来修；4 = 不知情工程师能直接修"],
  ["hallucination_severity", "幻觉严重程度（越高越糟）", "0 = 没编任何东西；4 = 编了多个大事"],
  ["overall_usefulness",     "整体有用性",            "0 = 没用；4 = 会直接交付给 oncall"],
];

let currentIndex = 0;
let labels = {};   // keyed by review_item_id

try {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) labels = JSON.parse(saved);
  const savedRev = localStorage.getItem(REVIEWER_KEY);
  if (savedRev) document.getElementById("reviewer-id").value = savedRev;
} catch (e) { console.warn("localStorage restore failed", e); }

function escapeHTML(s) {
  return String(s == null ? "" : s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}

function isAbsComplete(label) {
  if (!label) return false;
  for (const k of ABS_REQUIRED) {
    const v = label[k];
    if (k === "abstention_appropriateness") {
      if (!v) return false;
    } else {
      if (typeof v !== "number" || v < 0 || v > 4) return false;
    }
  }
  return true;
}

function isPairComplete(label) {
  if (!label) return false;
  const signals = [
    label.winner === "A" || label.winner === "B",
    !!label.tie,
    !!label.both_bad,
    !!label.insufficient_information,
  ];
  return signals.filter(Boolean).length === 1;
}

function isComplete(item, label) {
  return item.label_type === "absolute" ? isAbsComplete(label) : isPairComplete(label);
}

function saveAll() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(labels));
    localStorage.setItem(REVIEWER_KEY, document.getElementById("reviewer-id").value.trim());
  } catch (e) {
    console.warn("save failed", e);
    showToast("⚠️ localStorage 保存失败");
  }
}

function showToast(msg, ms) {
  ms = ms || 1400;
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => t.classList.remove("show"), ms);
}

function renderDiagnosis(diag) {
  if (!diag) return "<em>（无诊断）</em>";
  const evidence = (diag.evidence || []).map(ev => {
    return `<li><code>${escapeHTML(ev.quote)}</code><span class="reason">${escapeHTML(ev.reason)}</span></li>`;
  }).join("");
  const files = (diag.relevant_files || []).map(escapeHTML).join(", ");
  const tests = (diag.relevant_tests || []).map(escapeHTML).join(", ");
  return `
    <p class="d-summary">${escapeHTML(diag.summary)}</p>
    <div class="d-meta">
      <span class="cat">${escapeHTML(diag.root_cause_category || "unknown")}</span>
      <span class="conf">置信度 ${escapeHTML(diag.confidence ?? 0)}</span>
    </div>
    <div class="d-section"><strong>根本原因</strong>${escapeHTML(diag.root_cause)}</div>
    ${files ? `<div class="d-section"><strong>相关文件</strong>${files}</div>` : ""}
    ${tests ? `<div class="d-section"><strong>相关测试</strong>${tests}</div>` : ""}
    ${evidence ? `<div class="d-section"><strong>证据</strong><ul>${evidence}</ul></div>` : "<div class='d-section'><strong>证据</strong>（无）</div>"}
    ${diag.suggested_fix ? `<div class="d-section"><strong>建议修复</strong>${escapeHTML(diag.suggested_fix)}</div>` : ""}
  `;
}

function renderAbsoluteForm(rid, label) {
  label = label || {};
  const axesHTML = ABS_AXES.map(([key, lbl, help]) => {
    const v = label[key];
    const severity = key === "hallucination_severity" ? "severity" : "";
    const buttons = [0,1,2,3,4].map(s =>
      `<button class="score-btn ${severity} ${v===s?'selected':''}" data-axis="${key}" data-score="${s}">${s}</button>`
    ).join("");
    return `<div class="form-row">
      <div class="form-label">${escapeHTML(lbl)}<span class="help">${escapeHTML(help)}</span></div>
      <div class="score-buttons">${buttons}</div>
    </div>`;
  }).join("");
  const ab = label.abstention_appropriateness || "";
  return `
    <div class="form-card">
      <h3>单条评分 · ${escapeHTML(rid)}</h3>
      ${axesHTML}
      <div class="form-row">
        <div class="form-label">弃权（abstention）<span class="help">三选一</span></div>
        <select class="abstention-select" data-rid="${escapeHTML(rid)}">
          <option value="" ${ab===""?"selected":""}>— 请选择 —</option>
          <option value="appropriate" ${ab==="appropriate"?"selected":""}>appropriate（合理弃权：模型说 unknown，证据确实不够）</option>
          <option value="not_appropriate" ${ab==="not_appropriate"?"selected":""}>not_appropriate（不该弃权：证据其实很清楚但模型说 unknown）</option>
          <option value="not_applicable" ${ab==="not_applicable"?"selected":""}>not_applicable（不适用：模型没弃权 ← 最常见）</option>
        </select>
      </div>
      <div class="form-row">
        <div class="form-label">备注（notes）<span class="help">可选 · 切勿写方法名（raw / grep / rtk-* / llm-summary-* / hybrid-*）</span></div>
        <textarea class="notes-text" data-rid="${escapeHTML(rid)}" placeholder="可选；打 0 或 4 分时建议写一句解释">${escapeHTML(label.notes || "")}</textarea>
      </div>
    </div>
  `;
}

function renderPairwiseForm(rid, label) {
  label = label || {};
  const picks = [
    ["A", "A 更好"],
    ["B", "B 更好"],
    ["tie", "平局"],
    ["both_bad", "都不行"],
    ["insufficient_information", "信息不足"],
  ];
  const buttons = picks.map(([key, lbl]) => {
    let isSelected;
    if (key === "A" || key === "B") isSelected = label.winner === key;
    else isSelected = !!label[key];
    return `<button class="winner-btn ${isSelected?'selected':''}" data-pick="${key}">${escapeHTML(lbl)}</button>`;
  }).join("");
  return `
    <div class="form-card">
      <h3>两两对比 · ${escapeHTML(rid)}</h3>
      <div class="form-row">
        <div class="form-label">胜者<span class="help">平局打破顺序：根本原因 → 证据支持 → 定位 → 可执行性 → 不幻觉 → 合理弃权</span></div>
        <div class="winner-row">${buttons}</div>
      </div>
      <div class="form-row">
        <div class="form-label">理由（reason）<span class="help">可选一句话；切勿写方法名</span></div>
        <textarea class="notes-text" data-rid="${escapeHTML(rid)}" placeholder="可选一句话">${escapeHTML(label.reason || "")}</textarea>
      </div>
    </div>
  `;
}

function renderItem(idx) {
  currentIndex = ((idx % ITEMS.length) + ITEMS.length) % ITEMS.length;
  const it = ITEMS[currentIndex];
  const cp = it.case_packet || {};
  const split = SPLITS[it.case_id] || "?";
  const label = labels[it.review_item_id];
  const complete = isComplete(it, label);
  const kindLabel = it.label_type === "absolute" ? "单条评分" : "两两对比";
  const headerHTML = `
    <div class="case-header">
      <h1>${escapeHTML(it.review_item_id)}</h1>
      <div class="badge-row">
        <span class="badge kind">${kindLabel}</span>
        <span class="badge split">${split}</span>
        <span class="badge case">${escapeHTML(it.case_id)}</span>
        ${cp.framework ? `<span class="badge meta">框架: ${escapeHTML(cp.framework)}</span>` : ""}
        ${cp.repo ? `<span class="badge meta">仓库: ${escapeHTML(cp.repo)}</span>` : ""}
        ${cp.workflow_name ? `<span class="badge meta">workflow: ${escapeHTML(cp.workflow_name)}</span>` : ""}
        ${cp.job_name ? `<span class="badge meta">job: ${escapeHTML(cp.job_name)}</span>` : ""}
      </div>
    </div>
    <div class="card">
      <h3>Ground truth 总结（你打分的标准）</h3>
      <p class="gt-text">${escapeHTML(cp.allowed_ground_truth_summary || "（无）")}</p>
      ${cp.required_evidence_excerpt ? `<details><summary>原 log 关键片段（点击展开）</summary><pre>${escapeHTML(cp.required_evidence_excerpt)}</pre></details>` : ""}
    </div>
  `;
  let diagHTML, formHTML;
  if (it.label_type === "absolute") {
    diagHTML = `<div class="diag-grid"><div class="diag-card"><h3>诊断（diagnosis）</h3>${renderDiagnosis(it.diagnosis)}</div></div>`;
    formHTML = renderAbsoluteForm(it.review_item_id, label);
  } else {
    diagHTML = `
      <div class="diag-grid pair">
        <div class="diag-card"><h3>诊断 <span class="ab-tag">A</span></h3>${renderDiagnosis(it.diagnosis_a)}</div>
        <div class="diag-card"><h3>诊断 <span class="ab-tag">B</span></h3>${renderDiagnosis(it.diagnosis_b)}</div>
      </div>`;
    formHTML = renderPairwiseForm(it.review_item_id, label);
  }
  document.getElementById("panel").innerHTML = headerHTML + diagHTML + formHTML;

  // status
  const statusEl = document.getElementById("status");
  const completedSoFar = ITEMS.filter(x => isComplete(x, labels[x.review_item_id])).length;
  statusEl.textContent = `条目 ${currentIndex+1}/${ITEMS.length} · ${complete ? "✓ 已完成" : "○ 未完成"} · 累计 ${completedSoFar}/${ITEMS.length} 条已标`;
  statusEl.className = "status " + (complete ? "complete" : "incomplete");
  document.getElementById("prev-btn").disabled = currentIndex === 0;
  document.getElementById("next-btn").disabled = currentIndex === ITEMS.length - 1;
  renderItemList();
  updateProgress();
}

function renderItemList() {
  // Group by split for readability
  const by = { dev: [], holdout: [], stress: [], "?": [] };
  ITEMS.forEach((it, idx) => {
    const s = SPLITS[it.case_id] || "?";
    (by[s] || by["?"]).push({ it, idx });
  });
  let html = "";
  for (const s of ["dev","holdout","stress","?"]) {
    if (!by[s] || by[s].length === 0) continue;
    if (s !== "?") html += `<div class="sidebar-header">${s.toUpperCase()}</div>`;
    for (const { it, idx } of by[s]) {
      const label = labels[it.review_item_id];
      const complete = isComplete(it, label);
      const cls = ["item-btn"];
      if (idx === currentIndex) cls.push("current");
      cls.push(complete ? "complete" : "incomplete");
      html += `<button class="${cls.join(" ")}" data-idx="${idx}">${escapeHTML(it.review_item_id)} · ${escapeHTML(it.case_id)}</button>`;
    }
  }
  document.getElementById("item-list").innerHTML = html;
}

function updateProgress() {
  const total = ITEMS.length;
  const done = ITEMS.filter(it => isComplete(it, labels[it.review_item_id])).length;
  const absDone = ITEMS.filter(it => it.label_type === "absolute" && isComplete(it, labels[it.review_item_id])).length;
  const absTotal = ITEMS.filter(it => it.label_type === "absolute").length;
  const pairDone = ITEMS.filter(it => it.label_type === "pairwise" && isComplete(it, labels[it.review_item_id])).length;
  const pairTotal = ITEMS.filter(it => it.label_type === "pairwise").length;
  document.getElementById("progress-text").textContent = `${done}/${total} 已完成（单条 ${absDone}/${absTotal} · 对比 ${pairDone}/${pairTotal}）`;
  document.getElementById("progress-fill").style.width = (total === 0 ? 0 : (done / total * 100)) + "%";
}

function buildLabelRecord(item, label, reviewerId) {
  const rec = {
    review_item_id: item.review_item_id,
    reviewer_id: reviewerId,
    label_type: item.label_type,
  };
  if (item.label_type === "absolute") {
    for (const k of ["root_cause_correctness","evidence_support","localization_quality","actionability","hallucination_severity","overall_usefulness"]) {
      rec[k] = label[k];
    }
    // Translate human-friendly abstention -> validator's expected vocabulary
    const m = { appropriate: "correct_abstention", not_appropriate: "inappropriate_abstention", not_applicable: "not_applicable" };
    rec.abstention_appropriateness = m[label.abstention_appropriateness] || "not_applicable";
    if (label.notes && label.notes.trim()) rec.notes = label.notes.trim();
  } else {
    if (label.winner === "A" || label.winner === "B") rec.winner = label.winner;
    if (label.tie) rec.tie = true;
    if (label.both_bad) rec.both_bad = true;
    if (label.insufficient_information) rec.insufficient_information = true;
    if (label.reason && label.reason.trim()) rec.reason = label.reason.trim();
  }
  return rec;
}

// ---- Event delegation on the panel ----
document.getElementById("panel").addEventListener("click", (e) => {
  const t = e.target;
  if (t.matches(".score-btn")) {
    const rid = ITEMS[currentIndex].review_item_id;
    labels[rid] = labels[rid] || {};
    labels[rid][t.dataset.axis] = parseInt(t.dataset.score, 10);
    saveAll();
    renderItem(currentIndex);
  } else if (t.matches(".winner-btn")) {
    const rid = ITEMS[currentIndex].review_item_id;
    labels[rid] = labels[rid] || {};
    const pick = t.dataset.pick;
    delete labels[rid].winner;
    delete labels[rid].tie;
    delete labels[rid].both_bad;
    delete labels[rid].insufficient_information;
    if (pick === "A" || pick === "B") labels[rid].winner = pick;
    else labels[rid][pick] = true;
    saveAll();
    renderItem(currentIndex);
  }
});
document.getElementById("panel").addEventListener("change", (e) => {
  const t = e.target;
  if (t.matches(".abstention-select")) {
    const rid = t.dataset.rid;
    labels[rid] = labels[rid] || {};
    labels[rid].abstention_appropriateness = t.value;
    saveAll();
    renderItem(currentIndex);
  }
});
document.getElementById("panel").addEventListener("input", (e) => {
  const t = e.target;
  if (t.matches(".notes-text")) {
    const rid = t.dataset.rid;
    const item = ITEMS.find(it => it.review_item_id === rid);
    labels[rid] = labels[rid] || {};
    if (item.label_type === "absolute") labels[rid].notes = t.value;
    else labels[rid].reason = t.value;
    saveAll();
    // Don't re-render on every keystroke — just save
  }
});

// Sidebar item click
document.getElementById("item-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".item-btn");
  if (btn) renderItem(parseInt(btn.dataset.idx, 10));
});

// Footer prev/next
document.getElementById("prev-btn").addEventListener("click", () => renderItem(currentIndex - 1));
document.getElementById("next-btn").addEventListener("click", () => renderItem(currentIndex + 1));

// Reviewer ID input
document.getElementById("reviewer-id").addEventListener("input", saveAll);

// Reset button
document.getElementById("reset-btn").addEventListener("click", () => {
  if (!confirm("清空本 batch 全部 label？此操作无法撤销。")) return;
  labels = {};
  localStorage.removeItem(STORAGE_KEY);
  renderItem(0);
  showToast("已清空所有 label");
});

// Help modal
const helpModal = document.getElementById("help-modal");
document.getElementById("help-btn").addEventListener("click", () => {
  helpModal.hidden = false;
});
document.getElementById("help-close-btn").addEventListener("click", () => {
  helpModal.hidden = true;
});
helpModal.querySelector(".help-modal-backdrop").addEventListener("click", () => {
  helpModal.hidden = true;
});

// Download button
document.getElementById("download-btn").addEventListener("click", () => {
  const reviewerId = document.getElementById("reviewer-id").value.trim();
  if (!reviewerId) { alert("请先填写评审者 ID（例如 human_a）。"); return; }
  if (/^(claude|gpt|sonnet|opus|haiku)/i.test(reviewerId) || /expert/i.test(reviewerId)) {
    if (!confirm("该 ID 看起来像模型名。是否仍以此名下载？真人评建议使用 'human_a' 之类的 ID。")) return;
  }
  const lines = [];
  let incomplete = 0;
  for (const item of ITEMS) {
    const label = labels[item.review_item_id];
    if (!label || !isComplete(item, label)) { incomplete++; continue; }
    lines.push(JSON.stringify(buildLabelRecord(item, label, reviewerId)));
  }
  if (lines.length === 0) {
    alert("还没有任何完整的 label，先标完至少一条再下载。");
    return;
  }
  if (incomplete > 0) {
    if (!confirm(`${incomplete} / ${ITEMS.length} 条未完成，将被跳过。仍下载 ${lines.length} 条已完成的 label 吗？`)) return;
  }
  const blob = new Blob([lines.join("\n") + "\n"], { type: "application/x-ndjson" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `reviewer_${reviewerId}.jsonl`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 0);
  showToast(`已下载 ${lines.length} 条 label`);
});

// Keyboard nav
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !helpModal.hidden) { helpModal.hidden = true; return; }
  // Don't intercept while typing in textarea/select/input
  const tag = (e.target && e.target.tagName || "").toUpperCase();
  if (tag === "TEXTAREA" || tag === "SELECT" || tag === "INPUT") {
    if (e.key === "Escape") e.target.blur();
    return;
  }
  if (e.key === "ArrowLeft") { renderItem(currentIndex - 1); e.preventDefault(); }
  else if (e.key === "ArrowRight") { renderItem(currentIndex + 1); e.preventDefault(); }
});

// Show help on first ever visit (when no labels exist yet)
if (Object.keys(labels).length === 0) {
  helpModal.hidden = false;
}

// Initial render
renderItem(0);
</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--reviewer-id", default="human_a",
                    help="Default reviewer ID shown in the form (still editable in UI).")
    ap.add_argument("--review-root", type=Path,
                    default=ROOT / "review" / "batches")
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    batch_dir = args.review_root / args.batch_id
    items_path = batch_dir / "items.jsonl"
    if not items_path.exists():
        print(f"ERROR: {items_path} missing", file=sys.stderr)
        return 1

    raw_items = [
        json.loads(l)
        for l in items_path.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    # Strip any fields that could un-blind the reviewer (e.g. diagnoser)
    safe_items = []
    for it in raw_items:
        safe = {
            "review_item_id": it["review_item_id"],
            "case_id": it["case_id"],
            "label_type": it["label_type"],
            "case_packet": it.get("case_packet"),
        }
        if it["label_type"] == "absolute":
            safe["diagnosis"] = it.get("diagnosis")
        else:
            safe["diagnosis_a"] = it.get("diagnosis_a")
            safe["diagnosis_b"] = it.get("diagnosis_b")
        safe_items.append(safe)

    # Build a case_id → split map by walking cases dir
    splits_by_case: dict[str, str] = {}
    for s in ("dev", "holdout", "stress"):
        sd = args.cases_dir / s
        if sd.is_dir():
            for cd in sd.iterdir():
                if cd.is_dir():
                    splits_by_case[cd.name] = s

    items_json = json.dumps(safe_items, ensure_ascii=False)
    splits_json = json.dumps(splits_by_case, ensure_ascii=False)

    html = (HTML_TEMPLATE
            .replace("__BATCH_ID__", args.batch_id)
            .replace("__REVIEWER_ID__", args.reviewer_id)
            .replace("__ITEMS_JSON__", items_json)
            .replace("__SPLITS_JSON__", splits_json))

    out_path = args.out or (batch_dir / f"review_ui_{args.reviewer_id}.html")
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}  ({len(safe_items)} items embedded)")
    print()
    print("To use:")
    print(f"  open '{out_path}'")
    print(f"  # or: open the URL")
    print(f"  #   file://{out_path.resolve()}")
    print()
    print("When done, the page's 'Download JSONL' button will produce")
    print(f"  reviewer_<reviewer_id>.jsonl")
    print("Save it under:")
    print(f"  {(batch_dir / 'labels').relative_to(ROOT)}/")
    print("Then validate with:")
    print(f"  python3 tools/validate_human_review_labels.py --batch-id {args.batch_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
