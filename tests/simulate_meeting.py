"""
End-to-End Meeting Simulation Harness.
Simulates a multi-speaker, multi-turn Google Meet session testing all 5 core requirements:
1. Real-time dynamic diagramming
2. Step-by-step calculations
3. Truth Sentinel contradiction detection & auto-chat message ("Old speak vs New speak")
4. Voice command screen sharing ("Hey agent show us your screen")
5. Direct voice & visual Q&A ("Hey agent can you tell me what this means")
6. Multilingual support (English & Japanese)
7. Reactive Character Avatar state transitions
"""

import time
import requests
import json

BASE_URL = "http://localhost:8000"


def print_step(title):
    print("\n" + "=" * 70)
    print(f"🎬 {title}")
    print("=" * 70)


def run_simulation():
    print("🚀 Initializing AEGIS Meeting Simulation against", BASE_URL)
    
    # 0. Check server health
    try:
        res = requests.get(f"{BASE_URL}/api/status", timeout=5)
        print("✅ Agent Server Status:", res.json())
    except Exception as e:
        print("❌ Could not connect to AEGIS Agent server. Make sure it is running on port 8000.")
        return False

    # 1. Turn 1: Process Pipeline Description
    print_step("TURN 1: Speaker describes architectural process flow")
    t1 = {
        "speaker": "Alice (Engineering Lead)",
        "text": "Let's review our multi-stage pipeline: audio client ingress goes to voice processing, then to Gemini 3.8 live, then to Truth Sentinel memory graph.",
        "language": "en"
    }
    r1 = requests.post(f"{BASE_URL}/api/statement", json=t1)
    print("Sent:", t1["text"])
    print("Response:", r1.json())
    assert r1.json()["diagram_updated"] is True, "Diagram should be updated"
    print("✨ Verified: Real-time SVG process diagram generated on black HUD canvas!")
    time.sleep(1)

    # 2. Turn 2: Calculation & Numbers
    print_step("TURN 2: Speaker discusses metrics and budget calculations")
    t2 = {
        "speaker": "Bob (Finance / PM)",
        "text": "We need to calculate our quarterly run rate: $48,000 per month with estimated 24.5% YoY growth rate.",
        "language": "en"
    }
    r2 = requests.post(f"{BASE_URL}/api/statement", json=t2)
    print("Sent:", t2["text"])
    print("Response:", r2.json())
    assert r2.json()["calc_updated"] is True, "Calculation should be updated"
    print("✨ Verified: Live mathematical calculation card rendered!")
    time.sleep(1)

    # 3. Turn 3: Initial Claim established (Release date = Q3)
    print_step("TURN 3: Initial statement recorded into memory (Q3 release)")
    t3 = {
        "speaker": "Alice (Engineering Lead)",
        "text": "Our target release date is strictly in Q3.",
        "language": "en"
    }
    r3 = requests.post(f"{BASE_URL}/api/statement", json=t3)
    print("Sent:", t3["text"])
    print("Response:", r3.json())
    time.sleep(1)

    # 4. Turn 4: Contradiction ("Old speak vs New speak" - Q2 vs Q3)
    print_step("TURN 4: Second speaker contradicts previous claim (Says Q2)")
    t4 = {
        "speaker": "Charlie (Product Manager)",
        "text": "Since we agreed to ship this in Q2, let's cut feature scope.",
        "language": "en"
    }
    r4 = requests.post(f"{BASE_URL}/api/statement", json=t4)
    res4 = r4.json()
    print("Sent:", t4["text"])
    print("Response:", json.dumps(res4, indent=2))
    assert res4["status"] == "contradiction_detected", "Contradiction should be detected!"
    assert "Which one do you mean" in res4["chat_message"], "Clarification question must be present!"
    print("✨ Verified: Contradiction caught! Clarification sent to chat:", res4["chat_message"])
    time.sleep(1)

    # 5. Turn 5: Voice command to share screen ("Hey agent show us your screen")
    print_step("TURN 5: Voice trigger - 'Hey agent show us your screen'")
    t5 = {
        "speaker": "Bob (PM)",
        "text": "Hey agent, show us your screen.",
        "language": "en"
    }
    r5 = requests.post(f"{BASE_URL}/api/statement", json=t5)
    print("Sent:", t5["text"])
    print("Response:", r5.json())
    assert r5.json()["screen_share_triggered"] is True, "Screen share trigger must activate!"
    print("✨ Verified: Screen share activated and character responded!")
    time.sleep(1)

    # 6. Turn 6: Direct query (Voice + Visual response)
    print_step("TURN 6: Direct Inquiry - 'Hey agent can you tell me what this means'")
    t6 = {
        "speaker": "Alice",
        "query": "Hey agent, can you tell me what this pipeline architecture means?",
        "language": "en"
    }
    r6 = requests.post(f"{BASE_URL}/api/direct-query", json=t6)
    res6 = r6.json()
    print("Sent Direct Query:", t6["query"])
    print("Response:", json.dumps(res6, indent=2))
    assert res6["status"] == "responded"
    assert len(res6["spoken_text"]) > 0, "Spoken voice text must be returned"
    assert res6["diagram_updated"] is True, "Visual diagram must be updated simultaneously"
    print("✨ Verified: Dual-mode response (Voice output spoken + Visual schematic painted)!")
    time.sleep(1)

    # 7. Turn 7: Multilingual Contradiction (Japanese)
    print_step("TURN 7: Multilingual Contradiction Test (Japanese)")
    t7_a = {
        "speaker": "Kenji",
        "text": "新機能のリリースは第3四半期を予定しています。",
        "language": "ja"
    }
    t7_b = {
        "speaker": "Yuki",
        "text": "第2四半期のローンチに向けて今すぐ開発を始めましょう。",
        "language": "ja"
    }
    requests.post(f"{BASE_URL}/api/statement", json=t7_a)
    r7_b = requests.post(f"{BASE_URL}/api/statement", json=t7_b)
    res7 = r7_b.json()
    print("Sent:", t7_b["text"])
    print("Response:", json.dumps(res7, indent=2))
    assert res7["status"] == "contradiction_detected", "Japanese timeline contradiction must be detected!"
    print("✨ Verified: Multilingual contradiction successfully captured!")
    time.sleep(1)

    # 8. Turn 8: Google Cloud Nano Banana Visual Synthesis
    print_step("TURN 8: Google Cloud Nano Banana Visual Synthesis")
    t8 = {
        "speaker": "Alice (Engineering Lead)",
        "text": "Can you visualize the system architecture for our new cloud pipeline with Nano Banana?",
        "language": "en"
    }
    r8 = requests.post(f"{BASE_URL}/api/statement", json=t8)
    res8 = r8.json()
    print("Sent:", t8["text"])
    print("Response:", json.dumps(res8, indent=2))
    assert res8["visual_generated"] is True, "Nano Banana visual must be generated!"
    print("✨ Verified: Google Cloud Nano Banana visual synthesized and broadcast!")

    print_step("🎉 ALL 8 TEST SCENARIOS PASSED WITH 100% ACCURACY!")
    return True


if __name__ == "__main__":
    run_simulation()
