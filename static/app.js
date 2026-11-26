const vehicle = document.querySelector("#vehicle");
const session = document.querySelector("#session");
const answer = document.querySelector("#answer");
const journal = document.querySelector("#journal");
const draftBox = document.querySelector("#draft");
const draftBody = document.querySelector("#draft-body");
const draftReason = document.querySelector("#draft-reason");
const ticket = document.querySelector("#ticket");
const figures = document.querySelector("#figures");
const figuresBody = document.querySelector("#figures-body");
const walkthrough = document.querySelector("#walkthrough");
const walkMeta = document.querySelector("#walk-meta");
const walkRef = document.querySelector("#walk-ref");
const walkText = document.querySelector("#walk-text");
const walkFigure = document.querySelector("#walk-figure");
const walkCap = document.querySelector("#walk-cap");
const walkImg = document.querySelector("#walk-img");
const walkPrev = document.querySelector("#walk-prev");
const walkNext = document.querySelector("#walk-next");
const voiceToggle = document.querySelector("#voice-toggle");
const voiceStatus = document.querySelector("#voice-status");

let vehicles = [];
let draftId = null;
let repairSteps = [];
let guidePages = [];
let stepIndex = 0;
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
            `${draft}${err}${rubOne}<br><span class="hint">${row.answer_preview || ""}</span></li>`
          );
        })
        .join("") || "<li class='hint'>пока пусто</li>";
      document.querySelector("#vehicle-tickets").innerHTML = (body.tickets || [])
        .map(
          (row) =>
            `<li>${formatWhen(row.created_at)} · ${row.ticket_id} · проверка ${row.session_id}</li>`,
        )
        .join("") || "<li class='hint'>заявок нет</li>";
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
        `модель ${health.model}, фрагментов руководств ${health.index_chunks}, машин ${health.vehicles}`;
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

function stepsFromGuidePages(pages) {
  return normalizePages(pages).map((row, index) => ({
    n: index + 1,
    text: `Иллюстрация процедуры (${row.manual}, стр. ${row.pdf_page})`,
    manual: row.manual,
    pdf_page: row.pdf_page,
  }));
}

function enrichStepsLocal(steps, pages) {
  const refs = normalizePages(pages);
  return (steps || []).map((step, index) => {
    const pair = refs[index] || refs[refs.length - 1];
    let manual = step.manual;
    let page = step.pdf_page || step.page;
    if (pair) {
      manual = manual || pair.manual;
      page = page || pair.pdf_page;
    }
    const imageUrl =
      step.page_image_url ||
      (manual && page
        ? `/api/page-image?manual=${encodeURIComponent(manual)}&page=${page}`
        : null);
    return { ...step, manual, pdf_page: page, page_image_url: imageUrl };
  });
}

function showWalkthrough(steps, pages) {
  guidePages = pages || guidePages;
  let list = steps || [];
  if (list.length <= 1 && guidePages.length > 1) {
    const fromPages = stepsFromGuidePages(guidePages);
    if (fromPages.length > list.length) {
      list = fromPages;
    }
  }
  repairSteps = enrichStepsLocal(list, guidePages);
  stepIndex = 0;
  if (!repairSteps.length) {
    walkthrough.hidden = true;
    stopVoice();
    return;
  }
  walkthrough.hidden = false;
  renderWalkStep();
}

function renderWalkStep() {
  const step = repairSteps[stepIndex];
  walkMeta.textContent = `Шаг ${step.n} из ${repairSteps.length}`;
  walkText.textContent = step.text;
  walkPrev.disabled = stepIndex <= 0;
  walkNext.disabled = stepIndex >= repairSteps.length - 1;
  if (step.manual && step.pdf_page) {
    const label = `Руководство: ${step.manual} · стр. ${step.pdf_page}`;
    walkRef.textContent = label;
    walkRef.hidden = false;
    walkCap.textContent = label;
    walkImg.alt = label;
    walkImg.src =
      step.page_image_url ||
      `/api/page-image?manual=${encodeURIComponent(step.manual)}&page=${step.pdf_page}`;
    walkFigure.hidden = false;
  } else {
    walkRef.hidden = true;
    walkFigure.hidden = true;
  }
}

function goStep(delta) {
  const next = stepIndex + delta;
  if (next < 0 || next >= repairSteps.length) {
    return;
  }
  stepIndex = next;
  renderWalkStep();
}

function goStepNumber(n) {
  if (n < 1 || n > repairSteps.length) {
    return;
  }
  stepIndex = n - 1;
  renderWalkStep();
}

walkPrev.addEventListener("click", () => goStep(-1));
walkNext.addEventListener("click", () => goStep(1));

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
  answer.textContent = "жду ответ…";
  draftBox.hidden = true;
  figures.hidden = true;
  figuresBody.innerHTML = "";
  walkthrough.hidden = true;
  stopVoice();
  ticket.textContent = "";
  draftId = null;
  guidePages = [];
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
      answer.textContent = body.answer || body.error || "";
      journal.textContent = JSON.stringify({ steps: body.steps, usage: body.usage }, null, 2);
      const draftRefs = body.draft?.payload?.references || [];
      guidePages = normalizePages([...(body.guide_pages || []), ...draftRefs]);
      showFigures({ ...body, pages: guidePages });
      let steps = body.repair_steps || [];
      if (!steps.length && body.draft?.payload?.operations) {
        steps = stepsFromDraft(body.draft.payload);
      }
      showWalkthrough(steps, guidePages);
      if (body.draft) {
        draftId = body.draft.draft_id;
        draftBody.textContent = JSON.stringify(body.draft.payload, null, 2);
        draftReason.textContent = body.draft.reason || "";
        draftBox.hidden = false;
        showFigures({ pages: guidePages.length ? guidePages : draftRefs });
      }
      loadVehicleCard(vehicle.value);
    });
});

document.querySelector("#confirm").addEventListener("click", () => {
  if (!draftId) {
    return;
  }
  fetch(`/api/drafts/${draftId}/confirm`, { method: "POST" })
    .then((response) => response.json())
    .then((body) => {
      ticket.textContent = body.ticket_id
        ? `Заявка ${body.ticket_id}. ${body.reason || ""}`
        : JSON.stringify(body);
      loadVehicleCard(vehicle.value);
    });
});

function showFigures(body) {
  const pages = body.pages || [];
  const fromSteps = (body.steps || [])
    .map((step) => {
      try {
        const data = JSON.parse(step.result);
        if (Array.isArray(data)) {
          return data
            .filter((row) => row.page_image_url)
            .map((row) => ({ manual: row.manual, pdf_page: row.page }));
        }
      } catch {
        return [];
      }
      return [];
    })
    .flat();
  const merged = [...pages, ...fromSteps];
  const seen = new Set();
  const unique = merged.filter((row) => {
    const page = row.pdf_page || row.page;
    const key = `${row.manual}|${page}`;
    if (!row.manual || !page || seen.has(key)) {
      return false;
    }
    seen.add(key);
    row.pdf_page = page;
    return true;
  });
  if (!unique.length) {
    figures.hidden = true;
    return;
  }
  figuresBody.innerHTML = unique
    .map(
      (row) =>
        `<figure class="page-fig"><figcaption>${row.manual}, стр. ${row.pdf_page}</figcaption>` +
        `<img loading="lazy" alt="${row.manual} стр. ${row.pdf_page}" ` +
        `src="/api/page-image?manual=${encodeURIComponent(row.manual)}&page=${row.pdf_page}"></figure>`,
    )
    .join("");
  figures.hidden = false;
}

load();