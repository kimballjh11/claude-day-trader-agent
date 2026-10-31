/* global Chart */

const ERROR_COPY = {
  TESTS_FAILED:
    "The robot stopped because a safety test failed. Nothing traded. Check the latest commit.",
  MCP_AUTH:
    "Robinhood connection expired. Open Claude Code and run /mcp to log in again.",
  MCP_ERROR: "Robinhood returned an error.",
  DATA_STALE: "Price data did not reconcile; those symbols were skipped.",
  RULE_VIOLATION: "The audit found a rule violation. Review before the next run.",
  ORDER_REJECTED_PREVIEW: "Robinhood's preview rejected an order.",
  HALT_DAILY: "Daily loss halt — new buys paused.",
  HALT_WEEKLY: "Weekly loss halt — new buys paused.",
  LEDGER_INVALID: "The paper ledger failed validation. The run stopped.",
  ROBINHOOD_APPROVAL_REQUIRED:
    "Robinhood is holding an order for your approval in the app.",
  ORDER_NOT_CONFIRMED: "An order was sent but could not be confirmed.",
};

function fmtUsd(n) {
  return `$${Number(n || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return "—";
  const v = Number(n) * 100;
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

// Thesis, catalyst, and source text come from web research: escape everything.
function esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function safeUrl(u) {
  try {
    const url = new URL(String(u));
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

function missedRunBanner(state) {
  // scheduled_runs lists every run due after this file was built. If one is
  // past its grace period and the file was never rebuilt, that run never reported.
  const grace = (state.missed_run_grace_minutes || 60) * 60 * 1000;
  const built = new Date(state.generated_at).getTime();
  if (Number.isNaN(built)) return null;
  const now = Date.now();
  const missed = (state.scheduled_runs || []).find((r) => {
    const t = new Date(r.scheduled_at).getTime();
    return t > built && t + grace < now;
  });
  if (!missed) return null;
  return {
    severity: "error",
    code: "MISSED_RUN",
    text: `The ${missed.run} run scheduled for ${missed.scheduled_at} did not report. It may have hit a Claude usage limit or failed to start. Check Claude Code's scheduled tasks.`,
  };
}

function renderBanners(state) {
  const root = document.getElementById("banners");
  root.innerHTML = "";
  const items = [...(state.errors || [])];
  const missed = missedRunBanner(state);
  if (missed) items.unshift(missed);
  if (state.last_run && state.last_run.outcome === "market_closed") {
    root.appendChild(
      el(`<div class="banner warning">Market closed today.</div>`)
    );
  }
  for (const e of items) {
    const sev = e.severity || "error";
    const text =
      e.text ||
      ERROR_COPY[e.code] ||
      e.code ||
      "Unknown issue";
    const cls = sev === "warning" ? "warning" : "error";
    root.appendChild(el(`<div class="banner ${cls}"><strong>${esc(e.code || sev)}</strong> — ${esc(text)}</div>`));
  }
}

function renderScorecards(state) {
  const root = document.getElementById("scorecards");
  root.innerHTML = "";
  const books = [
    ["Claude", state.books.claude],
    ["Control", state.books.control],
    ["SPY", state.books.spy],
  ];
  for (const [name, b] of books) {
    const halt =
      b.halted
        ? `<div class="halt">HALTED${b.halt_reason ? `: ${esc(b.halt_reason)}` : ""}</div>`
        : "";
    const extra =
      name === "SPY"
        ? `<div class="pcts">Since inception ${fmtPct(b.since_inception_pct)}</div>`
        : `<div class="pcts">Day ${fmtPct(b.day_pct)} · Week ${fmtPct(b.week_pct)} · Since ${fmtPct(b.since_inception_pct)}</div>`;
    root.appendChild(
      el(`<div class="tile"><h3>${name}</h3><div class="eq">${fmtUsd(b.equity_usd)}</div>${extra}${halt}</div>`)
    );
  }
}

let chart;
function renderChart(state) {
  const series = state.equity_series || [];
  const labels = series.map((r) => `${r.date} ${r.run || ""}`.trim());
  const ctx = document.getElementById("equityChart");
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Claude", data: series.map((r) => r.claude), borderColor: "#1f4e79", tension: 0.15 },
        { label: "Control", data: series.map((r) => r.control), borderColor: "#c47a12", tension: 0.15 },
        { label: "SPY", data: series.map((r) => r.spy), borderColor: "#1a7f4b", tension: 0.15 },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom" } },
      scales: { y: { beginAtZero: false } },
    },
  });
}

async function castVote(decisionId, vote, btn) {
  const card = btn.closest(".decision");
  const prev = card.dataset.vote || "";
  card.dataset.vote = vote;
  card.querySelectorAll("button").forEach((b) => b.classList.remove("active-agree", "active-disagree"));
  btn.classList.add(vote === "agree" ? "active-agree" : "active-disagree");
  try {
    const res = await fetch("/api/vote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision_id: decisionId, vote }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
  } catch (e) {
    card.dataset.vote = prev;
    card.querySelectorAll("button").forEach((b) => b.classList.remove("active-agree", "active-disagree"));
    if (prev === "agree") card.querySelector("[data-v=agree]")?.classList.add("active-agree");
    if (prev === "disagree") card.querySelector("[data-v=disagree]")?.classList.add("active-disagree");
    alert(`Vote failed: ${e.message}`);
  }
}

const URL_RE = /https?:\/\/[^\s)]+/g;

// Pull inline URLs out of research text so they show as named source links instead.
function splitUrls(text) {
  const urls = String(text || "").match(URL_RE) || [];
  const clean = String(text || "").replace(URL_RE, "").replace(/\s+([.,;])/g, "$1").trim();
  return { clean, urls };
}

function sourceLabel(u) {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return "source";
  }
}

function fmtPrice(n) {
  return n == null || n === "" ? "—" : fmtUsd(n);
}

function renderDecisions(state) {
  const root = document.getElementById("decisions");
  root.innerHTML = "";
  const list = state.decisions_today || [];
  if (!list.length) {
    root.appendChild(el(`<p class="empty">No decisions yet.</p>`));
    return;
  }
  for (const d of list) {
    const catalyst = splitUrls(d.catalyst);
    const thesis = splitUrls(d.thesis_summary);
    const urls = [...new Set([...(d.sources || []), ...catalyst.urls, ...thesis.urls])];
    const sources = urls
      .map(safeUrl)
      .filter(Boolean)
      .map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(sourceLabel(u))}</a>`)
      .join(" · ");
    const amount = d.amount_usd ? fmtUsd(d.amount_usd) : "sized at open";
    const signals = (d.signals_fired || []).join(", ") || "—";
    const flags = (d.risk_flags || []).join(", ") || "—";
    const thesisRow = thesis.clean
      ? `<dt>Thesis</dt><dd>${esc(thesis.clean)}</dd>`
      : "";
    const card = el(`<article class="decision" data-vote="${esc(d.vote || "")}">
      <h3>${esc(d.symbol)} · ${esc(d.action)} · ${esc(d.conviction || "—")} · ${esc(amount)}</h3>
      <div class="meta">status: ${esc(d.status)} · ${esc(d.decision_id)}</div>
      <div class="factors">
        <span><b>Price</b> ${esc(fmtPrice(d.thesis_price))}</span>
        <span><b>12-1 mom</b> ${esc(fmtPct(d.mom_12_1))}</span>
        <span><b>60-day</b> ${esc(fmtPct(d.ret_60d))}</span>
        <span><b>From 52-wk high</b> ${esc(d.pct_from_52wk_high == null ? "—" : fmtPct(-d.pct_from_52wk_high))}</span>
        <span><b>Macro</b> ${esc(d.macro_regime || "—")}</span>
        <span><b>ATD</b> ${esc(d.atd_action || "—")}</span>
      </div>
      <dl>
        ${thesisRow}
        <dt>Catalyst</dt><dd>${esc(catalyst.clean || "—")}</dd>
        <dt>Counter</dt><dd>${esc(d.counter_case || "—")}</dd>
        <dt>Invalidation</dt><dd>${esc(d.invalidation_condition || "—")}</dd>
        <dt>Earnings</dt><dd>${esc(d.earnings_date || "—")}</dd>
        <dt>Signals</dt><dd>${esc(signals)}</dd>
        <dt>Risk flags</dt><dd>${esc(flags)}</dd>
        <dt>Risk</dt><dd>${esc(d.risk_verdict || "—")}</dd>
        <dt>Sources</dt><dd>${sources || "—"}</dd>
      </dl>
      <div class="actions">
        <button data-v="agree" class="primary ${d.vote === "agree" ? "active-agree" : ""}">Agree</button>
        <button data-v="disagree" class="${d.vote === "disagree" ? "active-disagree" : ""}">Disagree</button>
      </div>
    </article>`);
    card.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => castVote(d.decision_id, b.dataset.v, b));
    });
    root.appendChild(card);
  }
}

function table(headers, rows) {
  if (!rows.length) return `<p class="empty">None.</p>`;
  const th = headers.map((h) => `<th>${esc(h)}</th>`).join("");
  const tr = rows
    .map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`)
    .join("");
  return `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
}

function renderPositions(state) {
  const rows = (state.positions || []).map((p) => [
    p.book,
    p.symbol,
    p.sector,
    fmtUsd(p.market_value_usd),
    fmtPct(p.unrealized_pct),
    fmtUsd(p.stop_price_usd),
    fmtUsd(p.next_take_profit_usd),
    p.entry_date || "—",
    p.conviction || "—",
  ]);
  document.getElementById("positions").innerHTML = table(
    ["Book", "Symbol", "Sector", "Value", "Unreal.", "Stop", "Next TP", "Entry", "Conv."],
    rows
  );
}

function renderSectors(state) {
  const parts = [];
  const cap = state.max_positions_per_sector == null ? "—" : String(state.max_positions_per_sector);
  for (const book of ["claude", "control"]) {
    const rows = ((state.sector_exposure || {})[book] || []).map((s) => [
      book,
      s.sector,
      String(s.count),
      cap,
    ]);
    parts.push(table(["Book", "Sector", "Count", "Cap"], rows));
  }
  document.getElementById("sectors").innerHTML = parts.join("") || `<p class="empty">None.</p>`;
}

function renderBlocked(state) {
  const rows = (state.blocked || []).map((b) => [
    b.book || "—",
    b.symbol || "—",
    b.rule || "—",
    b.detail || "—",
  ]);
  document.getElementById("blocked").innerHTML = table(
    ["Book", "Symbol", "Rule", "Detail"],
    rows
  );
}

function renderTrades(state) {
  const rows = (state.recent_trades || []).map((t) => [
    t.date,
    t.book,
    t.symbol,
    t.side,
    fmtUsd(t.amount_usd),
    fmtUsd(t.price_usd),
    t.reason || "—",
  ]);
  document.getElementById("trades").innerHTML = table(
    ["Date", "Book", "Symbol", "Side", "Amount", "Price", "Reason"],
    rows
  );
}

function renderGraduation(state) {
  const root = document.getElementById("graduation");
  root.innerHTML = "";
  for (const item of (state.graduation || {}).items || []) {
    root.appendChild(
      el(`<li><span class="${item.met ? "ok" : "no"}">${item.met ? "✓" : "○"}</span>
        <span><strong>${esc(item.label)}</strong> — ${esc(item.detail || "")}</span></li>`)
    );
  }
}

function renderSignals(state) {
  const rows = (state.signal_attribution || []).map((s) => [
    s.signal,
    String(s.trades || 0),
    s.avg_fwd_5d_vs_spy_pct == null ? "not enough data yet" : fmtPct(s.avg_fwd_5d_vs_spy_pct),
    s.avg_fwd_20d_vs_spy_pct == null ? "not enough data yet" : fmtPct(s.avg_fwd_20d_vs_spy_pct),
  ]);
  document.getElementById("signals").innerHTML = rows.length
    ? table(["Signal", "Trades", "Fwd 5d vs SPY", "Fwd 20d vs SPY"], rows)
    : `<p class="empty">Not enough data yet.</p>`;
}

function renderHeader(state) {
  const badge = document.getElementById("modeBadge");
  const mode = state.mode || "paper";
  badge.textContent = mode.toUpperCase();
  badge.className = `badge ${mode === "live" ? "live" : "paper"}`;
  document.getElementById("modeNote").textContent =
    mode === "paper" ? "Simulated fills" : "Live account (claude book)";
  document.getElementById("updatedAt").textContent = state.generated_at || "—";
  const next = (state.next_runs || [])[0];
  document.getElementById("nextRun").textContent = next
    ? `${next.run} @ ${next.scheduled_at}`
    : "—";
  document.getElementById("unvoted").textContent = String(state.unvoted_count || 0);
}

async function main() {
  const res = await fetch("data/state.json", { cache: "no-store" });
  if (!res.ok) {
    document.getElementById("banners").appendChild(
      el(`<div class="banner error">Could not load data/state.json (${res.status}).</div>`)
    );
    return;
  }
  const state = await res.json();
  renderHeader(state);
  renderBanners(state);
  renderScorecards(state);
  renderChart(state);
  renderDecisions(state);
  renderPositions(state);
  renderSectors(state);
  renderBlocked(state);
  renderTrades(state);
  renderGraduation(state);
  renderSignals(state);
}

main();
