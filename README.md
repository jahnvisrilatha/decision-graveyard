# Decision Graveyard 🪦💡

An AI agent designed to help Product Managers evaluate new product or feature proposals against the organization's historical decisions.

It answers the core question:  
**"Have we tried something like this before?"**

---

## 📌 Step 4: Basic AI Agent & Backend

This repository implements **Step 4** of Decision Graveyard:
- Loads active proposals from `data/current_proposals.json`
- Loads historical organizational decisions from `data/historical_decisions.json`
- Loads company capabilities and historical changes from `data/company_context.json`
- Analyzes candidate historical decisions (outcomes, success/failure drivers, past constraints)
- Compares past conditions against current company context
- Identifies blockers that still exist vs. those that have changed/cleared
- Returns a structured **Decision Intelligence Report** via a FastAPI backend

*(Note: Hindsight, Ghost Decision Detection, and the frontend will be added in subsequent phases).*

---

## 📂 Project Structure

```text
decision_gravyard/
│
├── data/                                # (Unmodified) Source data files
│   ├── company_context.json             # Current operational metrics and changes
│   ├── current_proposals.json           # Proposals under review (P001–P005)
│   └── historical_decisions.json        # Past decisions (D001–D015)
│
├── agent/                               # Core AI Agent Logic
│   ├── __init__.py                      # Package exports
│   ├── models.py                        # Pydantic data schemas & Report models
│   ├── data_loader.py                   # Safe, structured JSON data loaders
│   ├── llm_client.py                    # Multi-provider LLM Client (Gemini, OpenAI, & Mock)
│   └── decision_agent.py                # 11-step Decision Analysis Agent
│
├── api/
│   └── main.py                          # FastAPI backend application
│
├── requirements.txt                     # Python dependencies
└── README.md                            # Documentation and quickstart
```

---

## 🚀 Quickstart Guide

### 1. Set Up Environment & Install Dependencies

Ensure you have Python 3.10+ installed.

```bash
# Create virtual environment (optional but recommended)
python -m venv venv

# Activate on Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Activate on macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables (Optional)

The agent supports **Google Gemini**, **OpenAI**, or runs in **Smart Fallback Mode** (out-of-the-box local reasoning engine if no API keys are provided).

To use an external LLM, create a `.env` file or export environment variables:

```bash
# For Google Gemini (Recommended):
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Or for OpenAI:
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

---

## 🏃 Running the FastAPI Server

Start the API with Uvicorn:

```bash
uvicorn api.main:app --reload --port 8000
```

Once running, interactive Swagger documentation is available at:  
👉 **http://127.0.0.1:8000/docs**

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check (`{"status": "ok"}`) |
| `GET` | `/proposals` | List all current proposals awaiting review from `current_proposals.json` |
| `POST` | `/analyze/{proposal_id}` | Analyze a proposal using `DecisionAgent` and store report in memory |
| `GET` | `/reports/{proposal_id}` | Retrieve previously generated report from in-memory session store |


---

## 🧪 Testing the Agent

### Example: Analyze Proposal `P001` (Unified Employee Mobile Platform)

Using `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/analyze/P001" -H "accept: application/json"
```

Or run directly in Python:

```python
from agent.decision_agent import DecisionAgent

agent = DecisionAgent()
report = agent.analyze_proposal("P001")

print(f"Report ID: {report.report_id}")
print(f"Have we tried this before? {report.have_we_tried_this_before}")
print(f"Verdict: {report.headline_verdict}")
print(f"Risk Level: {report.risk_level}")
print("\nRelated Historical Decisions:")
for d in report.related_decisions:
    print(f"- [{d.status}] {d.decision_id}: {d.title}")
    print(f"  Outcome: {d.historical_outcome}")
    print(f"  Past vs Present: {d.past_vs_present_conditions}")
```

### Sample Output (`DecisionIntelligenceReport`):

```json
{
  "report_id": "REP-P001-A4B1C2",
  "proposal_id": "P001",
  "proposal_title": "Unified Employee Mobile Platform",
  "proposal_category": "Product",
  "have_we_tried_this_before": true,
  "headline_verdict": "Yes, NovaTech previously attempted a native mobile application (D001) in 2024, which was abandoned. However, key conditions around mobile adoption and team size have improved dramatically.",
  "related_decisions": [
    {
      "decision_id": "D001",
      "title": "Employee Mobile Application",
      "category": "Product",
      "status": "Abandoned",
      "relevance_summary": "Attempted to build native Android and iOS mobile applications for employee attendance, leave management, and company notifications.",
      "historical_outcome": "Project was abandoned after initial development phase.",
      "outcome_drivers": [
        "Only 18% of employees regularly used mobile devices for company tasks in 2024.",
        "Small engineering team (5 developers) could not absorb dual-platform mobile overhead.",
        "Existing web portal already supported core workflows."
      ],
      "past_vs_present_conditions": "In 2024, mobile adoption was only 18% with 5 developers. In 2026, mobile adoption is 76% and the engineering team has expanded to 15 developers.",
      "blockers_still_existing": [
        "Maintenance overhead of native mobile applications compared to modern web/PWA.",
        "Web portal and PWA are already active and familiar to employees."
      ],
      "blockers_changed_or_cleared": [
        "Employee mobile usage increased from 18% to 76%.",
        "Engineering team expanded from 5 to 15 engineers.",
        "DevOps maturity is now High with automated CI/CD."
      ],
      "key_lesson": "Do not build separate native applications if employee mobile adoption needs can be fulfilled through Progressive Web Applications or responsive portals."
    }
  ],
  "overall_blockers_status": {
    "cleared": [
      "User adoption hurdle: Mobile adoption jumped from 18% to 76%.",
      "Engineering capacity: Team grew from 5 to 15 engineers."
    ],
    "still_present": [
      "Redundancy risk: Overlapping features with existing employee web portal."
    ]
  },
  "strategic_recommendations": [
    "Evaluate whether extending the existing Progressive Web Application (PWA) meets user needs before committing to native apps.",
    "Focus initially on mobile notification and leave approval rather than rebuilding all HR features."
  ],
  "risk_level": "Medium"
}
```
