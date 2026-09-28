"""
End-to-End Verification Script for Step 9
Tests all 5 proposal scenarios, backend endpoints, Hindsight memories,
field mappings, and error handling.
"""
import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def log(msg, status="INFO"):
    symbol = "[PASS]" if status == "PASS" else ("[FAIL]" if status == "FAIL" else "[INFO]")
    print(f"{symbol} {msg}")

def test_endpoint(url, method="GET", data=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data else (b"" if method == "POST" else None),
        headers={"Content-Type": "application/json"} if method == "POST" else {},
        method=method
    )
    try:
        res = urllib.request.urlopen(req)
        return res.getcode(), json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"detail": body}
    except Exception as e:
        return 500, {"detail": str(e)}

def run_tests():
    all_passed = True
    print("=" * 70)
    print("DECISION GRAVEYARD -- STEP 9 COMPREHENSIVE END-TO-END VALIDATION")
    print("=" * 70)

    # 1. Health check
    code, res = test_endpoint(f"{BASE_URL}/health")
    if code == 200 and res.get("status") in ["ok", "healthy"]:
        log("Backend health check passed: status ok", "PASS")
    else:
        log(f"Health check failed: {code} {res}", "FAIL")
        all_passed = False

    # 2. Proposals list
    code, res = test_endpoint(f"{BASE_URL}/proposals")
    proposals_list = res if isinstance(res, list) else res.get("proposals", [])
    if code == 200 and len(proposals_list) >= 5:
        pids = [p["proposal_id"] for p in proposals_list]
        log(f"Proposals endpoint returned {len(proposals_list)} proposals: {pids}", "PASS")
    else:
        log(f"Proposals list failed: {code} {res}", "FAIL")
        all_passed = False

    # 3. TEST 1: P001 — Single Ghost Case (D001 Abandoned & D006 Successful Precedent)
    print("\n--- TEST 1: P001 (Unified Employee Mobile Platform) ---")
    code, res = test_endpoint(f"{BASE_URL}/analyze/P001", method="POST")
    if code == 200:
        is_ghost = res.get("is_potential_ghost")
        conf = res.get("ghost_confidence_level")
        matches = res.get("historical_matches", [])
        related_decs = res.get("related_historical_decisions", [])
        memories = res.get("recalled_historical_memories", [])
        still_apply = res.get("blockers_that_may_still_apply", [])
        changed = res.get("blockers_that_may_have_changed", [])
        questions = res.get("questions_for_product_manager", [])

        # Check conditions
        c1 = is_ghost is True
        c2 = conf == "High"
        c3 = "D001" in matches and "D006" in matches
        c4 = len(memories) > 0
        c5 = len(still_apply) > 0 and len(changed) > 0
        c6 = len(questions) > 0

        # Check Primary vs Related Precedent
        primary = next((d for d in related_decs if d.get("decision_id") == "D001"), None)
        precedent = next((d for d in related_decs if d.get("decision_id") == "D006"), None)
        c7 = primary is not None and primary.get("status") == "Abandoned"
        c8 = precedent is not None and precedent.get("status") == "Successful"

        if c1 and c2 and c3 and c4 and c5 and c6 and c7 and c8:
            log(f"P001 ghost detected: {is_ghost} | Confidence: {conf}", "PASS")
            log(f"Historical matches: {matches}", "PASS")
            log(f"Primary match: D001 (Status: {primary['status']})", "PASS")
            log(f"Related precedent: D006 (Status: {precedent['status']})", "PASS")
            log(f"Hindsight recalled {len(memories)} authentic memories", "PASS")
            log(f"Then vs Now: {len(still_apply)} persistent risks, {len(changed)} favorable changes", "PASS")
            log(f"Questions generated: {len(questions)} leadership tradeoff questions", "PASS")
        else:
            log(f"P001 verification failed! Details: c1={c1}, c2={c2}, c3={c3}, c4={c4}, c5={c5}, c6={c6}, c7={c7}, c8={c8}", "FAIL")
            all_passed = False
    else:
        log(f"POST /analyze/P001 returned HTTP {code}", "FAIL")
        all_passed = False

    # 4. TEST 2: P002 — Microservices Architecture
    print("\n--- TEST 2: P002 (Microservices Architecture) ---")
    code, res = test_endpoint(f"{BASE_URL}/analyze/P002", method="POST")
    if code == 200:
        matches = res.get("historical_matches", [])
        conf = res.get("ghost_confidence_level")
        memories = res.get("recalled_historical_memories", [])
        if "D002" in matches and len(memories) > 0:
            log(f"P002 matched historical decision D002 (Microservices Migration) | Confidence: {conf}", "PASS")
            log(f"Hindsight recalled {len(memories)} memories", "PASS")
        else:
            log(f"P002 verification failed: matches={matches}", "FAIL")
            all_passed = False
    else:
        log(f"POST /analyze/P002 failed with HTTP {code}", "FAIL")
        all_passed = False

    # 5. TEST 3: P003 — Control Case (Infrastructure / Regional Datacenter)
    print("\n--- TEST 3: P003 (Control Case: Regional Customer Data Center) ---")
    code, res = test_endpoint(f"{BASE_URL}/analyze/P003", method="POST")
    if code == 200:
        is_ghost = res.get("is_potential_ghost")
        conf = res.get("ghost_confidence_level")
        matches = res.get("historical_matches", [])
        if not is_ghost and len(matches) == 0:
            log(f"P003 control case passed: No Strong Ghost Detected (is_ghost={is_ghost}, Confidence={conf})", "PASS")
            log("No false positive ghost triggered for distinct technical domain", "PASS")
        else:
            log(f"P003 control case failed: is_ghost={is_ghost}, matches={matches}", "FAIL")
            all_passed = False
    else:
        log(f"POST /analyze/P003 failed with HTTP {code}", "FAIL")
        all_passed = False

    # 6. TEST 4: P004 — Subscription Pricing Model
    print("\n--- TEST 4: P004 (Subscription Pricing Model) ---")
    code, res = test_endpoint(f"{BASE_URL}/analyze/P004", method="POST")
    if code == 200:
        matches = res.get("historical_matches", [])
        conf = res.get("ghost_confidence_level")
        memories = res.get("recalled_historical_memories", [])
        if "D004" in matches:
            log(f"P004 matched historical decision D004 (Subscription Pricing Model) | Confidence: {conf}", "PASS")
            log(f"Hindsight recalled {len(memories)} memories for pricing models", "PASS")
        else:
            log(f"P004 verification failed: matches={matches}", "FAIL")
            all_passed = False
    else:
        log(f"POST /analyze/P004 failed with HTTP {code}", "FAIL")
        all_passed = False

    # 7. TEST 5: P005 / P005A, P005B, P005C — Composite Ghost Scenario
    print("\n--- TEST 5: P005 (Composite Ghost: P005A, P005B, P005C -> D001) ---")
    code, res = test_endpoint(f"{BASE_URL}/analyze/P005", method="POST")
    if code == 200:
        is_comp = res.get("is_composite_ghost")
        comp_conf = res.get("composite_ghost_confidence_level")
        comp_result = res.get("composite_ghost_detection_result", {})
        comp_groups = comp_result.get("composite_ghost_groups", [])

        target_matched = any(g.get("matched_historical_decision_id") == "D001" for g in comp_groups)
        pids_grouped = comp_groups[0].get("grouped_proposal_ids", []) if comp_groups else []

        if is_comp and comp_conf == "High" and target_matched:
            log(f"P005 composite ghost detected: {is_comp} | Confidence: {comp_conf}", "PASS")
            log(f"Grouped modular proposals: {pids_grouped}", "PASS")
            log("Matched composite historical decision: D001 (Employee Mobile Application)", "PASS")
            log(f"Collective relationship explanation: {res.get('composite_relationship_explanation')[:80]}...", "PASS")
        else:
            log(f"P005 composite verification failed: is_comp={is_comp}, comp_conf={comp_conf}, target_matched={target_matched}", "FAIL")
            all_passed = False
    else:
        log(f"POST /analyze/P005 failed with HTTP {code}", "FAIL")
        all_passed = False

    # 8. TEST 6: Error Handling — Invalid Proposal ID
    print("\n--- TEST 6: Error Handling (Invalid Proposal ID) ---")
    code, res = test_endpoint(f"{BASE_URL}/analyze/NON_EXISTENT_ID_999", method="POST")
    if code == 404:
        log(f"Invalid proposal ID returned HTTP 404 with clean message: {res.get('detail')}", "PASS")
    else:
        log(f"Expected HTTP 404 for invalid ID, got {code} {res}", "FAIL")
        all_passed = False

    # 9. Verify report endpoint
    print("\n--- TEST 7: Cached Reports Endpoint (GET /reports/{proposal_id}) ---")
    code, res = test_endpoint(f"{BASE_URL}/reports/P001")
    if code == 200 and res.get("proposal_id") == "P001":
        log("GET /reports/P001 successfully retrieved cached Decision Intelligence Report", "PASS")
    else:
        log(f"GET /reports/P001 failed: {code} {res}", "FAIL")
        all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("ALL STEP 9 END-TO-END VERIFICATION CHECKS PASSED PERFECTLY!")
    else:
        print("SOME CHECKS FAILED. PLEASE REVIEW LOGS ABOVE.")
    print("=" * 70)
    return all_passed

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
