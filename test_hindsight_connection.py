"""Hindsight Connectivity and Memory Verification Test.

Step 5 Verification:
1. Loads HINDSIGHT_API_KEY, HINDSIGHT_BASE_URL, and HINDSIGHT_BANK_ID from .env.
2. Connects to the Hindsight memory bank.
3. Retains a sample historical decision memory.
4. Recalls memories using a semantic query.
5. Prints the returned memories.
"""

import os
import sys
from dotenv import load_dotenv

# Ensure stdout/stderr handles UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure the current project directory is available on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

TEST_MEMORY_CONTENT = (
    "NovaTech previously tested an employee mobile application in 2024. "
    "The initiative was abandoned because mobile adoption was only 18%, "
    "the engineering team was small, maintenance cost was high, "
    "and an existing web application was considered sufficient."
)

TEST_QUERY = "What happened when NovaTech previously considered an employee mobile application?"


def mask_key(key: str | None) -> str:
    """Mask sensitive API keys for display."""
    if not key or key.strip().lower() in ("your_hindsight_api_key_here", "placeholder", "changeme"):
        return "(none / placeholder)"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def run_hindsight_test():
    print("=" * 70)
    print("Decision Graveyard - Hindsight Connectivity Test")
    print("=" * 70)

    # 1. Load configuration from .env
    env_loaded = load_dotenv()
    api_key = os.getenv("HINDSIGHT_API_KEY")
    base_url = os.getenv("HINDSIGHT_BASE_URL", "http://localhost:8888")
    bank_id = os.getenv("HINDSIGHT_BANK_ID", "decision-graveyard")

    clean_api_key = api_key if (api_key and api_key.strip().lower() not in (
        "your_hindsight_api_key_here", "placeholder", "changeme"
    )) else None

    print(f"\n[1] Configuration Loaded (.env loaded: {env_loaded}):")
    print(f"    - HINDSIGHT_BASE_URL : {base_url}")
    print(f"    - HINDSIGHT_BANK_ID  : {bank_id}")
    print(f"    - HINDSIGHT_API_KEY  : {mask_key(api_key)}")

    # 2. Connect to Hindsight Client & Bank
    print(f"\n[2] Connecting to Hindsight server at '{base_url}'...")
    try:
        from hindsight_client import Hindsight
    except ImportError:
        print("\n[ERROR] 'hindsight-client' is not installed in the current environment.")
        print("        Install it via: pip install hindsight-client")
        return False

    client = Hindsight(
        base_url=base_url,
        api_key=clean_api_key,
    )

    # Verify connection and ensure bank exists
    bank_connected = False
    try:
        bank_config = client.get_bank_config(bank_id=bank_id)
        bank_connected = True
        print(f"    [OK] Successfully connected to existing bank '{bank_id}'.")
        if isinstance(bank_config, dict) and "name" in bank_config:
            print(f"         Bank Name: {bank_config.get('name')}")
    except Exception as check_err:
        err_str = str(check_err)
        # If connection is refused / network unreachable
        if "refused" in err_str.lower() or "cannot connect" in err_str.lower() or "10061" in err_str or "1225" in err_str:
            print(f"\n[ERROR] Cannot connect to Hindsight server at '{base_url}'.")
            print(f"        Network connection was refused.")
            print("\nNext steps to resolve:")
            print(f"1. Ensure the Hindsight service is running on {base_url}.")
            print("2. If running locally with Docker:")
            print("   docker run -d -p 8888:8888 ghcr.io/vectorize-io/hindsight:latest")
            print("3. If using an external/cloud Hindsight service, update .env with your URL and API key:")
            print("   HINDSIGHT_BASE_URL=https://your-hindsight-instance.com")
            print("   HINDSIGHT_API_KEY=your_actual_key")
            return False

        # Otherwise, the server responded but the bank might not exist yet -> attempt creation
        print(f"    [INFO] Bank '{bank_id}' not found. Attempting to create it...")
        try:
            client.create_bank(
                bank_id=bank_id,
                name="Decision Graveyard",
                mission=(
                    "Retain and synthesize organizational decision history, past project outcomes, "
                    "constraints, failure causes, and architectural trade-offs."
                ),
            )
            bank_connected = True
            print(f"    [OK] Successfully created memory bank '{bank_id}'.")
        except Exception as create_err:
            print(f"\n[ERROR] Failed to create bank '{bank_id}' at '{base_url}': {create_err}")
            return False

    if not bank_connected:
        return False

    # 3. Retain Test Memory
    print(f"\n[3] Retaining test memory into bank '{bank_id}'...")
    print(f"    Content: \"{TEST_MEMORY_CONTENT}\"")
    try:
        retain_res = client.retain(
            bank_id=bank_id,
            content=TEST_MEMORY_CONTENT,
            document_id="test-d001-connectivity",
            metadata={
                "source": "step-5-connectivity-test",
                "category": "Product",
                "initiative": "employee-mobile-app",
            },
            tags=["test", "mobile-app", "historical-precedent"],
        )
        items_count = getattr(retain_res, "items_count", 1)
        success = getattr(retain_res, "success", True)
        print(f"    [OK] Memory retained successfully! (success={success}, items_count={items_count})")
    except Exception as retain_err:
        print(f"\n[ERROR] Retain operation failed: {retain_err}")
        return False

    # 4. Recall Using Test Query
    print(f"\n[4] Recalling memories using query:")
    print(f"    Query: \"{TEST_QUERY}\"")
    try:
        recall_res = client.recall(
            bank_id=bank_id,
            query=TEST_QUERY,
            max_tokens=2048,
        )
    except Exception as recall_err:
        print(f"\n[ERROR] Recall operation failed: {recall_err}")
        return False

    # 5. Print Returned Memories
    print("\n[5] Returned Memories from Hindsight:")
    print("-" * 70)
    results = getattr(recall_res, "results", [])
    if not results:
        prompt_str = getattr(recall_res, "to_prompt_string", None)
        if callable(prompt_str):
            print(prompt_str())
        else:
            print("    (No memory units returned for this query)")
    else:
        for idx, item in enumerate(results, 1):
            item_id = getattr(item, "id", f"item-{idx}")
            item_type = getattr(item, "type", "observation")
            item_text = getattr(item, "text", str(item))
            item_tags = getattr(item, "tags", [])
            print(f"  [{idx}] Type: {item_type} | ID: {item_id}")
            if item_tags:
                print(f"      Tags: {', '.join(item_tags)}")
            print(f"      Text: {item_text}\n")

    print("-" * 70)
    print("[SUCCESS] Hindsight connectivity, retain, and recall test completed successfully!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_hindsight_test()
    sys.exit(0 if success else 1)
