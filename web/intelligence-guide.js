(function (root) {
  function mount(session, regional, adapters) {
    const api = root.GVAIIntelligence;
    const guide = document.getElementById("intelligence-guide");
    const pane = document.getElementById("regional-ask-pane");
    pane.open = true;
    const form = document.getElementById("regional-ask-form");
    const question = document.getElementById("regional-question");
    const status = document.getElementById("regional-ask-status");
    const button = form.querySelector("button");
    let busy = false;
    const open = () => { guide.open = true; pane.open = true; question.focus(); };
    const ask = (message, audience) => {
      if (busy) { status.textContent = "Wait for the current answer before sending another question."; open(); return; }
      if (audience) adapters.set_audience({ audience });
      question.value = message; open(); form.requestSubmit();
    };
    session.subscribe(state => {
      document.getElementById("intelligence-context").textContent =
        `${{ laborers: "Laborer", business: "Business", government: "Government" }[state.audience]} · ${state.selectedRegion?.label || "No place selected"}`;
      const conversation = document.getElementById("intelligence-conversation");
      conversation.innerHTML = state.messages.map(message =>
        `<article class="intelligence-message"><strong>${message.role === "user" ? "You" : "GVAI · AI interpretation"}</strong><p>${api.escape(message.content)}</p></article>`
      ).join("");
      conversation.scrollTop = conversation.scrollHeight;
      document.getElementById("intelligence-starters").hidden = state.messages.length > 0;
      document.getElementById("intelligence-why-content").innerHTML = api.whyMarkup(state.evidence, state.audience) +
        api.occupationMarkup(state.occupationEvidence[state.selectedRegion?.id]) +
        (state.scenario ? `<p>Scenario output · Assumed cohort ${api.escape(state.scenario.assumptions.workers)} workers,
          ${api.escape(state.scenario.assumptions.weeklyHours)} hours/week, ${api.escape(state.scenario.assumptions.taskShare)}% affected tasks,
          ${api.escape(state.scenario.assumptions.timeSaving)}% assumed saving:
          ${api.escape(state.scenario.result.potentialHours)} potential task hours/week. Not observed hours or predicted jobs.</p>` : "");
      document.getElementById("intelligence-comparison-content").innerHTML = api.comparisonMarkup(state.comparisons, state.audience, state.occupationEvidence);
      document.getElementById("intelligence-action-status").textContent = state.outcomes.map(outcome =>
        `${outcome.type.replaceAll("_", " ")}: ${outcome.status}${outcome.detail ? ` (${outcome.detail})` : ""}`
      ).join(" · ");
    });
    document.getElementById("ask-btn").addEventListener("click", open);
    document.getElementById("intelligence-clear").addEventListener("click", () => {
      if (busy) { status.textContent = "Wait for the current answer before starting a new conversation."; return; }
      session.clearConversation(); document.getElementById("regional-ask-reply").textContent = "";
      status.textContent = "New conversation. Your regional selection and shortlist remain.";
    });
    document.getElementById("intelligence-starters").addEventListener("click", event => {
      const prompt = event.target.closest("[data-intelligence-prompt]");
      if (prompt) ask(prompt.textContent, prompt.dataset.audience);
    });
    document.getElementById("intelligence-why-ask").addEventListener("click", () =>
      ask("Why does this place matter for my investigation? Explain the evidence, tradeoffs, and what is missing."));
    document.getElementById("intelligence-add-region").addEventListener("click", () => {
      try { session.addComparison(); status.textContent = "Selected place added to your shortlist."; }
      catch (error) { status.textContent = error.message; }
    });
    document.getElementById("intelligence-compare-ask").addEventListener("click", () => {
      if (session.get().comparisons.length < 2) { status.textContent = "Add at least two places before comparing."; return; }
      ask("Compare the shortlisted places for my stated criteria. Explain supported differences, tradeoffs and missing signals.");
    });
    document.getElementById("intelligence-comparison-content").addEventListener("click", event => {
      const remove = event.target.closest("[data-remove-region]");
      if (remove) session.removeComparison(remove.dataset.removeRegion);
    });
    document.getElementById("regional-ask-audience").addEventListener("change", event =>
      adapters.set_audience({ audience: event.target.value }));
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (busy) return;
      const message = question.value.trim();
      if (!message || new TextEncoder().encode(message).length > 8192) { status.textContent = "Enter a question up to 8 KiB."; return; }
      if (["loading", "refreshing"].includes(regional.get().status)) { status.textContent = "Wait for the selected-region evidence to finish loading."; return; }
      session.addMessage("user", message);
      const context = session.context();
      // Bound the encoded history, not only its message count.
      while (new TextEncoder().encode(JSON.stringify(context)).length > 60000 && context.messages.length) context.messages.shift();
      const actionContext = api.createActionContext(session);
      const isCurrent = actionContext.isCurrent;
      busy = true; button.disabled = true;
      document.getElementById("regional-ask-reply").textContent = "";
      status.textContent = "Reviewing your investigation and supported regional evidence...";
      try {
        const model = regional.get().model;
        const response = await fetch((root.GVAI_API_BASE || "") + "/api/chat", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, intelligence_session: context,
            ...(model ? { region_context: root.GVAIRegional.contextForChat(model, regional.get().audience) } : {}) })
        });
        const data = await response.json();
        if (!isCurrent()) {
          status.textContent = "Your region or workspace changed. The old response and its actions were ignored; ask again in the current context.";
          return;
        }
        if (!response.ok || !data.ok || typeof data.reply !== "string") throw new Error(data.reason || "No valid interpretation returned.");
        session.addMessage("assistant", data.reply);
        session.setOccupationEvidence(data.occupation_evidence);
        document.getElementById("regional-ask-reply").textContent = data.reply;
        const wrapped = Object.fromEntries(Object.entries(adapters).map(([type, adapter]) =>
          [type, action => adapter(action, isCurrent, actionContext.update)]));
        if (data.action_protocol === "gvai.ui-actions.v1") await api.executeActions(session, data.actions, wrapped, isCurrent);
        status.textContent = data.rejected_actions ? "Some interface requests were rejected. Advice is AI interpretation; inspect the sources."
          : "AI interpretation, not source data. Interface request results are shown below.";
        question.value = "";
      } catch (error) {
        status.textContent = `GVAI could not finish this question: ${error.message}. Your evidence and conversation remain available.`;
      } finally { busy = false; button.disabled = false; }
    });
    return { ask, open };
  }
  root.GVAIIntelligenceGuide = { mount };
})(window);
