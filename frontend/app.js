/**
 * Decision Graveyard - Enterprise SaaS Frontend Application Logic
 * Consumes the existing FastAPI backend to evaluate product proposals
 * against organizational memory, Hindsight recall, GhostDetector, and MultiProposalDetector.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Global State
  let loadedProposals = [];
  let loadedDecisions = [];
  let currentReport = null;

  // Navigation Links & Views
  const navLinks = document.querySelectorAll(".nav-link");
  const pageViews = document.querySelectorAll(".page-view");
  const navReportBtn = document.getElementById("navReportBtn");
  const reportReadyDot = document.getElementById("reportReadyDot");
  const brandLogoBtn = document.getElementById("brandLogoBtn");

  // Dashboard Elements
  const heroAnalyzeBtn = document.getElementById("heroAnalyzeBtn");
  const heroHistoryBtn = document.getElementById("heroHistoryBtn");
  const viewAllDecisionsBtn = document.getElementById("viewAllDecisionsBtn");
  const dashboardRecentDecisions = document.getElementById("dashboardRecentDecisions");

  // Proposal Form Elements
  const presetSelector = document.getElementById("presetSelector");
  const proposalForm = document.getElementById("proposalForm");
  const inpProposalId = document.getElementById("inpProposalId");
  const inpCategory = document.getElementById("inpCategory");
  const inpTitle = document.getElementById("inpTitle");
  const inpBusinessProblem = document.getElementById("inpBusinessProblem");
  const inpDescription = document.getElementById("inpDescription");
  const inpObjectives = document.getElementById("inpObjectives");
  const inpCurrentContext = document.getElementById("inpCurrentContext");
  const inpAlternatives = document.getElementById("inpAlternatives");
  const inpExpectedOutcome = document.getElementById("inpExpectedOutcome");
  const btnRunAnalysis = document.getElementById("btnRunAnalysis");

  // Loading Overlay & Error
  const analysisLoadingOverlay = document.getElementById("analysisLoadingOverlay");
  const loadingModalTitle = document.getElementById("loadingModalTitle");
  const loadingModalSubtitle = document.getElementById("loadingModalSubtitle");
  const analysisErrorCard = document.getElementById("analysisErrorCard");
  const analysisErrorMessage = document.getElementById("analysisErrorMessage");
  const btnCloseError = document.getElementById("btnCloseError");

  // Report Elements
  const reportEmptyState = document.getElementById("reportEmptyState");
  const reportActiveContainer = document.getElementById("reportActiveContainer");
  const btnGoToAnalyze = document.getElementById("btnGoToAnalyze");
  const btnCopyBriefing = document.getElementById("btnCopyBriefing");
  const btnCopyBriefingSandbox = document.getElementById("btnCopyBriefingSandbox");

  // Decision History Elements
  const histSearchInput = document.getElementById("histSearchInput");
  const histStatusFilter = document.getElementById("histStatusFilter");
  const histCategoryFilter = document.getElementById("histCategoryFilter");
  const decisionsTableBody = document.getElementById("decisionsTableBody");
  const decisionModal = document.getElementById("decisionModal");
  const btnCloseModal = document.getElementById("btnCloseModal");

  // =========================================================================
  // 1. ROUTING & VIEW NAVIGATION
  // =========================================================================

  function navigateToView(viewId) {
    pageViews.forEach(view => {
      if (view.id === `view-${viewId}`) {
        view.classList.add("active");
        view.classList.remove("hidden");
      } else {
        view.classList.remove("active");
        view.classList.add("hidden");
      }
    });

    navLinks.forEach(link => {
      if (link.getAttribute("data-view") === viewId) {
        link.classList.add("active");
      } else {
        link.classList.remove("active");
      }
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  navLinks.forEach(link => {
    link.addEventListener("click", () => {
      const viewId = link.getAttribute("data-view");
      navigateToView(viewId);
    });
  });

  if (brandLogoBtn) {
    brandLogoBtn.addEventListener("click", () => navigateToView("dashboard"));
  }
  if (heroAnalyzeBtn) {
    heroAnalyzeBtn.addEventListener("click", () => navigateToView("analyze"));
  }
  if (heroHistoryBtn || viewAllDecisionsBtn) {
    if (heroHistoryBtn) heroHistoryBtn.addEventListener("click", () => navigateToView("history"));
    if (viewAllDecisionsBtn) viewAllDecisionsBtn.addEventListener("click", () => navigateToView("history"));
  }
  if (btnGoToAnalyze) {
    btnGoToAnalyze.addEventListener("click", () => navigateToView("analyze"));
  }

  // =========================================================================
  // 2. DASHBOARD DATA FETCHING
  // =========================================================================

  async function fetchDashboardStats() {
    try {
      const res = await fetch("/dashboard-stats");
      if (!res.ok) throw new Error("Could not load dashboard stats");
      const stats = await res.json();

      document.getElementById("statTotalHistorical").textContent = stats.total_historical ?? 15;
      document.getElementById("statSuccessful").textContent = stats.successful_count ?? 6;
      document.getElementById("statFailed").textContent = stats.failed_abandoned_rejected_total ?? 9;
      document.getElementById("statActiveProposals").textContent = stats.active_proposals_count ?? 5;

      // Render recent precedents
      if (stats.recent_decisions && dashboardRecentDecisions) {
        dashboardRecentDecisions.innerHTML = "";
        stats.recent_decisions.forEach(d => {
          const card = document.createElement("div");
          card.className = "recent-decision-card";
          card.innerHTML = `
            <div class="rd-header">
              <span class="rd-id">${escapeHtml(d.decision_id)}</span>
              <span class="status-pill-big status-${(d.status || '').toLowerCase()}">${escapeHtml(d.status)}</span>
            </div>
            <div class="rd-title">${escapeHtml(d.title)}</div>
            <div class="rd-summary">${escapeHtml(d.summary || '')}</div>
          `;
          card.addEventListener("click", () => {
            const match = loadedDecisions.find(item => item.decision_id === d.decision_id);
            if (match) openDecisionModal(match);
            else navigateToView("history");
          });
          dashboardRecentDecisions.appendChild(card);
        });
      }
    } catch (err) {
      console.warn("Dashboard stats error:", err);
    }
  }

  // Handle Demo Scenario Cards on Dashboard
  document.querySelectorAll(".demo-card").forEach(card => {
    card.addEventListener("click", () => {
      const pid = card.getAttribute("data-proposal");
      selectAndRunProposal(pid);
    });
  });

  // =========================================================================
  // 3. PROPOSALS PRESET LOADING & FORM FILLING
  // =========================================================================

  async function fetchProposals() {
    try {
      const res = await fetch("/proposals");
      if (!res.ok) throw new Error("Could not load proposals");
      loadedProposals = await res.json();
      populatePresetDropdown(loadedProposals);

      // Pre-select P005 (flagship composite demo) by default
      const defaultProp = loadedProposals.find(p => p.proposal_id === "P005") || loadedProposals[0];
      if (defaultProp) {
        presetSelector.value = defaultProp.proposal_id;
        fillProposalForm(defaultProp);
      }
    } catch (err) {
      console.warn("Proposals fetch error:", err);
      if (presetSelector) {
        presetSelector.innerHTML = '<option value="" disabled selected>Unable to load proposals</option>';
      }
    }
  }

  function populatePresetDropdown(proposals) {
    if (!presetSelector) return;
    presetSelector.innerHTML = '<option value="" disabled>-- Select a Pre-Configured Organizational Proposal --</option>';
    proposals.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.proposal_id;
      const isComp = p.components && p.components.length ? " [FLAGSHIP COMPOSITE GHOST]" : "";
      opt.textContent = `${p.proposal_id}: ${p.title}${isComp}`;
      presetSelector.appendChild(opt);
    });
  }

  function fillProposalForm(p) {
    if (!p) return;
    inpProposalId.value = p.proposal_id || "";
    inpCategory.value = p.category || "Product";
    inpTitle.value = p.title || "";
    inpBusinessProblem.value = p.business_problem || "";
    inpDescription.value = p.proposal || "";
    inpObjectives.value = (p.objectives || []).join("\n");

    if (p.current_context) {
      inpCurrentContext.value = typeof p.current_context === "string"
        ? p.current_context
        : Object.entries(p.current_context).map(([k, v]) => `${k}: ${v}`).join(", ");
    } else {
      inpCurrentContext.value = "";
    }

    inpAlternatives.value = (p.alternatives_considered || []).join("\n");
    inpExpectedOutcome.value = p.expected_outcome || "";
  }

  if (presetSelector) {
    presetSelector.addEventListener("change", (e) => {
      const selId = e.target.value;
      const prop = loadedProposals.find(p => p.proposal_id === selId);
      if (prop) fillProposalForm(prop);
    });
  }

  document.querySelectorAll(".preset-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const pid = chip.getAttribute("data-id");
      const prop = loadedProposals.find(p => p.proposal_id === pid);
      if (prop) {
        if (presetSelector) presetSelector.value = prop.proposal_id;
        fillProposalForm(prop);
      }
    });
  });

  const btnSelectP005Quick = document.getElementById("btnSelectP005Quick");
  if (btnSelectP005Quick) {
    btnSelectP005Quick.addEventListener("click", () => {
      const prop = loadedProposals.find(p => p.proposal_id === "P005");
      if (prop) {
        if (presetSelector) presetSelector.value = prop.proposal_id;
        fillProposalForm(prop);
      }
    });
  }

  function selectAndRunProposal(pid) {
    navigateToView("analyze");
    const prop = loadedProposals.find(p => p.proposal_id === pid);
    if (prop) {
      if (presetSelector) presetSelector.value = prop.proposal_id;
      fillProposalForm(prop);
    } else {
      inpProposalId.value = pid;
    }
    // Automatically submit analysis
    setTimeout(() => {
      if (proposalForm) {
        proposalForm.dispatchEvent(new Event("submit"));
      }
    }, 200);
  }

  // =========================================================================
  // 4. ANIMATED MULTI-STEP LOADING SEQUENCE
  // =========================================================================

  let stepTimer = null;

  function startLoadingSteps() {
    analysisLoadingOverlay.classList.remove("hidden");
    const steps = [
      document.getElementById("mStep1"),
      document.getElementById("mStep2"),
      document.getElementById("mStep3"),
      document.getElementById("mStep4"),
      document.getElementById("mStep5"),
      document.getElementById("mStep6")
    ];

    steps.forEach(s => {
      if (s) {
        s.classList.remove("active", "done");
      }
    });

    if (steps[0]) steps[0].classList.add("active");

    const delays = [600, 1500, 2600, 3600, 4600];
    delays.forEach((delay, idx) => {
      setTimeout(() => {
        if (!analysisLoadingOverlay.classList.contains("hidden")) {
          if (steps[idx]) {
            steps[idx].classList.remove("active");
            steps[idx].classList.add("done");
          }
          if (steps[idx + 1]) {
            steps[idx + 1].classList.add("active");
          }
        }
      }, delay);
    });
  }

  function stopLoadingSteps() {
    analysisLoadingOverlay.classList.add("hidden");
  }

  // =========================================================================
  // 5. PROPOSAL SUBMISSION & API CALL
  // =========================================================================

  if (proposalForm) {
    proposalForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const proposalId = inpProposalId.value.trim().toUpperCase();
      const category = inpCategory.value.trim();
      const title = inpTitle.value.trim();
      const businessProblem = inpBusinessProblem.value.trim();
      const proposalDesc = inpDescription.value.trim();
      const objectives = inpObjectives.value.split("\n").map(s => s.trim()).filter(Boolean);
      const expectedOutcome = inpExpectedOutcome.value.trim();

      if (!proposalId) {
        alert("Please specify a Proposal ID");
        return;
      }

      analysisErrorCard.classList.add("hidden");
      btnRunAnalysis.disabled = true;
      startLoadingSteps();

      try {
        let response;
        // Check if known proposal ID or comma-separated composite list
        const isKnown = loadedProposals.some(p => p.proposal_id === proposalId) || proposalId.includes(",");

        if (isKnown) {
          response = await fetch(`/analyze/${encodeURIComponent(proposalId)}`, {
            method: "POST"
          });
        } else {
          // Custom Proposal via POST /analyze
          response = await fetch("/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              proposal_id: proposalId,
              category: category || "Product",
              title: title,
              business_problem: businessProblem,
              proposal: proposalDesc,
              objectives: objectives,
              expected_outcome: expectedOutcome || title
            })
          });
        }

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Server returned error HTTP ${response.status}`);
        }

        const report = await response.json();
        currentReport = report;

        // Render report
        renderDecisionIntelligenceReport(report);

        // Update nav badge & switch view
        if (reportReadyDot) reportReadyDot.classList.remove("hidden");
        navigateToView("report");

      } catch (err) {
        console.error("Analysis execution error:", err);
        let userMsg = "Unable to complete analysis. Please try again.";
        if (err.message && !err.message.includes("Traceback") && !err.message.includes("File \"") && !err.message.includes("line ")) {
          userMsg = err.message;
        }
        analysisErrorMessage.textContent = userMsg;
        analysisErrorCard.classList.remove("hidden");
      } finally {
        stopLoadingSteps();
        btnRunAnalysis.disabled = false;
      }
    });
  }

  if (btnCloseError) {
    btnCloseError.addEventListener("click", () => {
      analysisErrorCard.classList.add("hidden");
    });
  }

  // =========================================================================
  // HELPER UTILITIES: MARKDOWN CLEANING & REPORT DATA EXTRACTION
  // =========================================================================

  function cleanMarkdownString(text) {
    if (!text) return "";
    let s = String(text);
    // Remove markdown headers
    s = s.replace(/^#{1,6}\s+/gm, "");
    // Remove bold/italics
    s = s.replace(/\*\*([^*]+)\*\*/g, "$1");
    s = s.replace(/__([^_]+)__/g, "$1");
    s = s.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "$1");
    s = s.replace(/(?<!_)_([^_]+)_(?!_)/g, "$1");
    // Remove bullet points at line starts
    s = s.replace(/^[\s]*[-*+]\s+/gm, "");
    // Remove numbered list markers at line starts
    s = s.replace(/^[\s]*\d+\.\s+/gm, "");
    // Remove inline backticks
    s = s.replace(/`([^`]+)`/g, "$1");
    return s.trim();
  }

  function extractConfidence(report) {
    if (!report) return "None";
    if (report.is_composite_ghost) {
      if (report.composite_ghost_confidence_level && report.composite_ghost_confidence_level !== "None") {
        return report.composite_ghost_confidence_level;
      }
      if (report.composite_ghost_detection_result?.confidence_level && report.composite_ghost_detection_result.confidence_level !== "None") {
        return report.composite_ghost_detection_result.confidence_level;
      }
    }
    if (report.ghost_confidence_level && report.ghost_confidence_level !== "None") {
      return report.ghost_confidence_level;
    }
    if (report.ghost_detection_result?.confidence && report.ghost_detection_result.confidence !== "None") {
      return report.ghost_detection_result.confidence;
    }
    if (report.ghost_detection_result?.confidence_level && report.ghost_detection_result.confidence_level !== "None") {
      return report.ghost_detection_result.confidence_level;
    }
    return report.is_potential_ghost ? "High" : (report.ghost_confidence_level === "Low" ? "Low" : "None");
  }

  function generateExecutiveSummary(report) {
    const isComp = report.is_composite_ghost;
    const isGhost = report.is_potential_ghost;
    const pId = report.proposal_id || "Proposal";
    const pTitle = report.proposal_title ? `"${cleanMarkdownString(report.proposal_title)}"` : "";
    const matches = (report.historical_matches || []).join(", ");

    if (isComp) {
      const group = (report.composite_ghost_detection_result?.composite_ghost_groups || [])[0];
      const target = group ? `${group.matched_historical_decision_id} (${cleanMarkdownString(group.matched_historical_decision_title)})` : "historical initiatives";
      return `Organizational decision intelligence detected that current modular proposals collectively assemble a potential composite ghost recreation of ${target}. While each sub-proposal may appear modest individually, their combined architecture mirrors previous initiatives that encountered critical operational overhead. Review the Then vs. Now telemetry to assess if current company capacity alters the viability of this initiative.`;
    }

    if (isGhost) {
      const primaryDec = (report.related_historical_decisions || []).find(d => (d.status || '').toLowerCase() !== 'successful') || (report.related_historical_decisions || [])[0];
      const relatedDec = (report.related_historical_decisions || []).find(d => (d.status || '').toLowerCase() === 'successful');

      let summary = `Organizational memory audit complete. Decision Graveyard identified that proposal ${pId} ${pTitle} conceptually mirrors prior initiative ${primaryDec ? primaryDec.decision_id + ' (' + cleanMarkdownString(primaryDec.title) + ')' : matches}.`;

      if (primaryDec && (primaryDec.status || '').toLowerCase() === 'abandoned') {
        summary += ` Historically, ${primaryDec.decision_id} was abandoned after initial development due to constrained team capacity and low target adoption.`;
      }

      if (relatedDec) {
        summary += ` The organization subsequently executed ${relatedDec.decision_id} (${cleanMarkdownString(relatedDec.title)}) with status "${relatedDec.status}", establishing a proven alternative precedent.`;
      }

      if ((report.blockers_that_may_have_changed || []).length > 0) {
        summary += ` Current company conditions demonstrate significant evolution, mitigating several past constraints, while key architectural tradeoffs require leadership review.`;
      }

      return summary;
    }

    return `Organizational memory audit completed for proposal ${pId} ${pTitle}. No direct historical ghost match or failure precedent was detected in organizational memory. The proposed initiative introduces distinct operational scope. Standard cross-functional and architecture review is recommended.`;
  }

  function createHistoricalMatchCard(decision, roleLabel, isPrimary) {
    const card = document.createElement("div");
    card.className = `historical-match-card ${isPrimary ? 'primary-match-card' : 'precedent-match-card'}`;

    const statusStr = decision.status || "Archived";
    const statusClass = `status-${statusStr.toLowerCase()}`;

    let outcomeDriversHtml = "";
    if (decision.outcome_drivers && decision.outcome_drivers.length) {
      outcomeDriversHtml = `
        <div class="match-section">
          <span class="match-section-label">Outcome Drivers:</span>
          <ul class="match-drivers-list">
            ${decision.outcome_drivers.map(drv => `<li>${escapeHtml(cleanMarkdownString(drv))}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="match-card-top">
        <div class="match-role-badges">
          <span class="badge-role ${isPrimary ? 'role-primary' : 'role-precedent'}">${roleLabel}</span>
          <span class="status-pill ${statusClass}">${escapeHtml(statusStr)}</span>
        </div>
        <span class="match-cat-tag">${escapeHtml(decision.category || 'Architecture')}</span>
      </div>

      <div class="match-card-title-row">
        <span class="match-id-chip">${escapeHtml(decision.decision_id)}</span>
        <h4 class="match-title">${escapeHtml(cleanMarkdownString(decision.title))}</h4>
      </div>

      ${decision.similarity_reason ? `
        <div class="match-section">
          <span class="match-section-label">Similarity / Precedent Context:</span>
          <p class="match-text">${escapeHtml(cleanMarkdownString(decision.similarity_reason))}</p>
        </div>
      ` : ''}

      ${decision.actual_outcome ? `
        <div class="match-section">
          <span class="match-section-label">Historical Outcome:</span>
          <p class="match-text">${escapeHtml(cleanMarkdownString(decision.actual_outcome))}</p>
        </div>
      ` : ''}

      ${outcomeDriversHtml}

      ${decision.lesson_learned ? `
        <div class="match-lesson-box">
          <span class="lesson-tag">Key Organizational Lesson:</span>
          <p class="lesson-text">${escapeHtml(cleanMarkdownString(decision.lesson_learned))}</p>
        </div>
      ` : ''}
    `;

    return card;
  }

  function renderHistoricalMatches(report, container) {
    if (!container) return;
    container.innerHTML = "";
    const relDecs = report.related_historical_decisions || [];

    if (!relDecs.length && (report.historical_matches || []).length) {
      // Fallback if full objects not present
      (report.historical_matches || []).forEach((mId) => {
        const fallbackCard = document.createElement("div");
        fallbackCard.className = "historical-match-card primary-match-card";
        fallbackCard.innerHTML = `
          <div class="match-card-top">
            <span class="badge-role role-primary">HISTORICAL MATCH</span>
            <span class="status-pill status-abandoned">${escapeHtml(report.historical_status || 'Archived')}</span>
          </div>
          <div class="match-card-title-row">
            <span class="match-id-chip">${escapeHtml(mId)}</span>
            <h4 class="match-title">Historical Precedent</h4>
          </div>
          <div class="match-section">
            <span class="match-section-label">Resemblance:</span>
            <p class="match-text">${escapeHtml(cleanMarkdownString(report.relationship_explanation || 'Archived precedent in memory.'))}</p>
          </div>
        `;
        container.appendChild(fallbackCard);
      });
      return;
    }

    if (!relDecs.length) {
      container.innerHTML = `
        <div class="empty-state-card" style="padding: 2.5rem 1.5rem; width: 100%; grid-column: 1 / -1;">
          <div class="empty-icon" style="font-size: 2.2rem; margin-bottom: 0.5rem;">🌱</div>
          <h4 style="font-size: 1.1rem; color: #fff; margin-bottom: 0.35rem;">No Direct Historical Graveyard Match</h4>
          <p style="font-size: 0.85rem; color: var(--text-muted); margin: 0 auto; max-width: 480px;">
            This proposal introduces distinct operational scope that does not match prior abandoned or failed organizational initiatives.
          </p>
        </div>
      `;
      return;
    }

    // Separate Primary Historical Match from Related Precedents
    let primaryMatch = relDecs.find(d => (d.status || '').toLowerCase() !== 'successful') || relDecs[0];
    let relatedPrecedents = relDecs.filter(d => d !== primaryMatch);

    if (primaryMatch) {
      const card = createHistoricalMatchCard(primaryMatch, "PRIMARY HISTORICAL MATCH", true);
      container.appendChild(card);
    }

    if (relatedPrecedents.length > 0) {
      relatedPrecedents.forEach(prec => {
        const card = createHistoricalMatchCard(prec, "RELATED HISTORICAL PRECEDENT", false);
        container.appendChild(card);
      });
    }
  }

  function formatAnalysisBreakdown(rawAnalysis) {
    if (!rawAnalysis) return "<p class='text-muted'>Analysis complete.</p>";

    const lines = rawAnalysis.split("\n").map(l => l.trim()).filter(Boolean);
    let html = `<div class="analysis-structured-table">`;

    for (let line of lines) {
      if (line.startsWith("###")) {
        const heading = cleanMarkdownString(line);
        html += `<div class="analysis-table-header">${escapeHtml(heading)}</div>`;
        continue;
      }

      const kvMatch = line.match(/^[-*+]?\s*\*\*([^*]+)\*\*:\s*(.*)$/);
      if (kvMatch) {
        const label = cleanMarkdownString(kvMatch[1]);
        const value = cleanMarkdownString(kvMatch[2]);

        if (value.includes(";")) {
          const items = value.split(";").map(s => s.trim()).filter(Boolean);
          html += `
            <div class="analysis-table-row">
              <div class="analysis-row-key">${escapeHtml(label)}</div>
              <div class="analysis-row-val">
                <ul class="analysis-nested-list">
                  ${items.map(it => `<li>${escapeHtml(it)}</li>`).join("")}
                </ul>
              </div>
            </div>
          `;
        } else {
          html += `
            <div class="analysis-table-row">
              <div class="analysis-row-key">${escapeHtml(label)}</div>
              <div class="analysis-row-val">${escapeHtml(value)}</div>
            </div>
          `;
        }
      } else {
        const cleaned = cleanMarkdownString(line);
        if (cleaned) {
          html += `<p class="analysis-plain-p">${escapeHtml(cleaned)}</p>`;
        }
      }
    }

    html += `</div>`;
    return html;
  }

  // =========================================================================
  // 6. RENDER DECISION INTELLIGENCE REPORT
  // =========================================================================

  function renderDecisionIntelligenceReport(report) {
    if (!report) return;

    reportEmptyState.classList.add("hidden");
    reportActiveContainer.classList.remove("hidden");

    // Header info
    document.getElementById("repProposalTitle").textContent = report.proposal_title || "Proposal Evaluation";
    document.getElementById("repProposalId").textContent = report.proposal_id || "N/A";
    document.getElementById("repGeneratedAt").textContent = new Date().toLocaleTimeString();

    const isComp = report.is_composite_ghost;
    const isGhost = report.is_potential_ghost;
    const conf = extractConfidence(report);
    const matches = report.historical_matches || [];

    // -----------------------------------------------------------------------
    // SECTION A: ANALYSIS SUMMARY
    // -----------------------------------------------------------------------
    const execSummary = document.getElementById("repExecutiveSummary");
    if (execSummary) {
      execSummary.textContent = generateExecutiveSummary(report);
    }

    // -----------------------------------------------------------------------
    // SECTION B: POTENTIAL GHOST DECISION ASSESSMENT
    // -----------------------------------------------------------------------
    const ghostAssessmentCard = document.getElementById("ghostAssessmentCard");
    const assessGhostStatusText = document.getElementById("assessGhostStatusText");
    const assessGhostStatusSub = document.getElementById("assessGhostStatusSub");
    const assessStatusTile = document.getElementById("assessStatusTile");
    const assessConfidenceBadge = document.getElementById("assessConfidenceBadge");
    const assessConfidenceSub = document.getElementById("assessConfidenceSub");
    const assessDecisionsPills = document.getElementById("assessDecisionsPills");

    if (assessGhostStatusText && assessGhostStatusSub && assessStatusTile) {
      if (isComp) {
        assessGhostStatusText.textContent = "Potential Composite Ghost Detected";
        assessGhostStatusSub.textContent = "Modular proposals collectively recreate abandoned initiative";
        assessStatusTile.className = "assessment-tile-card status-detected";
      } else if (isGhost) {
        assessGhostStatusText.textContent = "Potential Ghost Decision Detected";
        assessGhostStatusSub.textContent = "Historical failure precedent identified in organizational memory";
        assessStatusTile.className = "assessment-tile-card status-detected";
      } else {
        assessGhostStatusText.textContent = "No Strong Historical Ghost Detected";
        assessGhostStatusSub.textContent = "Valid initiative (No direct failure precedent)";
        assessStatusTile.className = "assessment-tile-card status-clean";
      }
    }

    if (assessConfidenceBadge && assessConfidenceSub) {
      assessConfidenceBadge.textContent = `Confidence: ${conf}`;
      assessConfidenceBadge.className = `confidence-badge badge-conf-${conf.toLowerCase()}`;
      if (conf === "High") {
        assessConfidenceSub.textContent = "High semantic & structural precedent match";
      } else if (conf === "Medium") {
        assessConfidenceSub.textContent = "Moderate semantic similarity to past initiatives";
      } else if (conf === "Low") {
        assessConfidenceSub.textContent = "Low similarity; distinct exploratory parameters";
      } else {
        assessConfidenceSub.textContent = "No direct historical graveyard match";
      }
    }

    if (assessDecisionsPills) {
      assessDecisionsPills.innerHTML = "";
      if (matches.length) {
        matches.forEach(m => {
          const pill = document.createElement("span");
          pill.className = "decision-id-pill";
          pill.textContent = m;
          assessDecisionsPills.appendChild(pill);
        });
      } else {
        assessDecisionsPills.innerHTML = "<span class='text-muted' style='font-size:0.85rem;'>None</span>";
      }
    }

    // Relationship visual flow diagram
    const curName = document.getElementById("ghostCurrentProposalName");
    const curCode = document.getElementById("ghostCurrentProposalCode");
    const pastName = document.getElementById("ghostMatchedName");
    const pastStatus = document.getElementById("ghostHistoricalStatus");
    const arrowCaption = document.getElementById("ghostArrowCaption");

    if (curName) curName.textContent = report.proposal_title || report.proposal_id;
    if (curCode) curCode.textContent = report.proposal_id;

    if (isComp) {
      const compGroup = (report.composite_ghost_detection_result?.composite_ghost_groups || [])[0];
      const matchId = compGroup?.matched_historical_decision_id || "D001";
      const matchTitle = compGroup?.matched_historical_decision_title || "Employee Mobile Application";
      if (pastName) pastName.textContent = `${matchId} — ${matchTitle}`;
      if (pastStatus) {
        pastStatus.textContent = `Status: ${compGroup?.historical_status || 'Abandoned'}`;
        pastStatus.className = "entity-code status-abandoned";
      }
      if (arrowCaption) arrowCaption.textContent = "Collectively Recreates Historical Precedent";
    } else if (isGhost) {
      const primaryDec = (report.related_historical_decisions || []).find(d => (d.status || '').toLowerCase() !== 'successful') || (report.related_historical_decisions || [])[0];
      if (pastName) {
        pastName.textContent = primaryDec ? `${primaryDec.decision_id} — ${primaryDec.title}` : (matches.join(", ") || "Historical Precedent");
      }
      if (pastStatus) {
        const pStatus = primaryDec?.status || (report.historical_status?.split(";")[0]?.split(":")[1]?.trim()) || 'Abandoned';
        pastStatus.textContent = `Status: ${pStatus}`;
        pastStatus.className = `entity-code status-${pStatus.toLowerCase()}`;
      }
      if (arrowCaption) arrowCaption.textContent = "Resembles Historical Precedent";
    } else {
      if (pastName) pastName.textContent = "No Direct Historical Graveyard Match";
      if (pastStatus) {
        pastStatus.textContent = "Distinct Exploration Scope";
        pastStatus.className = "entity-code";
      }
      if (arrowCaption) arrowCaption.textContent = "Distinct Technical Trajectory";
    }

    // -----------------------------------------------------------------------
    // SECTION E: WHY THIS LOOKS FAMILIAR
    // -----------------------------------------------------------------------
    const explBox = document.getElementById("ghostRelationshipExplanation");
    if (explBox) {
      if (isComp) {
        explBox.textContent = cleanMarkdownString(report.composite_relationship_explanation || "Multiple modular proposals collectively assemble functionality previously abandoned due to prohibitive operational overhead.");
      } else if (isGhost) {
        explBox.textContent = cleanMarkdownString(report.relationship_explanation || "This proposal substantially resembles prior initiatives recorded in organizational memory.");
      } else {
        explBox.textContent = "This proposal introduces distinct operational scope and does not recreate previously explored failure drivers recorded in organizational memory.";
      }
    }

    // -----------------------------------------------------------------------
    // SECTIONS C & D: HISTORICAL MATCHES (PRIMARY & PRECEDENTS)
    // -----------------------------------------------------------------------
    const histMatchesGrid = document.getElementById("histMatchesGrid");
    renderHistoricalMatches(report, histMatchesGrid);

    // -----------------------------------------------------------------------
    // SECTION G: HISTORICAL BLOCKERS
    // -----------------------------------------------------------------------
    const histBlockersList = document.getElementById("repHistoricalBlockersList");
    if (histBlockersList) {
      histBlockersList.innerHTML = "";
      const blockers = report.historical_blockers || [];
      if (blockers.length) {
        blockers.forEach(b => {
          const card = document.createElement("li");
          card.className = "blocker-card-item neutral-blocker";
          card.innerHTML = `
            <span class="b-icon">&#128220;</span>
            <span class="b-text">${escapeHtml(cleanMarkdownString(b))}</span>
          `;
          histBlockersList.appendChild(card);
        });
      } else {
        histBlockersList.innerHTML = "<li class='blocker-card-item neutral-blocker'><span class='b-icon'>ℹ️</span><span class='b-text'>No historical blockers documented.</span></li>";
      }
    }

    // -----------------------------------------------------------------------
    // SECTION H: CURRENT CONDITIONS GRID
    // -----------------------------------------------------------------------
    const condGrid = document.getElementById("repCurrentConditionsGrid");
    if (condGrid) {
      condGrid.innerHTML = "";
      const conditions = report.current_conditions || {};
      const condEntries = Object.entries(conditions);
      if (condEntries.length) {
        condEntries.forEach(([k, v]) => {
          const chip = document.createElement("div");
          chip.className = "cond-chip";
          chip.innerHTML = `
            <div class="cond-key">${escapeHtml(k.replace(/_/g, ' '))}</div>
            <div class="cond-val">${escapeHtml(String(v))}</div>
          `;
          condGrid.appendChild(chip);
        });
      } else {
        condGrid.innerHTML = "<p class='text-muted'>Current conditions loaded.</p>";
      }
    }

    // -----------------------------------------------------------------------
    // SECTION I: THEN VS NOW (BLOCKERS STILL APPLY VS CHANGED)
    // -----------------------------------------------------------------------
    const stillApplyList = document.getElementById("repBlockersStillApplyList");
    if (stillApplyList) {
      stillApplyList.innerHTML = "";
      const still = report.blockers_that_may_still_apply || [];
      if (still.length) {
        still.forEach(b => {
          const card = document.createElement("li");
          card.className = "blocker-card-item danger-blocker";
          card.innerHTML = `
            <span class="b-icon">&#9888;&#65039;</span>
            <span class="b-text">${escapeHtml(cleanMarkdownString(b))}</span>
          `;
          stillApplyList.appendChild(card);
        });
      } else {
        stillApplyList.innerHTML = "<li class='blocker-card-item neutral-blocker'><span class='b-icon'>✓</span><span class='b-text'>No persistent blockers identified.</span></li>";
      }
    }

    const changedList = document.getElementById("repBlockersChangedList");
    if (changedList) {
      changedList.innerHTML = "";
      const changed = report.blockers_that_may_have_changed || [];
      if (changed.length) {
        changed.forEach(b => {
          const card = document.createElement("li");
          card.className = "blocker-card-item success-blocker";
          card.innerHTML = `
            <span class="b-icon">&#9989;</span>
            <span class="b-text">${escapeHtml(cleanMarkdownString(b))}</span>
          `;
          changedList.appendChild(card);
        });
      } else {
        changedList.innerHTML = "<li class='blocker-card-item neutral-blocker'><span class='b-icon'>ℹ️</span><span class='b-text'>No cleared constraints identified.</span></li>";
      }
    }

    // -----------------------------------------------------------------------
    // KILLER FEATURE: COMPOSITE GHOST DETECTION TAB
    // -----------------------------------------------------------------------
    renderCompositeTab(report);

    // -----------------------------------------------------------------------
    // SECTION F: HINDSIGHT MEMORY TAB
    // -----------------------------------------------------------------------
    renderHindsightTab(report);

    // -----------------------------------------------------------------------
    // SECTION J: AI DECISION REASONING
    // -----------------------------------------------------------------------
    const fullAnalysisContainer = document.getElementById("repFullAnalysisText");
    if (fullAnalysisContainer) {
      fullAnalysisContainer.innerHTML = formatAnalysisBreakdown(report.analysis);
    }

    // -----------------------------------------------------------------------
    // SECTION K: QUESTIONS FOR THE PRODUCT MANAGER
    // -----------------------------------------------------------------------
    const questionsList = document.getElementById("repHumanQuestionsList");
    if (questionsList) {
      questionsList.innerHTML = "";
      const questions = report.questions_for_product_manager || [];
      if (questions.length) {
        questions.forEach((q, idx) => {
          const card = document.createElement("li");
          card.className = "question-card-item";
          card.innerHTML = `
            <div class="q-card-header">
              <span class="q-badge">QUESTION ${idx + 1}</span>
              <span class="q-role-tag">Leadership Inquiry</span>
            </div>
            <div class="q-card-content">
              <span class="q-icon">&#10067;</span>
              <p class="q-text">${escapeHtml(cleanMarkdownString(q))}</p>
            </div>
          `;
          questionsList.appendChild(card);
        });
      } else {
        questionsList.innerHTML = "<li class='question-card-item'><p class='q-text'>Standard cross-functional technical and business review applies.</p></li>";
      }
    }

    // Pre-fill PM Sandbox Notes
    const pmNotes = document.getElementById("pmDecisionNotes");
    if (pmNotes) {
      pmNotes.value = `Evaluated against historical precedents (${matches.join(', ') || 'None'}).\nKey mitigations: `;
    }

    // Switch to first report tab by default
    document.querySelector('.rep-tab-btn[data-reptab="rep-summary"]')?.click();
  }

  function renderCompositeTab(report) {
    const compPill = document.getElementById("repCompositePill");
    const compProposalsList = document.getElementById("compProposalsList");
    const compMatchedBox = document.getElementById("compMatchedDecisionBox");
    const compExpl = document.getElementById("compRecreationExplanation");
    const compStillApply = document.getElementById("compBlockersStillApplyList");
    const compChanged = document.getElementById("compBlockersChangedList");
    const compQuestions = document.getElementById("compQuestionsList");

    const isComp = report.is_composite_ghost;
    const compResult = report.composite_ghost_detection_result;

    if (isComp && compResult && compResult.composite_ghost_groups?.length) {
      if (compPill) compPill.classList.remove("hidden");
      const group = compResult.composite_ghost_groups[0];

      // Proposals Stack
      if (compProposalsList) {
        compProposalsList.innerHTML = "";
        const pids = group.grouped_proposal_ids || [];
        const titles = group.grouped_proposal_titles || [];
        pids.forEach((pid, idx) => {
          const pill = document.createElement("div");
          pill.className = "component-pill";
          const titleStr = titles[idx] ? ` &bull; ${cleanMarkdownString(titles[idx])}` : "";
          pill.innerHTML = `<strong>${escapeHtml(pid)}</strong>${escapeHtml(titleStr)}`;
          compProposalsList.appendChild(pill);
        });
      }

      // Target Decision
      if (compMatchedBox) {
        compMatchedBox.innerHTML = `
          <div style="font-family: var(--font-mono); font-size: 1.1rem; font-weight: 800; color: #f43f5e;">
            ${escapeHtml(group.matched_historical_decision_id)}
          </div>
          <div style="font-size: 1rem; font-weight: 700; color: #fff; margin: 0.2rem 0;">
            ${escapeHtml(cleanMarkdownString(group.matched_historical_decision_title))}
          </div>
          <div>
            <span class="status-pill-big status-${(group.historical_status || 'abandoned').toLowerCase()}">
              ${escapeHtml(group.historical_status || 'Abandoned')}
            </span>
          </div>
        `;
      }

      if (compExpl) {
        compExpl.textContent = cleanMarkdownString(group.composite_relationship_explanation || report.composite_relationship_explanation || "Collectively recreate past abandoned scope.");
      }

      // Collective Blockers
      if (compStillApply) {
        compStillApply.innerHTML = "";
        (group.blockers_that_still_apply || report.blockers_that_may_still_apply || []).forEach(b => {
          const li = document.createElement("li");
          li.textContent = cleanMarkdownString(b);
          compStillApply.appendChild(li);
        });
      }

      if (compChanged) {
        compChanged.innerHTML = "";
        (group.blockers_that_may_have_changed || report.blockers_that_may_have_changed || []).forEach(b => {
          const li = document.createElement("li");
          li.textContent = cleanMarkdownString(b);
          compChanged.appendChild(li);
        });
      }

      // Questions
      if (compQuestions) {
        compQuestions.innerHTML = "";
        (group.human_review_questions || report.questions_for_product_manager || []).slice(0, 3).forEach(q => {
          const li = document.createElement("li");
          li.textContent = cleanMarkdownString(q);
          compQuestions.appendChild(li);
        });
      }

    } else {
      if (compPill) compPill.classList.add("hidden");
      if (compProposalsList) {
        compProposalsList.innerHTML = `<div class="component-pill"><strong>${escapeHtml(report.proposal_id)}</strong> &bull; Individual Initiative</div>`;
      }
      if (compMatchedBox) {
        compMatchedBox.innerHTML = `<div style="color: #cbd5e1;">No Composite Recreation Detected</div>`;
      }
      if (compExpl) {
        compExpl.textContent = "This proposal was evaluated individually. It does not assemble multiple discrete proposals into a previously abandoned scope.";
      }
      if (compStillApply) compStillApply.innerHTML = "<li>None</li>";
      if (compChanged) compChanged.innerHTML = "<li>None</li>";
      if (compQuestions) compQuestions.innerHTML = "<li>Standard single-initiative review applies.</li>";
    }
  }

  function renderHindsightTab(report) {
    const memoryCount = document.getElementById("hindsightMemoryCount");
    const container = document.getElementById("recalledMemoriesContainer");
    const hindsightSubtitle = document.querySelector("#rep-hindsight .box-subtitle");

    const memories = report.recalled_historical_memories || report.recalled_memories || [];
    memoryCount.textContent = String(memories.length);

    container.innerHTML = "";
    if (memories.length) {
      if (hindsightSubtitle) {
        hindsightSubtitle.textContent = "Authentic historical memories retrieved via Hindsight Cloud semantic search";
        hindsightSubtitle.style.color = "#34d399";
      }

      memories.forEach((mem, idx) => {
        let title = `#HINDSIGHT-RECORD-${String(idx + 1).padStart(2, '0')}`;
        let status = "";
        let contextText = mem;

        // Pattern matching: "D001 — Employee Mobile Application [Abandoned]: The project to build..."
        const patternMatch = mem.match(/^([A-Z0-9_\-\s\u2013\u2014]+?)\s*\[(Abandoned|Failed|Successful|Rejected)\]:\s*([\s\S]+)$/i);
        if (patternMatch) {
          title = patternMatch[1].trim();
          status = patternMatch[2].trim();
          contextText = patternMatch[3].trim();
        } else {
          const dMatch = mem.match(/\b(D\d{3})\b/);
          if (dMatch) {
            title = `${dMatch[1]} Historical Memory Precedent`;
          }
          if (/\babandoned\b/i.test(mem)) status = "Abandoned";
          else if (/\bfailed\b/i.test(mem)) status = "Failed";
          else if (/\bsuccessful\b/i.test(mem)) status = "Successful";
        }

        const bubble = document.createElement("div");
        bubble.className = "memory-bubble";

        let statusBadge = "";
        if (status) {
          const badgeClass = status.toLowerCase() === "successful" ? "badge-success" : (status.toLowerCase() === "abandoned" ? "badge-alert" : "badge-evidence");
          statusBadge = `<span class="${badgeClass}">${escapeHtml(status.toUpperCase())}</span>`;
        }

        bubble.innerHTML = `
          <div class="mem-top">
            <span class="mem-id">${escapeHtml(title)}</span>
            <div class="mem-badges" style="display: flex; gap: 0.5rem; align-items: center;">
              ${statusBadge}
              <span class="badge-evidence">ORGANIZATIONAL PRECEDENT</span>
            </div>
          </div>
          <div class="mem-text" style="line-height: 1.6; margin-top: 0.5rem;">
            <strong style="color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 0.25rem;">Historical Context:</strong>
            ${escapeHtml(contextText)}
          </div>
        `;
        container.appendChild(bubble);
      });
    } else {
      if (hindsightSubtitle) {
        hindsightSubtitle.textContent = "Local historical archive utilized as baseline context (0 Hindsight memories retrieved)";
        hindsightSubtitle.style.color = "#94a3b8";
      }

      container.innerHTML = `
        <div class="memory-bubble">
          <p class="text-muted">No explicit memories retrieved from Hindsight memory bank; local historical archive utilized as baseline context.</p>
        </div>
      `;
    }
  }

  // Report Sub-Tabs Navigation
  const repTabBtns = document.querySelectorAll(".rep-tab-btn");
  const repTabContents = document.querySelectorAll(".rep-tab-content");

  repTabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-reptab");
      repTabBtns.forEach(b => b.classList.remove("active"));
      repTabContents.forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const activeContent = document.getElementById(target);
      if (activeContent) activeContent.classList.add("active");
    });
  });

  // PM Decision Sandbox Actions
  const btnSaveDecision = document.getElementById("btnSaveDecision");
  const sandboxConfirmation = document.getElementById("sandboxConfirmation");

  if (btnSaveDecision) {
    btnSaveDecision.addEventListener("click", () => {
      sandboxConfirmation.classList.remove("hidden");
      setTimeout(() => {
        sandboxConfirmation.classList.add("hidden");
      }, 4000);
    });
  }

  function copyBriefingToClipboard() {
    if (!currentReport) {
      alert("Please analyze a proposal first.");
      return;
    }

    const isComp = currentReport.is_composite_ghost;
    const isGhost = currentReport.is_potential_ghost;
    const statusStr = isComp
      ? "YES [Potential Composite Ghost Detected]"
      : (isGhost ? "YES [Potential Ghost Detected]" : "NO [No Strong Historical Ghost Detected]");
    const conf = extractConfidence(currentReport);

    let text = `======================================================================\n`;
    text += `DECISION GRAVEYARD - PRODUCT MANAGER DECISION BRIEFING\n`;
    text += `======================================================================\n`;
    text += `1. Potential Ghost Decision Detected:\n   ${statusStr} [Confidence: ${conf}]\n\n`;
    text += `2. Current Proposals Involved:\n   ${currentReport.proposal_id} (${cleanMarkdownString(currentReport.proposal_title)})\n\n`;
    text += `3. Historical Decision Matched:\n   ${(currentReport.historical_matches || []).join(", ") || "None"}\n\n`;
    text += `4. Why This Looks Familiar:\n   ${cleanMarkdownString(currentReport.composite_relationship_explanation || currentReport.relationship_explanation || "N/A")}\n\n`;
    text += `5. Historical Outcome:\n   ${cleanMarkdownString(currentReport.historical_status || "Abandoned")}\n\n`;
    text += `6. Historical Blockers:\n${(currentReport.historical_blockers || []).map(b => `   - ${cleanMarkdownString(b)}`).join("\n") || "   - None documented"}\n\n`;
    text += `7. Current Company Conditions:\n${Object.entries(currentReport.current_conditions || {}).map(([k, v]) => `   - ${k.replace(/_/g, ' ').toUpperCase()}: ${v}`).join("\n") || "   - Operational context available"}\n\n`;
    text += `8. Blockers That May Still Apply:\n${(currentReport.blockers_that_may_still_apply || []).map(b => `   - ${cleanMarkdownString(b)}`).join("\n") || "   - None identified"}\n\n`;
    text += `9. Blockers That May Have Changed:\n${(currentReport.blockers_that_may_have_changed || []).map(b => `   - ${cleanMarkdownString(b)}`).join("\n") || "   - None identified"}\n\n`;
    text += `10. Human Review Questions (For PM Evaluation):\n${(currentReport.questions_for_product_manager || []).map(q => `   ? ${cleanMarkdownString(q)}`).join("\n") || "   ? What are key architectural tradeoffs?"}\n`;
    text += `======================================================================\n`;
    text += `NOTE: Consultative intelligence only. The Product Manager remains the\nfinal decision-maker regarding approval, modification, or rejection.\n`;

    navigator.clipboard.writeText(text).then(() => {
      alert("10-Point Product Manager Briefing copied to clipboard!");
    }).catch(() => {
      console.log(text);
      alert("Briefing copied to console.");
    });
  }

  if (btnCopyBriefing) btnCopyBriefing.addEventListener("click", copyBriefingToClipboard);
  if (btnCopyBriefingSandbox) btnCopyBriefingSandbox.addEventListener("click", copyBriefingToClipboard);

  // =========================================================================
  // 7. DECISION HISTORY TABLE & MODAL
  // =========================================================================

  async function fetchHistoricalDecisions() {
    try {
      const res = await fetch("/historical-decisions");
      if (!res.ok) throw new Error("Could not load historical decisions");
      loadedDecisions = await res.json();
      renderDecisionsTable(loadedDecisions);
    } catch (err) {
      console.warn("Historical decisions fetch error:", err);
      if (decisionsTableBody) {
        decisionsTableBody.innerHTML = '<tr><td colspan="7" class="text-muted" style="text-align: center; padding: 2rem;">Unable to load historical decisions.</td></tr>';
      }
    }
  }

  function renderDecisionsTable(decisions) {
    if (!decisionsTableBody) return;
    decisionsTableBody.innerHTML = "";

    if (!decisions.length) {
      decisionsTableBody.innerHTML = '<tr><td colspan="7" class="text-muted" style="text-align: center; padding: 2rem;">No matching historical decisions found.</td></tr>';
      return;
    }

    decisions.forEach(d => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="td-id">${escapeHtml(d.decision_id)}</td>
        <td class="td-title">${escapeHtml(d.title)}</td>
        <td><span class="badge-evidence">${escapeHtml(d.category)}</span></td>
        <td><span class="status-pill-big status-${(d.status || '').toLowerCase()}">${escapeHtml(d.status)}</span></td>
        <td>${escapeHtml(d.date || 'N/A')}</td>
        <td class="td-summary">${escapeHtml(d.lesson_learned || d.business_problem || '')}</td>
        <td style="text-align: right;">
          <button class="btn-secondary btn-small btn-view-d" data-id="${d.decision_id}">Details</button>
        </td>
      `;

      tr.querySelector(".btn-view-d").addEventListener("click", () => {
        openDecisionModal(d);
      });

      decisionsTableBody.appendChild(tr);
    });
  }

  function filterDecisions() {
    const query = (histSearchInput?.value || "").toLowerCase().trim();
    const statusVal = histStatusFilter?.value || "ALL";
    const catVal = histCategoryFilter?.value || "ALL";

    const filtered = loadedDecisions.filter(d => {
      const matchesQuery = !query ||
        d.decision_id.toLowerCase().includes(query) ||
        d.title.toLowerCase().includes(query) ||
        (d.business_problem || "").toLowerCase().includes(query) ||
        (d.lesson_learned || "").toLowerCase().includes(query);

      const matchesStatus = statusVal === "ALL" || d.status.toLowerCase() === statusVal.toLowerCase();
      const matchesCat = catVal === "ALL" || d.category.toLowerCase() === catVal.toLowerCase();

      return matchesQuery && matchesStatus && matchesCat;
    });

    renderDecisionsTable(filtered);
  }

  if (histSearchInput) histSearchInput.addEventListener("input", filterDecisions);
  if (histStatusFilter) histStatusFilter.addEventListener("change", filterDecisions);
  if (histCategoryFilter) histCategoryFilter.addEventListener("change", filterDecisions);

  function openDecisionModal(d) {
    if (!decisionModal) return;
    document.getElementById("modalDecisionId").textContent = d.decision_id;
    document.getElementById("modalDecisionTitle").textContent = d.title;
    document.getElementById("modalDecisionCategory").textContent = d.category;
    document.getElementById("modalDecisionDate").textContent = d.date;

    const statusPill = document.getElementById("modalDecisionStatus");
    statusPill.className = `status-pill-big status-${(d.status || '').toLowerCase()}`;
    statusPill.textContent = d.status;

    document.getElementById("modalBusinessProblem").textContent = d.business_problem || "N/A";
    document.getElementById("modalProposal").textContent = d.proposal || d.chosen_option || "N/A";

    const failReasonsList = document.getElementById("modalFailureReasons");
    failReasonsList.innerHTML = "";
    const reasons = d.failure_reasons || d.reasoning || [];
    if (reasons.length) {
      reasons.forEach(r => {
        const li = document.createElement("li");
        li.textContent = r;
        failReasonsList.appendChild(li);
      });
    } else {
      failReasonsList.innerHTML = "<li>No specific failure reasons documented.</li>";
    }

    document.getElementById("modalLessonLearned").textContent = d.lesson_learned || d.expected_outcome || "No formal lesson recorded.";

    decisionModal.classList.remove("hidden");
  }

  if (btnCloseModal) {
    btnCloseModal.addEventListener("click", () => {
      decisionModal.classList.add("hidden");
    });
  }

  if (decisionModal) {
    decisionModal.addEventListener("click", (e) => {
      if (e.target === decisionModal) decisionModal.classList.add("hidden");
    });
  }

  // =========================================================================
  // 7.5. ADVISORY INTELLIGENCE MODAL INTERACTION
  // =========================================================================

  const btnAdvisoryIntelligence = document.getElementById("btnAdvisoryIntelligence");
  const advisoryModal = document.getElementById("advisoryModal");
  const btnCloseAdvisoryModal = document.getElementById("btnCloseAdvisoryModal");
  const btnDismissAdvisoryModal = document.getElementById("btnDismissAdvisoryModal");
  let advisoryOpen = false;

  function setAdvisoryModalState(isOpen) {
    advisoryOpen = Boolean(isOpen);
    if (!advisoryModal) return;
    if (advisoryOpen) {
      advisoryModal.classList.remove("hidden");
      advisoryModal.style.display = "flex";
    } else {
      advisoryModal.classList.add("hidden");
      advisoryModal.style.display = "none";
    }
  }

  window.setAdvisoryModalState = setAdvisoryModalState;

  function openAdvisoryModal() {
    setAdvisoryModalState(true);
  }

  function closeAdvisoryModal() {
    setAdvisoryModalState(false);
  }

  if (btnAdvisoryIntelligence) {
    btnAdvisoryIntelligence.addEventListener("click", openAdvisoryModal);
  }

  if (btnCloseAdvisoryModal) {
    btnCloseAdvisoryModal.addEventListener("click", closeAdvisoryModal);
  }

  if (btnDismissAdvisoryModal) {
    btnDismissAdvisoryModal.addEventListener("click", closeAdvisoryModal);
  }

  if (advisoryModal) {
    advisoryModal.addEventListener("click", (e) => {
      if (e.target === advisoryModal) {
        closeAdvisoryModal();
      }
    });
  }

  // Keyboard accessibility: ESC key closes open modals
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (advisoryOpen || (advisoryModal && !advisoryModal.classList.contains("hidden"))) {
        closeAdvisoryModal();
      }
      if (decisionModal && !decisionModal.classList.contains("hidden")) {
        decisionModal.classList.add("hidden");
      }
    }
  });

  // =========================================================================
  // 8. INITIALIZE APP
  // =========================================================================

  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  fetchDashboardStats();
  fetchProposals();
  fetchHistoricalDecisions();
});
