(() => {
  "use strict";

  const state = { report: {}, queue: [], metrics: {} };
  const channels = ["note", "x", "threads", "video"];
  const channelLabels = { note: "note", x: "X", threads: "Threads", video: "動画" };
  const tabs = [...document.querySelectorAll(".tab")];
  const panels = [...document.querySelectorAll(".tab-panel")];

  const $ = (selector) => document.querySelector(selector);
  const safeText = (value, fallback = "—") => {
    const text = String(value ?? "").trim();
    return text || fallback;
  };
  const number = (value) => Number.isFinite(Number(value)) ? Number(value).toLocaleString("ja-JP") : "—";
  const compact = (value, limit = 180) => {
    const text = safeText(value, "").replace(/\s+/g, " ");
    return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`;
  };
  const validUrl = (value) => {
    try {
      const parsed = new URL(String(value), document.baseURI);
      return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : "";
    } catch (_) {
      return "";
    }
  };
  const packHref = (path, fallback = "") => {
    const value = String(path || fallback || "");
    const match = value.match(/data\/drafts\/[A-Za-z0-9_-]+\.md/);
    return match ? `pack.html?file=${encodeURIComponent(match[0])}` : fallback;
  };
  const formatDate = (value) => {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return compact(value, 22);
    return new Intl.DateTimeFormat("ja-JP", {
      timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit",
    }).format(date);
  };
  const clear = (node) => { while (node.firstChild) node.removeChild(node.firstChild); };
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const link = (label, url, className = "action-link") => {
    const href = validUrl(url);
    if (!href) return null;
    const node = el("a", className, label);
    node.href = href;
    return node;
  };
  const append = (parent, child) => { if (child) parent.appendChild(child); };

  function scoreBadge(score, label = "点") {
    const wrapper = el("div", "score");
    wrapper.appendChild(el("span", "", `${number(score)}${label}`));
    wrapper.appendChild(el("small", "", "確認優先度"));
    return wrapper;
  }

  function validationLabel(status) {
    return ({ unverified: "未検証", signal: "反応あり", validated: "検証済み", rejected: "見送り" })[status] || "未検証";
  }

  function outcomeLabel(status) {
    return ({ not_measured: "未計測", measuring: "計測中", signal: "反応あり", converted: "成約あり", no_signal: "反応なし" })[status] || "未計測";
  }

  function resultLine(item) {
    const views = number(item.views || 0);
    const clicks = number(item.clicks || 0);
    const signups = number(item.signups || 0);
    const sales = number(item.sales || 0);
    const revenue = number(item.revenue || 0);
    return `結果：${outcomeLabel(item.outcome_status)} · 閲覧 ${views} · クリック ${clicks} · 登録 ${signups} · 成約 ${sales} · 売上 ${revenue}円`;
  }

  function revenueCard(item, drafts) {
    const card = el("article", "signal-card");
    const top = el("div", "card-top");
    const main = el("div");
    const kicker = el("p", "card-kicker", `${safeText(item.source)} / ${safeText(item.status, "要確認")}`);
    const heading = el("h3");
    append(heading, link(safeText(item.ai_title || item.service_name || item.title), item.url, ""));
    main.append(kicker, heading);
    top.append(main, scoreBadge(item.final_score));
    card.appendChild(top);
    card.appendChild(el("p", "card-summary", compact(item.why_now || item.summary || item.evidence, 220)));
    const meta = el("div", "card-meta");
    meta.append(
      el("span", "", `${safeText(item.category, "AI / SaaS")} · ${priceLine(item)}`),
      el("span", "", `実利用：${usageLabel(item.usage_status)}`),
      el("span", "", `収益準備度：${number(item.revenue_readiness || 0)}点 · 需要：${validationLabel(item.validation_status)}`),
      el("span", "", resultLine(item)),
      el("span", "code", `コード ${safeText(item.id, "").slice(0, 8)}`),
    );
    card.appendChild(meta);
    const actions = el("div", "card-actions");
    const draft = drafts.get(String(item.id));
    append(actions, link("発信用パック", packHref(draft?.path, draft?.url), "action-link"));
    append(actions, link("公式ページ", item.url, "action-link"));
    card.appendChild(actions);
    return card;
  }

  function topicCard(topic) {
    const card = el("article", "signal-card topic-card");
    const top = el("div", "card-top");
    const main = el("div");
    main.appendChild(el("p", "card-kicker", `${safeText(topic.source)} / ${safeText(topic.status, "新規")}`));
    const heading = el("h3");
    append(heading, link(safeText(topic.service_name || topic.title), topic.url, ""));
    main.appendChild(heading);
    top.append(main, scoreBadge(topic.content_score));
    card.appendChild(top);
    const topicSummary = topic.content_angle || topic.reader_problem || topic.project_summary
      ? [
        topic.content_angle ? `切り口：${compact(topic.content_angle, 150)}` : "",
        topic.reader_problem ? `読者の悩み：${compact(topic.reader_problem, 130)}` : "",
        topic.project_summary ? `これは何か：${compact(topic.project_summary, 150)}` : "",
      ].filter(Boolean).join("　")
      : "6つの発信切り口と30秒動画パックを生成済み。まず公式情報を確認し、使った範囲だけ追記します。";
    card.appendChild(el("p", "card-summary", topicSummary));
    const meta = el("div", "card-meta");
    meta.append(el("span", "code", `コード ${safeText(topic.code || topic.id, "").slice(0, 8)}`));
    meta.append(el("span", "", `実利用：${usageLabel(topic.usage_status)}`));
    meta.append(el("span", "", `収益準備度：${number(topic.revenue_readiness || 0)}点 · 需要：${validationLabel(topic.validation_status)}`));
    meta.append(el("span", "", resultLine(topic)));
    if (topic.content_grade) meta.append(el("span", "", safeText(topic.content_grade)));
    if (topic.monetization) meta.append(el("span", "", `収益化：${compact(topic.monetization, 110)}`));
    if (topic.project_type) meta.append(el("span", "", safeText(topic.project_type)));
    card.appendChild(meta);
    const actions = el("div", "card-actions");
    append(actions, link("発信用パック", packHref(topic.pack_path, topic.pack_url), "action-link"));
    append(actions, link("原文", topic.url, "action-link"));
    card.appendChild(actions);
    return card;
  }

  function usageLabel(status) {
    return ({ not_used: "未使用", trial: "試用中", used: "使用済み", published: "公開済み" })[status] || "未使用";
  }

  function priceLine(item) {
    const currency = safeText(item.currency, "");
    if (item.current_price !== undefined && item.current_price !== null) {
      const current = `${currency} ${item.current_price}`.trim();
      if (item.original_price !== undefined && item.original_price !== null) return `${current}（通常 ${currency} ${item.original_price}）`.trim();
      return current;
    }
    if (item.discount !== undefined && item.discount !== null) return `${item.discount}% OFF候補`;
    if (item.affiliate_rate !== undefined && item.affiliate_rate !== null) return `報酬 ${item.affiliate_rate}%`;
    return "条件はリンク先で確認";
  }

  function renderReport() {
    const report = state.report || {};
    const drafts = new Map((Array.isArray(report.drafts) ? report.drafts : []).map((item) => [String(item.id), item]));
    $("#last-updated").textContent = formatDate(report.run_at);
    $("#stat-fetched").textContent = number(report.fetched_count);
    $("#stat-new").textContent = number(report.new_count);
    $("#stat-promising").textContent = number(report.promising_count);
    $("#stat-packs").textContent = number(report.content_pack_count ?? report.draft_count);
    const top = Array.isArray(report.top3) ? report.top3 : [];
    const topics = Array.isArray(report.publishing_topics) ? report.publishing_topics : [];
    const revenueList = $("#revenue-list");
    clear(revenueList);
    top.slice(0, 3).forEach((item) => revenueList.appendChild(revenueCard(item, drafts)));
    $("#revenue-empty").hidden = top.length > 0;
    const topicList = $("#topic-list");
    const topicPreview = $("#topic-preview");
    clear(topicList); clear(topicPreview);
    topics.forEach((topic) => topicList.appendChild(topicCard(topic)));
    topics.slice(0, 2).forEach((topic) => topicPreview.appendChild(topicCard(topic)));
    $("#topic-count").textContent = `${number(topics.length)}件`;
    if (!topics.length) topicList.appendChild(el("div", "empty-state", "今回は発信ネタもありません。次回の巡回を待ちます。"));
    if (!topics.length) topicPreview.appendChild(el("div", "empty-state", "今回は発信ネタなし。次回の変化を待ちます。"));
    const latestLink = validUrl(report.latest?.url);
    if (latestLink) $("#latest-link").href = latestLink;
  }

  function renderQueue() {
    const queue = Array.isArray(state.queue) ? state.queue : [];
    const summary = state.report.queue || summarizeQueue(queue);
    const summaryNode = $("#queue-summary");
    clear(summaryNode);
    [["ready", "未着手"], ["in_progress", "進行中"], ["completed", "完了"]].forEach(([key, label]) => {
      const item = el("div", "queue-stat");
      item.append(el("strong", "", number(summary[key] || 0)), el("span", "", label));
      summaryNode.appendChild(item);
    });
    const list = $("#queue-list");
    clear(list);
    const visible = queue.filter((item) => item.status !== "completed").slice(0, 20);
    if (!visible.length) { list.appendChild(el("div", "empty-state", "未投稿の発信用パックはありません。")); return; }
    visible.forEach((item) => {
      const row = el("article", "queue-row");
      const heading = el("h3");
      append(heading, link(safeText(item.service_name || item.title), packHref(item.pack_path, item.pack_url), ""));
      row.appendChild(heading);
      row.appendChild(el("small", "", `コード ${safeText(item.code || item.id, "").slice(0, 8)} · ${safeText(item.status, "ready")} · 次：${channelLabels[item.next_channel] || "—"}`));
      const track = el("div", "progress-track");
      channels.forEach((channel) => {
        const step = el("span", "progress-step");
        if (item.channels?.[channel]?.status === "posted") step.classList.add("is-posted");
        track.appendChild(step);
      });
      row.appendChild(track);
      const labels = el("div", "progress-labels");
      channels.forEach((channel) => labels.appendChild(el("span", "", channelLabels[channel])));
      row.appendChild(labels);
      list.appendChild(row);
    });
  }

  function summarizeQueue(queue) {
    return {
      total: queue.length,
      ready: queue.filter((item) => item.status === "ready").length,
      in_progress: queue.filter((item) => item.status === "in_progress").length,
      completed: queue.filter((item) => item.status === "completed").length,
    };
  }

  function renderMetrics() {
    const metrics = state.metrics || {};
    const outcomes = metrics.outcomes || {};
    $("#metric-runs").textContent = `${number(metrics.runs || 0)}回`;
    const entries = [
      ["発信パック", metrics.content_pack_count ?? metrics.draft_count],
      ["発信ネタ", metrics.topic_count],
      ["価値あり", metrics.feedback_valuable],
      ["今回は不要", metrics.feedback_not_valuable],
      ["Affiliate候補", metrics.affiliate_count],
      ["計測対象", outcomes.tracked_items],
      ["クリック", outcomes.clicks],
      ["登録", outcomes.signups],
      ["成約", outcomes.sales],
      ["売上（円）", outcomes.revenue],
      ["AI呼び出し", metrics.ai_calls],
      ["重複", metrics.duplicate_count],
      ["エラー", metrics.error_count],
    ];
    const list = $("#metric-list");
    clear(list);
    entries.forEach(([label, value]) => {
      const row = el("div", "metric-row");
      row.append(el("span", "", label), el("strong", "", number(value || 0)));
      list.appendChild(row);
    });
  }

  function showTab(name) {
    tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === name));
    panels.forEach((panel) => panel.classList.toggle("is-active", panel.dataset.panel === name));
    if (history.replaceState) history.replaceState(null, "", `#${name}`);
  }

  function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => toast.classList.remove("is-visible"), 2200);
  }

  async function fetchJson(path) {
    const url = new URL(path, document.baseURI);
    url.searchParams.set("v", Date.now().toString());
    const response = await fetch(url.href, { cache: "no-store" });
    if (!response.ok) throw new Error(`${path}: ${response.status}`);
    return response.json();
  }

  async function loadData(showMessage = false) {
    try {
      const [report, queue, metrics] = await Promise.all([
        fetchJson("data/last_report.json"),
        fetchJson("data/content_queue.json"),
        fetchJson("data/metrics_7d.json"),
      ]);
      state.report = report && typeof report === "object" ? report : {};
      state.queue = Array.isArray(queue) ? queue : [];
      state.metrics = metrics && typeof metrics === "object" ? metrics : {};
      renderReport(); renderQueue(); renderMetrics();
      if (showMessage) showToast("最新データに更新しました");
    } catch (error) {
      console.error("AI VALUE RADAR data load failed", error);
      $("#last-updated").textContent = "データ未取得";
      showToast("データを取得できませんでした。GitHub Actionsの結果を確認してください");
    }
  }

  tabs.forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.tab)));
  document.querySelectorAll("[data-jump]").forEach((button) => button.addEventListener("click", () => showTab(button.dataset.jump)));
  $("#refresh-button").addEventListener("click", () => loadData(true));
  const initialTab = window.location.hash.slice(1);
  if (["overview", "topics", "queue", "metrics"].includes(initialTab)) showTab(initialTab);
  loadData();
})();
