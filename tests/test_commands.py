import asyncio
from app.commands import (
    COMMANDS,
    handle_start,
    handle_pause,
    handle_end,
    handle_clear,
    handle_undo,
    handle_toggle,
    handle_inspect,
    extract_voice_command,
)
from app.store import save_block, get_block, get_blocks

async def test_all_commands():
    sid = "test_cmd_session"
    emitted = []

    async def mock_ws_sender(payload):
        emitted.append(payload)

    # Test start, pause, end
    res_start = await handle_start(sid, {}, mock_ws_sender)
    assert res_start["session"] == "active"

    res_pause = await handle_pause(sid, {}, mock_ws_sender)
    assert res_pause["session"] == "paused"

    res_end = await handle_end(sid, {}, mock_ws_sender)
    assert res_end["session"] == "ended"

    # Test checklist toggle
    chk_json = {
        "title": "Tasks",
        "items": [
            {"text": "Task A", "owner": "Alice", "done": False},
            {"text": "Task B", "owner": "Bob", "done": True},
        ]
    }
    save_block(sid, "chk1", "checklist", chk_json)

    res_toggle = await handle_toggle(sid, {"block_id": "chk1", "ref": "item:0"}, mock_ws_sender)
    assert res_toggle["done"] is True
    updated = get_block(sid, "chk1")
    assert updated["json"]["items"][0]["done"] is True

    # Test inspect / drilling in
    flow_json = {
        "title": "Pipeline",
        "nodes": [
            {"id": "step_review", "label": "Code Review", "shape": "step", "note": "Peer review"}
        ],
        "edges": []
    }
    save_block(sid, "flow1", "flow", flow_json)

    # First inspect click -> creates child attached block
    res_inspect1 = await handle_inspect(sid, {"block_id": "flow1", "ref": "step_review"}, mock_ws_sender)
    assert res_inspect1["status"] in ("created", "served_from_cache")
    child_id = res_inspect1["child_id"]

    child_block = get_block(sid, child_id)
    assert child_block is not None
    assert child_block["parent"] == {"block_id": "flow1", "ref": "step_review"}

    # Second inspect click on same element -> collapses it! (Section 6b)
    res_inspect2 = await handle_inspect(sid, {"block_id": "flow1", "ref": "step_review"}, mock_ws_sender)
    assert res_inspect2["status"] == "collapsed"
    assert get_block(sid, child_id) is None

    # Third inspect click -> served from cache! (Section 6b rule 1)
    res_inspect3 = await handle_inspect(sid, {"block_id": "flow1", "ref": "step_review"}, mock_ws_sender)
    assert res_inspect3["status"] == "served_from_cache"

    # Test undo
    res_undo = await handle_undo(sid, {}, mock_ws_sender)
    assert res_undo["status"] == "ok"

    # Test clear
    res_clear = await handle_clear(sid, {}, mock_ws_sender)
    assert res_clear["status"] == "ok"
    assert len(get_blocks(sid)) == 0

    # Test voice command regex stripping
    cmd, args, stripped = extract_voice_command(sid, "pause session please")
    assert cmd == "pause_session"
    assert "please" in stripped

    cmd2, args2, stripped2 = extract_voice_command(sid, "tell me more about Code Review")
    assert cmd2 == "inspect"

    print("ALL COMMAND & DRILLING TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_all_commands())
