const API = "";

let network = null;
let diseaseOptions = [];
let drugOptions = [];

const chipStores = {
  clinical: [],
  prescription: [],
};

const els = {
  statusBadge: document.getElementById("statusBadge"),
  statusText: document.getElementById("statusText"),
  statDrugs: document.getElementById("statDrugs"),
  statDiseases: document.getElementById("statDiseases"),
  statPlans: document.getElementById("statPlans"),
  statInteractions: document.getElementById("statInteractions"),
  statContraindications: document.getElementById("statContraindications"),
  statAdverse: document.getElementById("statAdverse"),
  statTreats: document.getElementById("statTreats"),
  resultsSection: document.getElementById("resultsSection"),
  resultsTitle: document.getElementById("resultsTitle"),
  resultsCount: document.getElementById("resultsCount"),
  resultsBody: document.getElementById("resultsBody"),
  riskBanner: document.getElementById("riskBanner"),
  graphContainer: document.getElementById("graphContainer"),
  loadingOverlay: document.getElementById("loadingOverlay"),
  diseaseInput: document.getElementById("diseaseInput"),
  icdInput: document.getElementById("icdInput"),
  drugInput: document.getElementById("drugInput"),
  comorbidityInput: document.getElementById("comorbidityInput"),
  qaInput: document.getElementById("qaInput"),
  clinicalDiseases: document.getElementById("clinicalDiseases"),
  clinicalCondition: document.getElementById("clinicalCondition"),
  clinicalDrugInput: document.getElementById("clinicalDrugInput"),
  clinicalDrugChips: document.getElementById("clinicalDrugChips"),
  prescriptionInput: document.getElementById("prescriptionInput"),
  prescriptionChips: document.getElementById("prescriptionChips"),
  diseaseTags: document.getElementById("diseaseTags"),
  drugTags: document.getElementById("drugTags"),
  prescriptionTags: document.getElementById("prescriptionTags"),
  qaTags: document.getElementById("qaTags"),
};

const graphGroups = {
  disease: { color: { background: "#dbeafe", border: "#2563eb" }, shape: "dot", size: 22 },
  category: { color: { background: "#e0e7ff", border: "#4338ca" }, shape: "ellipse", size: 20 },
  plan: { color: { background: "#ede9fe", border: "#7c3aed" }, shape: "box" },
  drug: { color: { background: "#d1fae5", border: "#059669" }, shape: "dot", size: 18 },
  effect: { color: { background: "#fee2e2", border: "#dc2626" }, shape: "triangle", size: 16 },
};

const SCENARIOS = {
  "clinical-htn-dm": {
    view: "clinical",
    diseases: "高血压, 2型糖尿病",
    drugs: ["二甲双胍", "氨氯地平"],
    condition: "",
  },
  "prescription-dapt": {
    view: "prescription",
    drugs: ["阿司匹林", "氯吡格雷"],
  },
  "prescription-arb": {
    view: "prescription",
    drugs: ["缬沙坦", "厄贝沙坦"],
  },
  "recommend-htn": {
    view: "recommend",
    disease: "高血压",
  },
  "drug-metformin": {
    view: "drug",
    drug: "二甲双胍",
  },
  "qa-interaction": {
    view: "qa",
    question: "阿司匹林和氯吡格雷能一起吃吗？",
  },
};

// ===== Utilities =====

async function fetchJSON(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout ?? 15000);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(typeof err.detail === "string" ? err.detail : "请求失败");
    }
    return res.json();
  } catch (err) {
    if (err.name === "AbortError") throw new Error("请求超时，请检查 Neo4j 是否正常运行");
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

function showLoading(show) {
  if (!els.loadingOverlay) return;
  els.loadingOverlay.hidden = !show;
}

function setStatus(ok, text) {
  els.statusBadge.classList.remove("ok", "error");
  els.statusBadge.classList.add(ok ? "ok" : "error");
  els.statusText.textContent = text;
}

function lineLabel(line) {
  return { first: "一线", second: "二线" }[line] || line || "未知";
}

function severityLabel(sev) {
  return { major: "严重", moderate: "中等", minor: "轻微", mild: "轻度" }[sev] || sev || "-";
}

function freqLabel(freq) {
  return { common: "常见", uncommon: "偶见", rare: "罕见" }[freq] || freq || "-";
}

function evidenceChip(level) {
  if (!level) return `<span class="chip">证据: -</span>`;
  const cls = level === "A" ? "evidence-a" : level === "B" ? "evidence-b" : "";
  return `<span class="chip ${cls}">证据 ${level} 级</span>`;
}

function showResults(title, countText, badgeClass = "") {
  els.resultsSection.hidden = false;
  els.resultsTitle.textContent = title;
  els.resultsCount.textContent = countText;
  els.resultsCount.className = "badge" + (badgeClass ? ` ${badgeClass}` : "");
  els.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function hideRiskBanner() {
  els.riskBanner.hidden = true;
  els.riskBanner.className = "risk-banner";
}

function showRiskBanner(type, icon, message) {
  els.riskBanner.hidden = false;
  els.riskBanner.className = `risk-banner ${type}`;
  els.riskBanner.innerHTML = `<span class="risk-banner-icon">${icon}</span><span>${message}</span>`;
}

function renderEmpty(message, hint = "") {
  els.resultsBody.innerHTML = `
    <div class="empty-state">
      <p>${message}</p>
      ${hint ? `<p class="muted">${hint}</p>` : ""}
    </div>`;
}

function renderError(message) {
  hideRiskBanner();
  showResults("查询失败", "错误", "danger");
  els.resultsBody.innerHTML = `<div class="error-box">${message}</div>`;
}

function updateWorkflowStep(step) {
  document.querySelectorAll(".workflow-steps .step").forEach((el, i) => {
    el.classList.remove("active", "done");
    if (i + 1 < step) el.classList.add("done");
    else if (i + 1 === step) el.classList.add("active");
  });
}

// ===== Chip Input =====

function renderChips(store, container) {
  container.innerHTML = chipStores[store]
    .map(
      (name, i) => `
      <span class="drug-chip">
        ${name}
        <button type="button" data-store="${store}" data-index="${i}" aria-label="移除">×</button>
      </span>`
    )
    .join("");
}

function addChip(store, name) {
  const trimmed = name.trim();
  if (!trimmed || chipStores[store].includes(trimmed)) return;
  chipStores[store].push(trimmed);
  const container = store === "clinical" ? els.clinicalDrugChips : els.prescriptionChips;
  renderChips(store, container);
}

function removeChip(store, index) {
  chipStores[store].splice(index, 1);
  const container = store === "clinical" ? els.clinicalDrugChips : els.prescriptionChips;
  renderChips(store, container);
}

function setupChipInput(inputEl, store, container) {
  const add = () => {
    if (inputEl.value.trim()) {
      addChip(store, inputEl.value);
      inputEl.value = "";
    }
  };
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); add(); }
  });
  container.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-store]");
    if (btn) removeChip(btn.dataset.store, parseInt(btn.dataset.index, 10));
  });
  return add;
}

// ===== Renderers =====

function renderRecommendResults(data) {
  if (!data.count) {
    showResults("方案推荐", "0 条");
    showRiskBanner("warn", "ℹ", "未找到匹配方案，请尝试其他疾病名称或 ICD 编码");
    renderEmpty("暂无推荐方案");
    return;
  }

  showResults("治疗方案推荐", `${data.count} 条方案`);
  showRiskBanner("safe", "✓", `共找到 ${data.count} 套指南推荐方案，已按治疗线别与证据等级排序`);

  els.resultsBody.innerHTML = data.results
    .map((item) => {
      const drugs = (item.drugs || [])
        .map(
          (d) => `
          <div class="drug-item">
            <strong>${d.generic_name}</strong>
            ${d.brand_name ? `<span> / ${d.brand_name}</span>` : ""}
            ${d.dose ? `<div class="muted">${d.dose} · ${d.frequency || ""} · ${d.route || "口服"}</div>` : ""}
            ${d.atc ? `<div class="muted">ATC ${d.atc}</div>` : ""}
          </div>`
        )
        .join("");

      return `
        <article class="result-card ${item.line === "first" ? "safe-card" : ""}">
          <h3>${item.plan}</h3>
          <div class="meta">
            <span class="chip">${item.disease}</span>
            <span class="chip">ICD ${item.icd || "-"}</span>
            <span class="chip ${item.line === "first" ? "line-first" : ""}">${lineLabel(item.line)}</span>
            ${evidenceChip(item.evidence_level)}
            <span class="chip">${item.population || "-"}</span>
          </div>
          ${item.plan_description ? `<p style="font-size:0.85rem;color:var(--muted);margin:0 0 10px">${item.plan_description}</p>` : ""}
          <h4>方案用药</h4>
          <div class="drug-list">${drugs}</div>
          <div class="meta" style="margin-top:10px;margin-bottom:0">
            <span class="chip" style="font-size:0.75rem">来源：${item.source || "-"}</span>
          </div>
        </article>`;
    })
    .join("");
}

function renderDrugResults(data) {
  if (!data.count) {
    showResults("药品查阅", "未找到", "danger");
    renderEmpty("未找到该药品");
    return;
  }

  showResults("药品信息", data.results[0].drug, "");

  els.resultsBody.innerHTML = data.results
    .map((item) => {
      const diseases = (item.diseases || [])
        .filter((d) => d.disease)
        .map(
          (d) => `
          <div class="disease-item">
            <strong>${d.disease}</strong>
            <div class="meta">
              <span class="chip">ICD ${d.icd || "-"}</span>
              <span class="chip ${d.line === "first" ? "line-first" : ""}">${lineLabel(d.line)}</span>
              ${d.dose ? `<span class="chip">${d.dose} ${d.frequency || ""}</span>` : ""}
            </div>
          </div>`
        )
        .join("");

      const effects = (item.adverse_effects || [])
        .filter((e) => e.effect)
        .map((e) => `<span class="chip warn">${e.effect}（${freqLabel(e.frequency)}）</span>`)
        .join("");

      const contra = (item.contraindications || [])
        .filter((c) => c.condition)
        .map((c) => `<span class="chip danger">${c.condition} — ${severityLabel(c.severity)}</span>`)
        .join("");

      const majorContra = (item.contraindications || []).filter((c) => c.severity === "major").length;

      if (majorContra) {
        showRiskBanner("danger", "⚠", `该药品有 ${majorContra} 项严重禁忌，处方前请务必核对`);
      }

      return `
        <article class="result-card">
          <h3>${item.drug}${item.brand ? `（${item.brand}）` : ""}</h3>
          <div class="meta">
            <span class="chip">ATC ${item.atc || "-"}</span>
            <span class="chip">${item.atc_name || ""}</span>
            <span class="chip">${item.dosage_form || ""}</span>
            ${item.manufacturer ? `<span class="chip">${item.manufacturer}</span>` : ""}
          </div>
          <h4>适应症</h4>
          <div class="disease-list">${diseases || '<span class="muted">无记录</span>'}</div>
          <h4>不良反应</h4>
          <div class="meta">${effects || '<span class="muted">无记录</span>'}</div>
          <h4>禁忌 / 慎用</h4>
          <div class="meta">${contra || '<span class="muted">无记录</span>'}</div>
        </article>`;
    })
    .join("");
}

function renderInteractionResults(data, title = "处方审核报告") {
  const major = (data.interactions || []).filter((i) => i.severity === "major").length;
  const moderate = (data.interactions || []).filter((i) => i.severity === "moderate").length;
  const dupCount = (data.duplicate_classes || []).length;

  if (data.safe) {
    showResults(title, "审核通过", "safe");
    showRiskBanner("safe", "✓", `已审核 ${data.resolved_count} 种药品，未发现已知显著相互作用或同类重复用药`);
    els.resultsBody.innerHTML = `
      <div class="clinical-summary">
        <div class="summary-card safe"><span>审核结论</span><strong>通过</strong></div>
        <div class="summary-card safe"><span>审核药品</span><strong>${data.resolved_count}</strong></div>
        <div class="summary-card safe"><span>风险项</span><strong>0</strong></div>
      </div>
      <div class="success-box">处方药品组合未发现已知冲突，但仍需结合患者肝肾功能、年龄等因素综合判断。</div>
      <p style="font-size:0.85rem;color:var(--muted)">审核药品：${data.drug_names?.join("、") || "-"}</p>`;
    return;
  }

  showResults(title, `${major + moderate + dupCount} 项风险`, "danger");
  showRiskBanner(
    major ? "danger" : "warn",
    major ? "⚠" : "!",
    `发现 ${major} 项严重、${moderate} 项中等相互作用${dupCount ? `，${dupCount} 项同类重复用药` : ""}，请调整处方`
  );

  els.resultsBody.innerHTML = `
    <div class="clinical-summary">
      <div class="summary-card ${major ? "danger" : "warn"}"><span>严重</span><strong>${major}</strong></div>
      <div class="summary-card warn"><span>中等</span><strong>${moderate}</strong></div>
      <div class="summary-card warn"><span>同类重复</span><strong>${dupCount}</strong></div>
    </div>
    ${(data.interactions || [])
      .map(
        (i) => `
        <article class="result-card ${i.severity === "major" ? "danger-card" : "warn-card"}">
          <h3>${i.drug_a} ↔ ${i.drug_b}</h3>
          <div class="meta"><span class="chip danger">${severityLabel(i.severity)}</span></div>
          <p style="margin:0 0 8px;font-size:0.9rem">${i.description || ""}</p>
          <p style="margin:0;font-size:0.85rem;color:var(--muted)"><strong>处置建议：</strong>${i.recommendation || "-"}</p>
        </article>`
      )
      .join("")}
    ${(data.duplicate_classes || [])
      .map(
        (d) => `
        <article class="result-card warn-card">
          <h3>同类重复用药 — ${d.atc_name}</h3>
          <div class="meta">${(d.drugs || []).map((n) => `<span class="chip danger">${n}</span>`).join("")}</div>
          <p style="margin:8px 0 0;font-size:0.85rem;color:var(--muted)">ATC ${d.atc_code}：同一药理类别药物不应重复使用</p>
        </article>`
      )
      .join("")}`;
}

function renderComorbidityResults(data, title = "合并症方案分析") {
  const ix = data.interaction_check || {};
  const major = (ix.interactions || []).filter((i) => i.severity === "major").length;

  showResults(title, `${(data.plans || []).length} 个方案`, ix.safe ? "safe" : "danger");

  if (ix.safe) {
    showRiskBanner("safe", "✓", "各病方案合并后未发现已知用药冲突");
  } else {
    showRiskBanner("danger", "⚠", `合并用药存在 ${(ix.interactions || []).length} 项潜在冲突${major ? `（${major} 项严重）` : ""}`);
  }

  const plans = (data.plans || [])
    .map(
      (p) => `
      <article class="result-card">
        <h3>${p.disease}</h3>
        <div class="meta">
          <span class="chip">${p.plan}</span>
          <span class="chip">ICD ${p.icd || "-"}</span>
          <span class="chip ${p.line === "first" ? "line-first" : ""}">${lineLabel(p.line)}</span>
        </div>
        <div class="drug-list">${(p.drugs || []).map((d) => `<span class="drug-item">${d}</span>`).join("")}</div>
      </article>`
    )
    .join("");

  let ixHtml = "";
  if (!ix.safe && ix.interactions?.length) {
    ixHtml = `<div class="section-title">交叉用药冲突</div>` +
      ix.interactions.map(
        (i) => `
        <article class="result-card danger-card">
          <h3>${i.drug_a} ↔ ${i.drug_b}</h3>
          <div class="meta"><span class="chip danger">${severityLabel(i.severity)}</span></div>
          <p style="font-size:0.88rem;margin:0">${i.description}。${i.recommendation || ""}</p>
        </article>`
      ).join("");
  }

  els.resultsBody.innerHTML = `
    <p style="font-size:0.88rem;color:var(--muted);margin:0 0 12px">
      诊断：${data.diseases?.join("、")} · 涉及药品 ${(data.combined_drugs || []).length} 种
    </p>
    <div class="section-title">各病治疗方案</div>
    ${plans}
    ${ixHtml}`;
}

function renderClinicalResults(diseases, drugs, comorbidityData, interactionData, contraindications) {
  updateWorkflowStep(3);

  const ix = interactionData || {};
  const major = (ix.interactions || []).filter((i) => i.severity === "major").length;
  const contraMajor = (contraindications || []).filter((c) => c.severity === "major").length;
  const hasRisk = !ix.safe || contraMajor > 0;

  showResults("临床用药评估报告", hasRisk ? "需关注" : "可继续", hasRisk ? "danger" : "safe");

  if (hasRisk) {
    showRiskBanner("danger", "⚠",
      `评估发现 ${major} 项严重相互作用、${contraMajor} 项禁忌匹配，建议调整方案后再处方`);
  } else {
    showRiskBanner("safe", "✓", "当前用药组合未发现已知显著冲突，方案符合指南推荐");
  }

  let html = `
    <div class="clinical-summary">
      <div class="summary-card"><span>诊断</span><strong>${diseases.length}</strong></div>
      <div class="summary-card"><span>当前用药</span><strong>${drugs.length}</strong></div>
      <div class="summary-card ${hasRisk ? "danger" : "safe"}"><span>风险项</span><strong>${major + contraMajor + (ix.duplicate_classes?.length || 0)}</strong></div>
    </div>
    <p style="font-size:0.85rem;color:var(--muted);margin-bottom:16px">
      诊断：${diseases.join("、") || "-"} · 用药：${drugs.join("、") || "未录入"}
    </p>`;

  if (contraindications?.length) {
    html += `<div class="section-title">禁忌症警示</div>`;
    html += contraindications.map(
      (c) => `
      <article class="result-card danger-card">
        <h3>${c.drug} — ${c.condition}</h3>
        <div class="meta"><span class="chip danger">${severityLabel(c.severity)}</span></div>
        <p style="font-size:0.88rem;margin:0">${c.description || ""}</p>
      </article>`
    ).join("");
  }

  if (comorbidityData?.plans?.length) {
    html += `<div class="section-title">指南推荐方案</div>`;
    html += comorbidityData.plans.map(
      (p) => `
      <article class="result-card">
        <h3>${p.disease} — ${p.plan}</h3>
        <div class="meta">
          <span class="chip ${p.line === "first" ? "line-first" : ""}">${lineLabel(p.line)}</span>
        </div>
        <div class="drug-list">${(p.drugs || []).map((d) => `<span class="drug-item">${d}</span>`).join("")}</div>
      </article>`
    ).join("");
  }

  if (!ix.safe) {
    html += `<div class="section-title">相互作用检测</div>`;
    html += (ix.interactions || []).map(
      (i) => `
      <article class="result-card ${i.severity === "major" ? "danger-card" : "warn-card"}">
        <h3>${i.drug_a} ↔ ${i.drug_b}</h3>
        <div class="meta"><span class="chip danger">${severityLabel(i.severity)}</span></div>
        <p style="font-size:0.88rem;margin:0">${i.description}。<strong>建议：</strong>${i.recommendation || "-"}</p>
      </article>`
    ).join("");
    html += (ix.duplicate_classes || []).map(
      (d) => `
      <article class="result-card warn-card">
        <h3>同类重复 — ${d.atc_name}</h3>
        <div class="meta">${d.drugs.map((n) => `<span class="chip danger">${n}</span>`).join("")}</div>
      </article>`
    ).join("");
  } else if (drugs.length >= 2) {
    html += `<div class="success-box">当前 ${drugs.length} 种用药未发现已知相互作用</div>`;
  }

  els.resultsBody.innerHTML = html;
}

function renderQAResults(data) {
  const intentMap = {
    interaction_check: "相互作用咨询",
    recommend: "方案推荐",
    drug_info: "药品查询",
    contraindication_check: "禁忌咨询",
    unknown: "通用",
  };
  showResults("智能助手回复", intentMap[data.intent] || data.intent, "");
  showRiskBanner("safe", "💬", "以下回答基于知识图谱检索，仅供参考");
  els.resultsBody.innerHTML = `
    <article class="result-card">
      <div class="meta"><span class="chip">${intentMap[data.intent] || data.intent}</span></div>
      <div class="qa-answer">${(data.answer || "").replace(/\n/g, "<br>")}</div>
    </article>`;
}

function renderGraph(data) {
  if (!data.nodes?.length) {
    if (network) { network.destroy(); network = null; }
    els.graphContainer.innerHTML = `<div class="empty-state"><p>暂无关联图谱</p></div>`;
    return;
  }
  els.graphContainer.innerHTML = "";
  const nodes = new vis.DataSet(data.nodes.map((n) => ({ ...n, font: { size: 13 } })));
  const edges = new vis.DataSet(
    data.edges.map((e) => ({
      ...e, arrows: "to", font: { align: "middle", size: 10 }, color: { color: "#94a3b8" },
    }))
  );
  network = new vis.Network(
    els.graphContainer,
    { nodes, edges },
    {
      groups: graphGroups,
      physics: { stabilization: { iterations: 120 }, barnesHut: { gravitationalConstant: -2500, springLength: 130 } },
      interaction: { hover: true, tooltipDelay: 100 },
    }
  );
}

// ===== Search Actions =====

async function withLoading(fn) {
  showLoading(true);
  try { await fn(); } finally { showLoading(false); }
}

async function searchRecommend(disease, icd) {
  const params = new URLSearchParams();
  if (disease) params.set("disease", disease);
  if (icd) params.set("icd", icd);
  const [recommend, graph] = await Promise.all([
    fetchJSON(`${API}/recommend?${params}`),
    fetchJSON(`${API}/graph?${params}`),
  ]);
  renderRecommendResults(recommend);
  renderGraph(graph);
}

async function searchDrug(drugName) {
  const params = new URLSearchParams({ drug_name: drugName });
  const [drug, graph] = await Promise.all([
    fetchJSON(`${API}/drug?${params}`),
    fetchJSON(`${API}/graph?${params}`),
  ]);
  renderDrugResults(drug);
  renderGraph(graph);
}

async function searchInteraction(drugs, title) {
  const params = new URLSearchParams({ drugs: drugs.join(",") });
  const data = await fetchJSON(`${API}/interactions?${params}`);
  renderInteractionResults(data, title);
  if (drugs.length) {
    const graph = await fetchJSON(`${API}/graph?drug_name=${encodeURIComponent(drugs[0])}`);
    renderGraph(graph);
  }
}

async function searchComorbidity(diseases, title) {
  const data = await fetchJSON(`${API}/comorbidity`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ diseases }),
  });
  renderComorbidityResults(data, title);
  if (diseases.length) {
    const graph = await fetchJSON(`${API}/graph?disease=${encodeURIComponent(diseases[0])}`);
    renderGraph(graph);
  }
}

async function searchQA(question) {
  const data = await fetchJSON(`${API}/qa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  renderQAResults(data);
}

async function runClinicalAssessment(diseases, drugs, condition) {
  updateWorkflowStep(2);

  const tasks = [];

  if (diseases.length) {
    tasks.push(
      fetchJSON(`${API}/comorbidity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ diseases }),
      })
    );
  } else {
    tasks.push(Promise.resolve(null));
  }

  if (drugs.length >= 2) {
    tasks.push(fetchJSON(`${API}/interactions?drugs=${encodeURIComponent(drugs.join(","))}`));
  } else {
    tasks.push(Promise.resolve({ safe: true, interactions: [], duplicate_classes: [] }));
  }

  if (drugs.length && condition) {
    tasks.push(
      Promise.all(
        drugs.map((d) =>
          fetchJSON(`${API}/contraindications?drug_name=${encodeURIComponent(d)}&condition=${encodeURIComponent(condition)}`)
            .then((r) => r.results)
            .catch(() => [])
        )
      ).then((arr) => arr.flat())
    );
  } else {
    tasks.push(Promise.resolve([]));
  }

  const [comorbidityData, interactionData, contraindications] = await Promise.all(tasks);

  renderClinicalResults(diseases, drugs, comorbidityData, interactionData, contraindications);

  const graphQuery = diseases[0]
    ? `disease=${encodeURIComponent(diseases[0])}`
    : drugs[0]
      ? `drug_name=${encodeURIComponent(drugs[0])}`
      : null;
  if (graphQuery) {
    const graph = await fetchJSON(`${API}/graph?${graphQuery}`);
    renderGraph(graph);
  }
}

// ===== Navigation =====

function switchView(viewId) {
  document.querySelectorAll(".nav-item").forEach((n) => {
    n.classList.toggle("active", n.dataset.view === viewId);
  });
  document.querySelectorAll(".view").forEach((v) => {
    v.classList.toggle("active", v.id === `view-${viewId}`);
  });
  if (viewId === "clinical") updateWorkflowStep(1);
}

function runScenario(key) {
  const s = SCENARIOS[key];
  if (!s) return;
  switchView(s.view);

  if (s.view === "clinical") {
    els.clinicalDiseases.value = s.diseases || "";
    els.clinicalCondition.value = s.condition || "";
    chipStores.clinical = [...(s.drugs || [])];
    renderChips("clinical", els.clinicalDrugChips);
    withLoading(() => runClinicalAssessment(
      s.diseases.split(/[,，]/).map((d) => d.trim()).filter(Boolean),
      s.drugs || [],
      s.condition || ""
    )).catch((err) => renderError(err.message));
  } else if (s.view === "prescription") {
    chipStores.prescription = [...s.drugs];
    renderChips("prescription", els.prescriptionChips);
    withLoading(() => searchInteraction(s.drugs, "处方审核报告")).catch((err) => renderError(err.message));
  } else if (s.view === "recommend") {
    els.diseaseInput.value = s.disease;
    withLoading(() => searchRecommend(s.disease, "")).catch((err) => renderError(err.message));
  } else if (s.view === "drug") {
    els.drugInput.value = s.drug;
    withLoading(() => searchDrug(s.drug)).catch((err) => renderError(err.message));
  } else if (s.view === "qa") {
    els.qaInput.value = s.question;
    withLoading(() => searchQA(s.question)).catch((err) => renderError(err.message));
  }
}

// ===== Init =====

async function loadStats() {
  const stats = await fetchJSON(`${API}/stats`);
  els.statDrugs.textContent = stats.drugs ?? "-";
  els.statDiseases.textContent = stats.diseases ?? "-";
  els.statPlans.textContent = stats.plans ?? "-";
  els.statInteractions.textContent = stats.interactions ?? "-";
  els.statContraindications.textContent = stats.contraindications ?? "-";
  els.statAdverse.textContent = stats.adverse_effects ?? "-";
  if (els.statTreats) els.statTreats.textContent = stats.treats ?? "-";
}

async function loadOptions() {
  const [diseases, drugs] = await Promise.all([
    fetchJSON(`${API}/diseases`),
    fetchJSON(`${API}/drugs`),
  ]);
  diseaseOptions = diseases.results;
  drugOptions = drugs.results;

  const diseaseOpts = diseaseOptions.map((d) => `<option value="${d.name}">${d.icd || ""}</option>`).join("");
  document.querySelectorAll("datalist[id^='diseaseList']").forEach((el) => { el.innerHTML = diseaseOpts; });

  const drugOpts = drugOptions.map((d) => `<option value="${d.name}">${d.brand || ""}</option>`).join("");
  document.querySelectorAll("datalist[id^='drugList']").forEach((el) => { el.innerHTML = drugOpts; });

  els.diseaseTags.innerHTML = diseaseOptions.slice(0, 5)
    .map((d) => `<button type="button" class="tag" data-disease="${d.name}">${d.name}</button>`).join("");

  els.drugTags.innerHTML = drugOptions.slice(0, 5)
    .map((d) => `<button type="button" class="tag" data-drug="${d.name}">${d.name}</button>`).join("");

  els.prescriptionTags.innerHTML = `
    <button type="button" class="tag" data-rx="缬沙坦,厄贝沙坦">ARB 重复</button>
    <button type="button" class="tag" data-rx="阿司匹林,氯吡格雷">双抗联用</button>
    <button type="button" class="tag" data-rx="氨氯地平,辛伐他汀">CYP3A4</button>`;

  els.qaTags.innerHTML = `
    <button type="button" class="tag" data-qa="阿司匹林和氯吡格雷能一起吃吗？">联用咨询</button>
    <button type="button" class="tag" data-qa="高血压推荐什么方案？">方案推荐</button>
    <button type="button" class="tag" data-qa="二甲双胍的适应症">药品适应症</button>`;
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });

  document.querySelectorAll(".scenario-card").forEach((card) => {
    card.addEventListener("click", () => runScenario(card.dataset.scenario));
  });

  const addClinical = setupChipInput(els.clinicalDrugInput, "clinical", els.clinicalDrugChips);
  const addRx = setupChipInput(els.prescriptionInput, "prescription", els.prescriptionChips);

  document.getElementById("addClinicalDrug").addEventListener("click", addClinical);
  document.getElementById("addPrescriptionDrug").addEventListener("click", addRx);

  document.getElementById("clinicalDemo").addEventListener("click", () => {
    els.clinicalDiseases.value = "高血压, 2型糖尿病";
    els.clinicalCondition.value = "";
    chipStores.clinical = ["二甲双胍", "氨氯地平", "阿司匹林"];
    renderChips("clinical", els.clinicalDrugChips);
  });

  document.getElementById("clinicalForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const diseases = els.clinicalDiseases.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
    const drugs = [...chipStores.clinical];
    const condition = els.clinicalCondition.value;
    if (!diseases.length && !drugs.length) return renderError("请至少录入诊断或当前用药");
    await withLoading(() => runClinicalAssessment(diseases, drugs, condition)).catch((err) => renderError(err.message));
  });

  document.getElementById("recommendForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const disease = els.diseaseInput.value.trim();
    const icd = els.icdInput.value.trim();
    if (!disease && !icd) return renderError("请输入疾病名称或 ICD 编码");
    await withLoading(() => searchRecommend(disease, icd)).catch((err) => renderError(err.message));
  });

  document.getElementById("prescriptionForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const drugs = [...chipStores.prescription];
    if (drugs.length < 2) return renderError("处方审核至少需要 2 种药品");
    await withLoading(() => searchInteraction(drugs, "处方审核报告")).catch((err) => renderError(err.message));
  });

  document.getElementById("drugForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = els.drugInput.value.trim();
    if (!name) return renderError("请输入药品名称");
    await withLoading(() => searchDrug(name)).catch((err) => renderError(err.message));
  });

  document.getElementById("comorbidityForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const diseases = els.comorbidityInput.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
    if (!diseases.length) return renderError("请输入至少一种疾病");
    await withLoading(() => searchComorbidity(diseases)).catch((err) => renderError(err.message));
  });

  document.getElementById("qaForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = els.qaInput.value.trim();
    if (!q) return renderError("请输入问题");
    await withLoading(() => searchQA(q)).catch((err) => renderError(err.message));
  });

  els.diseaseTags.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-disease]");
    if (!btn) return;
    els.diseaseInput.value = btn.dataset.disease;
    await withLoading(() => searchRecommend(btn.dataset.disease, "")).catch((err) => renderError(err.message));
  });

  els.drugTags.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-drug]");
    if (!btn) return;
    els.drugInput.value = btn.dataset.drug;
    await withLoading(() => searchDrug(btn.dataset.drug)).catch((err) => renderError(err.message));
  });

  els.prescriptionTags.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-rx]");
    if (!btn) return;
    chipStores.prescription = btn.dataset.rx.split(",");
    renderChips("prescription", els.prescriptionChips);
    await withLoading(() => searchInteraction(chipStores.prescription, "处方审核报告")).catch((err) => renderError(err.message));
  });

  els.qaTags.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-qa]");
    if (!btn) return;
    els.qaInput.value = btn.dataset.qa;
    await withLoading(() => searchQA(btn.dataset.qa)).catch((err) => renderError(err.message));
  });

  document.getElementById("printResults").addEventListener("click", () => window.print());
  document.getElementById("clearResults").addEventListener("click", () => {
    els.resultsSection.hidden = true;
    hideRiskBanner();
    if (network) { network.destroy(); network = null; }
    els.graphContainer.innerHTML = "";
  });
}

async function bootstrap() {
  showLoading(false);
  bindEvents();
  try {
    const health = await fetchJSON(`${API}/health`);
    setStatus(true, "Neo4j 已连接");
    await Promise.all([loadStats(), loadOptions()]);
  } catch (err) {
    setStatus(false, "数据库未连接");
    switchView("dashboard");
  } finally {
    showLoading(false);
  }
}

bootstrap();
