

// --- GvAI voice input ---
(function () {
  function findInput() {
    return document.querySelector("#messageInput")
      || document.querySelector("#userInput")
      || document.querySelector("textarea")
      || document.querySelector('input[type="text"]');
  }

  function findSendButton() {
    return document.querySelector("#sendBtn")
      || document.querySelector("#sendButton")
      || document.querySelector('button[type="submit"]')
      || Array.from(document.querySelectorAll("button")).find(b =>
          /send|ask|submit/i.test((b.textContent || "") + " " + (b.id || ""))
        );
  }

  function setInputValue(input, value) {
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.focus();
  }

  function installVoice() {
    const btn = document.querySelector("#voiceBtn");
    if (!btn) return;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      btn.disabled = true;
      btn.title = "Voice input is not supported in this browser";
      btn.textContent = "🎙️";
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;

    let listening = false;
    let finalText = "";

    btn.addEventListener("click", () => {
      if (listening) {
        recognition.stop();
        return;
      }

      finalText = "";
      btn.classList.add("listening");
      btn.textContent = "🛑";
      listening = true;

      try {
        recognition.start();
      } catch (err) {
        console.warn("Voice start failed:", err);
        listening = false;
        btn.classList.remove("listening");
        btn.textContent = "🎙️";
      }
    });

    recognition.onresult = (event) => {
      let interim = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += transcript;
        else interim += transcript;
      }

      const input = findInput();
      if (input) {
        const spoken = (finalText + interim).trim();
        if (spoken) setInputValue(input, spoken);
      }
    };

    recognition.onerror = (event) => {
      console.warn("Voice error:", event.error);
    };

    recognition.onend = () => {
      listening = false;
      btn.classList.remove("listening");
      btn.textContent = "🎙️";

      const input = findInput();
      const spoken = input ? input.value.trim() : "";

      // Do NOT auto-send yet. Safer first pass:
      // User can review the transcript, then tap Send.
      if (spoken) input.focus();
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installVoice);
  } else {
    installVoice();
  }
})();

// --- Force GvAI mic button install v2 ---
(function () {
  function installMicButton() {
    if (document.querySelector("#voiceBtn")) return;

    const input =
      document.querySelector("textarea") ||
      document.querySelector("#messageInput") ||
      document.querySelector("#userInput") ||
      document.querySelector('input[type="text"]');

    if (!input) return;

    const btn = document.createElement("button");
    btn.id = "voiceBtn";
    btn.className = "voice-btn";
    btn.type = "button";
    btn.title = "Talk to GvAI";
    btn.setAttribute("aria-label", "Talk to GvAI");
    btn.textContent = "🎙️";

    input.insertAdjacentElement("afterend", btn);

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      btn.disabled = true;
      btn.title = "Voice input not supported in this browser";
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;

    let listening = false;
    let finalText = "";

    btn.addEventListener("click", () => {
      if (listening) {
        recognition.stop();
        return;
      }

      finalText = "";
      listening = true;
      btn.classList.add("listening");
      btn.textContent = "🛑";

      try {
        recognition.start();
      } catch (err) {
        console.warn("Mic start failed", err);
        listening = false;
        btn.classList.remove("listening");
        btn.textContent = "🎙️";
      }
    });

    recognition.onresult = (event) => {
      let interim = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += transcript;
        else interim += transcript;
      }

      const spoken = (finalText + interim).trim();
      if (spoken) {
        input.value = spoken;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        input.focus();
      }
    };

    recognition.onend = () => {
      listening = false;
      btn.classList.remove("listening");
      btn.textContent = "🎙️";
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installMicButton);
  } else {
    installMicButton();
  }

  setTimeout(installMicButton, 1000);
})();
