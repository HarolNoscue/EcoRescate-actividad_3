"use strict";

// API HTTP: comandos y consultas se encuentran detrás de Nginx.
const COMMAND_API = "/api/command";
const QUERY_API = "/api/query";
const byId = (id) => document.getElementById(id);

function escapeHtml(value) {
  const replacements = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(value).replace(/[&<>"']/g, (character) => replacements[character]);
}

function showMessage(message, isError = false) {
  const notification = byId("flash");
  notification.textContent = message;
  notification.classList.toggle("flash--error", isError);
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || JSON.stringify(body));
  }
  return body;
}

function setDefaultExpiry() {
  const date = new Date(Date.now() + 4 * 60 * 60 * 1000);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  byId("expiresInput").value = date.toISOString().slice(0, 16);
}

function offerTemplate(offer) {
  const available = offer.status === "AVAILABLE";
  const statusClass = available ? "" : "off";
  const disabled = available ? "" : "disabled";
  const expires = new Date(offer.expires_at).toLocaleString("es-CO");
  return `
    <article class="offer">
      <div class="row">
        <small>${escapeHtml(offer.provider)} · ${escapeHtml(offer.zone)}</small>
        <span class="pill ${statusClass}">${escapeHtml(offer.status)}</span>
      </div>
      <h3>${escapeHtml(offer.title)}</h3>
      <div class="row">
        <span>${escapeHtml(offer.available_quantity)} / ${escapeHtml(offer.total_quantity)}
          unidades · ${escapeHtml(offer.category)}</span>
        <button type="button" data-action="reserve" data-offer-id="${escapeHtml(offer.id)}" ${disabled}>
          Reservar
        </button>
      </div>
      <small>Caduca: ${escapeHtml(expires)}</small>
    </article>`;
}

function claimTemplate(claim) {
  const cancelButton = claim.status === "ACTIVE"
    ? `<button type="button" class="light" data-action="cancel" data-claim-id="${escapeHtml(claim.id)}">Cancelar</button>`
    : "";
  return `
    <div class="claim row">
      <span>
        <b>${escapeHtml(claim.organization)}</b> · ${escapeHtml(claim.quantity)}
        unidades · ${escapeHtml(claim.status)}
        <small>Donación ${escapeHtml(claim.offer_id.slice(0, 8))}</small>
      </span>
      ${cancelButton}
    </div>`;
}

async function refresh() {
  try {
    const [offers, claims, metrics] = await Promise.all([
      apiRequest(`${QUERY_API}/offers`),
      apiRequest(`${QUERY_API}/claims`),
      apiRequest(`${QUERY_API}/metrics`),
    ]);

    byId("statOffers").textContent = metrics.published_offers;
    byId("statClaims").textContent = metrics.active_claims;
    byId("statUnits").textContent = metrics.reserved_units;
    byId("offers").innerHTML = offers.length
      ? offers.map(offerTemplate).join("")
      : "No hay donaciones publicadas todavía.";
    byId("claims").innerHTML = claims.length
      ? claims.map(claimTemplate).join("")
      : "Aún no hay reservas.";
  } catch (error) {
    showMessage(`No fue posible consultar servicios: ${error.message}`, true);
  }
}

async function publish(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  data.quantity = Number(data.quantity);
  data.expires_at = new Date(data.expires_at).toISOString();

  try {
    await apiRequest(`${COMMAND_API}/offers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    showMessage("Donación aceptada. Esperando proyección por evento…");
    window.setTimeout(refresh, 900);
    form.reset();
    setDefaultExpiry();
  } catch (error) {
    showMessage(error.message, true);
  }
}

async function reserve(offerId) {
  const organization = window.prompt("Nombre de la organización social:");
  if (!organization) return;
  const quantity = Number(window.prompt("¿Cuántas unidades quieres reservar?", "1"));
  if (!Number.isInteger(quantity) || quantity < 1) {
    showMessage("Cantidad no válida", true);
    return;
  }

  try {
    await apiRequest(`${COMMAND_API}/offers/${offerId}/claims`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ organization, quantity }),
    });
    showMessage("Reserva confirmada en el servicio de comandos. La vista se actualizará.");
    window.setTimeout(refresh, 900);
  } catch (error) {
    showMessage(error.message, true);
  }
}

async function cancelClaim(claimId) {
  if (!window.confirm("¿Cancelar esta reserva?")) return;
  try {
    await apiRequest(`${COMMAND_API}/claims/${claimId}/cancel`, { method: "POST" });
    showMessage("Cancelación registrada; se reflejará en la vista.");
    window.setTimeout(refresh, 900);
  } catch (error) {
    showMessage(error.message, true);
  }
}

// Delegación de eventos: no necesitamos onclick embebidos en el HTML.
function handleAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  if (button.dataset.action === "reserve") reserve(button.dataset.offerId);
  if (button.dataset.action === "cancel") cancelClaim(button.dataset.claimId);
}

byId("publishForm").addEventListener("submit", publish);
byId("refreshButton").addEventListener("click", refresh);
byId("offers").addEventListener("click", handleAction);
byId("claims").addEventListener("click", handleAction);
setDefaultExpiry();
refresh();
window.setInterval(refresh, 5000);
