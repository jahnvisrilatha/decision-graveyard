"""Verification script for STEP 8: Decision Graveyard Frontend Prototype.

Validates:
1. Static frontend assets and HTML views (Dashboard, Analyze, Report, History, How It Works).
2. API endpoints (/health, /proposals, /dashboard-stats, /historical-decisions, /analyze).
3. Test Scenario 1: P001 -> Ghost Decision D001 (Abandoned)
4. Test Scenario 2: P002 -> Precedent D002 (Microservices)
5. Test Scenario 3: P003 -> Control Case (No strong ghost)
6. Test Scenario 4: P004 -> Precedent D004 (Tiered Pricing)
7. Test Scenario 5: P005 / P005A+B+C -> Flagship Composite Ghost D001
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from api.main import app

def main():
    print("=" * 75)
    print("STEP 8: VERIFYING DECISION GRAVEYARD FRONTEND PROTOTYPE")
    print("=" * 75)

    client = TestClient(app)

    # 1. Verify Health
    h_res = client.get("/health")
    assert h_res.status_code == 200, f"Health check failed: {h_res.status_code}"
    print("[PASS] 1. API Health Check OK: /health -> 200 OK")

    # 2. Verify Root UI HTML and View Containers
    ui_res = client.get("/")
    assert ui_res.status_code == 200, f"Root UI request failed: {ui_res.status_code}"
    html = ui_res.text
    required_views = [
        ("view-dashboard", "Dashboard Page View"),
        ("view-analyze", "Analyze Proposal Form View"),
        ("view-report", "Decision Intelligence Report View"),
        ("view-history", "Decision History Table View"),
        ("view-how-it-works", "How It Works Pipeline View"),
    ]
    for view_id, desc in required_views:
        assert view_id in html, f"Missing view '{view_id}' in index.html"
        print(f"[PASS] 2. UI View Verified: {desc} (#{view_id})")

    # 3. Verify Static Assets
    css_res = client.get("/static/styles.css")
    assert css_res.status_code == 200 and len(css_res.text) > 2000
    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200 and len(js_res.text) > 2000
    print("[PASS] 3. Static Assets OK: /static/styles.css and /static/app.js served")

    # 4. Verify Dashboard Stats
    stats_res = client.get("/dashboard-stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats.get("total_historical") == 15
    assert stats.get("successful_count") == 6
    assert stats.get("failed_abandoned_rejected_total") == 9
    print(f"[PASS] 4. Dashboard Stats OK: 15 Historical Decisions (6 Successful, 9 Failed/Abandoned/Rejected)")

    # 5. Verify Historical Decisions
    hist_res = client.get("/historical-decisions")
    assert hist_res.status_code == 200
    decisions = hist_res.json()
    assert len(decisions) == 15
    print(f"[PASS] 5. Historical Decisions API OK: {len(decisions)} records loaded")

    # 6. Test Scenario 1: P001 (Unified Employee Mobile Platform)
    print("\n--- Testing Scenario 1: P001 (Unified Employee Mobile Platform) ---")
    p001_res = client.post("/analyze/P001")
    assert p001_res.status_code == 200
    p001_data = p001_res.json()
    assert p001_data.get("is_potential_ghost") is True, "P001 should be flagged as potential ghost"
    assert "D001" in str(p001_data.get("historical_matches")), "P001 should match historical decision D001"
    assert len(p001_data.get("recalled_historical_memories", [])) > 0
    print("[PASS] Scenario 1 OK: Potential Ghost Detected -> Matched D001 (Abandoned)")

    # 7. Test Scenario 2: P002 (Microservices Architecture)
    print("\n--- Testing Scenario 2: P002 (Microservices Architecture) ---")
    p002_res = client.post("/analyze/P002")
    assert p002_res.status_code == 200
    p002_data = p002_res.json()
    assert "D002" in str(p002_data.get("historical_matches")), "P002 should match historical decision D002"
    print("[PASS] Scenario 2 OK: Historical Relationship with D002 verified")

    # 8. Test Scenario 3: P003 (Regional Customer Data Center - Control Case)
    print("\n--- Testing Scenario 3: P003 (Regional Customer Data Center - Control Case) ---")
    p003_res = client.post("/analyze/P003")
    assert p003_res.status_code == 200
    p003_data = p003_res.json()
    assert p003_data.get("is_potential_ghost") is False, "P003 should NOT be flagged as ghost"
    assert p003_data.get("is_composite_ghost") is False, "P003 should NOT be composite ghost"
    print("[PASS] Scenario 3 OK: Control Case verified -> No Strong Historical Ghost Detected")

    # 9. Test Scenario 4: P004 (Tiered Subscription Pricing)
    print("\n--- Testing Scenario 4: P004 (Tiered Subscription Pricing) ---")
    p004_res = client.post("/analyze/P004")
    assert p004_res.status_code == 200
    p004_data = p004_res.json()
    assert "D004" in str(p004_data.get("historical_matches")), "P004 should relate to D004"
    print("[PASS] Scenario 4 OK: Historical Relationship with D004 verified")

    # 10. Test Scenario 5: P005 (Composite Ghost: P005A + P005B + P005C -> D001)
    print("\n--- Testing Scenario 5: P005 (Flagship Composite Ghost Detection) ---")
    p005_res = client.post("/analyze/P005")
    assert p005_res.status_code == 200
    p005_data = p005_res.json()
    assert p005_data.get("is_composite_ghost") is True, "P005 should detect composite ghost"
    comp_group = p005_data.get("composite_ghost_detection_result", {}).get("composite_ghost_groups", [{}])[0]
    assert comp_group.get("matched_historical_decision_id") == "D001"
    assert "P005A" in comp_group.get("grouped_proposal_ids", [])
    assert "P005B" in comp_group.get("grouped_proposal_ids", [])
    assert "P005C" in comp_group.get("grouped_proposal_ids", [])
    print(f"[PASS] Scenario 5 OK: Composite Ghost Detected -> P005A+B+C recreates D001 ({comp_group.get('matched_historical_decision_title')})")

    print("\n" + "=" * 75)
    print("ALL STEP 8 FRONTEND & BACKEND INTEGRATION TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 75)

if __name__ == "__main__":
    main()
