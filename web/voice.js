(function () {
  function installVoice() {
    const input = document.querySelector("#prompt");
    const sendBtn = Array.from(document.querySelectorAll("button"))
      .find(b => (b.textContent || "").trim().toLowerCase() === "send");

    if (!input || !sendBtn) return;
    if (document.querySelector("#voiceBtn")) return;

    const btn = document.createElement("button");
    btn.id = "voiceBtn";
    btn.type = "button";
    btn.textContent = "🎙️";
    btn.title = "Talk to GvAI";
    btn.style.marginRight = "10px";
    btn.style.minWidth = "56px";
    btn.style.borderRadius = "16px";
    btn.style.border = "1px solid rgba(255,255,255,.2)";
    btn.style.background = "rgba(255,255,255,.08)";
    btn.style.color = "white";
    btn.style.fontSize = "22px";
    btn.style.cursor = "pointer";

    sendBtn.parentNode.insertBefore(btn, sendBtn);

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      btn.textContent = "❌";
      btn.title = "Voice input not supported";
      return;
    }

    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = false;

    let finalText = "";

    btn.onclick = () => {
      finalText = "";
      btn.textContent = "🛑";
      rec.start();
    };

    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t;
        else interim += t;
      }

      input.value = (finalText + interim).trim();
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      input.focus();
    };

    rec.onend = () => {
      btn.textContent = "🎙️";
    };
  }

  installVoice();
  setInterval(installVoice, 1000);
})();
