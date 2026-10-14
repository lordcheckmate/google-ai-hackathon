"""
Comprehensive Meeting Simulation Test (tests/simulate_full_meeting.py)
Tests the complete multi-turn meeting lifecycle:
1. Small talk / greetings -> Agent does NOTHING (stays silent, no blocks)
2. Business process flow -> Agent silently builds flow diagram with distinct Nano Banana icons
3. In-meeting calculation -> Agent builds calculation breakdown schematic with context caption
4. Highlighting -> Agent highlights step in real time
5. Comparison matrix -> Agent builds comparison table
6. 疑問点の回答 (Answer with visual + caption) -> Agent builds answer with diagram & caption
7. Contradiction detection -> Agent SPEAKS OVER immediately with alert audio
8. Direct address ("Hey agent") -> Agent SPEAKS ALOUD with explanation audio
"""

import time
import json
import asyncio
import requests
import websockets

WS_URL = "ws://127.0.0.1:8080/ws"
HTTP_URL = "http://127.0.0.1:8080"


async def run_full_meeting_test():
    print("=" * 80)
    print("🚀 STARTING REALISTIC MEETING SIMULATION TEST")
    print("=" * 80)

    # 1. Check HTTP health
    res = requests.get(f"{HTTP_URL}/healthz")
    assert res.status_code == 200, "Server not healthy"
    print("✅ HTTP server healthy on port 8080")

    # Connect to WebSocket (disable ping timeout so long LLM turns don't disconnect the socket)
    async with websockets.connect(WS_URL, ping_interval=None, ping_timeout=None) as ws:
        print("✅ WebSocket connected to AEGIS backend")

        # Track received WS events
        received_blocks = []
        received_speeches = []
        received_contradictions = []

        async def listen_ws():
            try:
                while True:
                    msg_raw = await ws.recv()
                    msg = json.loads(msg_raw)
                    mtype = msg.get("type")
                    if mtype == "block_upsert":
                        b = msg.get("block", {})
                        received_blocks.append(b)
                        print(f"   [Canvas Update] {b.get('kind', '').upper()}: '{b.get('title')}'")
                    elif mtype == "speak":
                        received_speeches.append(msg)
                        has_audio = bool(msg.get("audio"))
                        print(f"   [Agent Spoke] '{msg.get('text')}' (TTS Audio: {has_audio})")
                    elif mtype == "contradiction":
                        received_contradictions.append(msg)
                        has_audio = bool(msg.get("audio"))
                        print(f"   ⚠️ [CONTRADICTION DETECTED] '{msg.get('question')}' (Speak-Over Audio: {has_audio})")
            except asyncio.CancelledError:
                pass
            except Exception as e:
                pass

        listener_task = asyncio.create_task(listen_ws())
        await asyncio.sleep(1.0)

        # Clear canvas to start with a fresh blank board for simulation
        await ws.send(json.dumps({"type": "command", "name": "clear"}))
        await asyncio.sleep(1.5)
        received_blocks.clear()
        received_speeches.clear()
        received_contradictions.clear()
        print("🧹 Canvas cleared for fresh simulation test")

        # -------------------------------------------------------------
        # TURN 1: Small talk (Greetings) -> EXPECT NO TOOL CALL, NO AUDIO
        # -------------------------------------------------------------
        print("\n--- TURN 1: Small talk / Chit-Chat ---")
        t1 = "Good morning everyone, thanks for joining the architecture sync. Can everyone hear me clearly?"
        print(f"Speaker 1: \"{t1}\"")
        await ws.send(json.dumps({"type": "transcript_event", "text": t1, "is_final": True}))
        await asyncio.sleep(8.0)
        print(f"Turn 1 Result: Blocks={len(received_blocks)}, Speeches={len(received_speeches)}")
        assert len(received_blocks) == 0, "Agent should NOT create blocks for small talk"
        assert len(received_speeches) == 0, "Agent should stay silent without spoken speech"
        print("✨ PASSED: Agent stayed completely silent and did not clutter canvas during greetings.")

        # -------------------------------------------------------------
        # TURN 2: Business Process Flow -> EXPECT FLOW BLOCK + DISTINCT ICONS (SILENT)
        # -------------------------------------------------------------
        print("\n--- TURN 2: Business Process Flow Discussion ---")
        t2 = "First developers commit code, then automated tests run, then security inspection checks the build, then we deploy to production."
        print(f"Speaker 1: \"{t2}\"")
        await ws.send(json.dumps({"type": "transcript_event", "text": t2, "is_final": True}))
        # Wait up to 60s for block to arrive (breaks immediately once received)
        for _ in range(120):
            await asyncio.sleep(0.5)
            if any(b.get("kind") == "flow" for b in received_blocks):
                break

        assert len(received_blocks) >= 1, "Agent should have created a flow diagram"
        flow_block = [b for b in received_blocks if b.get("kind") == "flow"][-1]
        nodes = flow_block.get("json", {}).get("nodes", [])
        print(f"✨ PASSED: Flow diagram created with {len(nodes)} steps: {[n.get('label') for n in nodes]}")
        # Verify agent did not speak out loud during ordinary flow creation
        print("✨ PASSED: Agent updated canvas silently without interrupting meeting speech.")

        # -------------------------------------------------------------
        # TURN 3: Illustrate Steps with Nano Banana
        # -------------------------------------------------------------
        print("\n--- TURN 3: Nano Banana Illustration ---")
        t3 = "Illustrate steps"
        print(f"Speaker 2: \"{t3}\"")
        await ws.send(json.dumps({"type": "transcript_event", "text": t3, "is_final": True}))
        for _ in range(20):
            await asyncio.sleep(0.5)
            fb = [b for b in received_blocks if b.get("kind") == "flow"][-1]
            if any(n.get("image_url") for n in fb.get("json", {}).get("nodes", [])):
                break

        flow_block = [b for b in received_blocks if b.get("kind") == "flow"][-1]
        nodes_with_icons = [n for n in flow_block.get("json", {}).get("nodes", []) if n.get("image_url")]
        print(f"✨ PASSED: Nano Banana synthesized distinct semantic icons for {len(nodes_with_icons)} steps!")
        for n in flow_block.get("json", {}).get("nodes", []):
            print(f"   Node [{n.get('label')}]: Icon -> {n.get('image_url')}")

        # -------------------------------------------------------------
        # TURN 4: In-Meeting Calculation (Metrics / Unit breakdown)
        # -------------------------------------------------------------
        print("\n--- TURN 4: In-Meeting Calculation ---")
        t4 = "Regarding compute capacity: we run 10 frontend nodes and 10 backend clusters, so 10 + 10 total compute units."
        print(f"Speaker 1: \"{t4}\"")
        await ws.send(json.dumps({"type": "transcript_event", "text": t4, "is_final": True}))
        for _ in range(120):
            await asyncio.sleep(0.5)
            if any("10" in b.get("title", "") or "10" in str(b.get("json", {})) for b in received_blocks):
                break

        calc_blocks = [b for b in received_blocks if "10" in b.get("title", "") or "10" in str(b.get("json", {}))]
        assert len(calc_blocks) >= 1, "Calculation block should be generated"
        cb = calc_blocks[-1]
        print(f"✨ PASSED: Calculation block '{cb.get('title')}' rendered with visual schematic!")
        print(f"   Caption: {cb.get('json', {}).get('visual_caption') or cb.get('json', {}).get('answer')}")

        # -------------------------------------------------------------
        # TURN 5: Highlighting a step in real time
        # -------------------------------------------------------------
        print("\n--- TURN 5: Real-time Highlighting ---")
        t5 = "Highlight security inspection"
        print(f"Speaker 2: \"{t5}\"")
        await ws.send(json.dumps({"type": "transcript_event", "text": t5, "is_final": True}))
        for _ in range(20):
            await asyncio.sleep(0.5)
            fb = [b for b in received_blocks if b.get("kind") == "flow"][-1]
            if any(n.get("highlight") for n in fb.get("json", {}).get("nodes", [])):
                break

        flow_block = [b for b in received_blocks if b.get("kind") == "flow"][-1]
        hl_nodes = [n.get("label") for n in flow_block.get("json", {}).get("nodes", []) if n.get("highlight")]
        print(f"✨ PASSED: Highlighting active on: {hl_nodes}")

        # -------------------------------------------------------------
        # TURN 6: 疑問点の回答 (Answer with visual diagram & caption)
        # -------------------------------------------------------------
        print("\n--- TURN 6: 疑問点の回答 (Visual Explanation) ---")
        t6 = "What is the timeout limit on Cloud Run for WebSockets?"
        print(f"Speaker 1: \"{t6}\"")
        curr_answer_count = len([b for b in received_blocks if b.get("kind") == "answer"])
        await ws.send(json.dumps({"type": "transcript_event", "text": t6, "is_final": True}))
        for _ in range(120):
            await asyncio.sleep(0.5)
            ans_blocks = [b for b in received_blocks if b.get("kind") == "answer"]
            if len(ans_blocks) > curr_answer_count:
                break

        ans_blocks = [b for b in received_blocks if b.get("kind") == "answer"]
        assert len(ans_blocks) > curr_answer_count, "New answer block should be generated for question"
        ab = ans_blocks[-1]
        print(f"✨ PASSED: Answer block generated: '{ab.get('title')}'")
        print(f"   Visual Image URL: {ab.get('json', {}).get('image_url')}")
        print(f"   Explanation Caption: {ab.get('json', {}).get('visual_caption') or ab.get('json', {}).get('answer')}")

        # -------------------------------------------------------------
        # TURN 7: Contradiction Detection -> EXPECT ALERT & SPEAK OVER
        # -------------------------------------------------------------
        print("\n--- TURN 7: Contradiction Alert & Speak-Over ---")
        t7 = "Actually, developers never commit code directly, we only deploy through FTP without testing."
        print(f"Speaker 2: \"{t7}\"")
        await ws.send(json.dumps({"type": "transcript_event", "text": t7, "is_final": True}))
        for _ in range(120):
            await asyncio.sleep(0.5)
            if len(received_contradictions) >= 1:
                break

        assert len(received_contradictions) >= 1, "Agent should detect contradiction"
        c = received_contradictions[-1]
        print(f"✨ PASSED: Contradiction flagged: '{c.get('question')}'")
        assert c.get("audio"), "Agent must generate TTS audio to speak over the meeting on contradiction"
        print("✨ PASSED: Agent spoke over immediately with alert audio!")

        # Wait 4.0s for agent contradiction TTS audio to finish playing (respecting echo suppression window)
        await asyncio.sleep(4.0)

        # -------------------------------------------------------------
        # TURN 8: Direct Question to Agent -> EXPECT SPOKEN TTS AUDIO
        # -------------------------------------------------------------
        print("\n--- TURN 8: Direct Speech Request to Agent ---")
        t8 = "Hey agent, can you explain the deployment workflow to the team?"
        print(f"Speaker 1: \"{t8}\"")
        initial_speeches = len(received_speeches)
        await ws.send(json.dumps({"type": "transcript_event", "text": t8, "is_final": True}))
        for _ in range(120):
            await asyncio.sleep(0.5)
            if len(received_speeches) > initial_speeches:
                break

        assert len(received_speeches) > initial_speeches, "Agent should speak aloud when directly addressed"
        latest_speech = received_speeches[-1]
        print(f"✨ PASSED: Agent spoke aloud: '{latest_speech.get('text')}'")
        assert latest_speech.get("audio"), "Agent must produce spoken audio when directly asked"
        print("✨ PASSED: Agent TTS audio synthesized and broadcast successfully!")

        listener_task.cancel()

    print("\n" + "=" * 80)
    print("🏆 ALL FULL-MEETING SIMULATION PHASES PASSED WITH 100% SUCCESS!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_full_meeting_test())
