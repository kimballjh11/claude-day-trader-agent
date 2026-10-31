/**
 * POST { decision_id, vote: "agree"|"disagree" }
 * Writes reviews/votes/<decision_id>.json via GitHub Contents API.
 * Env: GITHUB_TOKEN, GITHUB_REPO (owner/name)
 */
const fs = require("fs");
const path = require("path");

const DECISION_RE = /^\d{8}-[A-Z.\-]{1,10}-claude$/;

function readStateJson() {
  // Read the copy bundled with this deployment (vercel.json includeFiles).
  // Fetching our own URL fails once Vercel Authentication is on.
  const file = path.join(__dirname, "..", "data", "state.json");
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

async function githubPutVote(decisionId, vote, token, repo) {
  const path = `reviews/votes/${decisionId}.json`;
  const api = `https://api.github.com/repos/${repo}/contents/${path}`;
  const bodyObj = {
    decision_id: decisionId,
    vote,
    voted_at: new Date().toISOString(),
  };
  const content = Buffer.from(JSON.stringify(bodyObj, null, 2) + "\n").toString(
    "base64"
  );

  let sha;
  const getRes = await fetch(api, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "claude-day-trader-agent-dashboard",
    },
  });
  if (getRes.ok) {
    const existing = await getRes.json();
    sha = existing.sha;
  } else if (getRes.status !== 404) {
    const t = await getRes.text();
    throw new Error(`GitHub GET ${getRes.status}: ${t}`);
  }

  const putRes = await fetch(api, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "claude-day-trader-agent-dashboard",
    },
    body: JSON.stringify({
      message: `vote: ${decisionId} -> ${vote}`,
      content,
      sha,
    }),
  });
  if (!putRes.ok) {
    const t = await putRes.text();
    throw new Error(`GitHub PUT ${putRes.status}: ${t}`);
  }
  return putRes.json();
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "method_not_allowed" });
    return;
  }

  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO;
  if (!token || !repo) {
    res.status(500).json({ error: "missing_github_env" });
    return;
  }

  let payload = req.body;
  if (typeof payload === "string") {
    try {
      payload = JSON.parse(payload);
    } catch {
      res.status(400).json({ error: "invalid_json" });
      return;
    }
  }

  const decisionId = payload && payload.decision_id;
  const vote = payload && payload.vote;
  if (!decisionId || !DECISION_RE.test(decisionId)) {
    res.status(400).json({ error: "invalid_decision_id" });
    return;
  }
  if (vote !== "agree" && vote !== "disagree") {
    res.status(400).json({ error: "invalid_vote" });
    return;
  }

  try {
    const state = readStateJson();
    const known =
      (state.votable_ids || []).includes(decisionId) ||
      (state.decisions_today || []).some((d) => d.decision_id === decisionId);
    if (!known) {
      res.status(404).json({ error: "decision_not_in_state" });
      return;
    }
    await githubPutVote(decisionId, vote, token, repo);
    res.status(200).json({ ok: true, decision_id: decisionId, vote });
  } catch (e) {
    res.status(500).json({ error: "vote_failed", detail: String(e.message || e) });
  }
};
