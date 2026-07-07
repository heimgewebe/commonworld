const MODE_COPY = {
  map: "Karte: lokale Commons erscheinen als Orte. Hybride Commons tragen eine digitale Säule.",
  aether: "Äther: digitale Commons erscheinen als thematische, horizontal swipebare Ströme mit Ortssignalen für hybride Projekte.",
};

const buttons = [...document.querySelectorAll("[data-mode-target]")];
const summary = document.querySelector("#mode-summary");

function setMode(mode) {
  if (!Object.prototype.hasOwnProperty.call(MODE_COPY, mode)) return;
  document.body.dataset.mode = mode;
  summary.textContent = MODE_COPY[mode];
  buttons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.modeTarget === mode));
  });
}

buttons.forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.modeTarget));
});
