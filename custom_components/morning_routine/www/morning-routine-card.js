class MorningRoutineCard extends HTMLElement {
  setConfig() {}
  connectedCallback() {
    this.textContent = "Morning Routine";
  }
}
customElements.define("morning-routine-card", MorningRoutineCard);
