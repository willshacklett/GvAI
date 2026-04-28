(function () {
  const API_MARKER = "/api/chat";

  function speak(text) {
    if (!text || !("speechSynthesis" in window)) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 0.95;
    u.pitch = 1;
    u.volume = 1;
    speechSynthesis.speak(u);
  }

  function getPrompt() {
    return document.querySelector("#prompt") || document.querySelector("textarea");
  }

  function makeVoiceButton() {
    if (document.querySelector("#gvVoiceDock")) return;

    const dock = document.createElement("button");
    dock.id = "gvVoiceDock";
    dock.type = "button";
    dock.textContent = "🎙️";
    dock.title = "Talk to GvAI";
    document.body.appendChild(dock);

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      dock.textContent = "❌";
      dock.title = "Voice input not supported in this browser";
      dock.disabled = true;
      return;
    }

    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = false;

    let finalText = "";

    dock.onclick = function () {
      finalText = "";
      dock.textContent = "🛑";
      try {
        rec.start();
      } catch (e) {
        console.warn("Voice start failed", e);
        dock.textContent = "🎙️";
      }
    };

    rec.onresult = function (event) {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += t;
        else interim += t;
      }

      const input = getPrompt();
      if (input) {
        input.value = (finalText + interim).trim();
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        input.focus();
      }
    };

    rec.onend = function () {
      dock.textContent = "🎙️";
    };
  }

  function patchFetchForSpeech() {
    if (window.__gvVoiceFetchPatched) return;
    window.__gvVoiceFetchPatched = true;

    const originalFetch = window.fetch;
    window.fetch = async function (...args) {
      const res = await originalFetch.apply(this, args);

      try {
        const url = String(args[0] && args[0].url ? args[0].url : args[0]);
        if (url.includes(API_MARKER)) {
          const clone = res.clone();
          clone.json().then(data => {
            const text = data.reply || data.response || data.message;
            if (text) speak(text);
          }).catch(() => {});
        }
      } catch (e) {}

      return res;
    };
  }

  function boot() {
    makeVoiceButton();
    patchFetchForSpeech();
  }

  boot();
  window.addEventListener("DOMContentLoaded", boot);
  setInterval(boot, 1000);
})();
