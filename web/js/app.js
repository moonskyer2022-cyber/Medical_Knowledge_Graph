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
  jumpWorkbench: document.getElementById("jumpWorkbench"),
  runIntroScenario: document.getElementById("runIntroScenario"),
};

const graphGroups = {
  disease: { color: { background: "#d7e8ff", border: "#3278c9" }, shape: "dot", size: 22 },
  category: { color: { background: "#ece3ff", border: "#8a6ad9" }, shape: "ellipse", size: 18 },
  plan: { color: { background: "#ffe6d6", border: "#b45a2d" }, shape: "box" },
  drug: { color: { background: "#dff4e8", border: "#1f8d62" }, shape: "dot", size: 18 },
  effect: { color: { background: "#f9ded6", border: "#c25b42" }, shape: "triangle", size: 16 },
};

const SCENARIOS = {
  "clinical-htn-dm": {
    view: "clinical",
    diseases: "高血压, 2型糖尿病",
    drugs: ["二甲双胍", "氨氯地平", "阿司匹林"],
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

function lineLabel(line) {
  return { first: "一线", second: "二线" }[line] || line || "未知";
}

function severityLabel(severity) {
  return {
    major: "严重",
    moderate: "中等",
    minor: "轻度",
    mild: "轻度",
  }[severity] || severity || "-";
}

function frequencyLabel(frequency) {
  return {
    common: "常见",
    uncommon: "偶见",
    rare: "罕见",
  }[frequency] || frequency || "-";
}

function evidenceChip(level) {
  if (!level) return `<span class="chip">证据等级 -</span>`;
  const cls = level === "A" ? "evidence-a" : level === "B" ? "evidence-b" : "";
  return `<span class="chip ${cls}">证据 ${level}</span>`;
}

async function fetchJSON(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout ?? 15000);

  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(typeof error.detail === "string" ? error.detail : "请求失败");
    }
    return response.json();
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("请求超时，请检查 API 或 Neo4j 是否已经正常启动");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function showLoading(show) {
  els.loadingOverlay.hidden = !show;
}

function setStatus(ok, text) {
  els.statusBadge.classList.remove("ok", "error");
  els.statusBadge.classList.add(ok ? "ok" : "error");
  els.statusText.textContent = text;
}

function showResults(title, countText, badgeClass = "") {
  els.resultsSection.hidden = false;
  els.resultsTitle.textContent = title;
  els.resultsCount.textContent = countText;
  els.resultsCount.className = `results-badge${badgeClass ? ` ${badgeClass}` : ""}`;
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
    </div>
  `;
}

function renderError(message) {
  hideRiskBanner();
  showResults("查询失败", "错误");
  els.resultsBody.innerHTML = `<div class="error-box">${message}</div>`;
}

function updateWorkflowStep(step) {
  document.querySelectorAll(".workflow-steps .step").forEach((element, index) => {
    element.classList.remove("active", "done");
    if (index + 1 < step) element.classList.add("done");
    if (index + 1 === step) element.classList.add("active");
  });
}

function renderChips(store, container) {
  container.innerHTML = chipStores[store]
    .map(
      (name, index) => `
        <span class="drug-chip">
          ${name}
          <button type="button" data-store="${store}" data-index="${index}" aria-label="删除">×</button>
        </span>
      `
    )
    .join("");
}

function addChip(store, value) {
  const trimmed = value.trim();
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

function setupChipInput(inputElement, store, container) {
  const add = () => {
    if (inputElement.value.trim()) {
      addChip(store, inputElement.value);
      inputElement.value = "";
    }
  };

  inputElement.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      add();
    }
  });

  container.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-store]");
    if (!button) return;
    removeChip(button.dataset.store, Number.parseInt(button.dataset.index, 10));
  });

  return add;
}

function renderRecommendResults(data) {
  if (!data.count) {
    showResults("治疗方案推荐", "0 条结果");
    showRiskBanner("warn", "!" , "没有查到匹配方案，请尝试更换疾病名称或 ICD 编码");
    renderEmpty("暂无推荐方案");
    return;
  }

  showResults("治疗方案推荐", `${data.count} 条方案`);
  showRiskBanner("safe", "✓", `已找到 ${data.count} 个候选方案，结果已按治疗线别与证据等级排序`);

  els.resultsBody.innerHTML = data.results
    .map((item) => {
      const drugs = (item.drugs || [])
        .map(
          (drug) => `
            <div class="drug-item">
              <strong>${drug.generic_name || "-"}</strong>
              ${drug.brand_name ? `<span>${drug.brand_name}</span>` : ""}
              ${drug.dose ? `<div class="muted">${drug.dose} · ${drug.frequency || ""} · ${drug.route || "口服"}</div>` : ""}
            </div>
          `
        )
        .join("");

      return `
        <article class="result-card ${item.line === "first" ? "safe-card" : ""}">
          <h3>${item.plan || "未命名方案"}</h3>
          <div class="meta">
            <span class="chip">${item.disease || "-"}</span>
            <span class="chip">ICD ${item.icd || "-"}</span>
            <span class="chip ${item.line === "first" ? "line-first" : ""}">${lineLabel(item.line)}</span>
            ${evidenceChip(item.evidence_level)}
            <span class="chip">${item.population || "未标注人群"}</span>
          </div>
          ${item.plan_description ? `<p class="muted">${item.plan_description}</p>` : ""}
          <h4>方案用药</h4>
          <div class="drug-list">${drugs || '<span class="muted">暂无药物信息</span>'}</div>
        </article>
      `;
    })
    .join("");
}

function renderDrugResults(data) {
  if (!data.count) {
    showResults("药品详情查询", "未找到");
    renderEmpty("没有找到对应药品");
    return;
  }

  const primary = data.results[0];
  showResults("药品详情", primary.drug || "药品");

  els.resultsBody.innerHTML = data.results
    .map((item) => {
      const diseases = (item.diseases || [])
        .filter((entry) => entry.disease)
        .map(
          (entry) => `
            <div class="disease-item">
              <strong>${entry.disease}</strong>
              <div class="meta">
                <span class="chip">ICD ${entry.icd || "-"}</span>
                <span class="chip ${entry.line === "first" ? "line-first" : ""}">${lineLabel(entry.line)}</span>
                ${entry.dose ? `<span class="chip">${entry.dose} ${entry.frequency || ""}</span>` : ""}
              </div>
            </div>
          `
        )
        .join("");

      const effects = (item.adverse_effects || [])
        .filter((entry) => entry.effect)
        .map((entry) => `<span class="chip warn">${entry.effect} · ${frequencyLabel(entry.frequency)}</span>`)
        .join("");

      const contraindications = (item.contraindications || [])
        .filter((entry) => entry.condition)
        .map((entry) => `<span class="chip danger">${entry.condition} · ${severityLabel(entry.severity)}</span>`)
        .join("");

      return `
        <article class="result-card">
          <h3>${item.drug || "-"}${item.brand ? ` / ${item.brand}` : ""}</h3>
          <div class="meta">
            <span class="chip">ATC ${item.atc || "-"}</span>
            ${item.atc_name ? `<span class="chip">${item.atc_name}</span>` : ""}
            ${item.dosage_form ? `<span class="chip">${item.dosage_form}</span>` : ""}
            ${item.manufacturer ? `<span class="chip">${item.manufacturer}</span>` : ""}
          </div>
          <h4>适应症</h4>
          <div class="disease-list">${diseases || '<span class="muted">暂无适应症记录</span>'}</div>
          <h4>不良反应</h4>
          <div class="meta">${effects || '<span class="muted">暂无不良反应记录</span>'}</div>
          <h4>禁忌与慎用</h4>
          <div class="meta">${contraindications || '<span class="muted">暂无禁忌记录</span>'}</div>
        </article>
      `;
    })
    .join("");
}

function renderInteractionResults(data, title = "处方审查结果") {
  const major = (data.interactions || []).filter((entry) => entry.severity === "major").length;
  const moderate = (data.interactions || []).filter((entry) => entry.severity === "moderate").length;
  const duplicateCount = (data.duplicate_classes || []).length;

  if (data.safe) {
    showResults(title, "审查通过");
    showRiskBanner("safe", "✓", `已审查 ${data.resolved_count || 0} 种药物，未发现已知显著冲突或同类重复用药`);
    els.resultsBody.innerHTML = `
      <div class="clinical-summary">
        <div class="summary-card safe"><span>审查结论</span><strong>通过</strong></div>
        <div class="summary-card safe"><span>药品数量</span><strong>${data.resolved_count || 0}</strong></div>
        <div class="summary-card safe"><span>风险项</span><strong>0</strong></div>
      </div>
      <div class="success-box">
        当前组合未发现知识库中已知的显著冲突，但仍建议结合患者年龄、肝肾功能、既往病史和指南综合判断。
      </div>
    `;
    return;
  }

  showResults(title, `${major + moderate + duplicateCount} 项风险`);
  showRiskBanner(
    major ? "danger" : "warn",
    major ? "⚠" : "!",
    `发现 ${major} 项严重冲突、${moderate} 项中等冲突${duplicateCount ? `，以及 ${duplicateCount} 组同类重复用药` : ""}`
  );

  const interactions = (data.interactions || [])
    .map(
      (entry) => `
        <article class="result-card ${entry.severity === "major" ? "danger-card" : "warn-card"}">
          <h3>${entry.drug_a || "-"} ↔ ${entry.drug_b || "-"}</h3>
          <div class="meta"><span class="chip danger">${severityLabel(entry.severity)}</span></div>
          <p>${entry.description || "暂无描述"}</p>
          <p class="muted"><strong>建议：</strong>${entry.recommendation || "暂无建议"}</p>
        </article>
      `
    )
    .join("");

  const duplicates = (data.duplicate_classes || [])
    .map(
      (entry) => `
        <article class="result-card warn-card">
          <h3>同类重复用药 · ${entry.atc_name || "-"}</h3>
          <div class="meta">${(entry.drugs || []).map((name) => `<span class="chip danger">${name}</span>`).join("")}</div>
          <p class="muted">ATC ${entry.atc_code || "-"}，建议核对是否存在同类药物重复使用。</p>
        </article>
      `
    )
    .join("");

  els.resultsBody.innerHTML = `
    <div class="clinical-summary">
      <div class="summary-card ${major ? "danger" : "warn"}"><span>严重</span><strong>${major}</strong></div>
      <div class="summary-card warn"><span>中等</span><strong>${moderate}</strong></div>
      <div class="summary-card warn"><span>重复</span><strong>${duplicateCount}</strong></div>
    </div>
    ${interactions}
    ${duplicates}
  `;
}

function renderComorbidityResults(data, title = "合并症方案分析") {
  const interactionCheck = data.interaction_check || {};
  const plans = data.plans || [];

  showResults(title, `${plans.length} 个方案`);

  if (interactionCheck.safe) {
    showRiskBanner("safe", "✓", "各病种方案合并后未发现显著用药冲突");
  } else {
    showRiskBanner("danger", "⚠", `合并方案后发现 ${(interactionCheck.interactions || []).length} 项潜在交叉用药风险`);
  }

  const planHtml = plans
    .map(
      (plan) => `
        <article class="result-card">
          <h3>${plan.disease || "-"} · ${plan.plan || "未命名方案"}</h3>
          <div class="meta">
            <span class="chip">ICD ${plan.icd || "-"}</span>
            <span class="chip ${plan.line === "first" ? "line-first" : ""}">${lineLabel(plan.line)}</span>
          </div>
          <div class="drug-list">${(plan.drugs || []).map((drug) => `<span class="drug-item">${drug}</span>`).join("")}</div>
        </article>
      `
    )
    .join("");

  const interactionHtml = interactionCheck.safe
    ? ""
    : (interactionCheck.interactions || [])
        .map(
          (entry) => `
            <article class="result-card danger-card">
              <h3>${entry.drug_a || "-"} ↔ ${entry.drug_b || "-"}</h3>
              <div class="meta"><span class="chip danger">${severityLabel(entry.severity)}</span></div>
              <p>${entry.description || ""}</p>
            </article>
          `
        )
        .join("");

  els.resultsBody.innerHTML = `
    <p class="muted">涉及疾病：${(data.diseases || []).join("、") || "-"}；合并药品数量：${(data.combined_drugs || []).length}</p>
    <div class="section-title">推荐方案</div>
    ${planHtml || '<div class="empty-state"><p>暂无方案结果</p></div>'}
    ${interactionHtml ? `<div class="section-title">交叉用药风险</div>${interactionHtml}` : ""}
  `;
}

function renderClinicalResults(diseases, drugs, comorbidityData, interactionData, contraindications) {
  updateWorkflowStep(3);

  const interactions = interactionData || { safe: true, interactions: [], duplicate_classes: [] };
  const major = (interactions.interactions || []).filter((entry) => entry.severity === "major").length;
  const majorContraindications = (contraindications || []).filter((entry) => entry.severity === "major").length;
  const duplicateCount = (interactions.duplicate_classes || []).length;
  const totalRisk = major + majorContraindications + duplicateCount;

  showResults("临床用药评估报告", totalRisk ? "需重点关注" : "建议可继续");

  if (totalRisk) {
    showRiskBanner("danger", "⚠", `发现 ${major} 项严重相互作用、${majorContraindications} 项严重禁忌、${duplicateCount} 组重复用药`);
  } else {
    showRiskBanner("safe", "✓", "当前组合未发现显著冲突，适合继续结合临床背景评估");
  }

  let html = `
    <div class="clinical-summary">
      <div class="summary-card"><span>诊断数量</span><strong>${diseases.length}</strong></div>
      <div class="summary-card"><span>当前用药</span><strong>${drugs.length}</strong></div>
      <div class="summary-card ${totalRisk ? "danger" : "safe"}"><span>风险项</span><strong>${totalRisk}</strong></div>
    </div>
    <p class="muted">疾病：${diseases.join("、") || "-"}；当前用药：${drugs.join("、") || "-"}</p>
  `;

  if (contraindications?.length) {
    html += `<div class="section-title">禁忌提示</div>`;
    html += contraindications
      .map(
        (entry) => `
          <article class="result-card danger-card">
            <h3>${entry.drug || "-"} · ${entry.condition || "-"}</h3>
            <div class="meta"><span class="chip danger">${severityLabel(entry.severity)}</span></div>
            <p>${entry.description || ""}</p>
          </article>
        `
      )
      .join("");
  }

  if (comorbidityData?.plans?.length) {
    html += `<div class="section-title">合并方案建议</div>`;
    html += comorbidityData.plans
      .map(
        (entry) => `
          <article class="result-card">
            <h3>${entry.disease || "-"} · ${entry.plan || "-"}</h3>
            <div class="meta">
              <span class="chip ${entry.line === "first" ? "line-first" : ""}">${lineLabel(entry.line)}</span>
            </div>
            <div class="drug-list">${(entry.drugs || []).map((drug) => `<span class="drug-item">${drug}</span>`).join("")}</div>
          </article>
        `
      )
      .join("");
  }

  if (!interactions.safe) {
    html += `<div class="section-title">相互作用与重复用药</div>`;
    html += (interactions.interactions || [])
      .map(
        (entry) => `
          <article class="result-card ${entry.severity === "major" ? "danger-card" : "warn-card"}">
            <h3>${entry.drug_a || "-"} ↔ ${entry.drug_b || "-"}</h3>
            <div class="meta"><span class="chip danger">${severityLabel(entry.severity)}</span></div>
            <p>${entry.description || ""}</p>
            <p class="muted"><strong>建议：</strong>${entry.recommendation || "-"}</p>
          </article>
        `
      )
      .join("");
    html += (interactions.duplicate_classes || [])
      .map(
        (entry) => `
          <article class="result-card warn-card">
            <h3>同类重复用药 · ${entry.atc_name || "-"}</h3>
            <div class="meta">${(entry.drugs || []).map((drug) => `<span class="chip danger">${drug}</span>`).join("")}</div>
          </article>
        `
      )
      .join("");
  }

  els.resultsBody.innerHTML = html;
}

function renderQAResults(data) {
  const intentMap = {
    interaction_check: "联用检查",
    recommend: "方案推荐",
    drug_info: "药品查询",
    contraindication_check: "禁忌检查",
    unknown: "通用问答",
  };

  showResults("规则问答结果", intentMap[data.intent] || data.intent || "问答");
  showRiskBanner("safe", "✦", "以下回答来自规则问答与知识图谱检索结果，适合作品演示与学习用途");

  els.resultsBody.innerHTML = `
    <article class="result-card">
      <div class="meta">
        <span class="chip">${intentMap[data.intent] || data.intent || "未知"}</span>
      </div>
      <div class="qa-answer">${(data.answer || "").replace(/\n/g, "<br>")}</div>
    </article>
  `;
}

function renderGraph(data) {
  if (!data?.nodes?.length) {
    if (network) {
      network.destroy();
      network = null;
    }
    els.graphContainer.innerHTML = `<div class="empty-state"><p>当前查询没有可视化图谱结果</p></div>`;
    return;
  }

  els.graphContainer.innerHTML = "";

  const nodes = new vis.DataSet(
    data.nodes.map((node) => ({
      ...node,
      font: {
        size: 13,
        face: "Noto Serif SC",
      },
    }))
  );

  const edges = new vis.DataSet(
    data.edges.map((edge) => ({
      ...edge,
      arrows: "to",
      font: { align: "middle", size: 10 },
      color: { color: "#9aa6b2" },
    }))
  );

  network = new vis.Network(
    els.graphContainer,
    { nodes, edges },
    {
      groups: graphGroups,
      interaction: { hover: true, tooltipDelay: 100 },
      physics: {
        stabilization: { iterations: 140 },
        barnesHut: {
          gravitationalConstant: -2800,
          springLength: 130,
        },
      },
    }
  );
}

async function withLoading(fn) {
  showLoading(true);
  try {
    await fn();
  } finally {
    showLoading(false);
  }
}

async function searchRecommend(disease, icd) {
  const params = new URLSearchParams();
  if (disease) params.set("disease", disease);
  if (icd) params.set("icd", icd);

  const [recommend, graph] = await Promise.all([
    fetchJSON(`${API}/recommend?${params.toString()}`),
    fetchJSON(`${API}/graph?${params.toString()}`),
  ]);

  renderRecommendResults(recommend);
  renderGraph(graph);
}

async function searchDrug(drugName) {
  const params = new URLSearchParams({ drug_name: drugName });
  const [drug, graph] = await Promise.all([
    fetchJSON(`${API}/drug?${params.toString()}`),
    fetchJSON(`${API}/graph?${params.toString()}`),
  ]);

  renderDrugResults(drug);
  renderGraph(graph);
}

async function searchInteraction(drugs, title) {
  const params = new URLSearchParams({ drugs: drugs.join(",") });
  const data = await fetchJSON(`${API}/interactions?${params.toString()}`);
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

  const comorbidityTask = diseases.length
    ? fetchJSON(`${API}/comorbidity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ diseases }),
      })
    : Promise.resolve(null);

  const interactionTask = drugs.length >= 2
    ? fetchJSON(`${API}/interactions?drugs=${encodeURIComponent(drugs.join(","))}`)
    : Promise.resolve({ safe: true, interactions: [], duplicate_classes: [] });

  const contraindicationTask = drugs.length && condition
    ? Promise.all(
        drugs.map((drug) =>
          fetchJSON(
            `${API}/contraindications?drug_name=${encodeURIComponent(drug)}&condition=${encodeURIComponent(condition)}`
          )
            .then((result) => result.results)
            .catch(() => [])
        )
      ).then((results) => results.flat())
    : Promise.resolve([]);

  const [comorbidityData, interactionData, contraindications] = await Promise.all([
    comorbidityTask,
    interactionTask,
    contraindicationTask,
  ]);

  renderClinicalResults(diseases, drugs, comorbidityData, interactionData, contraindications);

  const graphQuery = diseases[0]
    ? `disease=${encodeURIComponent(diseases[0])}`
    : drugs[0]
      ? `drug_name=${encodeURIComponent(drugs[0])}`
      : "";

  if (graphQuery) {
    const graph = await fetchJSON(`${API}/graph?${graphQuery}`);
    renderGraph(graph);
  }
}

function switchView(viewId) {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === viewId);
  });

  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${viewId}`);
  });

  if (viewId === "clinical") {
    updateWorkflowStep(1);
  }
}

function runScenario(key) {
  const scenario = SCENARIOS[key];
  if (!scenario) return;

  switchView(scenario.view);
  document.getElementById("workbench").scrollIntoView({ behavior: "smooth", block: "start" });

  if (scenario.view === "clinical") {
    els.clinicalDiseases.value = scenario.diseases || "";
    els.clinicalCondition.value = scenario.condition || "";
    chipStores.clinical = [...(scenario.drugs || [])];
    renderChips("clinical", els.clinicalDrugChips);
    withLoading(() =>
      runClinicalAssessment(
        (scenario.diseases || "")
          .split(/[，,]/)
          .map((item) => item.trim())
          .filter(Boolean),
        scenario.drugs || [],
        scenario.condition || ""
      )
    ).catch((error) => renderError(error.message));
  }

  if (scenario.view === "prescription") {
    chipStores.prescription = [...(scenario.drugs || [])];
    renderChips("prescription", els.prescriptionChips);
    withLoading(() => searchInteraction(scenario.drugs || [], "处方审查结果")).catch((error) => renderError(error.message));
  }

  if (scenario.view === "recommend") {
    els.diseaseInput.value = scenario.disease || "";
    withLoading(() => searchRecommend(scenario.disease || "", "")).catch((error) => renderError(error.message));
  }

  if (scenario.view === "drug") {
    els.drugInput.value = scenario.drug || "";
    withLoading(() => searchDrug(scenario.drug || "")).catch((error) => renderError(error.message));
  }

  if (scenario.view === "qa") {
    els.qaInput.value = scenario.question || "";
    withLoading(() => searchQA(scenario.question || "")).catch((error) => renderError(error.message));
  }
}

async function loadStats() {
  const stats = await fetchJSON(`${API}/stats`);
  els.statDrugs.textContent = stats.drugs ?? "-";
  els.statDiseases.textContent = stats.diseases ?? "-";
  els.statPlans.textContent = stats.plans ?? "-";
  els.statInteractions.textContent = stats.interactions ?? "-";
  els.statContraindications.textContent = stats.contraindications ?? "-";
  els.statAdverse.textContent = stats.adverse_effects ?? "-";
  els.statTreats.textContent = stats.treats ?? "-";
}

async function loadOptions() {
  const [diseases, drugs] = await Promise.all([
    fetchJSON(`${API}/diseases`),
    fetchJSON(`${API}/drugs`),
  ]);

  diseaseOptions = diseases.results || [];
  drugOptions = drugs.results || [];

  const diseaseOptionsHtml = diseaseOptions
    .map((entry) => `<option value="${entry.name}">${entry.icd || ""}</option>`)
    .join("");

  document.querySelectorAll("datalist[id^='diseaseList']").forEach((element) => {
    element.innerHTML = diseaseOptionsHtml;
  });

  const drugOptionsHtml = drugOptions
    .map((entry) => `<option value="${entry.name}">${entry.brand || ""}</option>`)
    .join("");

  document.querySelectorAll("datalist[id^='drugList']").forEach((element) => {
    element.innerHTML = drugOptionsHtml;
  });

  els.diseaseTags.innerHTML = diseaseOptions
    .slice(0, 6)
    .map((entry) => `<button type="button" class="tag" data-disease="${entry.name}">${entry.name}</button>`)
    .join("");

  els.drugTags.innerHTML = drugOptions
    .slice(0, 6)
    .map((entry) => `<button type="button" class="tag" data-drug="${entry.name}">${entry.name}</button>`)
    .join("");

  els.prescriptionTags.innerHTML = `
    <button type="button" class="tag" data-rx="缬沙坦,厄贝沙坦">同类重复用药</button>
    <button type="button" class="tag" data-rx="阿司匹林,氯吡格雷">双抗联用</button>
    <button type="button" class="tag" data-rx="氨氯地平,辛伐他汀">典型相互作用</button>
  `;

  els.qaTags.innerHTML = `
    <button type="button" class="tag" data-qa="阿司匹林和氯吡格雷能一起吃吗？">联用检查</button>
    <button type="button" class="tag" data-qa="高血压推荐什么方案？">方案推荐</button>
    <button type="button" class="tag" data-qa="二甲双胍的适应症是什么？">药品问答</button>
  `;
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });

  document.querySelectorAll(".scenario-card").forEach((card) => {
    card.addEventListener("click", () => runScenario(card.dataset.scenario));
  });

  const addClinical = setupChipInput(els.clinicalDrugInput, "clinical", els.clinicalDrugChips);
  const addPrescription = setupChipInput(els.prescriptionInput, "prescription", els.prescriptionChips);

  document.getElementById("addClinicalDrug").addEventListener("click", addClinical);
  document.getElementById("addPrescriptionDrug").addEventListener("click", addPrescription);

  document.getElementById("clinicalDemo").addEventListener("click", () => runScenario("clinical-htn-dm"));

  els.jumpWorkbench.addEventListener("click", () => {
    document.getElementById("workbench").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  els.runIntroScenario.addEventListener("click", () => runScenario("clinical-htn-dm"));

  document.getElementById("clinicalForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const diseases = els.clinicalDiseases.value
      .split(/[，,]/)
      .map((item) => item.trim())
      .filter(Boolean);
    const drugs = [...chipStores.clinical];
    const condition = els.clinicalCondition.value;

    if (!diseases.length && !drugs.length) {
      renderError("请至少输入诊断疾病或当前用药");
      return;
    }

    await withLoading(() => runClinicalAssessment(diseases, drugs, condition)).catch((error) => renderError(error.message));
  });

  document.getElementById("recommendForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const disease = els.diseaseInput.value.trim();
    const icd = els.icdInput.value.trim();
    if (!disease && !icd) {
      renderError("请输入疾病名称或 ICD 编码");
      return;
    }

    await withLoading(() => searchRecommend(disease, icd)).catch((error) => renderError(error.message));
  });

  document.getElementById("prescriptionForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const drugs = [...chipStores.prescription];
    if (drugs.length < 2) {
      renderError("处方审查至少需要 2 种药物");
      return;
    }

    await withLoading(() => searchInteraction(drugs, "处方审查结果")).catch((error) => renderError(error.message));
  });

  document.getElementById("drugForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = els.drugInput.value.trim();
    if (!name) {
      renderError("请输入药品名称");
      return;
    }

    await withLoading(() => searchDrug(name)).catch((error) => renderError(error.message));
  });

  document.getElementById("comorbidityForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const diseases = els.comorbidityInput.value
      .split(/[，,]/)
      .map((item) => item.trim())
      .filter(Boolean);

    if (!diseases.length) {
      renderError("请至少输入一种疾病");
      return;
    }

    await withLoading(() => searchComorbidity(diseases)).catch((error) => renderError(error.message));
  });

  document.getElementById("qaForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = els.qaInput.value.trim();
    if (!question) {
      renderError("请输入临床问题");
      return;
    }

    await withLoading(() => searchQA(question)).catch((error) => renderError(error.message));
  });

  els.diseaseTags.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-disease]");
    if (!button) return;
    els.diseaseInput.value = button.dataset.disease;
    await withLoading(() => searchRecommend(button.dataset.disease, "")).catch((error) => renderError(error.message));
  });

  els.drugTags.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-drug]");
    if (!button) return;
    els.drugInput.value = button.dataset.drug;
    await withLoading(() => searchDrug(button.dataset.drug)).catch((error) => renderError(error.message));
  });

  els.prescriptionTags.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-rx]");
    if (!button) return;
    chipStores.prescription = button.dataset.rx.split(",").map((item) => item.trim()).filter(Boolean);
    renderChips("prescription", els.prescriptionChips);
    await withLoading(() => searchInteraction(chipStores.prescription, "处方审查结果")).catch((error) => renderError(error.message));
  });

  els.qaTags.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-qa]");
    if (!button) return;
    els.qaInput.value = button.dataset.qa;
    await withLoading(() => searchQA(button.dataset.qa)).catch((error) => renderError(error.message));
  });

  document.getElementById("printResults").addEventListener("click", () => window.print());

  document.getElementById("clearResults").addEventListener("click", () => {
    els.resultsSection.hidden = true;
    hideRiskBanner();
    if (network) {
      network.destroy();
      network = null;
    }
    els.graphContainer.innerHTML = "";
  });
}

async function bootstrap() {
  showLoading(false);
  bindEvents();

  try {
    await fetchJSON(`${API}/health`);
    setStatus(true, "Neo4j / API 已连接");
    await Promise.all([loadStats(), loadOptions()]);
  } catch (error) {
    setStatus(false, "演示页已加载，但后端当前未连接");
  } finally {
    showLoading(false);
  }
}

bootstrap();
