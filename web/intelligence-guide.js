(function (root) {
  function requestBody(message, context, regionalContext, continuation = false) {
    const payload = { message, intelligence_session: context, continuation,
      ...(regionalContext ? { region_context: regionalContext } : {}) };
    while (new TextEncoder().encode(JSON.stringify(payload)).length > 64000 && context.messages.length) context.messages.shift();
    if (new TextEncoder().encode(JSON.stringify(payload)).length > 64000) throw new Error("Investigation request is too large. Reduce criteria or start a new conversation.");
    return JSON.stringify(payload);
  }
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
    let comparisonRequested = false;
    const open = () => { guide.open = true; pane.open = true; question.focus(); };
    const ask = (message, audience) => {
      if (busy) { status.textContent = "Wait for the current answer before sending another question."; open(); return; }
      if (audience) regional.selectAudience(audience);
      question.value = message; open(); return send(message);
    };
    session.subscribe(state => {
      const active = state.messages.length > 0 || !!state.investigation;
      const selected = state.selectedRegion || regional.get().selection;
      document.getElementById("intelligence-context").hidden = !active && !state.selectedRegion;
      document.getElementById("intelligence-clear").hidden = !state.messages.length;
      document.getElementById("intelligence-why").hidden = !state.evidence && !state.scenario;
      document.getElementById("intelligence-investigation").hidden = !state.investigation;
      document.getElementById("intelligence-comparison").hidden = !state.selectedRegion && !state.comparisons.length && !state.investigation && !comparisonRequested;
      document.getElementById("intelligence-audience-control").hidden = !active;
      document.getElementById("intelligence-disclaimer").hidden = !state.messages.length;
      document.getElementById("regional-outlook-panel").hidden = !selected;
      document.getElementById("app").classList.toggle("intelligence-active", active);
      document.getElementById("app").classList.toggle("intelligence-contextual", active || !!selected);
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
      const panel = document.getElementById("intelligence-investigation-content");
      const editingCriteria = panel.querySelector("[data-criteria-editor]")?.open;
      panel.innerHTML = root.GVAIInvestigation.render(state);
      if (editingCriteria && panel.querySelector("[data-criteria-editor]")) panel.querySelector("[data-criteria-editor]").open = true;
      const choice = document.getElementById("intelligence-place-choice");
      choice.hidden = !state.placeChoice;
      choice.innerHTML = state.placeChoice ? `<h3>Which ${api.escape(state.placeChoice.query)}?</h3><p>These are place-search results, not recommendations. Choose explicitly; your investigation remains intact.</p>` +
        state.placeChoice.candidates.map((place, index) => `<button type="button" data-place-choice="${index}">${api.escape(place.label)}</button>`).join("") +
        '<button type="button" data-place-cancel>Cancel place choice</button>' : "";
      document.getElementById("intelligence-action-status").textContent = state.outcomes.map(outcome =>
        `${outcome.type.replaceAll("_", " ")}: ${outcome.status}${outcome.detail ? ` (${outcome.detail})` : ""}`
      ).join(" · ");
    });
    document.getElementById("ask-btn").addEventListener("click", open);
    document.getElementById("intelligence-clear").addEventListener("click", () => {
      if (busy) { status.textContent = "Wait for the current answer before starting a new conversation."; return; }
      comparisonRequested = false;
      session.clearConversation(); document.getElementById("regional-ask-reply").textContent = "";
      status.textContent = "New conversation. Your regional selection and shortlist remain.";
    });
    document.getElementById("intelligence-starters").addEventListener("click", event => {
      const prompt = event.target.closest("[data-intelligence-prompt]");
      if (prompt) {
        if (busy) { open(); return; }
        comparisonRequested = prompt.hasAttribute("data-start-comparison");
        ask(prompt.dataset.intelligencePrompt || prompt.textContent, prompt.dataset.audience);
      }
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
    document.getElementById("intelligence-place-choice").addEventListener("click", event => {
      const place = event.target.closest("[data-place-choice]");
      if (place) session.resolvePlaceChoice(Number(place.dataset.placeChoice));
      else if (event.target.closest("[data-place-cancel]")) session.resolvePlaceChoice(null);
    });
    const panel = document.getElementById("intelligence-investigation-content");
    panel.addEventListener("change", event => {
      const control = event.target.closest("[data-criterion-key]");
      if (!control) return;
      const criterion = session.get().investigation?.criteria.find(item => item.key === control.dataset.criterionKey);
      if (!criterion) return;
      try {
        session.setCriteria([{ ...criterion, [control.dataset.criterionField]: control.value }]);
        status.textContent = "Criteria changed. The previous read is invalidated; reassess when ready.";
      } catch (error) { status.textContent = error.message; }
    });
    panel.addEventListener("click", async event => {
      const remove = event.target.closest("[data-remove-criterion]");
      if (remove) { session.removeCriterion(remove.dataset.removeCriterion); return; }
      const command = event.target.closest("[data-investigation-command]");
      if (command) {
        if (command.dataset.investigationCommand === "compare") {
          await runCandidateAction({ type: "compare_candidates" });
        } else ask(command.dataset.investigationCommand === "leader" ?
          "Why is the working leader ahead for my stated criteria? Explain accepted tradeoffs and what would change it." :
          "Reassess my investigation using the visible criteria, candidates and current evidence. Explain tradeoffs and what could change the recommendation.");
        return;
      }
      const candidate = event.target.closest("[data-candidate-action]");
      if (!candidate) return;
      const action = { type: candidate.dataset.candidateAction, region_id: candidate.dataset.regionId };
      if (action.type === "reject_candidate") {
        action.reason = candidate.closest("li").querySelector("[data-rejection-for]").value.trim();
      }
      await runCandidateAction(action);
    });
    async function runCandidateAction(action) {
      const actionContext = api.createActionContext(session);
      const adapter = adapters[action.type];
      const outcomes = await api.executeActions(session, [action], { [action.type]: request =>
        adapter(request, actionContext.isCurrent, actionContext.update) }, actionContext.isCurrent);
      status.textContent = outcomes.at(-1)?.status === "completed"
        ? "Candidate change recorded. Reassess to update the evidence-bound read."
        : "Candidate request was not completed. See the interface result for the reason.";
    }
    async function send(input) {
      if (busy) return;
      const message = typeof input === "string" ? input.trim() : "";
      if (!message || new TextEncoder().encode(message).length > 8192) { status.textContent = "Enter a question up to 8 KiB."; return; }
      if (["loading", "refreshing"].includes(regional.get().status)) { status.textContent = "Wait for the selected-region evidence to finish loading."; return; }
      session.addMessage("user", message);
      const context = session.context();
      const actionContext = api.createActionContext(session);
      const isCurrent = actionContext.isCurrent;
      const initialEpoch = session.get().epoch;
      busy = true; button.disabled = true;
      document.getElementById("regional-ask-reply").textContent = "";
      status.textContent = "Reviewing your investigation and supported regional evidence...";
      try {
        const model = regional.get().model;
        const response = await fetch((root.GVAI_API_BASE || "") + "/api/chat", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: requestBody(message, context, model ? root.GVAIRegional.contextForChat(model, regional.get().audience) : null)
        });
        const data = await response.json();
        if (!isCurrent()) {
          status.textContent = "Your region or workspace changed. The old response and its actions were ignored; ask again in the current context.";
          return;
        }
        if (!response.ok || !data.ok || typeof data.reply !== "string") throw new Error(data.reason || "No valid interpretation returned.");
        session.addMessage("assistant", data.reply);
        session.setOccupationEvidence(data.occupation_evidence);
        session.setDecisionRead(data.decision_read);
        document.getElementById("regional-ask-reply").textContent = data.reply;
        const wrapped = Object.fromEntries(Object.entries(adapters).map(([type, adapter]) =>
          [type, action => adapter(action, isCurrent, actionContext.update)]));
        if (data.action_protocol === "gvai.ui-actions.v1") await api.executeActions(session, data.actions, wrapped, isCurrent);
        if (!isCurrent()) {
          status.textContent = "Your investigation changed during retrieval. Remaining requests and automatic advice were ignored.";
          return;
        }
        if (session.get().epoch !== initialEpoch && session.get().outcomes.some(outcome => outcome.status === "completed")) {
          status.textContent = "Evidence and criteria updated. Explaining the tradeoffs...";
          const followContext = session.context({ includeLatest: true });
          const followModel = regional.get().model;
          const follow = await fetch((root.GVAI_API_BASE || "") + "/api/chat", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: requestBody("Continue the investigation using the completed interface outcomes and newly retrieved evidence. Explain what this changes relative to our criteria and shortlist, why each place belongs, material tradeoffs, and what would change the working read. Ask only a materially necessary clarification. Do not request further interface actions.",
              followContext, followModel ? root.GVAIRegional.contextForChat(followModel, regional.get().audience) : null, true)
          });
          const continuation = await follow.json();
          if (!isCurrent()) {
            status.textContent = "Your investigation changed. The old continuation was ignored.";
            return;
          }
          if (!follow.ok || !continuation.ok || typeof continuation.reply !== "string") throw new Error(continuation.reason || "No valid continuation returned.");
          session.addMessage("assistant", continuation.reply);
          session.setOccupationEvidence(continuation.occupation_evidence);
          session.setDecisionRead(continuation.decision_read);
          document.getElementById("regional-ask-reply").textContent = continuation.reply;
        }
        status.textContent = data.rejected_actions ? "Some interface requests were rejected. Advice is AI interpretation; inspect the sources."
          : "AI interpretation, not source data. Interface request results are shown below.";
        question.value = "";
      } catch (error) {
        status.textContent = `GVAI could not finish this question: ${error.message}. Your evidence and conversation remain available.`;
      } finally { busy = false; button.disabled = false; }
    }
    form.addEventListener("submit", event => { event.preventDefault(); send(question.value); });
    return { ask, send, open };
  }
  root.GVAIIntelligenceGuide = { mount, requestBody };
})(window);
