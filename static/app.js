const quick = document.querySelector("#quick");
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
    });
  fetch("/api/quick-checks")
    .then((response) => response.json())
    .then((sessions) => {
      quick.innerHTML =
        `<option value="">— не использовать —</option>` +
        sessions
          .map(
            (item) =>
              `<option value="${item.vehicle_id}|${item.session_id}">${item.label}: ${item.vehicle_id} / ${item.session_id}</option>`,
          )
          .join("");
    });
  setupVoice();
}

quick.addEventListener("change", () => {
  if (!quick.value) {
    return;
  }
  const [vehicleId, sessionId] = quick.value.split("|");
  vehicle.value = vehicleId;
  fillSessions(vehicleId, sessionId);
});

vehicle.addEventListener("change", () => fillSessions(vehicle.value));

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
  const refs = normalizePages(payload.references || []);
  return ops.map((text, index) => {
    const ref = refs[index] || refs[refs.length - 1];
    return {
      n: index + 1,
      text,
      manual: ref ? ref.manual : null,
      pdf_page: ref ? ref.pdf_page : null,
    };
  });
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
  repairSteps = enrichStepsLocal(steps, guidePages);
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

function httpsVoiceUrl() {
  const host = location.hostname || "localhost";
  const port = location.port || "8080";
  if (location.protocol === "https:") {
    return location.href;
  }
  return `https://${host}:${port}${location.pathname}${location.search}`;
}

function showHttpsHint() {
  const box = document.querySelector("#https-hint");
  if (!box || window.isSecureContext || location.protocol === "file:") {
    return;
  }
  const url = httpsVoiceUrl();
  box.hidden = false;
  box.innerHTML =
    `Голос «Помощник» — тот же порт 8080 по HTTPS: <a href="${url}">${url}</a> (примите сертификат). HTTP для http://…:8080 тоже на этом порту.`;
}

function setupVoice() {
  showHttpsHint();
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
  if (!window.isSecureContext) {
    voiceStatus.textContent =
      "Голос по HTTP недоступен — ссылка на HTTPS в шапке. Пока: «Следующий шаг» или клавиши ← →.";
    voiceToggle.addEventListener("click", () => {
      voiceStatus.textContent = `Откройте ${httpsVoiceUrl()} — там включится микрофон.`;
    });
    return;
  }
  if (!SpeechRecognition) {
    voiceToggle.disabled = true;
    voiceStatus.textContent = "Голосовые команды недоступны в этом браузере (нужен Chrome/Edge).";
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
    if (voiceOn && !walkthrough.hidden) {
      try {
        recognition.start();
      } catch {
        /* повторный start после паузы */
      }
    }
  };
  recognition.onerror = (event) => {
    if (!voiceOn) {
      return;
    }
    const code = event.error || "unknown";
    if (code === "not-allowed") {
      voiceStatus.textContent = "Доступ к микрофону запрещён — разрешите в браузере.";
    } else {
      voiceStatus.textContent = `Микрофон: ${code}; нажмите кнопку ещё раз.`;
    }
    voiceOn = false;
    voiceToggle.textContent = "Включить голосовые команды";
    voiceToggle.classList.remove("on");
  };
  voiceToggle.addEventListener("click", () => {
    if (voiceOn) {
      stopVoice();
      return;
    }
    voiceOn = true;
    voiceToggle.textContent = "Голосовые команды: ВКЛ";
    voiceToggle.classList.add("on");
    voiceStatus.textContent =
      "Сначала «Помощник», затем команда: «следующий шаг», «вернись на шаг назад», «шаг 3». Без кодового слова — тишина.";
    voiceStatus.classList.add("on");
    try {
      recognition.start();
    } catch {
      voiceStatus.textContent = "Не удалось включить микрофон.";
      voiceOn = false;
    }
  });
}

function stopVoice() {
  voiceOn = false;
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
  if (SpeechRecognition) {
    voiceStatus.textContent =
      "Нажмите кнопку и разрешите микрофон. Команды только с «Помощник» в начале.";
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