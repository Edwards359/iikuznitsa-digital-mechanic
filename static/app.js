const vehicle = document.querySelector("#vehicle");
const session = document.querySelector("#session");
const answer = document.querySelector("#answer");
const journal = document.querySelector("#journal");
const procedure = document.querySelector("#procedure");
const draftForm = document.querySelector("#draft-form");
const draftStatus = document.querySelector("#draft-status");
const draftBadge = document.querySelector("#draft-badge");
const draftEmpty = document.querySelector("#draft-empty");
const draftEmptyWhy = document.querySelector("#draft-empty-why");
const draftBody = document.querySelector("#draft-body");
const draftReason = document.querySelector("#draft-reason");
const ticket = document.querySelector("#ticket");
const partsQuery = document.querySelector("#parts-query");
const partsSearch = document.querySelector("#parts-search");
const partsStatus = document.querySelector("#parts-status");
const partsList = document.querySelector("#parts-list");
const partsAdd = document.querySelector("#parts-add");
const draftBuild = document.querySelector("#draft-build");
const walkthrough = document.querySelector("#walkthrough");
const walkMeta = document.querySelector("#walk-meta");
const walkRef = document.querySelector("#walk-ref");
const walkText = document.querySelector("#walk-text");
const walkExcerpt = document.querySelector("#walk-excerpt");
const walkFigure = document.querySelector("#walk-figure");
const walkCap = document.querySelector("#walk-cap");
const walkImg = document.querySelector("#walk-img");
const walkImgErr = document.querySelector("#walk-img-err");
const walkShowPage = document.querySelector("#walk-show-page");
const walkPrev = document.querySelector("#walk-prev");
const walkNext = document.querySelector("#walk-next");
const procModeFull = document.querySelector("#proc-mode-full");
const procModePro = document.querySelector("#proc-mode-pro");
const procModeHint = document.querySelector("#proc-mode-hint");
const voiceToggle = document.querySelector("#voice-toggle");
const voiceStatus = document.querySelector("#voice-status");

let vehicles = [];
let draftId = null;
let consultId = null;
let repairSteps = [];
let guidePages = [];
let stepIndex = 0;
let procedureMode = localStorage.getItem("procMode") === "pro" ? "pro" : "full";
let proPageOpen = false;
let lastSpareItems = [];
let selectedSpareLabels = [];
let lastDraftPayload = null;
const partsSelected = document.querySelector("#parts-selected");
const partsSelectedList = document.querySelector("#parts-selected-list");
let voiceOn = false;
let recognition = null;
let micStream = null;
let voiceEngine = "none";
let voiceMode = "browser";
let voiceBusy = false;
let voiceLoopToken = 0;

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

function fillSessions(vehicleId, preferred) {
  const row = vehicles.find((item) => item.vehicle_id === vehicleId);
  const list = row ? row.sessions : [];
  session.innerHTML = list
    .map(
      (item) =>
        `<option value="${item.session_id}">${item.session_id} · ${item.status}${item.anomaly_type ? " · " + item.anomaly_type : ""}</option>`,
    )
    .join("");
  if (preferred) {
    session.value = preferred;
  }
}

function formatWhen(iso) {
  if (!iso) {
    return "";
  }
  try {
    return new Date(iso).toLocaleString("ru-RU", { timeZone: "UTC" });
  } catch {
    return iso;
  }
}

function loadVehicleCard(vehicleId) {
  const box = document.querySelector("#vehicle-card");
  fetch(`/api/vehicles/${encodeURIComponent(vehicleId)}`)
    .then((response) => (response.ok ? response.json() : null))
    .then((body) => {
      if (!body) {
        box.hidden = true;
        return;
      }
      const v = body.vehicle;
      const manuals = (v.manuals || [])
        .map((row) => `<li>${row.manual_id}</li>`)
        .join("");
      document.querySelector("#vehicle-meta").innerHTML = [
        `<strong>${v.vehicle_id}</strong> · гараж ${v.garage_no || "—"} · ${v.make || ""} ${v.model || ""}`,
        `Двигатель ${v.engine_model}, ${v.fuel || ""}. Тип: ${v.vehicle_type || "—"}.`,
        manuals ? `<div class="hint">Руководства: <ul class="vehicle-list">${manuals}</ul></div>` : "",
      ].join("<br>");
      document.querySelector("#vehicle-checks").innerHTML = (v.sessions || [])
        .map(
          (item) =>
            `<li>${item.checked_at || "—"} · ${item.session_id} · ${item.status}` +
            `${item.anomaly_type ? ` · ${item.anomaly_type}` : ""}` +
            `${item.signal_quality ? ` · качество ${item.signal_quality}` : ""}</li>`,
        )
        .join("");
      const usage = body.usage || {};
      const rub = usage.cost_rub ? `, ≈${Number(usage.cost_rub).toFixed(2)} ₽` : "";
      document.querySelector("#vehicle-usage").textContent =
        usage.consults
          ? `Консультаций: ${usage.consults}; токены вход ${usage.input_tokens || 0} / выход ${usage.output_tokens || 0}${rub}.`
          : "Консультаций по этой машине ещё не было.";
      document.querySelector("#vehicle-consults").innerHTML = (body.consultations || [])
        .map((row) => {
          const draft = row.has_draft ? " · черновик" : "";
          const err = row.error ? ` · ошибка` : "";
          const rubOne = row.cost_rub ? ` · ≈${row.cost_rub} ₽` : "";
          return (
            `<li>${formatWhen(row.created_at)} · ${row.session_id || "—"} · ${row.tools?.join(", ") || "—"}` +
            `${draft}${err}${rubOne}<br><span class="hint">${escapeHtml(demarkdown(row.answer_preview || ""))}</span></li>`
          );
        })
        .join("") || "<li class='hint'>пока пусто</li>";
      document.querySelector("#vehicle-tickets").innerHTML = (body.tickets || [])
        .map(
          (row) =>
            `<li>${formatWhen(row.created_at)} · ${row.ticket_id} · проверка ${row.session_id}</li>`,
        )
        .join("") || "<li class='hint'>заявок нет</li>";
      document.querySelector("#vehicle-repair").innerHTML = (body.repair_progress || [])
        .map((row) => {
          const step =
            row.step_total > 0
              ? `шаг ${row.step_index + 1}/${row.step_total}`
              : "без пошагового режима";
          return (
            `<li>${row.session_id} · ${row.status} · ${step}` +
            `<br><span class="hint">${formatWhen(row.updated_at)} — ${row.summary || ""}</span></li>`
          );
        })
        .join("") || "<li class='hint'>нет сохранённого прогресса</li>";
      box.hidden = false;
    })
    .catch(() => {
      box.hidden = true;
    });
}

function syncLangFromApi(rows) {
  if (!rows || !rows.length) {
    return;
  }
  const lang = document.querySelector("#lang");
  const selected = lang.value;
  lang.innerHTML = rows
    .map((row) => `<option value="${row.code}">${row.label}</option>`)
    .join("");
  if (selected) {
    lang.value = selected;
  }
}

function load() {
  fetch("/api/languages")
    .then((response) => (response.ok ? response.json() : []))
    .then(syncLangFromApi)
    .catch(() => {});
  fetch("/api/health")
    .then((response) => response.json())
    .then((health) => {
      document.querySelector("#health").textContent =
        `модель ${health.model}, фрагментов ${health.index_chunks}, гибрид ${health.search_hybrid ? "да" : "нет"}, машин ${health.vehicles}`;
      const prio = health.priority_meaning || {};
      document.querySelector("#policy-body").innerHTML = [
        `<div><strong>Заявка</strong>: confidence ≥ ${health.min_ticket_confidence ?? 0.5}</div>`,
        `<div><strong>Срочность</strong>: не завышаем при confidence &lt; ${health.low_confidence ?? 0.56} или помехах</div>`,
        `<div><strong>high</strong> — ${prio.high || "дефектовка до рейса"}</div>`,
        `<div><strong>medium</strong> — ${prio.medium || "ближайшее ТО"}</div>`,
        `<div><strong>low</strong> — ${prio.low || "следующая проверка"}</div>`,
      ].join("");
    });
  fetch("/api/vehicles")
    .then((response) => response.json())
    .then((rows) => {
      vehicles = rows;
      vehicle.innerHTML = rows
        .map(
          (item) =>
            `<option value="${item.vehicle_id}">${item.vehicle_id} · ${item.engine_model}</option>`,
        )
        .join("");
      fillSessions(vehicle.value);
      loadVehicleCard(vehicle.value);
    });
  fetch("/api/voice/status")
    .then((response) => response.json())
    .then((body) => {
      voiceMode = body.mode || "browser";
      voiceEngine = body.engine || voiceMode;
      const bar = document.querySelector("#voice-bar");
      setupWalkKeysOnly();
      ensureSecurePage();
      if (voiceMode === "off") {
        bar.hidden = true;
        return;
      }
      bar.hidden = false;
      voiceStatus.textContent = body.hint || body.cost || "";
      if (voiceMode === "yandex" && body.enabled) {
        setupVoiceYandexPtt();
      } else if (voiceMode === "browser") {
        setupVoiceBrowser();
      } else {
        voiceStatus.textContent = "Голос недоступен: нет ключа Yandex. Задайте VOICE_MODE=browser.";
      }
    })
    .catch(() => {
      setupWalkKeysOnly();
      setupVoiceBrowser();
    });
}

vehicle.addEventListener("change", () => {
  fillSessions(vehicle.value);
  loadVehicleCard(vehicle.value);
});

function normalizePages(pages) {
  return (pages || [])
    .map((row) => ({
      manual: row.manual,
      pdf_page: row.pdf_page || row.page,
    }))
    .filter((row) => row.manual && row.pdf_page);
}

function stepsFromDraft(payload) {
  const ops = payload.operations || [];
  const refs = payload.references || [];
  const count = Math.max(ops.length, refs.length);
  if (!count) {
    return [];
  }
  return Array.from({ length: count }, (_, index) => {
    const ref = refs[index] || refs[refs.length - 1];
    const text =
      (ops[index] || "").trim() ||
      (ref && ref.quote) ||
      (ref ? `По руководству (${ref.manual}, стр. ${ref.pdf_page})` : "");
    return {
      n: index + 1,
      text,
      manual: ref ? ref.manual : null,
      pdf_page: ref ? ref.pdf_page || ref.page : null,
    };
  });
}

function pagesFromClippedJson(raw) {
  const rows = [];
  const text = String(raw || "");
  // Полный JSON (если не обрезан) или куски с manual/page в обрезанном результате.
  try {
    const data = JSON.parse(text);
    if (Array.isArray(data)) {
      for (const row of data) {
        const page = row.page || row.pdf_page;
        if (row.manual && page) {
          rows.push({
            manual: row.manual,
            pdf_page: page,
            excerpt: String(row.excerpt || row.text || "")
              .trim()
              .slice(0, 400),
          });
        }
      }
      return rows;
    }
  } catch {
    /* ниже — regex по обрезанному журналу */
  }
  const re =
    /"manual"\s*:\s*"([^"]+)"[\s\S]{0,180}?"(?:page|pdf_page)"\s*:\s*(\d+)/g;
  let match;
  while ((match = re.exec(text))) {
    rows.push({ manual: match[1], pdf_page: Number(match[2]), excerpt: "" });
  }
  return rows;
}

function pagesFromJournal(steps) {
  const rows = [];
  for (const step of steps || []) {
    if (!["read_pages", "search_manual", "search_spare_parts"].includes(step.tool)) {
      continue;
    }
    rows.push(...pagesFromClippedJson(step.result));
  }
  return rows;
}

function selectedEngine() {
  const row = vehicles.find((item) => item.vehicle_id === vehicle.value);
  return (row && row.engine_model) || "";
}

function manualOkForEngine(manual, engine) {
  const m = String(manual || "").toLowerCase();
  const e = String(engine || "").toLowerCase();
  if (!m) {
    return false;
  }
  if (!e) {
    return true;
  }
  if (e.includes("ямз-236") || e.includes("yamz-236")) {
    return m.includes("236") && !m.includes("536");
  }
  if (e.includes("ямз-536") || e.includes("yamz-536")) {
    return m.includes("536");
  }
  if (e.includes("змз-5234")) {
    return m.includes("5234");
  }
  if (e.includes("змз-409")) {
    return m.includes("409");
  }
  return true;
}

function pagesFromAnswer(text) {
  const rows = [];
  const patterns = [
    /\(([^)]+?),\s*(?:стр\.|страница)\s*(\d+)\)/gi,
    /«([^»]+)»\s*,\s*(?:стр\.|страница)\s*(\d+)/gi,
    /([0-9A-Za-zА-Яа-я.\-]+(?:\s+[А-Яа-яA-Za-z.]+){0,6})\s*,\s*(?:стр\.|страница)\s*(\d+)/gi,
  ];
  for (const re of patterns) {
    let match;
    while ((match = re.exec(text || ""))) {
      rows.push({ manual: match[1].trim(), pdf_page: Number(match[2]), excerpt: "" });
    }
  }
  return rows;
}

function cleanStepText(text) {
  return demarkdown(String(text || "")).replace(/^#+\s*/, "").trim();
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Убрать Markdown, JSON, имена инструментов — обычный текст как в акте. */
function demarkdown(text) {
  let raw = String(text || "");
  raw = raw.replace(/```[\s\S]*?```/g, "");
  raw = raw.replace(
    /^\s*(?:вызов\s+)?(?:get_vehicle|list_checks|get_check|explain_code|search_manual|search_spare_parts|read_pages|ticket_history|draft_ticket)\b.*$/gim,
    "",
  );
  raw = raw.replace(/^\s*(?:подготовка черновика заявки|параметры:).*$/gim, "");
  raw = raw.replace(/^\s*#{1,6}\s*/gm, "");
  raw = raw.replace(/\*\*(.+?)\*\*/g, "$1");
  raw = raw.replace(/__(.+?)__/g, "$1");
  raw = raw.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "$1");
  raw = raw.replace(/`([^`]+)`/g, "$1");
  raw = raw.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  raw = raw.replace(/^\s*[-*_]{3,}\s*$/gm, "");
  raw = raw.replace(/^\s*>\s?/gm, "");
  raw = raw.replace(/^\s*[-*+]\s+/gm, "• ");
  return raw.replace(/\n{3,}/g, "\n\n").trim();
}

function scrubAnswer(text) {
  return demarkdown(text);
}

const ANSWER_HEADINGS = [
  "наблюдаемые признаки",
  "вероятные причины и риск",
  "вероятные причины",
  "что делаем по руководству",
  "ремонт по шагам",
  "запчасти",
  "заключение",
];

function isAnswerHeading(line) {
  const t = line.replace(/[:.]\s*$/, "").trim().toLowerCase();
  if (!t || t.length > 80) {
    return false;
  }
  if (ANSWER_HEADINGS.some((h) => t === h || t.startsWith(h))) {
    return true;
  }
  return /^(признаки|причины|риск|порядок|диагноз)\b/i.test(t) && t.length < 60;
}

function renderAnswerDoc(raw) {
  const text = scrubAnswer(raw);
  if (!answer) {
    return;
  }
  if (!text) {
    answer.innerHTML = '<p class="muted">Пустой ответ.</p>';
    return;
  }
  const lines = text.split(/\n/);
  const blocks = [];
  let listType = null;
  let listItems = [];

  const flushList = () => {
    if (!listItems.length) {
      return;
    }
    const tag = listType === "ol" ? "ol" : "ul";
    blocks.push(
      `<${tag}>${listItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</${tag}>`,
    );
    listItems = [];
    listType = null;
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      continue;
    }
    const ol = line.match(/^(\d+)[.)]\s+(.+)$/);
    if (ol) {
      if (listType && listType !== "ol") {
        flushList();
      }
      listType = "ol";
      listItems.push(ol[2]);
      continue;
    }
    if (/^•\s+/.test(line)) {
      if (listType && listType !== "ul") {
        flushList();
      }
      listType = "ul";
      listItems.push(line.replace(/^•\s+/, ""));
      continue;
    }
    flushList();
    if (isAnswerHeading(line)) {
      blocks.push(`<h3>${escapeHtml(line.replace(/[:.]\s*$/, ""))}</h3>`);
    } else {
      blocks.push(`<p>${escapeHtml(line)}</p>`);
    }
  }
  flushList();
  answer.innerHTML = blocks.join("") || `<p>${escapeHtml(text)}</p>`;
}

/** Целые предложения для «текста со страницы», без обрывков. */
function isContentsText(raw) {
  const text = String(raw || "");
  if (!text.trim()) {
    return false;
  }
  const head = text.slice(0, 120).toLowerCase().replace(/\s+/g, " ");
  if (head.includes("содержание") || head.includes("оглавление") || head.includes("contents")) {
    return true;
  }
  const lines = text.split(/\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length < 5) {
    return false;
  }
  const dotted = lines.filter(
    (line) => /[\.…]{3,}\s*\d{1,3}\s*$/.test(line) || /\S.{6,}\s{2,}\d{1,3}\s*$/.test(line),
  ).length;
  return dotted / lines.length >= 0.55;
}

function tidyExcerpt(raw, maxLen = 420) {
  let text = String(raw || "")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) {
    return "";
  }
  const start = text.search(/[А-ЯA-ZЁ0-9«"'(]/);
  if (start > 0 && start < 48) {
    text = text.slice(start).trim();
  }
  const parts = text.split(/(?<=[.!?…])\s+/).filter((part) => part.trim().length >= 8);
  let out = "";
  for (const part of parts) {
    const next = out ? `${out} ${part}` : part;
    if (out && next.length > maxLen) {
      break;
    }
    out = next;
    if (out.length >= Math.floor(maxLen * 0.65)) {
      break;
    }
  }
  if (!out) {
    const cut = text.slice(0, maxLen);
    const sp = cut.lastIndexOf(" ");
    out = sp > 40 ? `${cut.slice(0, sp)}…` : `${cut}…`;
  }
  if (out.length > 40 && !/[.!?…]$/.test(out)) {
    const lastStop = Math.max(out.lastIndexOf("."), out.lastIndexOf("!"), out.lastIndexOf("?"));
    if (lastStop > 60) {
      out = out.slice(0, lastStop + 1);
    }
  }
  return out.trim();
}

const URGENCY_LABEL = {
  high: "Высокий — дефектовка до рейса",
  medium: "Средний — на ближайшем ТО",
  low: "Низкий — на следующей проверке",
};

function renderDraftCard(payload) {
  if (!draftBody) {
    return;
  }
  const data = payload || {};
  lastDraftPayload = data;
  const ops = (data.operations || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const parts = (data.spare_parts || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const refs = (data.references || [])
    .map((row) => {
      const page = row.pdf_page || row.page;
      const quote = tidyExcerpt(row.quote || "", 160);
      const quoteBit = quote ? ` — «${escapeHtml(quote)}»` : "";
      return `<li>${escapeHtml(row.manual || "документ")}, стр. ${escapeHtml(page)}${quoteBit}</li>`;
    })
    .join("");
  draftBody.innerHTML = `
    <h3>Диагноз</h3>
    <p class="draft-conclusion">${escapeHtml(data.conclusion || "—")}</p>
    <h3>Приоритет</h3>
    <p>${escapeHtml(URGENCY_LABEL[data.urgency] || data.urgency || "—")}</p>
    <h3>Работы</h3>
    <ul>${ops || "<li>не указаны</li>"}</ul>
    <h3>Запчасти</h3>
    <ul>${parts || "<li>не указаны — найдите кнопкой выше и добавьте</li>"}</ul>
    <h3>Ссылки на руководство</h3>
    <ul>${refs || "<li>нет</li>"}</ul>
  `;
}

function syncSelectedPartsView() {
  if (!partsSelected || !partsSelectedList) {
    return;
  }
  if (!selectedSpareLabels.length) {
    partsSelected.hidden = true;
    partsSelectedList.innerHTML = "";
    if (partsAdd) {
      partsAdd.hidden = true;
      partsAdd.disabled = true;
    }
    return;
  }
  partsSelected.hidden = false;
  partsSelectedList.innerHTML = selectedSpareLabels
    .map((label) => `<li>${escapeHtml(label)}</li>`)
    .join("");
  if (partsAdd) {
    partsAdd.hidden = false;
    partsAdd.disabled = !draftId;
    partsAdd.textContent = draftId
      ? `Добавить выбранные в заявку (${selectedSpareLabels.length})`
      : "Сначала соберите черновик заявки";
  }
}

function toggleSpareSelection(index) {
  const row = lastSpareItems[index];
  if (!row || !row.label) {
    return;
  }
  const label = row.label;
  const pos = selectedSpareLabels.indexOf(label);
  if (pos >= 0) {
    selectedSpareLabels.splice(pos, 1);
  } else {
    selectedSpareLabels.push(label);
  }
  renderPartsList(lastSpareItems);
  syncSelectedPartsView();
}

function renderPartsList(items) {
  lastSpareItems = items || [];
  if (!partsList) {
    return;
  }
  if (!lastSpareItems.length) {
    partsList.innerHTML = "";
    syncSelectedPartsView();
    return;
  }
  partsList.innerHTML = lastSpareItems
    .map((row, index) => {
      const label = row.label || "";
      const picked = selectedSpareLabels.includes(label);
      // Только имя детали + короткий источник; тексты РЭ/процессов в список не выводим.
      const source =
        row.source_label ||
        (row.source === "manual" ? "РЭ/РК" : "Интернет (без магазина и производителя)");
      return `
      <li>
        <input type="checkbox" id="part-${index}" data-idx="${index}" ${picked ? "checked" : ""}>
        <label for="part-${index}">
          ${escapeHtml(label)}
          <span class="hint">${escapeHtml(source)}</span>
        </label>
        <button type="button" class="part-pick${picked ? " on" : ""}" data-idx="${index}">
          ${picked ? "Выбрано" : "Выбрать"}
        </button>
      </li>`;
    })
    .join("");
  partsList.querySelectorAll("input[type=checkbox]").forEach((box) => {
    box.addEventListener("change", () => {
      toggleSpareSelection(Number(box.getAttribute("data-idx")));
    });
  });
  partsList.querySelectorAll("button.part-pick").forEach((btn) => {
    btn.addEventListener("click", () => {
      toggleSpareSelection(Number(btn.getAttribute("data-idx")));
    });
  });
  syncSelectedPartsView();
}

function runPartsSearch(queryOverride) {
  if (!vehicle.value) {
    if (partsStatus) {
      partsStatus.textContent = "Сначала выберите машину.";
    }
    return;
  }
  const query = (queryOverride != null ? queryOverride : partsQuery?.value || "").trim();
  if (partsStatus) {
    partsStatus.textContent = "Ищем запчасти по поломке в интернете…";
  }
  if (partsSearch) {
    partsSearch.disabled = true;
  }
  fetch("/api/spare-parts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vehicle_id: vehicle.value,
      session_id: session.value || null,
      query,
    }),
  })
    .then((response) => response.json())
    .then((body) => {
      if (partsQuery && body.query) {
        partsQuery.value = body.query;
      }
      const items = body.items || [];
      // Новый поиск — сброс выбора, чтобы механик явно отметил позиции.
      selectedSpareLabels = [];
      renderPartsList(items);
      const fault = body.fault || {};
      const faultBit = fault.anomaly_type
        ? `${fault.anomaly_type}${fault.anomaly_title ? " · " + fault.anomaly_title : ""}`
        : "без кода проверки";
      if (partsStatus) {
        partsStatus.textContent = items.length
          ? `${body.mode_note || "Кандидаты для выбора."} Найдено ${items.length} по «${body.query || query}» (${faultBit}). Нажмите «Выбрать» у нужных позиций.`
          : `Ничего не найдено по «${body.query || query}». Уточните узел/код поломки.`;
      }
    })
    .catch((err) => {
      if (partsStatus) {
        partsStatus.textContent = `Ошибка поиска: ${err}`;
      }
    })
    .finally(() => {
      if (partsSearch) {
        partsSearch.disabled = false;
      }
    });
}

function addSelectedPartsToDraft() {
  if (!draftId) {
    if (partsStatus) {
      partsStatus.textContent = "Сначала нужен черновик заявки (разберите отклонение или нажмите «Собрать черновик»).";
    }
    return;
  }
  const selected = selectedSpareLabels.slice();
  if (!selected.length) {
    if (partsStatus) {
      partsStatus.textContent = "Сначала выберите запчасть кнопкой «Выбрать».";
    }
    return;
  }
  fetch(`/api/drafts/${draftId}/spare-parts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spare_parts: selected }),
  })
    .then((response) => response.json())
    .then((body) => {
      if (body.draft) {
        renderDraftCard(body.draft.payload || {});
        if (partsStatus) {
          partsStatus.textContent = `В заявку добавлено выбранных запчастей: ${selected.length}.`;
        }
      } else if (partsStatus) {
        partsStatus.textContent = body.detail || "Не удалось обновить заявку.";
      }
    })
    .catch((err) => {
      if (partsStatus) {
        partsStatus.textContent = `Ошибка: ${err}`;
      }
    });
}

/** Краткая формулировка шага для режима «профи». */
function shortenStepText(text) {
  let line = cleanStepText(text);
  const pageTail = line.match(/\(.*?стр\.\s*\d+\)\s*$/i);
  const ref = pageTail ? ` ${pageTail[0]}` : "";
  if (pageTail) {
    line = line.slice(0, pageTail.index).trim();
  }
  const cut = line.split(/(?<=[.!;])\s+/)[0] || line;
  const short = cut.length > 140 ? `${cut.slice(0, 137).trim()}…` : cut;
  return `${short}${ref}`.trim();
}

function syncProcModeButtons() {
  if (procModeFull) {
    procModeFull.classList.toggle("active", procedureMode === "full");
  }
  if (procModePro) {
    procModePro.classList.toggle("active", procedureMode === "pro");
  }
  if (procModeHint) {
    procModeHint.textContent =
      procedureMode === "pro"
        ? "Сокращённый: только действие и ссылка на стр.; рисунок PDF — по кнопке."
        : "Полный: действие + текст страницы + рисунок PDF.";
  }
}

function setProcedureMode(mode) {
  procedureMode = mode === "pro" ? "pro" : "full";
  localStorage.setItem("procMode", procedureMode);
  proPageOpen = false;
  syncProcModeButtons();
  if (repairSteps.length) {
    renderWalkStep();
  }
}

function mergeGuidePages(apiPages, journalSteps) {
  const merged = [...(apiPages || []), ...pagesFromJournal(journalSteps)];
  const seen = new Set();
  return merged.filter((row) => {
    const key = `${row.manual}|${row.pdf_page}`;
    if (!row.manual || !row.pdf_page || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function stepsFromGuidePages(pages) {
  return (pages || [])
    .filter((row) => row.manual && (row.pdf_page || row.page))
    .map((row, index) => {
      const pdf_page = row.pdf_page || row.page;
      const excerpt = (row.excerpt || "").trim();
      return {
        n: index + 1,
        text: excerpt || `Выполнить по руководству (${row.manual}, стр. ${pdf_page})`,
        manual: row.manual,
        pdf_page,
      };
    });
}

function parseManualPage(text) {
  const rows = pagesFromAnswer(text || "");
  return rows.length ? rows[0] : null;
}

function enrichStepsLocal(steps, pages) {
  const engine = selectedEngine();
  const refs = normalizePages(pages).filter((row) =>
    manualOkForEngine(row.manual, engine),
  );
  const byPage = new Map(
    (pages || [])
      .filter((row) => row.manual && (row.pdf_page || row.page))
      .map((row) => [`${row.manual}|${row.pdf_page || row.page}`, row]),
  );
  return (steps || []).map((step, index) => {
    const fromText = parseManualPage(step.text);
    const pair = refs[index] || refs[refs.length - 1];
    let manual = step.manual;
    let page = step.pdf_page || step.page;
    let foreign = step.foreign_manual || null;
    if (fromText) {
      if (manualOkForEngine(fromText.manual, engine)) {
        manual = manual || fromText.manual;
        page = page || fromText.pdf_page;
      } else {
        foreign = foreign || fromText.manual;
      }
    }
    if (manual && !manualOkForEngine(manual, engine)) {
      foreign = foreign || manual;
      manual = null;
      page = null;
    }
    if (pair) {
      manual = manual || pair.manual;
      page = page || pair.pdf_page;
    }
    const imageUrl =
      step.page_image_url ||
      (manual && page
        ? `/api/page-image?manual=${encodeURIComponent(manual)}&page=${page}`
        : null);
    const excerptRow = manual && page ? byPage.get(`${manual}|${page}`) : null;
    let excerpt = tidyExcerpt(step.excerpt || (excerptRow && excerptRow.excerpt) || "");
    let contents = Boolean(step.contents_page);
    if (excerpt && isContentsText(excerpt)) {
      contents = true;
      manual = null;
      page = null;
      excerpt = "";
    }
    return {
      ...step,
      text: cleanStepText(step.text),
      manual,
      pdf_page: page,
      page_image_url: manual && page ? imageUrl : null,
      excerpt,
      foreign_manual: foreign,
      contents_page: contents,
    };
  });
}

function showWalkthrough(steps, pages) {
  guidePages = pages || guidePages;
  let list = steps || [];
  if (!list.length && guidePages.length) {
    list = stepsFromGuidePages(guidePages);
  }
  repairSteps = enrichStepsLocal(list, guidePages);
  const withPages = repairSteps.filter((step) => step.manual && step.pdf_page).length;
  // Если шаги из ответа без ссылок на PDF — лучше показать страницы РК, чем пустую колонку.
  if (guidePages.length && withPages === 0) {
    repairSteps = enrichStepsLocal(stepsFromGuidePages(guidePages), guidePages);
  }
  stepIndex = 0;
  if (!repairSteps.length) {
    procedure.hidden = true;
    stopVoice();
    return;
  }
  procedure.hidden = false;
  proPageOpen = false;
  syncProcModeButtons();
  renderWalkStep();
}

function setDraftBadge(kind, text) {
  if (!draftBadge) {
    return;
  }
  draftBadge.className = `draft-badge draft-badge-${kind}`;
  draftBadge.textContent = text;
}

function showDraftPanel(body) {
  draftForm.hidden = true;
  if (draftEmpty) {
    draftEmpty.hidden = true;
  }
  ticket.textContent = "";
  if (body.draft) {
    draftId = body.draft.draft_id;
    renderDraftCard(body.draft.payload || {});
    draftReason.textContent = body.draft.reason || "";
    document.querySelector("#draft-urgency").value = body.draft.payload?.urgency || "medium";
    const viaFallback = (body.draft_notice || "").includes("резерв");
    setDraftBadge(
      "ready",
      viaFallback
        ? "Статус: черновик готов (собран резервом по страницам РК)"
        : "Статус: черновик готов — проверьте и отправьте",
    );
    draftStatus.textContent =
      "Состав заявки ниже обычным текстом. Смените приоритет при необходимости и нажмите кнопку — без неё в ТОиР ничего не уходит.";
    if (body.draft_notice) {
      draftReason.textContent = `${body.draft.reason || ""}\n${body.draft_notice}`.trim();
    }
    draftForm.hidden = false;
    if (draftBuild) {
      draftBuild.hidden = true;
    }
    syncSelectedPartsView();
    draftPanelScroll();
    return;
  }
  draftId = null;
  syncSelectedPartsView();
  const notice =
    body.draft_notice ||
    "Черновик заявки не создан. При отклонении агент должен вызвать draft_ticket — см. журнал шагов.";
  setDraftBadge("missing", "Статус: черновика нет — заявка ещё не собрана");
  draftStatus.textContent =
    "Ожидался явный черновик заявки (не только текст в ответе). Пока кнопка отправки недоступна — соберите черновик кнопкой ниже.";
  if (draftEmpty) {
    draftEmpty.hidden = false;
  }
  if (draftEmptyWhy) {
    draftEmptyWhy.textContent = notice;
  }
  if (draftBuild) {
    draftBuild.hidden = !(vehicle.value && session.value);
  }
}

function buildDraftNow() {
  if (!vehicle.value || !session.value) {
    if (draftEmptyWhy) {
      draftEmptyWhy.textContent = "Выберите машину и проверку с отклонением.";
    }
    return;
  }
  if (draftBuild) {
    draftBuild.disabled = true;
  }
  setDraftBadge("wait", "Статус: собираем черновик заявки…");
  fetch("/api/drafts/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vehicle_id: vehicle.value,
      session_id: session.value,
      answer: answer.innerText || "",
    }),
  })
    .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
    .then(({ ok, body }) => {
      if (!ok || !body.draft) {
        setDraftBadge("missing", "Статус: черновик не собран");
        if (draftEmptyWhy) {
          draftEmptyWhy.textContent = body.detail || body.draft_notice || "Не удалось собрать заявку.";
        }
        return;
      }
      showDraftPanel({ draft: body.draft, draft_notice: body.draft_notice });
    })
    .catch((err) => {
      setDraftBadge("missing", "Статус: ошибка сборки");
      if (draftEmptyWhy) {
        draftEmptyWhy.textContent = String(err);
      }
    })
    .finally(() => {
      if (draftBuild) {
        draftBuild.disabled = false;
      }
    });
}

function draftPanelScroll() {
  document.querySelector("#draft-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function pushRepairProgress() {
  if (!vehicle.value || !session.value || !repairSteps.length) {
    return;
  }
  const step = repairSteps[stepIndex];
  fetch("/api/repair-progress", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vehicle_id: vehicle.value,
      session_id: session.value,
      consult_id: consultId,
      step_index: stepIndex,
      step_total: repairSteps.length,
      status: "in_progress",
      summary: (step && step.text) || "",
    }),
  }).catch(() => {});
}

function showContradictionBanner(hints) {
  const box = document.querySelector("#contradiction-banner");
  if (!hints || !hints.length) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  const h = hints[0];
  const sources = (h.sources || [])
    .map((s) => `${s.manual}, стр. ${s.page}: ${s.note}`)
    .join("<br>");
  box.innerHTML = `<strong>Противоречие в руководствах:</strong> ${h.topic}<br>${sources}<br><em>${h.safe_rule}</em>`;
  box.hidden = false;
}

function loadStepPageImage(step, label) {
  walkCap.textContent = label;
  walkImg.alt = label;
  if (walkImgErr) {
    walkImgErr.hidden = true;
  }
  walkImg.onload = () => {
    if (walkImgErr) {
      walkImgErr.hidden = true;
    }
  };
  walkImg.onerror = () => {
    if (walkImgErr) {
      walkImgErr.hidden = false;
    }
  };
  walkImg.src =
    step.page_image_url ||
    `/api/page-image?manual=${encodeURIComponent(step.manual)}&page=${step.pdf_page}`;
}

function renderWalkStep() {
  const step = repairSteps[stepIndex];
  const pro = procedureMode === "pro";
  walkMeta.textContent = `Шаг ${step.n} из ${repairSteps.length}${pro ? " · профи" : ""}`;
  walkText.textContent = pro ? shortenStepText(step.text) : step.text;
  walkText.classList.toggle("pro", pro);
  walkPrev.disabled = stepIndex <= 0;
  walkNext.disabled = stepIndex >= repairSteps.length - 1;
  pushRepairProgress();

  const excerpt = (step.excerpt || "").trim();
  if (walkShowPage) {
    walkShowPage.hidden = true;
  }

  if (step.manual && step.pdf_page) {
    const label = `Руководство: ${step.manual} · стр. ${step.pdf_page}`;
    walkRef.textContent = label;
    walkRef.hidden = false;
    if (walkExcerpt) {
      if (!pro && excerpt && excerpt !== step.text) {
        walkExcerpt.hidden = false;
        walkExcerpt.textContent = `Текст со страницы:\n${tidyExcerpt(excerpt)}`;
      } else {
        walkExcerpt.hidden = true;
        walkExcerpt.textContent = "";
      }
    }
    if (pro && !proPageOpen) {
      walkFigure.hidden = true;
      if (walkShowPage) {
        walkShowPage.hidden = false;
        walkShowPage.textContent = "Показать страницу РК";
      }
    } else {
      loadStepPageImage(step, label);
      walkFigure.hidden = false;
      if (walkShowPage && pro) {
        walkShowPage.hidden = false;
        walkShowPage.textContent = "Скрыть страницу РК";
      }
    }
  } else {
    walkRef.hidden = true;
    walkFigure.hidden = true;
    if (walkExcerpt) {
      walkExcerpt.hidden = false;
      if (step.contents_page) {
        walkExcerpt.textContent =
          "Страница оглавления/содержания PDF запрещена. Нужна страница процедуры из РЭ или РК (не содержание). Повторите разбор.";
      } else if (step.foreign_manual) {
        walkExcerpt.textContent =
          `В ответе указано чужое руководство «${step.foreign_manual}» — для двигателя ${selectedEngine() || "этой машины"} оно не подходит. Нужны страницы своего РК (для ЯМЗ-236М2: 236.01.01 РК). Повторите разбор.`;
      } else {
        walkExcerpt.textContent =
          "Нет привязки к странице PDF: в шаге нет ссылки «свой документ, стр. N», и поиск по РК не дал страницу. Повторите разбор.";
      }
    }
  }
}

function goStep(delta) {
  const next = stepIndex + delta;
  if (next < 0 || next >= repairSteps.length) {
    return;
  }
  stepIndex = next;
  proPageOpen = false;
  renderWalkStep();
}

function goStepNumber(n) {
  if (n < 1 || n > repairSteps.length) {
    return;
  }
  stepIndex = n - 1;
  proPageOpen = false;
  renderWalkStep();
}

walkPrev.addEventListener("click", () => goStep(-1));
walkNext.addEventListener("click", () => goStep(1));
if (procModeFull) {
  procModeFull.addEventListener("click", () => setProcedureMode("full"));
}
if (procModePro) {
  procModePro.addEventListener("click", () => setProcedureMode("pro"));
}
if (walkShowPage) {
  walkShowPage.addEventListener("click", () => {
    proPageOpen = !proPageOpen;
    renderWalkStep();
  });
}
syncProcModeButtons();

const ORDINALS = {
  один: 1,
  два: 2,
  три: 3,
  четыре: 4,
  пять: 5,
  шесть: 6,
  семь: 7,
  восемь: 8,
  девять: 9,
  десять: 10,
  первый: 1,
  второй: 2,
  третий: 3,
  четвертый: 4,
  пятый: 5,
  шестой: 6,
  седьмой: 7,
  восьмой: 8,
  девятый: 9,
  десятый: 10,
};

const WAKE_WORD = "помощник";

function normalizeVoice(text) {
  return (text || "").toLowerCase().replace(/ё/g, "е").trim();
}

/** Команда только после кодового слова — шум цеха и разговоры игнорируются. */
function commandAfterWake(text) {
  const idx = text.indexOf(WAKE_WORD);
  if (idx < 0) {
    return null;
  }
  return text.slice(idx + WAKE_WORD.length).replace(/^[\s,.:;!?-]+/, "").trim();
}

function runStepCommand(cmd) {
  if (/(следующ|дальше|вперед|следующий шаг)/.test(cmd)) {
    goStep(1);
    return true;
  }
  if (/(назад|предыдущ|вернись|шаг назад|на шаг назад)/.test(cmd)) {
    goStep(-1);
    return true;
  }
  if (/(первый|в начало|сначала)/.test(cmd)) {
    goStepNumber(1);
    return true;
  }
  if (/(последн|конец)/.test(cmd)) {
    goStepNumber(repairSteps.length);
    return true;
  }
  const digit = cmd.match(/\bшаг\s*(\d{1,2})\b/) || cmd.match(/\b(\d{1,2})\s*шаг/);
  if (digit) {
    goStepNumber(parseInt(digit[1], 10));
    return true;
  }
  for (const [word, n] of Object.entries(ORDINALS)) {
    if (cmd.includes(word)) {
      goStepNumber(n);
      return true;
    }
  }
  return false;
}

function handleVoiceCommand(raw) {
  const text = normalizeVoice(raw);
  if (!text || !repairSteps.length) {
    return;
  }
  const cmd = commandAfterWake(text);
  if (cmd === null) {
    return;
  }
  if (!cmd) {
    voiceStatus.textContent = "Жду команду: например «следующий шаг» или «вернись на шаг назад».";
    return;
  }
  if (!runStepCommand(cmd)) {
    voiceStatus.textContent = `Не понял после «Помощник»: ${cmd}. Примеры: следующий шаг, назад, шаг 3.`;
  }
}

function secureEntryUrl() {
  const host = location.hostname || "localhost";
  const port = location.port || "8080";
  return `https://${host}:${port}${location.pathname}${location.search}`;
}

function ensureSecurePage() {
  const link = document.querySelector("#https-entry");
  const url = secureEntryUrl();
  if (link) {
    link.href = url;
    link.textContent = url;
  }
  if (location.protocol === "http:" && location.hostname) {
    location.replace(url);
  }
}

async function postAudioChunk(blob) {
  if (voiceBusy || !blob.size) {
    return;
  }
  voiceBusy = true;
  try {
    const response = await fetch("/api/voice", {
      method: "POST",
      headers: { "Content-Type": blob.type || "application/octet-stream" },
      body: blob,
    });
    const body = await response.json();
    if (body.text) {
      handleVoiceCommand(body.text);
    } else if (body.detail) {
      voiceStatus.textContent = String(body.detail);
    }
  } catch {
    voiceStatus.textContent = "Нет связи с сервером распознавания (Yandex).";
  } finally {
    voiceBusy = false;
  }
}

function pickAudioMime() {
  return (
    ["audio/ogg;codecs=opus", "audio/webm;codecs=opus", "audio/webm"].find((type) =>
      MediaRecorder.isTypeSupported(type),
    ) || ""
  );
}

function recordOnce(stream, mime, ms) {
  return new Promise((resolve) => {
    const chunks = [];
    const rec = new MediaRecorder(stream, { mimeType: mime });
    rec.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunks.push(event.data);
      }
    };
    rec.onstop = () => resolve(new Blob(chunks, { type: mime }));
    rec.start();
    window.setTimeout(() => {
      if (rec.state !== "inactive") {
        rec.stop();
      }
    }, ms);
  });
}

/** Один фрагмент на удержание кнопки — без бесконечного цикла (экономия SpeechKit). */
async function yandexPushToTalkOnce() {
  const mime = pickAudioMime();
  if (!mime) {
    voiceStatus.textContent = "Браузер не умеет записать аудио для SpeechKit.";
    return;
  }
  try {
    if (!micStream) {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
    voiceStatus.textContent = "Говорите…";
    const blob = await recordOnce(micStream, mime, 4500);
    await postAudioChunk(blob);
    if (voiceOn) {
      voiceStatus.textContent = "Удерживайте кнопку и скажите: Помощник, следующий шаг.";
    }
  } catch {
    voiceStatus.textContent = "Микрофон недоступен.";
  }
}

function setupBrowserRecognition() {
  if (!SpeechRecognition) {
    return;
  }
  recognition = new SpeechRecognition();
  recognition.lang = "ru-RU";
  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.onresult = (event) => {
    const last = event.results[event.results.length - 1];
    if (last.isFinal) {
      handleVoiceCommand(last[0].transcript);
    }
  };
  recognition.onend = () => {
    if (voiceOn && recognition) {
      try {
        recognition.start();
      } catch {
        /* busy */
      }
    }
  };
  recognition.onerror = (event) => {
    if (!voiceOn) {
      return;
    }
    const code = event.error || "unknown";
    if (code === "no-speech" || code === "aborted") {
      return;
    }
    voiceStatus.textContent =
      code === "network"
        ? "Браузер не достучался до облака STT. Попробуйте Edge/Chrome или клавиши ← →."
        : `Микрофон: ${code}. Дубль: ← →.`;
    if (code !== "network") {
      stopVoice();
    }
  };
}

function setupWalkKeysOnly() {
  document.addEventListener("keydown", (event) => {
    if (walkthrough.hidden || !repairSteps.length) {
      return;
    }
    if (event.key === "ArrowRight") {
      goStep(1);
    }
    if (event.key === "ArrowLeft") {
      goStep(-1);
    }
  });
}

function setupVoiceBrowser() {
  if (!window.isSecureContext) {
    voiceStatus.textContent = "Нужен HTTPS — страница перезагрузится.";
    voiceToggle.disabled = true;
    return;
  }
  if (!SpeechRecognition) {
    voiceStatus.textContent = "Нет Web Speech API — используйте ← → или Chrome/Edge.";
    voiceToggle.disabled = true;
    return;
  }
  setupBrowserRecognition();
  voiceToggle.addEventListener("click", () => {
    if (voiceOn) {
      stopVoice();
      return;
    }
    voiceOn = true;
    voiceToggle.textContent = "Голосовые команды: ВКЛ";
    voiceToggle.classList.add("on");
    voiceStatus.textContent = "Слушаю… «Помощник, следующий шаг».";
    voiceStatus.classList.add("on");
    try {
      recognition.start();
    } catch {
      voiceStatus.textContent = "Разрешите микрофон в браузере.";
      stopVoice();
    }
  });
}

function setupVoiceYandexPtt() {
  if (!window.isSecureContext) {
    voiceToggle.disabled = true;
    return;
  }
  voiceToggle.textContent = "Удерживать и говорить";
  let holding = false;
  const startHold = async () => {
    if (holding) {
      return;
    }
    holding = true;
    voiceOn = true;
    voiceToggle.classList.add("on");
    await yandexPushToTalkOnce();
    holding = false;
    voiceOn = false;
    voiceToggle.classList.remove("on");
  };
  voiceToggle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    startHold();
  });
}

function stopVoice() {
  voiceOn = false;
  voiceLoopToken += 1;
  if (micStream) {
    micStream.getTracks().forEach((track) => track.stop());
    micStream = null;
  }
  if (recognition) {
    try {
      recognition.stop();
    } catch {
      /* already stopped */
    }
  }
  voiceToggle.textContent = "Включить голосовые команды";
  voiceToggle.classList.remove("on");
  voiceStatus.classList.remove("on");
  if (voiceMode === "browser") {
    voiceStatus.textContent = "Нажмите кнопку. Кодовое слово «Помощник», затем команда.";
  }
}

document.querySelector("#ask").addEventListener("click", () => {
  renderAnswerDoc("Жду ответ…");
  procedure.hidden = true;
  stopVoice();
  ticket.textContent = "";
  draftForm.hidden = true;
  if (draftEmpty) {
    draftEmpty.hidden = true;
  }
  setDraftBadge("wait", "Статус: ждём ответ агента…");
  draftStatus.textContent = "Агент собирает процедуру и черновик заявки. Это может занять 1–3 минуты.";
  draftId = null;
  consultId = null;
  guidePages = [];
  document.querySelector("#contradiction-banner").hidden = true;
  fetch("/api/consult", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vehicle_id: vehicle.value,
      session_id: session.value,
      message: document.querySelector("#question").value,
      lang: document.querySelector("#lang").value,
    }),
  })
    .then((response) => response.json())
    .then((body) => {
      renderAnswerDoc(body.answer || body.error || "");
      consultId = body.consultation_id || null;
      showContradictionBanner(body.contradiction_hints);
      journal.textContent = JSON.stringify(
        { steps: body.steps, usage: body.usage, consultation_id: consultId },
        null,
        2,
      );
      const engine = body.engine || selectedEngine();
      const draftRefs = body.draft?.payload?.references || [];
      const answerPages = pagesFromAnswer(body.answer || "").filter((row) =>
        manualOkForEngine(row.manual, engine),
      );
      const foreignInAnswer = pagesFromAnswer(body.answer || "").filter(
        (row) => row.manual && !manualOkForEngine(row.manual, engine),
      );
      const mergedPages = mergeGuidePages(
        [...(body.guide_pages || []), ...draftRefs, ...answerPages],
        body.steps,
      );
      guidePages = mergedPages
        .filter(
          (row) =>
            row.manual &&
            (row.pdf_page || row.page) &&
            manualOkForEngine(row.manual, engine) &&
            !isContentsText(row.excerpt || ""),
        )
        .map((row) => ({
          manual: row.manual,
          pdf_page: row.pdf_page || row.page,
          excerpt: tidyExcerpt(row.excerpt || ""),
        }))
        .filter((row) => row.excerpt && !isContentsText(row.excerpt));
      if (!guidePages.length && foreignInAnswer.length) {
        console.warn(
          "В ответе только чужие руководства:",
          foreignInAnswer.map((row) => row.manual),
        );
      }
      let steps = body.repair_steps || [];
      if (!steps.length && body.draft?.payload?.operations) {
        steps = stepsFromDraft(body.draft.payload);
      }
      showWalkthrough(steps, guidePages);
      showDraftPanel(body);
      if (body.spare_query && partsQuery) {
        partsQuery.value = body.spare_query;
      }
      // После разбора поломки всегда подтягиваем интернет-кандидаты для выбора.
      if (session.value || body.spare_query || partsQuery?.value) {
        runPartsSearch(body.spare_query || partsQuery?.value || "");
      }
      loadVehicleCard(vehicle.value);
    })
    .catch((err) => {
      renderAnswerDoc(`Ошибка запроса: ${err}`);
      setDraftBadge("missing", "Статус: запрос не удался");
      draftStatus.textContent = "Повторите разбор. Черновик заявки не получен.";
    });
});

if (partsSearch) {
  partsSearch.addEventListener("click", () => runPartsSearch());
}
if (partsAdd) {
  partsAdd.addEventListener("click", () => addSelectedPartsToDraft());
}
if (draftBuild) {
  draftBuild.addEventListener("click", () => buildDraftNow());
}
if (partsQuery) {
  partsQuery.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runPartsSearch();
    }
  });
}

document.querySelector("#confirm").addEventListener("click", () => {
  if (!draftId) {
    return;
  }
  const urgency = document.querySelector("#draft-urgency").value;
  fetch(`/api/drafts/${draftId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ urgency }),
  })
    .then((response) => response.json())
    .then((body) => {
      if (body.ticket_id) {
        ticket.textContent = `Заявка ${body.ticket_id} создана в ТОиР. ${body.reason || ""}`;
        setDraftBadge("sent", `Статус: отправлено · ${body.ticket_id}`);
        draftStatus.textContent =
          "Заявка принята заглушкой ТОиР. Повторное подтверждение того же черновика вернёт тот же номер.";
        draftForm.hidden = true;
      } else {
        ticket.textContent = JSON.stringify(body);
        setDraftBadge("missing", "Статус: ТОиР не принял заявку");
      }
      document.querySelector("#vehicle-card").hidden = false;
      loadVehicleCard(vehicle.value);
    });
});

load();