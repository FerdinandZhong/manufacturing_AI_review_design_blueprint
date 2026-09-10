const pptxgen = require("pptxgenjs");

// ---- Reference standard (Cloudera manufacturing deck, slide14 / layout60 / master2) ----
const NAVY = "15154A";        // headings on slides
const NAVY_DEEP = "120046";   // title placeholder color / RESULT fill
const INK = "1B1B3A";
const MUTED = "5A5A72";
const ORANGE = "EE5A29";
const ORANGE_BAR = "FF550D";  // bottom bar (layout60)
const INDIGO = "5555F9";
const TEAL = "34D399";
const WHITE = "FFFFFF";
const LINE = "E2E2EC";
const CARD_BG = "F7F7FB";
const ICE = "CADCFC";
const GREY_CR = "888892";     // copyright grey
const RESULT_SUB = "C9C9E8";

const MOTIF = "docs/assets/corner-motif.png";     // 349x739, placed (8.33,0) 1.676x3.549
const WORDMARK = "docs/assets/cloudera-wordmark.png"; // 956x120, placed (8.26,5.21) 1.24x0.156

const FONTS = { en: "Plus Jakarta Sans", zh: "Microsoft YaHei" };

// ---------------------------------------------------------------------------
// Bilingual content
// ---------------------------------------------------------------------------
const D = {
  en: {
    s1: {
      title: "What the Vehicle NPI Blueprint Does",
      sub: "A single Cloudera application: a deterministic engineering test bench, a design-risk model, and a 5-agent gate-review workbench that turns raw program data into an auditable release decision.",
      cols: [
        { label: "ENGINEER", title: "Dashboard — Program Cockpit", items: [
          "Requirements → design → test traced end-to-end, gaps flagged automatically",
          "5-agent swarm audits coverage, test verdicts, compliance, design risk, prior-program reuse",
          "Findings + code-computed PASS / CONDITIONAL / FAIL, then human decision" ] },
        { label: "SCORE", title: "Design-Risk Model", items: [
          "Gradient-boosted model trained on historical program outcomes",
          "Every requirement scored LOW / MEDIUM / HIGH with top contributing features",
          "New program data → re-score → refreshed risk view at each gate" ] },
        { label: "REUSE", title: "Open to Any Agent Framework", items: [
          "Multimodal knowledge base (Lance) of prior-program specs, images, test reports",
          "Customer-centric API + Swagger",
          "Cloudera AI Agent Studio / Claude Code" ] },
      ],
      caption: "One governed platform — audit, score, and reuse engineering knowledge on your own program data.",
    },
    s2: {
      title: "One Governed Loop — Code Decides, Agents Explain",
      sub: "Engineers work the gate review; every recommendation traces back to a deterministic computation — the LLM only narrates.",
      stages: [
        { t: "Program Data", s: "Requirements, specs, BOM, test plans (CSV / Iceberg-ready)" },
        { t: "Test Bench +\nTraceability", s: "Deterministic margins, coverage %, gap list" },
        { t: "Design-Risk\nModel", s: "GBM scores each requirement LOW/MED/HIGH" },
        { t: "5-Agent\nGate Review", s: "Coverage · verdict · compliance · risk · reuse" },
        { t: "Human\nDecision", s: "Approve / conditions / reject, logged with evidence" },
      ],
      callout: "Determinism is sacred: the same program data always produces the same recommendation — the LLM affects prose only, never the decision.",
    },
    s3: {
      title: "Integration with Cloudera AI Agent Studio",
      sub: "Drives the gate review: any agent framework calls the same tool set over the platform's API — no direct database access.",
      leftBox: "Cloudera AI\nAgent Studio /\nClaude Code",
      leftCap: "calls agent tools, no direct data access",
      midTitle: "Agent Tools",
      tools: [
        "get_program / get_traceability",
        "get_test_results",
        "get_design_risk / get_model_explanation",
        "kb_search / get_asset",
        "ontology_describe" ],
      rightTitle: "Customer-Centric API",
      rightItems: [
        "FastAPI + Swagger at /api/docs",
        "SSE stream for live gate review",
        "The single source of truth" ],
      caption: "Agent Studio drives the platform through tools — the API is the single source of truth.",
    },
    s4: {
      title: "How It Fits Cloudera AI: Deploy → Govern → Open",
      sub: "A single CAI application on CML — fork onto real PLM/MES/ERP sources by swapping the source layer.",
      rows: [
        { label: "DEPLOY", sub: "one CAI app on CML", lines: [
          "Install → generate data → prepare (test bench + model + KB) → launch job chain serves the React UI + FastAPI backend",
          "CAII serves the LLM narration — swap to vLLM or Ollama by config" ] },
        { label: "GOVERN", sub: "data and model", lines: [
          "Read-only source layer (CSV now, Iceberg/SDX-ready) — one copy, no egress",
          "Seeded, versioned risk model with deterministic scoring — retrain on new program outcomes" ] },
        { label: "OPEN", sub: "to any agent", lines: [
          "Agent tool registry exposes the platform to Cloudera AI Agent Studio and any MCP-compatible client",
          "Customer-centric API + Swagger at /api/docs — the single source of truth" ] },
      ],
      cap1: "Fork it: point the source layer at your PLM/MES schema and prod model dir — no API or frontend change, same app end-to-end.",
      cap2: "Engineers, program managers, and external agents all work the same governed data and model.",
    },
    s5: {
      title: "Autonomous Gate Review on Your Data",
      sub: "Example: from a program at its release gate to an auditable PASS / CONDITIONAL / FAIL decision. All on your data, no egress.",
      rail: "GATE REVIEW FLOW",
      steps: [
        { num: "01 · INGEST", verb: "Program at gate", accent: NAVY, border: NAVY,
          desc: "Showcase battery-pack program PACK-ATLAS-01 enters its release gate and starts the 5-agent review" },
        { num: "02 · ENGINEERING AGENTS", verb: "Coverage & test verdicts", accent: ORANGE, border: ORANGE,
          desc: "Traceability matrix computed — one requirement has no test plan; the thermal test lands MARGINAL at a +3% margin" },
        { num: "03 · RISK & COMPLIANCE", verb: "Score & standards", accent: INDIGO, border: ORANGE,
          desc: "Design-risk model flags the thermal requirement HIGH; required standards UN 38.3 · GB 38031 · IEC 62660 checked for coverage" },
      ],
      k: { num: "04 · KNOWLEDGE-REUSE", verb: "Verify with history",
        b1: "KB retrieves PACK-ORION-00 thermal design image + test report (a past FAIL)",
        b2: "Prior failure corroborates the HIGH risk + MARGINAL test — concern confirmed" },
      result: { label: "RESULT", verb: "Recommendation + evidence",
        strong: "CONDITIONAL. ",
        rest: "Code-computed by traceability.decide(); every finding is compiled into a chain of evidence, then a human adjudicates." },
      cap1: "A deterministic core plus a connected knowledge layer turns a raw program into a ",
      cap2: "trusted, auditable gate decision, on your data.",
    },
  },
  zh: {
    s1: {
      title: "车辆 NPI 蓝图能做什么",
      sub: "一个 Cloudera 应用：确定性工程测试台、设计风险模型，以及一个 5 智能体的关口评审工作台，把原始项目数据转化为可审计的放行决策。",
      cols: [
        { label: "工程", title: "仪表盘 — 项目驾驶舱", items: [
          "需求 → 设计 → 测试端到端追溯，缺口自动标记",
          "5 智能体协同审查覆盖度、测试结论、合规、设计风险与历史项目复用",
          "汇总发现 + 代码计算的 PASS / CONDITIONAL / FAIL，再由人工决策" ] },
        { label: "评分", title: "设计风险模型", items: [
          "基于历史项目结果训练的梯度提升模型",
          "每条需求评为 LOW / MEDIUM / HIGH，并给出主要贡献特征",
          "新项目数据 → 重新评分 → 每个关口刷新风险视图" ] },
        { label: "复用", title: "面向任意智能体框架开放", items: [
          "多模态知识库（Lance）：历史项目的规格、图像与测试报告",
          "以客户为中心的 API + Swagger",
          "Cloudera AI Agent Studio / Claude Code" ] },
      ],
      caption: "一个受治理的平台 —— 在你自己的项目数据上审查、评分并复用工程知识。",
    },
    s2: {
      title: "一个受治理的闭环 —— 代码做决策，智能体做解读",
      sub: "工程师执行关口评审；每条建议都可追溯到确定性计算 —— 大模型只负责叙述。",
      stages: [
        { t: "项目数据", s: "需求、规格、BOM、测试计划（CSV / 兼容 Iceberg）" },
        { t: "测试台 +\n追溯", s: "确定性裕度、覆盖率、缺口清单" },
        { t: "设计风险\n模型", s: "GBM 为每条需求评分 LOW/MED/HIGH" },
        { t: "5 智能体\n关口评审", s: "覆盖 · 结论 · 合规 · 风险 · 复用" },
        { t: "人工\n决策", s: "批准 / 有条件 / 驳回，并记录证据" },
      ],
      callout: "确定性至上：相同的项目数据始终产出相同的建议 —— 大模型只影响文字，绝不影响决策。",
    },
    s3: {
      title: "与 Cloudera AI Agent Studio 集成",
      sub: "驱动关口评审：任意智能体框架都通过平台 API 调用同一套工具 —— 不直接访问数据库。",
      leftBox: "Cloudera AI\nAgent Studio /\nClaude Code",
      leftCap: "调用智能体工具，不直接访问数据",
      midTitle: "智能体工具",
      tools: [
        "get_program / get_traceability",
        "get_test_results",
        "get_design_risk / get_model_explanation",
        "kb_search / get_asset",
        "ontology_describe" ],
      rightTitle: "以客户为中心的 API",
      rightItems: [
        "FastAPI + Swagger（/api/docs）",
        "SSE 实时推送关口评审",
        "唯一可信数据源" ],
      caption: "Agent Studio 通过工具驱动平台 —— API 即唯一可信数据源。",
    },
    s4: {
      title: "如何融入 Cloudera AI：部署 → 治理 → 开放",
      sub: "CML 上的单一 CAI 应用 —— 替换数据源层即可对接真实 PLM/MES/ERP。",
      rows: [
        { label: "部署", sub: "CML 上的单一应用", lines: [
          "安装 → 生成数据 → 准备（测试台 + 模型 + 知识库）→ 启动作业链，提供 React 前端 + FastAPI 后端",
          "CAII 提供大模型叙述 —— 通过配置切换到 vLLM 或 Ollama" ] },
        { label: "治理", sub: "数据与模型", lines: [
          "只读数据源层（当前 CSV，兼容 Iceberg/SDX）—— 单副本、不出域",
          "带种子、版本化的风险模型，确定性评分 —— 可基于新项目结果重训" ] },
        { label: "开放", sub: "面向任意智能体", lines: [
          "智能体工具注册表将平台开放给 Cloudera AI Agent Studio 及任意兼容 MCP 的客户端",
          "以客户为中心的 API + Swagger（/api/docs）—— 唯一可信数据源" ] },
      ],
      cap1: "自行分叉：把数据源层指向你的 PLM/MES 架构与生产模型目录 —— 无需改动 API 或前端，端到端同一应用。",
      cap2: "工程师、项目经理与外部智能体，共用同一套受治理的数据与模型。",
    },
    s5: {
      title: "在你的数据上自主完成关口评审",
      sub: "示例：从处于放行关口的项目，到可审计的 PASS / CONDITIONAL / FAIL 决策。全部在你的数据上，不出域。",
      rail: "关口评审流程",
      steps: [
        { num: "01 · 接入", verb: "项目进入关口", accent: NAVY, border: NAVY,
          desc: "示范电池包项目 PACK-ATLAS-01 进入放行关口，启动 5 智能体评审" },
        { num: "02 · 工程智能体", verb: "覆盖与测试结论", accent: ORANGE, border: ORANGE,
          desc: "计算追溯矩阵 —— 有一条需求无测试计划；热测试以 +3% 裕度落在 MARGINAL" },
        { num: "03 · 风险与合规", verb: "评分与标准", accent: INDIGO, border: ORANGE,
          desc: "设计风险模型将热需求标为 HIGH；核对必备标准 UN 38.3 · GB 38031 · IEC 62660 的覆盖" },
      ],
      k: { num: "04 · 知识复用", verb: "结合历史验证",
        b1: "知识库检索到 PACK-ORION-00 的热设计图 + 测试报告（历史 FAIL）",
        b2: "历史失败印证了 HIGH 风险 + MARGINAL 测试 —— 隐患得到确认" },
      result: { label: "结果", verb: "建议 + 证据",
        strong: "CONDITIONAL。",
        rest: "由 traceability.decide() 代码计算；每条发现都汇编成证据链，再由人工裁定。" },
      cap1: "确定性内核加上互联的知识层，把一个原始项目转化为 ",
      cap2: "可信、可审计的关口决策，就在你的数据上。",
    },
  },
};

// ---------------------------------------------------------------------------
// Builder
// ---------------------------------------------------------------------------
function buildDeck(lang, outFile) {
  const HEAD = FONTS[lang], BODY = FONTS[lang];
  const t = D[lang];
  const mkShadow = () => ({ type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.12 });

  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "Cloudera";
  pres.title = t.s1.title;

  // Reference chrome: corner motif (top-right), orange bottom bar,
  // copyright (bottom-left), CLOUDERA wordmark (bottom-right)
  const chrome = (slide) => {
    slide.addImage({ path: MOTIF, x: 8.33, y: 0, w: 1.676, h: 3.549 });
    slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.545, w: 10, h: 0.08, fill: { color: ORANGE_BAR }, line: { type: "none" } });
    slide.addText("©2026 Cloudera, Inc. All Rights Reserved.", {
      x: 0.416, y: 5.181, w: 5.05, h: 0.315, fontSize: 6, color: GREY_CR, fontFace: BODY, margin: 0, valign: "middle" });
    slide.addImage({ path: WORDMARK, x: 8.26, y: 5.21, w: 1.24, h: 0.156 });
  };

  // Reference title block: (0.583,0.311) bold; subtitle (0.583,0.803) 11pt
  // 22pt + w 8.4 keeps the longest titles on one line, clear of the motif
  const titleBlock = (slide, title, sub, subColor) => {
    slide.addText(title, { x: 0.583, y: 0.311, w: 8.4, h: 0.547, fontSize: 22, bold: true, color: NAVY_DEEP, fontFace: HEAD, margin: 0, valign: "middle" });
    slide.addText(sub, { x: 0.583, y: 0.803, w: 7.6, h: 0.4, fontSize: 11, color: subColor || MUTED, fontFace: BODY, margin: 0, valign: "top" });
  };

  // ---- Slide 1 ----
  {
    const slide = pres.addSlide();
    slide.background = { color: WHITE };
    titleBlock(slide, t.s1.title, t.s1.sub);
    const colW = 2.7, gap = 0.32, startX = 0.583, y0 = 1.55, cardH = 3.1;
    t.s1.cols.forEach((c, i) => {
      const x = startX + i * (colW + gap);
      slide.addShape(pres.shapes.RECTANGLE, { x, y: y0, w: colW, h: cardH, fill: { color: CARD_BG }, line: { color: LINE, width: 1 }, shadow: mkShadow() });
      slide.addShape(pres.shapes.RECTANGLE, { x, y: y0, w: colW, h: 0.08, fill: { color: ORANGE }, line: { type: "none" } });
      slide.addText(c.label, { x: x + 0.22, y: y0 + 0.2, w: colW - 0.44, h: 0.32, fontSize: 13, bold: true, color: ORANGE, fontFace: HEAD, charSpacing: 1, margin: 0 });
      slide.addText(c.title, { x: x + 0.22, y: y0 + 0.54, w: colW - 0.44, h: 0.42, fontSize: 12.5, bold: true, color: NAVY, fontFace: HEAD, margin: 0 });
      slide.addText(
        c.items.map((tx, idx) => ({ text: tx, options: { bullet: { code: "2022" }, breakLine: idx < c.items.length - 1, color: INK } })),
        { x: x + 0.22, y: y0 + 1.02, w: colW - 0.44, h: cardH - 1.24, fontSize: 10, fontFace: BODY, valign: "top", paraSpaceAfter: 8, margin: 0 });
    });
    slide.addText(t.s1.caption, { x: 0.583, y: 4.78, w: 8.8, h: 0.3, fontSize: 11.5, bold: true, italic: true, color: NAVY, fontFace: BODY, margin: 0 });
    chrome(slide);
  }

  // ---- Slide 2 ----
  {
    const slide = pres.addSlide();
    slide.background = { color: WHITE };
    titleBlock(slide, t.s2.title, t.s2.sub);
    const boxY = 2.1, boxH = 0.88, n = t.s2.stages.length, gap = 0.28;
    const boxW = (8.4 - gap * (n - 1)) / n;   // pipeline ends at 8.98, clear of motif
    let x = 0.583;
    t.s2.stages.forEach((st, i) => {
      slide.addShape(pres.shapes.RECTANGLE, { x, y: boxY, w: boxW, h: boxH, fill: { color: i === n - 1 ? NAVY : CARD_BG }, line: { color: i === n - 1 ? NAVY : LINE, width: 1 }, shadow: mkShadow() });
      slide.addText(st.t, { x: x + 0.06, y: boxY + 0.06, w: boxW - 0.12, h: boxH - 0.12, fontSize: 10.5, bold: true, align: "center", valign: "middle", color: i === n - 1 ? WHITE : NAVY, fontFace: HEAD, margin: 0 });
      if (i < n - 1) slide.addShape(pres.shapes.LINE, { x: x + boxW, y: boxY + boxH / 2, w: gap, h: 0, line: { color: MUTED, width: 1.5, endArrowType: "triangle" } });
      x += boxW + gap;
    });
    x = 0.583;
    t.s2.stages.forEach((st) => {
      slide.addText(st.s, { x, y: boxY + boxH + 0.16, w: boxW, h: 1.0, fontSize: 9.5, color: MUTED, fontFace: BODY, align: "center", valign: "top", margin: 0 });
      x += boxW + gap;
    });
    slide.addShape(pres.shapes.RECTANGLE, { x: 0.583, y: 4.5, w: 8.4, h: 0.4, fill: { color: "FCEFE9" }, line: { color: ORANGE, width: 1 } });
    slide.addText(t.s2.callout, { x: 0.783, y: 4.5, w: 8.0, h: 0.4, fontSize: 10.5, italic: true, color: NAVY, fontFace: BODY, valign: "middle", margin: 0 });
    chrome(slide);
  }

  // ---- Slide 3 ----
  {
    const slide = pres.addSlide();
    slide.background = { color: WHITE };
    titleBlock(slide, t.s3.title, t.s3.sub);
    const leftX = 0.583, leftW = 2.4, leftY = 1.7, leftH = 2.95, arrowW = 0.45;
    slide.addShape(pres.shapes.RECTANGLE, { x: leftX, y: leftY, w: leftW, h: leftH, fill: { color: NAVY }, line: { type: "none" }, shadow: mkShadow() });
    slide.addText(t.s3.leftBox, { x: leftX + 0.15, y: leftY + 0.25, w: leftW - 0.3, h: 0.9, fontSize: 14, bold: true, color: WHITE, fontFace: HEAD, align: "center", valign: "middle", margin: 0 });
    slide.addText(t.s3.leftCap, { x: leftX + 0.15, y: leftY + leftH - 0.55, w: leftW - 0.3, h: 0.4, fontSize: 9.5, color: ICE, fontFace: BODY, align: "center", margin: 0 });
    slide.addShape(pres.shapes.LINE, { x: leftX + leftW, y: leftY + leftH / 2, w: arrowW, h: 0, line: { color: MUTED, width: 1.5, endArrowType: "triangle" } });
    const midX = leftX + leftW + arrowW, midW = 2.9;
    slide.addShape(pres.shapes.RECTANGLE, { x: midX, y: leftY, w: midW, h: leftH, fill: { color: CARD_BG }, line: { color: LINE, width: 1 }, shadow: mkShadow() });
    slide.addText(t.s3.midTitle, { x: midX + 0.2, y: leftY + 0.2, w: midW - 0.4, h: 0.35, fontSize: 13, bold: true, color: NAVY, fontFace: HEAD, margin: 0 });
    slide.addText(
      t.s3.tools.map((tx, i) => ({ text: tx, options: { bullet: { code: "2022" }, breakLine: i < t.s3.tools.length - 1 } })),
      { x: midX + 0.2, y: leftY + 0.62, w: midW - 0.4, h: leftH - 0.82, fontSize: 10.5, color: INK, fontFace: BODY, valign: "top", paraSpaceAfter: 6, margin: 0 });
    slide.addShape(pres.shapes.LINE, { x: midX + midW, y: leftY + leftH / 2, w: arrowW, h: 0, line: { color: MUTED, width: 1.5, endArrowType: "triangle" } });
    const rightX = midX + midW + arrowW, rightW = 2.5;   // ends at 9.28; text stays clear of motif
    slide.addShape(pres.shapes.RECTANGLE, { x: rightX, y: leftY, w: rightW, h: leftH, fill: { color: WHITE }, line: { color: ORANGE, width: 1.5 }, shadow: mkShadow() });
    slide.addText(t.s3.rightTitle, { x: rightX + 0.15, y: leftY + 0.2, w: rightW - 0.3, h: 0.6, fontSize: 13, bold: true, color: ORANGE, fontFace: HEAD, margin: 0 });
    slide.addText(
      t.s3.rightItems.map((tx, i) => ({ text: tx, options: { bullet: { code: "2022" }, breakLine: i < t.s3.rightItems.length - 1 } })),
      { x: rightX + 0.15, y: leftY + 0.85, w: rightW - 0.3, h: leftH - 1.05, fontSize: 10.5, color: INK, fontFace: BODY, valign: "top", paraSpaceAfter: 6, margin: 0 });
    slide.addText(t.s3.caption, { x: 0.583, y: 4.78, w: 8.8, h: 0.3, fontSize: 11.5, bold: true, italic: true, color: NAVY, fontFace: BODY, margin: 0 });
    chrome(slide);
  }

  // ---- Slide 4 ----
  {
    const slide = pres.addSlide();
    slide.background = { color: WHITE };
    titleBlock(slide, t.s4.title, t.s4.sub);
    const rowY0 = 1.45, rowH = 0.82, rowGap = 0.1;
    t.s4.rows.forEach((r, i) => {
      const y = rowY0 + i * (rowH + rowGap);
      slide.addShape(pres.shapes.RECTANGLE, { x: 0.583, y, w: 1.55, h: rowH, fill: { color: NAVY }, line: { type: "none" } });
      slide.addText(r.label, { x: 0.583, y, w: 1.55, h: 0.5, fontSize: 13, bold: true, color: WHITE, fontFace: HEAD, align: "center", valign: "middle", margin: 0 });
      slide.addText(r.sub, { x: 0.583, y: y + 0.5, w: 1.55, h: 0.4, fontSize: 9, color: ICE, fontFace: BODY, align: "center", valign: "top", margin: 0 });
      slide.addShape(pres.shapes.RECTANGLE, { x: 2.233, y, w: 6.9, h: rowH, fill: { color: CARD_BG }, line: { color: LINE, width: 1 } });
      slide.addText(
        r.lines.map((tx, idx) => ({ text: tx, options: { bullet: { code: "2022" }, breakLine: idx < r.lines.length - 1 } })),
        { x: 2.433, y: y + 0.08, w: 6.3, h: rowH - 0.16, fontSize: 10, color: INK, fontFace: BODY, valign: "middle", paraSpaceAfter: 4, margin: 0 });
    });
    const capY = rowY0 + 3 * (rowH + rowGap) + 0.08;
    slide.addText(t.s4.cap1, { x: 0.583, y: capY, w: 8.8, h: 0.3, fontSize: 10, italic: true, color: MUTED, fontFace: BODY, margin: 0 });
    slide.addText(t.s4.cap2, { x: 0.583, y: capY + 0.32, w: 8.8, h: 0.3, fontSize: 11.5, bold: true, color: NAVY, fontFace: BODY, margin: 0 });
    chrome(slide);
  }

  // ---- Slide 5 (exact geometry of reference slide 14) ----
  {
    const slide = pres.addSlide();
    slide.background = { color: WHITE };
    titleBlock(slide, t.s5.title, t.s5.sub, INDIGO);

    // Rail: rotated label at (-1.05,2.734) 2.515x0.328 8pt; orange arrow down
    slide.addText(t.s5.rail, {
      x: -1.05, y: 2.734, w: 2.515, h: 0.328, fontSize: 8, bold: true, color: MUTED,
      fontFace: BODY, align: "center", charSpacing: 1, rotate: 270, margin: 0, valign: "middle" });
    slide.addShape(pres.shapes.LINE, {
      x: 0.42, y: 1.6, w: 0, h: 2.75,
      line: { color: ORANGE, width: 1.5, endArrowType: "triangle" } });

    // Rows — reference slide14 geometry: label (0.817, w 2.242), desc (3.357, w 5.906)
    const rowX = 0.817, labelW = 2.242, descX = 3.357, descW = 5.906;
    const rowW = descX + descW - rowX;         // 8.446
    const divX = 3.26;                          // divider just left of desc column
    const ys = [1.334, 1.947, 2.559];           // rows 1-3, h 0.536
    const rH = 0.536;

    t.s5.steps.forEach((s, i) => {
      const y = ys[i];
      slide.addShape(pres.shapes.RECTANGLE, { x: rowX, y, w: rowW, h: rH, fill: { color: WHITE }, line: { color: s.border, width: 1.25 } });
      slide.addText(s.num, { x: rowX + 0.14, y: y + 0.05, w: labelW - 0.24, h: 0.2, fontSize: 8, bold: true, color: s.accent, fontFace: HEAD, charSpacing: 0.5, margin: 0 });
      slide.addText(s.verb, { x: rowX + 0.14, y: y + 0.24, w: labelW - 0.24, h: 0.26, fontSize: 11, bold: true, color: NAVY, fontFace: HEAD, margin: 0 });
      slide.addShape(pres.shapes.LINE, { x: divX, y: y + 0.09, w: 0, h: rH - 0.18, line: { color: LINE, width: 1 } });
      // row 1 sits beside the motif's left blob column (starts x~8.34) — keep its text short of it
      slide.addText(s.desc, { x: descX, y, w: i === 0 ? 4.9 : 5.45, h: rH, fontSize: 9.5, color: MUTED, fontFace: BODY, valign: "middle", margin: 0 });
    });

    // Row 04 — knowledge-reuse, h 0.678, two colored-dot bullets
    {
      const y = 3.171, h = 0.678;
      slide.addShape(pres.shapes.RECTANGLE, { x: rowX, y, w: rowW, h, fill: { color: WHITE }, line: { color: ORANGE, width: 1.25 } });
      slide.addText(t.s5.k.num, { x: rowX + 0.14, y: y + 0.09, w: labelW - 0.24, h: 0.2, fontSize: 8, bold: true, color: ORANGE, fontFace: HEAD, charSpacing: 0.5, margin: 0 });
      slide.addText(t.s5.k.verb, { x: rowX + 0.14, y: y + 0.28, w: labelW - 0.24, h: 0.26, fontSize: 11, bold: true, color: NAVY, fontFace: HEAD, margin: 0 });
      slide.addShape(pres.shapes.LINE, { x: divX, y: y + 0.1, w: 0, h: h - 0.2, line: { color: LINE, width: 1 } });
      const bx = descX + 0.04, btx = bx + 0.18, btw = descW - 0.4;
      slide.addShape(pres.shapes.OVAL, { x: bx, y: y + 0.185, w: 0.08, h: 0.08, fill: { color: ORANGE }, line: { type: "none" } });
      slide.addText(t.s5.k.b1, { x: btx, y: y + 0.08, w: btw, h: 0.26, fontSize: 9.5, color: MUTED, fontFace: BODY, valign: "middle", margin: 0 });
      slide.addShape(pres.shapes.OVAL, { x: bx, y: y + 0.455, w: 0.08, h: 0.08, fill: { color: TEAL }, line: { type: "none" } });
      slide.addText(t.s5.k.b2, { x: btx, y: y + 0.35, w: btw, h: 0.26, fontSize: 9.5, color: MUTED, fontFace: BODY, valign: "middle", margin: 0 });
    }

    // RESULT row — dark navy fill
    {
      const y = 3.948, h = 0.536;
      slide.addShape(pres.shapes.RECTANGLE, { x: rowX, y, w: rowW, h, fill: { color: NAVY_DEEP }, line: { type: "none" } });
      slide.addText(t.s5.result.label, { x: rowX + 0.14, y: y + 0.06, w: labelW - 0.24, h: 0.2, fontSize: 8, bold: true, color: ORANGE, fontFace: HEAD, charSpacing: 0.5, margin: 0 });
      slide.addText(t.s5.result.verb, { x: rowX + 0.14, y: y + 0.25, w: labelW - 0.24, h: 0.26, fontSize: 11, bold: true, color: WHITE, fontFace: HEAD, margin: 0 });
      slide.addShape(pres.shapes.LINE, { x: divX, y: y + 0.09, w: 0, h: h - 0.18, line: { color: "3A3A66", width: 1 } });
      slide.addText(
        [ { text: t.s5.result.strong, options: { bold: true, color: WHITE } },
          { text: t.s5.result.rest, options: { color: RESULT_SUB } } ],
        { x: descX, y, w: descW - 0.15, h, fontSize: 9.5, fontFace: BODY, valign: "middle", margin: 0 });
    }

    // Takeaway — reference: full-width centered at y 4.579, 11pt
    slide.addText(
      [ { text: t.s5.cap1, options: { color: NAVY, bold: true } },
        { text: t.s5.cap2, options: { color: ORANGE, bold: true } } ],
      { x: 0, y: 4.579, w: 10, h: 0.437, fontSize: 11, fontFace: BODY, align: "center", valign: "middle", margin: 0 });
    chrome(slide);
  }

  return pres.writeFile({ fileName: outFile });
}

buildDeck("en", "docs/npi-overview.pptx")
  .then(() => buildDeck("zh", "docs/npi-overview-zh.pptx"))
  .then(() => console.log("done: EN + ZH"));
