const demo = document.querySelector("#demo");
const vehicle = document.querySelector("#vehicle");
const session = document.querySelector("#session");
const answer = document.querySelector("#answer");
const journal = document.querySelector("#journal");
const draftBox = document.querySelector("#draft");
const draftBody = document.querySelector("#draft-body");
const draftReason = document.querySelector("#draft-reason");
const ticket = document.querySelector("#ticket");
let vehicles = [];
let draftId = null;

function fillSessions(vehicleId, preferred) {
  const row = vehicles.find((item) => item.vehicle_id === vehicleId);
  const list = row ? row.sessions : [];
  session.innerHTML = list
    .map(
      (item) =>
        `<option value="${item.session_id}">${item.session_id} · ${item.status}${item.anomaly_type ? " " + item.anomaly_type : ""}</option>`,
    )
    .join("");
  if (preferred) {
    session.value = preferred;
  }
}

function load() {
  fetch("/api/health")
    .then((response) => response.json())
    .then((health) => {
      document.querySelector("#health").textContent =
        `модель ${health.model}, фрагментов ${health.index_chunks}, машин ${health.vehicles}`;
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
  fetch("/api/demo-sessions")
    .then((response) => response.json())
    .then((sessions) => {
      demo.innerHTML =
        `<option value="">— выбрать сценарий —</option>` +
        sessions
          .map(
            (item) =>
              `<option value="${item.vehicle_id}|${item.session_id}">${item.label}: ${item.vehicle_id} / ${item.session_id}</option>`,
          )
          .join("");
    });
}

demo.addEventListener("change", () => {
  if (!demo.value) {
    return;
  }
  const [vehicleId, sessionId] = demo.value.split("|");
  vehicle.value = vehicleId;
  fillSessions(vehicleId, sessionId);
});

vehicle.addEventListener("change", () => fillSessions(vehicle.value));

document.querySelector("#ask").addEventListener("click", () => {
  answer.textContent = "жду ответ…";
  draftBox.hidden = true;
  ticket.textContent = "";
  draftId = null;
  fetch("/api/consult", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vehicle_id: vehicle.value,
      session_id: session.value,
      message: document.querySelector("#question").value,
    }),
  })
    .then((response) => response.json())
    .then((body) => {
      answer.textContent = body.answer || body.error || "";
      journal.textContent = JSON.stringify({ steps: body.steps, usage: body.usage }, null, 2);
      if (body.draft) {
        draftId = body.draft.draft_id;
        draftBody.textContent = JSON.stringify(body.draft.payload, null, 2);
        draftReason.textContent = body.draft.reason || "";
        draftBox.hidden = false;
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

load();
