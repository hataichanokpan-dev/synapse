"""
Test all 16 Synapse MCP Tools
"""
import sys
sys.path.insert(0, 'synapse/mcp_server/src')

import asyncio
import json
from datetime import datetime

# Import all tools
from graphiti_mcp_server import (
    add_memory, search_nodes, search_memory_facts, search_memory_layers,
    delete_entity_edge, delete_episode, get_entity_edge, get_episodes,
    clear_graph, get_status, initialize_server
)

# Import Thai NLP module
try:
    from synapse import nlp as thai_nlp
    THAI_NLP_AVAILABLE = True
except ImportError:
    THAI_NLP_AVAILABLE = False

def print_result(name, result):
    print(f"\n{'='*60}")
    print(f"### {name}")
    print('='*60)
    if hasattr(result, 'model_dump'):
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    elif isinstance(result, dict):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result)

async def main():
    print("="*60)
    print("Synapse MCP Tools Test Suite")
    print(f"Time: {datetime.now().isoformat()}")
    print("="*60)

    # Initialize server first
    print("\nInitializing server...")
    try:
        await initialize_server()
        print("Server initialized!")
    except Exception as e:
        print(f"Init error: {e}")

    results = []

    # 1. get_status
    print("\n[1/16] Testing get_status...")
    try:
        r = await get_status()
        print_result("get_status", r)
        results.append(("get_status", "PASS" if r else "FAIL"))
    except Exception as e:
        print(f"ERROR: {e}")
        results.append(("get_status", f"ERROR: {e}"))

    # 2. add_memory
    print("\n[2/16] Testing add_memory...")
    try:
        r = await add_memory(
            name="test_episode",
            episode_body="ทดสอบการเพิ่ม memory ภาษาไทย โบ๊ทเป็น developer ที่ทำโปรเจค Synapse",
            group_id="test_group",
            source_description="MCP Test"
        )
        print_result("add_memory", r)
        results.append(("add_memory", "PASS" if r else "FAIL"))
    except Exception as e:
        print(f"ERROR: {e}")
        results.append(("add_memory", f"ERROR: {e}"))

    # 3. search_nodes
    print("\n[3/16] Testing search_nodes...")
    try:
        r = await search_nodes(query="โบ๊ท Synapse", group_ids=["test_group"])
        print_result("search_nodes", r)
        results.append(("search_nodes", "PASS" if r else "FAIL"))
    except Exception as e:
        print(f"ERROR: {e}")
        results.append(("search_nodes", f"ERROR: {e}"))

    # 4. search_memory_facts
    print("\n[4/16] Testing search_memory_facts...")
    try:
        r = await search_memory_facts(query="developer", group_ids=["test_group"])
        print_result("search_memory_facts", r)
        results.append(("search_memory_facts", "PASS" if r else "FAIL"))
    except Exception as e:
        print(f"ERROR: {e}")
        results.append(("search_memory_facts", f"ERROR: {e}"))

    # 5. search_memory_layers
    print("\n[5/16] Testing search_memory_layers...")
    try:
        r = await search_memory_layers(query="โบ๊ท", layers=["episodic", "semantic"])
        print_result("search_memory_layers", r)
        results.append(("search_memory_layers", "PASS" if r else "FAIL"))
    except Exception as e:
        print(f"ERROR: {e}")
        results.append(("search_memory_layers", f"ERROR: {e}"))

    # 6. get_episodes
    print("\n[6/16] Testing get_episodes...")
    try:
        r = await get_episodes(group_ids=["test_group"], max_episodes=5)
        print_result("get_episodes", r)
        results.append(("get_episodes", "PASS" if r else "FAIL"))
    except Exception as e:
        print(f"ERROR: {e}")
        results.append(("get_episodes", f"ERROR: {e}"))

    # 7. get_entity_edge
    print("\n[7/16] Testing get_entity_edge...")
    try:
        r = await get_entity_edge(uuid="non-existent-uuid")
        print_result("get_entity_edge", r)
        results.append(("get_entity_edge", "PASS"))
    except Exception as e:
        print(f"ERROR: {e}")
        results.append(("get_entity_edge", f"ERROR: {e}"))

    # 8. delete_entity_edge
    print("\n[8/16] Testing delete_entity_edge...")
    try:
        r = await delete_entity_edge(uuid="non-existent-uuid")
        print_result("delete_entity_edge", r)
        results.append(("delete_entity_edge", "PASS"))
    except Exception as e:
        print(f"ERROR: {e}")
        results.append(("delete_entity_edge", f"ERROR: {e}"))

    # 9. delete_episode
    print("\n[9/16] Testing delete_episode...")
    try:
        r = await delete_episode(uuid="non-existent-uuid")
        print_result("delete_episode", r)
        results.append(("delete_episode", "PASS"))
    except Exception as e:
        print(f"ERROR: {e}")
        results.append(("delete_episode", f"ERROR: {e}"))

    # 10. clear_graph (skip - destructive)
    print("\n[10/16] Skipping clear_graph (destructive)")
    results.append(("clear_graph", "SKIPPED"))

    # Thai NLP Tools
    print("\n" + "="*60)
    print("THAI NLP TOOLS")
    print("="*60)

    if not THAI_NLP_AVAILABLE:
        print("Thai NLP module not available, skipping tests...")
        for name in ["detect_language", "preprocess_for_extraction", "preprocess_for_search",
                     "tokenize_thai", "normalize_thai", "is_thai_text"]:
            results.append((name, "SKIPPED (module not available)"))
    else:
        # 11. detect_language
        print("\n[11/16] Testing detect_language...")
        try:
            r = thai_nlp.detect_language("สวัสดีครับ นี่คือการทดสอบ")
            print(f"language: {r.language}, confidence: {r.confidence}, thai_ratio: {r.thai_ratio}")
            results.append(("detect_language", "PASS"))
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(("detect_language", f"ERROR: {e}"))

        # 12. preprocess_for_extraction
        print("\n[12/16] Testing preprocess_for_extraction...")
        try:
            r = thai_nlp.preprocess_for_extraction("เเปลกมากๆ ที่่มีการเขียนผิด")
            print(f"original: {r.original}")
            print(f"processed: {r.processed}")
            print(f"was_normalized: {r.was_normalized}")
            results.append(("preprocess_for_extraction", "PASS"))
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(("preprocess_for_extraction", f"ERROR: {e}"))

        # 13. preprocess_for_search
        print("\n[13/16] Testing preprocess_for_search...")
        try:
            r = thai_nlp.preprocess_for_search("ค้นหาข้อมูลเกี่ยวกับโปรเจค")
            print(f"result: {r}")
            results.append(("preprocess_for_search", "PASS"))
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(("preprocess_for_search", f"ERROR: {e}"))

        # 14. tokenize_thai
        print("\n[14/16] Testing tokenize_thai...")
        try:
            r = thai_nlp.tokenize("ภาษาไทยไม่มีช่องว่างระหว่างคำ")
            print(f"tokens: {r}")
            results.append(("tokenize_thai", "PASS"))
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(("tokenize_thai", f"ERROR: {e}"))

        # 15. normalize_thai
        print("\n[15/16] Testing normalize_thai...")
        try:
            r = thai_nlp.normalize("เเปลก ําไร ่ ้", level="aggressive")
            print(f"normalized: {r}")
            results.append(("normalize_thai", "PASS"))
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(("normalize_thai", f"ERROR: {e}"))

        # 16. is_thai_text
        print("\n[16/16] Testing is_thai_text...")
        try:
            r = thai_nlp.is_thai("นี่คือภาษาไทย")
            print(f"is_thai: {r}")
            results.append(("is_thai_text", "PASS"))
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(("is_thai_text", f"ERROR: {e}"))

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, status in results:
        icon = "✅" if status == "PASS" else "⏭️" if "SKIPPED" in status else "❌"
        print(f"{icon} {name}: {status}")

    passed = sum(1 for _, s in results if s == "PASS")
    print(f"\nTotal: {passed}/16 passed")

if __name__ == "__main__":
    asyncio.run(main())
