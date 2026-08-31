(() => {
  "use strict";
  const prompt = document.querySelector("#fallback-prompt");
  const button = document.querySelector("#fallback-copy");
  if (!prompt || !button) return;

  async function copyPrompt() {
    const value = prompt.value.trim();
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
      } else {
        prompt.focus();
        prompt.select();
        if (!document.execCommand("copy")) throw new Error("copy failed");
        prompt.setSelectionRange(0, 0);
      }
      const old = button.textContent;
      button.textContent = "コピーしました";
      button.classList.add("is-ok");
      setTimeout(() => { button.textContent = old; button.classList.remove("is-ok"); }, 1800);
    } catch (_) {
      button.textContent = "長押しでコピー";
      prompt.focus();
      prompt.select();
    }
  }

  button.addEventListener("click", copyPrompt);
})();
