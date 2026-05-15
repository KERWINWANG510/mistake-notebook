<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NCollapse,
  NCollapseItem,
  NDivider,
  NEmpty,
  NFormItem,
  NGrid,
  NGi,
  NInputNumber,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NText,
  useMessage,
} from "naive-ui";
import FormattedAnalysis from "../components/FormattedAnalysis.vue";
import { formatAnalysisHtml, formatStemDisplayHtml } from "../utils/analysisFormat";
import type {
  GradeWithSubjects,
  MockPaperGenerateResult,
  MockPaperItemOut,
  MockPaperQuestionTypeItem,
  MistakeStatsTagRow,
} from "../api/client";
import {
  fetchGradeCatalog,
  fetchMockPaperQuestionTypes,
  fetchMistakeStatsTags,
  generateMockPaperStream,
} from "../api/client";

const message = useMessage();

const catalogLoading = ref(true);
const catalog = ref<GradeWithSubjects[]>([]);

const gradeId = ref<string | null>(null);
const subjectId = ref<string | null>(null);

const typesLoading = ref(false);
const questionTypes = ref<MockPaperQuestionTypeItem[]>([]);
const selectedTypeCodes = ref<string[]>([]);

const tagsLoading = ref(false);
const tagOptions = ref<{ label: string; value: string }[]>([]);
const selectedTags = ref<string[]>([]);

const totalScore = ref<number | null>(100);
const countsDraft = ref<Record<string, number | null>>({});

const generating = ref(false);
const exportingPdf = ref(false);
const paper = ref<MockPaperGenerateResult | null>(null);
/** 流式生成时右侧展示的原始文本（JSON 片段） */
const streamText = ref("");
const streamPhase = ref("");
const includeAnswersWhenPrint = ref(true);
const useAnswerSheet = ref(false);
const pdfRoot = ref<HTMLElement | null>(null);
/** 流式 JSON 预览区：用于自动滚到底 */
const streamPreRef = ref<HTMLElement | null>(null);
/** 中止出题请求 */
const generateAbort = ref<AbortController | null>(null);

const gradeOptions = computed(() =>
  catalog.value.map((g) => ({
    label: g.name,
    value: g.id,
  })),
);

const subjectOptions = computed(() => {
  const g = catalog.value.find((x) => x.id === gradeId.value);
  if (!g) return [];
  return g.subjects.map((s) => ({ label: s.name, value: s.id }));
});

const typesForCountInputs = computed(() => {
  if (selectedTypeCodes.value.length) {
    return selectedTypeCodes.value.filter((c) => questionTypes.value.some((t) => t.code === c));
  }
  return questionTypes.value.map((t) => t.code);
});

const scoreMismatch = computed(() => {
  if (!paper.value) return false;
  return paper.value.actual_total_score !== paper.value.requested_total_score;
});

const flatPaperItems = computed((): MockPaperItemOut[] => {
  if (!paper.value) return [];
  const out: MockPaperItemOut[] = [];
  for (const sec of paper.value.sections) {
    for (const it of sec.items) out.push(it);
  }
  return out;
});

function isSheetChoiceType(typeCode: string): boolean {
  return typeCode === "single_choice" || typeCode === "multiple_choice";
}

function isSheetTrueFalse(typeCode: string): boolean {
  return typeCode === "true_false";
}

function subjectiveAnswerLineCount(it: MockPaperItemOut): number {
  const base = 4;
  const extra = Math.min(14, Math.floor(it.score / 4));
  return Math.min(18, base + extra);
}

function ruledLinesForItem(it: MockPaperItemOut, ctx?: MockPaperGenerateResult | null): number {
  const p = ctx ?? paper.value;
  if (!p || p.use_answer_sheet) return 0;
  if (isSheetChoiceType(it.type_code) || isSheetTrueFalse(it.type_code)) return 0;
  return subjectiveAnswerLineCount(it);
}

async function loadCatalog() {
  catalogLoading.value = true;
  try {
    catalog.value = await fetchGradeCatalog();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    catalogLoading.value = false;
  }
}

async function loadQuestionTypes() {
  if (!gradeId.value || !subjectId.value) {
    questionTypes.value = [];
    selectedTypeCodes.value = [];
    countsDraft.value = {};
    return;
  }
  typesLoading.value = true;
  try {
    questionTypes.value = await fetchMockPaperQuestionTypes(gradeId.value, subjectId.value);
    selectedTypeCodes.value = [];
    const next: Record<string, number | null> = {};
    for (const t of questionTypes.value) next[t.code] = null;
    countsDraft.value = next;
  } catch (e) {
    message.error((e as Error).message);
    questionTypes.value = [];
  } finally {
    typesLoading.value = false;
  }
}

async function loadTags() {
  if (!gradeId.value || !subjectId.value) {
    tagOptions.value = [];
    selectedTags.value = [];
    return;
  }
  tagsLoading.value = true;
  try {
    const rows: MistakeStatsTagRow[] = await fetchMistakeStatsTags({
      grade_level_id: gradeId.value,
      subject_id: subjectId.value,
    });
    tagOptions.value = rows.map((r) => ({ label: `${r.tag}（${r.mistake_count}）`, value: r.tag }));
  } catch {
    tagOptions.value = [];
  } finally {
    tagsLoading.value = false;
  }
}

onMounted(() => {
  void loadCatalog();
});

watch(gradeId, () => {
  const g = catalog.value.find((x) => x.id === gradeId.value);
  const ids = g?.subjects.map((s) => s.id) ?? [];
  if (!subjectId.value || !ids.includes(subjectId.value)) {
    subjectId.value = ids[0] ?? null;
  }
});

watch([gradeId, subjectId], () => {
  void loadQuestionTypes();
  void loadTags();
  selectedTags.value = [];
  paper.value = null;
});

watch(selectedTypeCodes, (codes) => {
  const next = { ...countsDraft.value };
  for (const k of Object.keys(next)) {
    if (codes.length && !codes.includes(k)) {
      next[k] = null;
    }
  }
  countsDraft.value = next;
});

function scrollStreamToBottom() {
  const el = streamPreRef.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

watch(streamText, async () => {
  await nextTick();
  scrollStreamToBottom();
}, { flush: "post" });

watch(streamPhase, async () => {
  await nextTick();
  scrollStreamToBottom();
}, { flush: "post" });

const canGenerate = computed(() => !!gradeId.value && !!subjectId.value && !generating.value);

function onCancelGenerate() {
  generateAbort.value?.abort();
}

async function onGenerate() {
  if (!gradeId.value || !subjectId.value) return;
  generating.value = true;
  paper.value = null;
  streamText.value = "";
  streamPhase.value = "";
  const ac = new AbortController();
  generateAbort.value = ac;
  try {
    const counts_by_type: Record<string, number> = {};
    for (const code of typesForCountInputs.value) {
      const v = countsDraft.value[code];
      if (typeof v === "number" && v >= 1 && v <= 20) counts_by_type[code] = v;
    }
    const body = {
      grade_level_id: gradeId.value,
      subject_id: subjectId.value,
      knowledge_tags: selectedTags.value.length ? selectedTags.value : undefined,
      question_type_codes: selectedTypeCodes.value.length ? selectedTypeCodes.value : undefined,
      counts_by_type: Object.keys(counts_by_type).length ? counts_by_type : undefined,
      total_score: totalScore.value ?? undefined,
      use_answer_sheet: useAnswerSheet.value,
    };
    const result = await generateMockPaperStream(
      body,
      (ev) => {
        if (ev.type === "phase") {
          streamPhase.value = ev.label;
        } else if (ev.type === "delta") {
          streamText.value += ev.text;
        }
      },
      ac.signal,
    );
    paper.value = result;
    streamText.value = "";
    streamPhase.value = "";
    message.success("试卷已生成，可在右侧预览、打印或导出 PDF");
    await nextTick();
  } catch (e) {
    const msg = (e as Error).message || String(e);
    if (msg === "已取消生成") {
      message.info("已取消生成");
    } else {
      message.error(msg);
    }
  } finally {
    generateAbort.value = null;
    generating.value = false;
  }
}

function pdfFilename() {
  const raw = paper.value?.title?.trim() || "模拟练习卷";
  const safe = raw.replace(/[\\/:*?"<>|]/g, "_").slice(0, 48);
  return `${safe}.pdf`;
}

function questionLabel(it: { number: number; minor_index?: number | null }) {
  if (it.minor_index != null) return `${it.number}.（${it.minor_index}）`;
  return `${it.number}.`;
}

const PDF_HOST_STYLE = `
  .mp-pdf-host h1 { font-size: 20px; font-weight: 700; text-align: center; margin: 0 0 8px; letter-spacing: -0.02em; }
  .mp-pdf-host .mp-meta { text-align: center; font-size: 13px; color: #64748b; margin: 0 0 12px; }
  .mp-pdf-host .mp-student { display: flex; flex-wrap: wrap; gap: 12px 28px; justify-content: center; font-size: 14px; margin: 0 0 16px; color: #0f172a; }
  .mp-pdf-host .mp-student span { white-space: nowrap; }
  .mp-pdf-host .mp-student .mp-line { display: inline-block; min-width: 7em; border-bottom: 1px solid #334155; vertical-align: bottom; margin: 0 4px; height: 1.2em; }
  .mp-pdf-host .mp-ins { font-size: 13px; color: #334155; white-space: pre-wrap; margin: 0 0 18px; padding: 10px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }
  .mp-pdf-host .mp-sec { margin-bottom: 22px; }
  .mp-pdf-host .mp-sechead { font-size: 15px; font-weight: 700; margin: 0 0 12px; color: #0f172a; }
  .mp-pdf-host .mp-q { margin-bottom: 16px; page-break-inside: auto; }
  .mp-pdf-host .mp-qhead { font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 6px; }
  .mp-pdf-host .mp-qbody { padding: 12px 14px; border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; font-size: 14px; }
  .mp-pdf-host h2.mp-ans-title { font-size: 18px; font-weight: 700; margin: 0 0 16px; text-align: center; }
  .mp-pdf-host .mp-ans { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 12px; font-size: 14px; page-break-inside: auto; }
  .mp-pdf-host .mp-ansno { flex-shrink: 0; font-weight: 700; color: #475569; }
  .mp-pdf-host .mp-anstxt { flex: 1; min-width: 0; }
  .mp-pdf-host .mp-sheet-row { display: flex; gap: 12px; margin-bottom: 14px; align-items: flex-start; page-break-inside: auto; }
  .mp-pdf-host .mp-sheet-no { flex-shrink: 0; font-weight: 700; color: #475569; min-width: 3.2em; font-size: 14px; }
  .mp-pdf-host .mp-sheet-body { flex: 1; min-width: 0; }
  .mp-pdf-host .mp-sheet-opt { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: center; font-size: 14px; }
  .mp-pdf-host .mp-sheet-bubble { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border: 1.5px solid #334155; border-radius: 50%; font-weight: 600; }
  .mp-pdf-host .mp-sheet-hint { font-size: 12px; color: #64748b; }
  .mp-pdf-host .mp-sheet-line { height: 26px; border-bottom: 1px solid #94a3b8; margin-bottom: 6px; }
`;

function createPdfHostBase(): HTMLElement {
  const host = document.createElement("div");
  host.className = "mp-pdf-host";
  host.style.cssText =
    "box-sizing:border-box;width:794px;max-width:100%;padding:20px 22px;background:#fff;color:#0f172a;font-family:PingFang SC,Microsoft YaHei,sans-serif;line-height:1.65;";
  const style = document.createElement("style");
  style.textContent = PDF_HOST_STYLE;
  host.appendChild(style);
  return host;
}

function appendPdfHeader(host: HTMLElement, p: MockPaperGenerateResult) {
  const h1 = document.createElement("h1");
  h1.textContent = p.title;
  host.appendChild(h1);

  const meta = document.createElement("p");
  meta.className = "mp-meta";
  meta.textContent = `${p.grade_name} · ${p.subject_name} · 满分 ${p.requested_total_score} 分 · 建议用时 ${p.suggested_exam_minutes ?? 60} 分钟`;
  host.appendChild(meta);

  const stu = document.createElement("div");
  stu.className = "mp-student";
  stu.innerHTML =
    '<span>姓名<span class="mp-line"></span></span>' +
    '<span>年级<span class="mp-line"></span></span>' +
    '<span>学号<span class="mp-line"></span></span>';
  host.appendChild(stu);

  if (p.instructions?.trim()) {
    const insEl = document.createElement("div");
    insEl.className = "mp-ins";
    insEl.textContent = p.instructions;
    host.appendChild(insEl);
  }
}

function buildPdfQuestionsHost(p: MockPaperGenerateResult): HTMLElement {
  const host = createPdfHostBase();
  appendPdfHeader(host, p);

  for (const sec of p.sections) {
    const sectionEl = document.createElement("div");
    sectionEl.className = "mp-sec";
    const head = document.createElement("h3");
    head.className = "mp-sechead";
    head.textContent = sec.heading;
    sectionEl.appendChild(head);
    for (const it of sec.items) {
      const q = document.createElement("div");
      q.className = "mp-q";
      const qhead = document.createElement("div");
      qhead.className = "mp-qhead";
      qhead.textContent = `${questionLabel(it)} ${it.type_name}（${it.score} 分）`;
      q.appendChild(qhead);
      const body = document.createElement("div");
      body.className = "mp-qbody formatted-analysis formatted-analysis--stem";
      body.innerHTML = formatStemDisplayHtml(it.stem) || "—";
      q.appendChild(body);
      if (!p.use_answer_sheet) {
        const n = ruledLinesForItem(it, p);
        if (n > 0) {
          const sp = document.createElement("div");
          sp.className = "mp-qbody";
          sp.style.marginTop = "10px";
          sp.style.paddingTop = "10px";
          sp.style.borderTop = "1px dashed #cbd5e1";
          for (let i = 0; i < n; i++) {
            const ln = document.createElement("div");
            ln.className = "mp-sheet-line";
            sp.appendChild(ln);
          }
          q.appendChild(sp);
        }
      }
      sectionEl.appendChild(q);
    }
    host.appendChild(sectionEl);
  }
  return host;
}

function buildPdfAnswersHost(p: MockPaperGenerateResult): HTMLElement {
  const host = createPdfHostBase();
  const h2 = document.createElement("h2");
  h2.className = "mp-ans-title";
  h2.textContent = "参考答案";
  host.appendChild(h2);
  const sub = document.createElement("p");
  sub.className = "mp-meta";
  sub.textContent = p.title;
  host.appendChild(sub);
  for (const a of p.answers) {
    const row = document.createElement("div");
    row.className = "mp-ans";
    const no = document.createElement("span");
    no.className = "mp-ansno";
    no.textContent = `${a.number}.`;
    const txt = document.createElement("div");
    txt.className = "mp-anstxt formatted-analysis";
    txt.innerHTML = formatAnalysisHtml(a.answer) || "—";
    row.appendChild(no);
    row.appendChild(txt);
    host.appendChild(row);
  }
  return host;
}

function appendPdfSheetRow(host: HTMLElement, it: MockPaperItemOut) {
  const row = document.createElement("div");
  row.className = "mp-sheet-row";
  const no = document.createElement("div");
  no.className = "mp-sheet-no";
  no.textContent = questionLabel(it);
  const body = document.createElement("div");
  body.className = "mp-sheet-body";
  row.appendChild(no);
  row.appendChild(body);

  if (isSheetChoiceType(it.type_code)) {
    const opt = document.createElement("div");
    opt.className = "mp-sheet-opt";
    const letters = it.type_code === "multiple_choice" ? ["A", "B", "C", "D", "E"] : ["A", "B", "C", "D"];
    for (const L of letters) {
      const b = document.createElement("span");
      b.className = "mp-sheet-bubble";
      b.textContent = L;
      opt.appendChild(b);
    }
    if (it.type_code === "multiple_choice") {
      const h = document.createElement("span");
      h.className = "mp-sheet-hint";
      h.textContent = "（多选）";
      opt.appendChild(h);
    }
    body.appendChild(opt);
  } else if (isSheetTrueFalse(it.type_code)) {
    const opt = document.createElement("div");
    opt.className = "mp-sheet-opt";
    for (const t of ["对", "错"]) {
      const b = document.createElement("span");
      b.className = "mp-sheet-bubble";
      b.style.borderRadius = "8px";
      b.style.minWidth = "40px";
      b.textContent = t;
      opt.appendChild(b);
    }
    body.appendChild(opt);
  } else {
    const n = subjectiveAnswerLineCount(it);
    for (let i = 0; i < n; i++) {
      const ln = document.createElement("div");
      ln.className = "mp-sheet-line";
      body.appendChild(ln);
    }
    const cap = document.createElement("div");
    cap.className = "mp-sheet-hint";
    cap.textContent = `${it.type_name} · ${it.score} 分`;
    body.appendChild(cap);
  }
  host.appendChild(row);
}

function buildPdfAnswerSheetHost(p: MockPaperGenerateResult): HTMLElement {
  const host = createPdfHostBase();
  const h1 = document.createElement("h1");
  h1.textContent = "答题卡";
  host.appendChild(h1);
  const meta = document.createElement("p");
  meta.className = "mp-meta";
  meta.textContent = `${p.title} · 建议用时 ${p.suggested_exam_minutes ?? 60} 分钟`;
  host.appendChild(meta);
  const stu = document.createElement("div");
  stu.className = "mp-student";
  stu.innerHTML =
    '<span>姓名<span class="mp-line"></span></span>' +
    '<span>年级<span class="mp-line"></span></span>' +
    '<span>学号<span class="mp-line"></span></span>';
  host.appendChild(stu);
  for (const sec of p.sections) {
    for (const it of sec.items) {
      appendPdfSheetRow(host, it);
    }
  }
  return host;
}

const HTML2PDF_OPTS_BASE = {
  margin: [10, 10, 10, 10] as [number, number, number, number],
  image: { type: "jpeg" as const, quality: 0.92 },
  jsPDF: { unit: "mm" as const, format: "a4" as const, orientation: "portrait" as const },
  pagebreak: { mode: ["css", "legacy"] as const },
};

async function renderHostToPdfBytes(host: HTMLElement): Promise<ArrayBuffer> {
  host.style.maxHeight = "none";
  host.style.overflow = "visible";
  host.style.height = "auto";
  host.style.paddingBottom = "48px";
  await waitRaf2();
  await nextTick();

  const rootBox = host.getBoundingClientRect();
  let maxBottom = rootBox.height;
  for (const el of host.querySelectorAll<HTMLElement>("*")) {
    const br = el.getBoundingClientRect();
    if (br.width < 1 && br.height < 1) continue;
    maxBottom = Math.max(maxBottom, br.bottom - rootBox.top);
  }
  const h = Math.ceil(Math.max(maxBottom + 80, host.scrollHeight + 80, host.offsetHeight + 80));

  const { default: html2pdf } = await import("html2pdf.js");
  const w = Math.ceil(Math.max(host.scrollWidth, host.offsetWidth, 680));

  return html2pdf()
    .set({
      ...HTML2PDF_OPTS_BASE,
      html2canvas: {
        scale: 2,
        useCORS: true,
        logging: false,
        letterRendering: true,
        backgroundColor: "#ffffff",
        width: w,
        windowWidth: w,
        height: h,
        windowHeight: h,
        scrollX: 0,
        scrollY: 0,
      },
    })
    .from(host)
    .outputPdf("arraybuffer") as Promise<ArrayBuffer>;
}

function waitRaf2() {
  return new Promise<void>((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve());
    });
  });
}

function clearPdfHostsExceptTip(overlay: HTMLElement) {
  while (overlay.childNodes.length > 1) {
    overlay.removeChild(overlay.lastChild!);
  }
}

async function onExportPdf() {
  if (!paper.value) return;
  exportingPdf.value = true;
  await nextTick();

  const overlay = document.createElement("div");
  overlay.className = "mp-pdf-overlay";
  overlay.style.cssText =
    "position:fixed;inset:0;z-index:2147483000;background:rgba(255,255,255,0.98);display:block;overflow:visible;padding:20px 12px;box-sizing:border-box;";
  const tip = document.createElement("p");
  tip.style.cssText = "margin:0 0 12px;font-size:14px;color:#64748b;";
  tip.textContent = "正在生成 PDF，请稍候…";
  overlay.appendChild(tip);
  document.body.appendChild(overlay);

  try {
    const parts: ArrayBuffer[] = [];

    const qHost = buildPdfQuestionsHost(paper.value);
    overlay.appendChild(qHost);
    parts.push(await renderHostToPdfBytes(qHost));
    clearPdfHostsExceptTip(overlay);

    if (paper.value.use_answer_sheet) {
      tip.textContent = "正在生成答题卡…";
      const sHost = buildPdfAnswerSheetHost(paper.value);
      overlay.appendChild(sHost);
      await waitRaf2();
      parts.push(await renderHostToPdfBytes(sHost));
      clearPdfHostsExceptTip(overlay);
    }

    if (includeAnswersWhenPrint.value && paper.value.answers.length) {
      tip.textContent = "正在生成参考答案…";
      const aHost = buildPdfAnswersHost(paper.value);
      overlay.appendChild(aHost);
      await waitRaf2();
      parts.push(await renderHostToPdfBytes(aHost));
      clearPdfHostsExceptTip(overlay);
    }

    let finalBytes: ArrayBuffer;
    if (parts.length === 1) {
      finalBytes = parts[0];
    } else {
      const { PDFDocument } = await import("pdf-lib");
      const merged = await PDFDocument.create();
      for (const buf of parts) {
        const doc = await PDFDocument.load(buf);
        const pages = await merged.copyPages(doc, doc.getPageIndices());
        pages.forEach((pg) => merged.addPage(pg));
      }
      finalBytes = await merged.save();
    }

    const blob = new Blob([finalBytes], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = pdfFilename();
    a.click();
    URL.revokeObjectURL(url);
    message.success("PDF 已下载");
  } catch (e) {
    message.error((e as Error).message || "导出 PDF 失败，请重试或使用打印另存为 PDF");
  } finally {
    overlay.remove();
    exportingPdf.value = false;
  }
}

function onPrint() {
  if (!includeAnswersWhenPrint.value) {
    document.documentElement.classList.add("mock-paper-print-hide-answers");
  }
  const clear = () => document.documentElement.classList.remove("mock-paper-print-hide-answers");
  window.addEventListener("afterprint", clear, { once: true });
  window.print();
}
</script>

<template>
  <div class="page-root mock-paper-page">
    <header class="page-header mock-paper-header mock-paper-no-print">
      <h1 class="page-header__title">模拟练习卷</h1>
      <p class="page-header__desc">
        在左侧选择年级与科目，按需限定知识点与题型；生成后可在右侧预览，使用打印或导出 PDF 留存。
      </p>
    </header>

    <div class="mock-paper-layout">
      <aside class="mock-paper-side mock-paper-no-print">
        <NSpin :show="catalogLoading">
          <NCard class="mock-paper-side-card" size="small" :bordered="false">
            <template #header>
              <div class="mock-paper-side-card__head">
                <span class="mock-paper-side-card__dot" aria-hidden="true" />
                <span class="mock-paper-side-card__title">组卷条件</span>
              </div>
            </template>
            <NSpace vertical :size="18" style="width: 100%">
              <NGrid :cols="1" :x-gap="12" :y-gap="12" responsive="screen" item-responsive>
                <NGi span="24">
                  <NFormItem label="年级" :show-feedback="false" label-placement="top">
                    <NSelect
                      v-model:value="gradeId"
                      :options="gradeOptions"
                      placeholder="请选择年级"
                      filterable
                      clearable
                    />
                  </NFormItem>
                </NGi>
                <NGi span="24">
                  <NFormItem label="科目" :show-feedback="false" label-placement="top">
                    <NSelect
                      v-model:value="subjectId"
                      :options="subjectOptions"
                      placeholder="请先选年级"
                      :disabled="!gradeId"
                      filterable
                    />
                  </NFormItem>
                </NGi>
              </NGrid>

              <NDivider dashed style="margin: 0" />

              <NFormItem label="知识点标签" :show-feedback="false" label-placement="top">
                <template #label>
                  <span>知识点标签</span>
                  <NText depth="3" style="font-size: 12px; font-weight: 400; margin-left: 6px">选填 · 多选</NText>
                </template>
                <NSelect
                  v-model:value="selectedTags"
                  multiple
                  filterable
                  clearable
                  max-tag-count="responsive"
                  :options="tagOptions"
                  :loading="tagsLoading"
                  :disabled="!gradeId || !subjectId"
                  placeholder="不选则不限定知识点"
                />
              </NFormItem>

              <div class="mock-paper-panel">
                <NSpin :show="typesLoading">
                  <NFormItem :show-feedback="false" label-placement="top">
                    <template #label>
                      <span>出题题型</span>
                      <NText depth="3" style="font-size: 12px; font-weight: 400; margin-left: 6px">
                        选填 · 不勾选则由 AI 搭配
                      </NText>
                    </template>
                    <NCheckboxGroup
                      v-model:value="selectedTypeCodes"
                      size="small"
                      :disabled="!questionTypes.length"
                    >
                      <NSpace vertical :size="10" style="width: 100%">
                        <NCheckbox
                          v-for="t in questionTypes"
                          :key="t.code"
                          :value="t.code"
                          :label="t.name"
                        />
                      </NSpace>
                    </NCheckboxGroup>
                    <NText
                      v-if="gradeId && subjectId && !questionTypes.length && !typesLoading"
                      depth="3"
                      style="font-size: 13px; display: block; margin-top: 8px"
                    >
                      暂无题型数据
                    </NText>
                  </NFormItem>
                </NSpin>
              </div>

              <NCollapse class="mock-paper-collapse" display-directive="show">
                <NCollapseItem title="各题型题量（选填）" name="counts">
                  <NText depth="3" style="font-size: 12px; display: block; margin-bottom: 10px; line-height: 1.55">
                    仅对已勾选题型生效；未勾选题型时，对当前年级下全部适用题型生效。留空由 AI 分配题量。
                  </NText>
                  <NGrid :cols="1" :x-gap="12" :y-gap="10" responsive="screen" item-responsive>
                    <NGi v-for="code in typesForCountInputs" :key="code" span="24">
                      <NFormItem
                        :label="questionTypes.find((t) => t.code === code)?.name ?? code"
                        :show-feedback="false"
                        label-placement="top"
                      >
                        <NInputNumber
                          v-model:value="countsDraft[code]"
                          :min="1"
                          :max="20"
                          :show-button="false"
                          placeholder="留空"
                          clearable
                          style="width: 100%"
                        />
                      </NFormItem>
                    </NGi>
                  </NGrid>
                </NCollapseItem>
              </NCollapse>

              <NFormItem label="使用答题卡" :show-feedback="false" label-placement="top">
                <template #label>
                  <span>使用答题卡</span>
                  <NText depth="3" style="font-size: 12px; font-weight: 400; margin-left: 6px">
                    开启后单独生成答题卡页；关闭则在卷面预留作答横线
                  </NText>
                </template>
                <NSwitch v-model:value="useAnswerSheet" />
              </NFormItem>

              <NFormItem label="卷面总分" :show-feedback="false" label-placement="top">
                <NInputNumber
                  v-model:value="totalScore"
                  :min="20"
                  :max="200"
                  :step="5"
                  :show-button="false"
                  placeholder="默认 100"
                  style="width: 100%; max-width: 220px"
                />
              </NFormItem>

              <div class="app-actions">
                <NButton type="primary" block :disabled="!canGenerate" :loading="generating" @click="onGenerate">
                  生成模拟卷
                </NButton>
              </div>
            </NSpace>
          </NCard>
        </NSpin>
      </aside>

      <main class="mock-paper-main">
        <template v-if="generating && !paper">
          <div class="mock-paper-stream-wrap mock-paper-no-print">
            <div class="mock-paper-stream-head">
              <NSpin size="small" />
              <NText strong style="font-size: 14px">{{ streamPhase || "正在连接出题服务…" }}</NText>
              <NButton
                class="mock-paper-stream-cancel"
                size="small"
                secondary
                @click="onCancelGenerate"
              >
                取消生成
              </NButton>
            </div>
            <NText depth="3" style="font-size: 12px; display: block; margin-bottom: 8px">
              以下为模型实时输出（JSON），生成结束后将切换为排版好的试卷。
            </NText>
            <pre ref="streamPreRef" class="mock-paper-stream-pre" aria-live="polite">{{ streamText }}</pre>
          </div>
        </template>
        <template v-else-if="!paper">
          <div class="mock-paper-preview-shell mock-paper-no-print">
            <NEmpty description="生成后的试卷将显示在此处，支持预览与导出" size="large">
              <template #extra>
                <NText depth="3" style="font-size: 13px">请先完成左侧年级、科目并点击「生成模拟卷」</NText>
              </template>
            </NEmpty>
          </div>
        </template>
        <template v-else>
          <div class="mock-paper-result">
            <NAlert
              v-if="scoreMismatch"
              type="warning"
              class="mock-paper-no-print mock-paper-alert"
              :bordered="false"
              style="margin-bottom: 12px"
            >
              AI 赋分合计为 {{ paper.actual_total_score }} 分，与目标 {{ paper.requested_total_score }} 分不一致，可按需核对各题分值。
            </NAlert>

            <div class="mock-paper-toolbar mock-paper-no-print">
              <div class="mock-paper-toolbar__hint">
                <NText depth="2" style="font-size: 13px">打印答卷</NText>
                <NSwitch v-model:value="includeAnswersWhenPrint" size="small" />
                <NText depth="3" style="font-size: 12px">含参考答案</NText>
              </div>
              <div class="mock-paper-toolbar__actions app-actions">
                <NButton size="small" secondary :loading="exportingPdf" @click="onExportPdf">导出 PDF</NButton>
                <NButton size="small" type="primary" @click="onPrint">打印</NButton>
              </div>
            </div>

            <div class="mock-paper-main__scroll">
              <div ref="pdfRoot" class="mock-paper-pdf-root mock-paper-print-stack">
                <section class="mock-paper-a4 mock-paper-sheet" aria-label="试题">
                  <h2 class="mock-paper-a4__title">{{ paper.title }}</h2>
                  <p class="mock-paper-a4__meta">
                    {{ paper.grade_name }} · {{ paper.subject_name }} · 满分 {{ paper.requested_total_score }} 分 · 建议用时
                    {{ paper.suggested_exam_minutes ?? 60 }} 分钟
                    <template v-if="paper.use_answer_sheet"> · 配套答题卡</template>
                  </p>
                  <div class="mock-paper-student" aria-label="考生信息填写">
                    <span class="mock-paper-student__item">姓名<span class="mock-paper-student__line" /></span>
                    <span class="mock-paper-student__item">年级<span class="mock-paper-student__line" /></span>
                    <span class="mock-paper-student__item">学号<span class="mock-paper-student__line" /></span>
                  </div>
                  <p v-if="paper.instructions" class="mock-paper-a4__ins">{{ paper.instructions }}</p>
                  <div
                    v-for="sec in paper.sections"
                    :key="'sec-' + sec.section_order"
                    class="mock-paper-section"
                  >
                    <h3 class="mock-paper-section__head">{{ sec.heading }}</h3>
                    <div v-for="it in sec.items" :key="it.number" class="mock-paper-q">
                      <div class="mock-paper-q__head">
                        {{ questionLabel(it) }} {{ it.type_name }}（{{ it.score }} 分）
                      </div>
                      <FormattedAnalysis class="mock-paper-q__body" :text="it.stem" variant="stem" empty-text="—" />
                      <div
                        v-if="ruledLinesForItem(it) > 0"
                        class="mock-paper-answer-space"
                        aria-label="作答区"
                      >
                        <div
                          v-for="n in ruledLinesForItem(it)"
                          :key="'ln-' + it.number + '-' + n"
                          class="mock-paper-answer-space__line"
                        />
                      </div>
                    </div>
                  </div>
                </section>

                <section
                  v-if="paper.use_answer_sheet"
                  class="mock-paper-a4 mock-paper-sheet mock-paper-answer-sheet-block"
                  aria-label="答题卡"
                >
                  <h2 class="mock-paper-a4__title mock-paper-a4__title--sub">答题卡</h2>
                  <p class="mock-paper-a4__meta">{{ paper.title }} · 建议用时 {{ paper.suggested_exam_minutes ?? 60 }} 分钟</p>
                  <div class="mock-paper-student" aria-label="考生信息填写">
                    <span class="mock-paper-student__item">姓名<span class="mock-paper-student__line" /></span>
                    <span class="mock-paper-student__item">年级<span class="mock-paper-student__line" /></span>
                    <span class="mock-paper-student__item">学号<span class="mock-paper-student__line" /></span>
                  </div>
                  <div v-for="it in flatPaperItems" :key="'card-' + it.number" class="mock-paper-sheet-row">
                    <div class="mock-paper-sheet-no">{{ questionLabel(it) }}</div>
                    <div class="mock-paper-sheet-body">
                      <div v-if="isSheetChoiceType(it.type_code)" class="mock-paper-sheet-opt">
                        <span
                          v-for="L in it.type_code === 'multiple_choice' ? ['A', 'B', 'C', 'D', 'E'] : ['A', 'B', 'C', 'D']"
                          :key="L + '-' + it.number"
                          class="mock-paper-sheet-bubble"
                        >{{ L }}</span>
                        <span v-if="it.type_code === 'multiple_choice'" class="mock-paper-sheet-hint">（多选）</span>
                      </div>
                      <div v-else-if="isSheetTrueFalse(it.type_code)" class="mock-paper-sheet-opt">
                        <span class="mock-paper-sheet-bubble mock-paper-sheet-bubble--wide">对</span>
                        <span class="mock-paper-sheet-bubble mock-paper-sheet-bubble--wide">错</span>
                      </div>
                      <div v-else>
                        <div
                          v-for="n in subjectiveAnswerLineCount(it)"
                          :key="'sl-' + it.number + '-' + n"
                          class="mock-paper-sheet-line"
                        />
                        <div class="mock-paper-sheet-hint">{{ it.type_name }} · {{ it.score }} 分</div>
                      </div>
                    </div>
                  </div>
                </section>

                <section class="mock-paper-a4 mock-paper-sheet mock-paper-answers-block" aria-label="参考答案">
                  <h2 class="mock-paper-a4__title mock-paper-a4__title--sub">参考答案</h2>
                  <div v-for="a in paper.answers" :key="'a-' + a.number" class="mock-paper-ans">
                    <span class="mock-paper-ans__no">{{ a.number }}.</span>
                    <div class="mock-paper-ans__txt">
                      <FormattedAnalysis :text="a.answer" variant="analysis" empty-text="—" />
                    </div>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </template>
      </main>
    </div>
  </div>
</template>

<style scoped>
.mock-paper-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-bottom: 28px;
  width: 100%;
  max-width: 1320px;
  margin: 0 auto;
  box-sizing: border-box;
}

.mock-paper-header {
  margin-bottom: 20px;
}

.mock-paper-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 20px;
  align-items: start;
  width: 100%;
}

@media (min-width: 1060px) {
  .mock-paper-layout {
    grid-template-columns: minmax(300px, 380px) minmax(0, 1fr);
    gap: 24px;
    align-items: stretch;
  }
}

.mock-paper-side {
  min-width: 0;
}

.mock-paper-side-card {
  border-radius: 16px !important;
  background: linear-gradient(165deg, rgba(255, 255, 255, 0.94) 0%, rgba(248, 250, 255, 0.88) 100%) !important;
  border: 1px solid rgba(148, 163, 184, 0.28) !important;
  box-shadow: 0 8px 32px rgba(15, 23, 42, 0.06);
}

.mock-paper-side-card :deep(.n-card-header) {
  padding-bottom: 8px;
}

.mock-paper-side-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mock-paper-side-card__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.mock-paper-side-card__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.mock-paper-side-card :deep(.n-card__content) {
  padding-top: 4px;
}

.mock-paper-panel {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.22);
}

.mock-paper-panel :deep(.n-form-item-label) {
  padding-bottom: 6px;
}

.mock-paper-panel :deep(.n-form-item-blank) {
  width: 100%;
}

.mock-paper-collapse :deep(.n-collapse-item__header) {
  font-weight: 600;
  font-size: 13px;
}

.mock-paper-main {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.mock-paper-stream-wrap {
  flex: 1;
  min-height: 0;
  max-height: min(78dvh, calc(100dvh - 188px));
  display: flex;
  flex-direction: column;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.06);
}

.mock-paper-stream-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.mock-paper-stream-cancel {
  margin-left: auto;
  flex-shrink: 0;
}

.mock-paper-stream-pre {
  flex: 1;
  min-height: 120px;
  margin: 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.5;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, "Cascadia Code", "SF Mono", Menlo, Consolas, monospace;
}

/* 生成试卷后：仅试卷区域滚动，工具栏固定不随滚动 */
.mock-paper-result {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  width: 100%;
  min-width: 0;
}

.mock-paper-main__scroll {
  flex: 1;
  min-height: 0;
  max-height: min(82dvh, calc(100dvh - 168px));
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
  scrollbar-gutter: stable;
}

@media (max-width: 1059px) {
  .mock-paper-main__scroll {
    max-height: min(76dvh, calc(100dvh - 220px));
  }
}

.mock-paper-preview-shell {
  min-height: 360px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  border: 1px dashed rgba(148, 163, 184, 0.45);
  background: rgba(255, 255, 255, 0.35);
  padding: 32px 20px;
}

.mock-paper-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
  margin-bottom: 12px;
  padding: 12px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.25);
  box-shadow: 0 4px 20px rgba(15, 23, 42, 0.05);
}

.mock-paper-toolbar__hint {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.mock-paper-toolbar__actions {
  margin: 0;
  flex-shrink: 0;
}

.mock-paper-alert :deep(.n-alert-body) {
  font-size: 13px;
  line-height: 1.55;
}

.mock-paper-print-stack {
  margin-top: 0;
}

.mock-paper-pdf-root {
  width: 100%;
}

.mock-paper-a4 {
  width: 100%;
  max-width: 210mm;
  margin: 0 auto 18px;
  background: rgba(255, 255, 255, 0.96);
  color: #0f172a;
  box-sizing: border-box;
  padding: 14mm 16mm;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.08);
}

.mock-paper-a4__title {
  margin: 0 0 6px;
  font-size: 1.28rem;
  font-weight: 700;
  text-align: center;
  line-height: 1.35;
  letter-spacing: -0.02em;
}

.mock-paper-a4__title--sub {
  font-size: 1.08rem;
  margin-bottom: 14px;
  text-align: left;
}

.mock-paper-a4__meta {
  margin: 0 0 14px;
  text-align: center;
  font-size: 13px;
  color: #64748b;
}

.mock-paper-a4__ins {
  margin: 0 0 18px;
  padding: 10px 12px;
  font-size: 13px;
  white-space: pre-wrap;
  color: #334155;
  line-height: 1.65;
  border-radius: 10px;
  background: rgba(241, 245, 249, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.2);
}


.mock-paper-student {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  justify-content: center;
  margin: 0 0 16px;
  font-size: 14px;
  color: #0f172a;
}

.mock-paper-student__item {
  white-space: nowrap;
}

.mock-paper-student__line {
  display: inline-block;
  min-width: 6.5em;
  border-bottom: 1px solid #334155;
  margin-left: 6px;
  vertical-align: bottom;
  height: 1.25em;
}

.mock-paper-section {
  margin-bottom: 22px;
}

.mock-paper-section__head {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.45;
}

.mock-paper-answer-space {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed rgba(148, 163, 184, 0.65);
}

.mock-paper-answer-space__line {
  height: 26px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.85);
  margin-bottom: 6px;
}

.mock-paper-sheet-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.mock-paper-sheet-no {
  flex-shrink: 0;
  font-weight: 700;
  color: #475569;
  min-width: 3.2em;
  font-size: 14px;
}

.mock-paper-sheet-body {
  flex: 1;
  min-width: 0;
}

.mock-paper-sheet-opt {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  align-items: center;
}

.mock-paper-sheet-bubble {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1.5px solid #334155;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.mock-paper-sheet-bubble--wide {
  border-radius: 8px;
  min-width: 44px;
}

.mock-paper-sheet-line {
  height: 26px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.85);
  margin-bottom: 6px;
}

.mock-paper-sheet-hint {
  font-size: 12px;
  color: #64748b;
  width: 100%;
  margin-top: 4px;
}

.mock-paper-q {
  margin-bottom: 18px;
}

.mock-paper-q__head {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
}

.mock-paper-q__body {
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.75);
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
}

.mock-paper-ans {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 14px;
  font-size: 14px;
}

.mock-paper-ans__no {
  flex-shrink: 0;
  font-weight: 700;
  color: #475569;
}

.mock-paper-ans__txt {
  flex: 1;
  min-width: 0;
}

@media (max-width: 768px) {
  .mock-paper-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .mock-paper-toolbar__actions {
    justify-content: flex-end;
  }

  .mock-paper-a4 {
    padding: 12px 14px;
  }
}
</style>

<style>
/* 盖过本页 scoped 的 max-height/overflow（scoped 带 data 属性后优先级更高），打印时须整卷展开 */
@media print {
  .mock-paper-page,
  .mock-paper-layout,
  .mock-paper-main,
  .mock-paper-result,
  .mock-paper-main__scroll,
  .mock-paper-pdf-root {
    max-height: none !important;
    height: auto !important;
    min-height: auto !important;
    overflow: visible !important;
    overflow-x: visible !important;
    overflow-y: visible !important;
  }
}
</style>
