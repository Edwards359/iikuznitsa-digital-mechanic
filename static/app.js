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
const walkText = document.querySelector("#walk-text");
const walkFigure = document.querySelector("#walk-figure");
const walkCap = document.querySelector("#walk-cap");
const walkImg = document.querySelector("#walk-img");
const walkPrev = document.querySelector("#walk-prev");
const walkNext = document.querySelector("#walk-next");

let vehicles = [];
let draftId = null;
let repairSteps = [];
let stepIndex = 0;

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

function showWalkthrough(steps) {
  repairSteps = steps || [];
  stepIndex = 0;
  if (!repairSteps.length) {
    walkthrough.hidden = true;
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
    walkCap.textContent = `${step.manual}, стр. ${step.pdf_page}`;
    walkImg.alt = `${step.manual} стр. ${step.pdf_page}`;
    walkImg.src = `/api/page-image?manual=${encodeURIComponent(step.manual)}&page=${step.pdf_page}`;
    walkFigure.hidden = false;
  } else {
    walkFigure.hidden = true;
  }
}

walkPrev.addEventListener("click", () => {
  if (stepIndex > 0) {
    stepIndex -= 1;
    renderWalkStep();
  }
});

walkNext.addEventListener("click", () => {
  if (stepIndex < repairSteps.length - 1) {
    stepIndex += 1;
    renderWalkStep();
  }
});

document.querySelector("#ask").addEventListener("click", () => {
  answer.textContent = "жду ответ…";
  draftBox.hidden = true;
  figures.hidden = true;
  figuresBody.innerHTML = "";
  walkthrough.hidden = true;
  ticket.textContent = "";
  draftId = null;
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
      showFigures({ ...body, pages: body.guide_pages || [] });
      showWalkthrough(body.repair_steps || []);
      if (body.draft) {
        draftId = body.draft.draft_id;
        draftBody.textContent = JSON.stringify(body.draft.payload, null, 2);
        draftReason.textContent = body.draft.reason || "";
        draftBox.hidden = false;
        if (!repairSteps.length && body.draft.payload.operations) {
          showWalkthrough(
            body.draft.payload.operations.map((text, index) => ({
              n: index + 1,
              text,
              manual: null,
              pdf_page: null,
            })),
          );
        }
        showFigures({ pages: body.draft.payload.references || [] });
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