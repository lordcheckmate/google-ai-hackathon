<USER_REQUEST>
I changed the whole structure , first please build this 
# Build: AI Meeting Assistant (Google Cloud, ADK, Python)
You are building a complete, deployable application. I have **one day**. Follow the build
order at the bottom and **stop at each checkpoint** to confirm that step works before writing
the next one. Do not scaffold the whole app and then debug it.
---
## 1. What it does
An agent sits in a meeting, listens to the whole conversation, and maintains a **live canvas**
beside it — so whatever is being discussed is visible and correctable while the people who can
correct it are still in the room.
The important part: **the agent decides what to show.** It is not a diagram tool.
- Someone describes how their work runs → a **process diagram**, updated as they talk.
- Someone asks a question → an **answer card**.
- Someone weighs named options → a **comparison table**.
- Someone agrees to do things → a **checklist**.
**Everything it draws is clickable.** Click a step, a table cell, a checklist item — anything
on the canvas — and the agent explains that specific thing in whatever form suits it: clicking
a process step may open a sub-process, clicking a vendor name may open an answer card. The
same thing happens if you simply ask out loud.
It holds the context of the entire meeting, so a block raised twenty minutes apart is updated,
not duplicated. It also speaks up when two statements cannot both be true.
Everything is operable **by voice or by clicking**. Both paths call the same handlers. No
capability exists on only one path.
---
## 2. Hard constraints
- **Python 3.11+**, **Google ADK** (`google-adk`) for the agent.
- Deploys to **Cloud Run** behind a public HTTPS URL that must stay reachable for six weeks.
- Gemini must be called **through Vertex AI** (`GOOGLE_GENAI_USE_VERTEXAI=TRUE`), not AI Studio.
- Budget is $300 of credits across six weeks. **Scale to zero.** Never set `--min-instances`
above 0.
- **Do not hardcode model IDs anywhere in the code or in this design.** Read them from
environment variables (`REASONING_MODEL`, `IMAGE_MODEL`), resolved in one place. Before you
write the agent, look up the **current** Gemini model IDs available on Vertex AI in this
project and use the newest ones. Any model name written into a document is already stale;
check, don't assume.
- Pick from the **fast / light tier**, not the heavy reasoning tier. Latency is a feature
here: a slow model makes each turn unusable in a live meeting. Put the effort into prompts
and context, not model size. The image model must be the **Nano Banana** image-generation
model, whatever its current ID is.
- Frontend is **vanilla HTML/CSS/JS served as static files by the same FastAPI app**. No npm,
no bundler, no build step. There is not time.
### Do NOT do these
- Do not use the Google Meet Media API or try to make a bot join a Meet call. It requires
every participant to be enrolled in a Developer Preview, so it cannot work for a judge
opening the URL. The app captures the operator's own microphone and runs **alongside** Meet.
- **Do not let any model emit HTML or SVG.** See section 5 — this is the core rule.
- Do not record audio to disk or to a bucket. Audio is streamed and discarded; only text is
stored.
- Do not add auth, user accounts, or a login screen.
- Do not add block types beyond the four in section 6 until everything else works.
---
## 3. Google Cloud services (hackathon-required; use exactly these)
| Service | Role |
|---|---|
| **Cloud Run** | the one container: FastAPI + WebSocket + ADK agent + static files |
| **ADK** | the agent and its tool loop |
| **Gemini API via Vertex AI** | agent reasoning, and the instruction → typed-block-JSON call |
| **Nano Banana** | illustrations inside process steps (`IMAGE_MODEL`) |
| **Speech-to-Text (v2, streaming)** | live transcription with phrase hints |
| **Text-to-Speech** | the agent's spoken replies |
| **Firestore** | sessions, the block store, the turn-by-turn audit log |
| **Cloud Storage** | generated step images |
| **Secret Manager** | any API keys (prefer ADC and have no keys at all) |
---
## 4. Repository layout
```
.
├── Dockerfile
├── requirements.txt
├── .env.example
├── app/
│ ├── main.py # FastAPI: WebSocket, /command, /img/{id}, static mount
│ ├── agent.py # ADK LlmAgent + tool functions
│ ├── models.py # ONE module resolving REASONING_MODEL / IMAGE_MODEL
│ ├── stt.py # STT v2 streaming bridged into asyncio
│ ├── tts.py # synthesize -> mp3 bytes
│ ├── blocks/
│ │ ├── __init__.py # BLOCK_REGISTRY: kind -> (schema, renderer)
│ │ ├── schema.py # Pydantic models, one per block kind
│ │ ├── generate.py # instruction + existing block -> typed JSON via Gemini
│ │ ├── flow.py # renderer -> SVG (PURE PYTHON)
│ │ ├── compare.py # renderer -> HTML (PURE PYTHON)
│ │ ├── answer.py # renderer -> HTML (PURE PYTHON)
│ │ └── checklist.py # renderer -> HTML (PURE PYTHON)
│ ├── images.py # Nano Banana -> GCS -> /img/{id}
│ ├── store.py # Firestore reads/writes
│ └── commands.py # the single command registry (voice + click)
└── static/
├── index.html
├── app.js
├── pcm-worklet.js
└── style.css
```
---
## 5. The core architectural rule
**No model ever emits markup.** The pipeline is three separate, individually inspectable
stages:
```
transcript -> [ADK agent] -> a plain-language instruction + a block kind
instruction -> [Gemini + schema] -> typed block JSON (structured, validated)
block JSON -> [pure Python] -> HTML or SVG (deterministic, no model)
```
Three reasons this is non-negotiable:
1. **Debuggability.** When a block comes out wrong you read the stored instruction and the
stored JSON and know which stage failed. If one call went from speech to markup, every bug
would look identical.
2. **No injection surface.** Python builds the markup from validated fields with escaping, so
there is nothing to sanitize. Never `innerHTML` a model's output.
3. **Nothing is silently lost.** Deterministic layout cannot drop or invent a step.
Persist the instruction **and** the resulting JSON for every turn. That log is the
observability story.
---
## 6. Block types
The canvas is an **ordered stack of blocks**, not one picture. Each block has a stable
`block_id` so it can be updated in place rather than duplicated.
Every block also carries an optional `parent: {block_id, ref} | None`. A block with a parent
was produced by drilling into something (section 7b) and renders attached and indented under
its source rather than as a new top-level entry. This is one field and one CSS rule, not a
second rendering system.
`blocks/__init__.py` holds a registry mapping `kind -> (pydantic_schema, render_fn)`. Adding a
new kind must require only a schema and a render function — nothing in `agent.py`, `main.py`
or the frontend may branch on a specific kind. This extensibility is a graded criterion;
build it that way even though only four kinds ship.
Ship exactly these four:
### `flow` — a process (SVG)
```python
{"kind": "flow", "title": str,
"nodes": [{"id": str, "label": str, "shape": "start|step|decision|end",
"note": str, "highlight": bool, "image_url": str | None}],
"edges": [{"from": str, "to": str, "label": str}]}
```
Lay out top-to-bottom on a fixed grid; a `decision` node offsets its branches left and right.
Wrap labels at about 18 characters. Highlighted nodes get an accent stroke plus a CSS
`filter: drop-shadow(...)` — **not** `filter="url(#...)"` on a gradient fill, which renders the
node as an empty box in some engines. Put the title in the root `aria-label`; do **not** add
`<title>` or `<desc>` elements, which some renderers show as a visible box.
### `compare` — named options against criteria (HTML table)
```python
{"kind": "compare", "title": str, "options": [str],
"criteria": [str], "cells": [[str]], "recommendation": str | None}
```
`cells[criterion_index][option_index]`. Validate the dimensions match before rendering.
### `answer` — a question that came up (HTML card)
```python
{"kind": "answer", "question": str, "answer": str,
"detail": str | None, "sources": [{"title": str, "url": str}], "confidence": "high|medium|low"}
```
Show `confidence` visibly. If you have time, enable **Google Search grounding** on this one
call via Vertex and fill `sources` from the grounding metadata — an answer card with real
citations is worth far more than a confident guess, and an ungrounded card must say `low`.
### `checklist` — agreed actions or requirements (HTML)
```python
{"kind": "checklist", "title": str,
"items": [{"text": str, "owner": str | None, "done": bool}]}
```
Clicking an item toggles `done` through the normal command path.
**Later, if everything above works:** `chart` (CSS bar/line, no library) then `timeline`. Each
should be roughly twenty lines against the registry. Do not start them before step 7.
---
## 6b. Clickable content — drilling in
Anything meaningful the renderers draw must be clickable, and clicking it must produce an
explanation of **that specific thing**, in whatever form the agent judges best. This is a
graded differentiator: the canvas is explorable, not just a picture.
### Refs
Every renderer tags its meaningful elements with `data-ref`, using a value that addresses the
underlying JSON:
| kind | clickable elements | `data-ref` |
|---|---|---|
| `flow` | each node | the node `id` (`n3`) |
| `compare` | each cell, and each option header | `cell:2:1` (criterion:option), `opt:1` |
| `answer` | each source | `src:0` |
| `checklist` | each item | `item:4` |
Put the attribute on the outermost element of the thing itself — for SVG, on a `<g>` wrapping
the node's shape and text, so the whole node is the hit target, not just the glyph.
### The round trip
1. One delegated click listener on the canvas walks up from `event.target` to the nearest
`[data-ref]`, reads its `data-ref` and its block's `data-block-id`, and sends
`{type: "inspect", block_id, ref}` over the WebSocket.
2. The server **resolves the ref against the stored block JSON** and refuses anything that
does not address a real element. Never interpolate a client-supplied ref into a prompt
unresolved — look up the actual node, cell or item and pass *that*.
3. It starts an agent turn with the resolved subject plus the meeting context so far, phrased
as: the user is asking about *this* element of *this* block.
4. The agent answers with a normal `upsert_block` call, setting `parent` to the clicked
`{block_id, ref}`. **The agent chooses the kind** — a step may deserve a nested `flow`, a
vendor an `answer`, a vague requirement a `checklist`. Do not hardcode "clicks produce
answer cards."
5. The new block renders attached beneath its source. Clicking the same element again
collapses it.
### Rules
- **Cache by `(block_id, ref)`.** A second click on the same element serves the stored block
instead of calling a model again. Clicks are cheap to produce and judges will click a lot;
without this the demo stutters and the credits drain.
- **Invalidate on edit.** If the parent block changes, drop the cached children for refs whose
content changed — a stale explanation of a step that has since been renamed is worse than
none.
- **Voice parity.** "tell me more about inspection" must reach the same code path, resolving
the label to a ref. Clicking is a shortcut for asking, not a separate feature.
- **Make it look clickable.** `cursor: pointer` and a visible hover state on anything carrying
`data-ref`, and nothing else. An element that looks clickable and is not is worse than a
plain one.
- **Show it is working.** The clicked element gets a pending state immediately, because the
agent turn takes a second or two and an unresponsive click reads as a broken page.
---
## 7. The ADK agent
`LlmAgent`, model read from `REASONING_MODEL` (section 2 — never a literal). Give it these
tools and no others:
```python
upsert_block(block_id: str, kind: str, instruction: str) -> dict
# block_id: reuse an existing id to UPDATE that block, or a new id to add one.
# instruction: one plain-language delta, e.g. "add inspection after processing"
# or "add Vendor C with the pricing they just gave".
# NOT a full restatement. Runs blocks/generate.py then the renderer,
# then pushes the rendered block over the WebSocket.
remove_block(block_id: str) -> dict
highlight(block_id: str, labels: list[str]) -> dict
# accepts one OR MORE labels. Clears previous highlights in that block.
illustrate_step(block_id: str, node_label: str, visual_description: str) -> dict
# Nano Banana, flow blocks only. Only when asked for pictures.
flag_contradiction(earlier: str, now: str) -> dict
# speaks one short question asking which is correct.
# This is the agent's one unprompted behaviour.
read_back(block_id: str | None) -> str
# short spoken summary of one block, or of the canvas.
```
The agent is given the current canvas state (each block's id, kind and title) on every turn, so
it can decide between updating an existing block and creating a new one.
### Agent system instruction (use this verbatim; it encodes lessons already paid for)
```
You listen to a meeting and maintain a canvas of blocks showing what is being discussed.
WHEN TO DO NOTHING
Most of what you hear is greetings, filler, half-finished sentences and small talk.
Produce no tool call and no reply for those. Silence is the correct output more often
than not. Only act when something has been described, asked, compared or agreed — or
when you were addressed directly.
CHOOSING WHAT TO SHOW
You decide the representation. Nobody will tell you which to use.
- A sequence of steps, or how work moves through stages -> flow
- Named options being weighed against each other -> compare
- A question with a findable answer -> answer
- Things someone agreed to do, or must be true -> checklist
Pick the one that makes the point visible fastest. If none fits, show nothing.
Never show two blocks that say the same thing in different shapes.
UPDATE, DO NOT DUPLICATE
You can see every block already on the canvas. If the conversation returns to something
already there, call upsert_block with THAT block_id. Create a new block only for a
genuinely new subject. A meeting that revisits a topic four times must end with one
block, not four.
HOW TO CHANGE A BLOCK
Pass ONE short delta describing only what changed. Never restate the whole thing.
"add inspection after processing" — not a list of every step.
Build from the conversation as a whole, not sentence by sentence; if someone is
mid-explanation, wait for the thought to finish.
HIGHLIGHTING
When asked to highlight, pass EVERY item named. If they name two things, pass two.
CONTRADICTIONS
If something said now cannot both be true with something said earlier, call
flag_contradiction once and ask which is right in one short sentence. Do not raise the
same contradiction twice. Do not nitpick wording — only real conflicts.
ADDRESSING YOU
Treat any clear instruction aimed at you as addressed to you. Judge by direction, not
by exact wording — there is no magic phrase.
REPLIES
Spoken replies are one sentence. Never read a block out unless asked.
Never describe what you are about to do; just do it.
```
---
## 8. Voice / click parity
`commands.py` holds **one** registry:
```python
COMMANDS = {
"start_session": handle_start, "pause_session": handle_pause,
"end_session": handle_end, "undo": handle_undo,
"clear": handle_clear, "toggle_item": handle_toggle,
"inspect": handle_inspect,
}
```
`inspect` takes `{block_id, ref}`. The click path sends it with a ref read from the DOM; the
voice path resolves a spoken label ("tell me more about inspection") to the same ref and calls
the identical handler. Neither path may contain logic the other lacks.
- **Voice path:** a regex over the final transcript extracts a command, runs the handler, and
**strips the command text out of the transcript** so it never reaches the agent as content.
- **Click path:** `POST /command {"name": "...", "args": {...}}` runs the identical handler.
- Keep recognition armed while paused so "start session" can still be heard. The on-screen
button is the guaranteed way back regardless.
The demo video must show both paths, so neither may be a stub.
---
## 9. Firestore
```
sessions/{sid} {created_at, title, status}
sessions/{sid}/blocks/{block_id} {kind, json, order, updated_at, version}
sessions/{sid}/turns/{auto} {ts, transcript, tool, block_id, kind,
instruction, json_after, latency_ms}
```
`turns` is the audit log — one record per agent action including latency. It is the
observability answer and it costs four lines.
---
## 10. Audio in
Browser (`pcm-worklet.js` + `app.js`):
- `getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}})`
- An `AudioWorkletProcessor` converts Float32 to **Int16 LINEAR16 at 16 kHz** and posts
~100 ms buffers to the main thread, which sends them as binary WebSocket frames.
- Use AudioWorklet, not MediaRecorder — MediaRecorder's webm chunking causes codec surprises
that will cost hours you do not have.
Server (`stt.py`):
- Speech-to-Text **v2** `streaming_recognize`, recognizer
`projects/{PROJECT}/locations/global/recognizers/_`, inline `explicit_decoding_config`
LINEAR16 / 16000 / 1 channel, `language_codes=["en-US"]`, `interim_results=True`.
- **Gotcha that will bite you:** the Speech client is synchronous gRPC and consumes a request
*generator*. Run each session's stream on its own thread and bridge both directions through
`asyncio.Queue` with `loop.call_soon_threadsafe`. Do not try to `await` the client directly.
- Supply **phrase hints** built from every label currently on the canvas plus a domain term
list, refreshed when blocks change. This is what makes it usable on jargon the generic model
mishears — mention it in the README.
- Google's stream has a roughly 5 minute limit. Detect the end and transparently restart it,
carrying the phrase hints over. A meeting is longer than five minutes; if you skip this it
dies mid-demo.
**Echo suppression:** while TTS audio is playing, and for 700 ms after it ends, discard
incoming transcript. Otherwise the agent hears itself and answers its own sentences.
---
## 11. Nano Banana
Illustrations inside `flow` steps, generated only on request. Prompt for a **flat,
single-subject, monochrome-on-transparent line icon** so pictures look like one family rather
than five art styles — consistency is the point, since the client has to recognise their own
process at a glance.
Write the PNG to Cloud Storage, then serve it through `/img/{id}`, which streams the object.
**Do not use signed URLs** — they need a service-account key or SignBlob plumbing you do not
have time for. Proxying keeps the bucket private and is simpler.
---
## 12. Deploy
`.env.example`:
```
GOOGLE_CLOUD_PROJECT=
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GCS_BUCKET=
REASONING_MODEL=
IMAGE_MODEL=
```
Fill the two model variables from whatever is current when you build — list the models
available to this project on Vertex AI rather than copying an ID from anywhere. Resolve them
only in `app/models.py`; a model ID must not appear as a literal anywhere else. Swapping to a
newer model should be an env var change and a redeploy, nothing else.
### Run it locally — this is where almost all development happens
**Default to local.** Cloud Run is for proving the pipeline (checkpoint 1) and for the
milestone redeploys. Everything in between runs on localhost, because a Cloud Build round trip
is two minutes and there is not time to spend it on every edit.
```bash
pip install -r requirements.txt
cp .env.example .env # fill it in
uvicorn app.main:app --reload --port 8080
# open http://localhost:8080
```
This works fully offline from Cloud Run:
- **Credentials.** Everything authenticates through ADC from
`gcloud auth application-default login`. Vertex, Speech-to-Text, Text-to-Speech, Firestore
and Cloud Storage all work from localhost with no key file and no emulator.
- **Microphone.** `getUserMedia` requires a secure context, and **`http://localhost` counts as
one**. You do not need HTTPS or a tunnel for local mic testing. (A LAN IP like
`http://192.168.x.x` does *not* count — the mic will silently fail there.)
- **Firestore.** Point at the real database rather than the emulator. The free tier covers a
day of testing and the emulator is setup time you do not have.
- **WebSocket.** Works on plain `ws://` locally. The `--timeout` / `--session-affinity`
problems only exist on Cloud Run.
Write a `make dev` or a one-line script so the loop is: edit, reload, speak, look. Redeploy
only at checkpoints 1, 4 and 9, plus any time you want to check something that only breaks in
the cloud.
**Cost note:** local runs still call the real Vertex, Speech and TTS APIs, so testing consumes
credits exactly as deployed traffic does. This is fine at this scale — just don't leave a hot
mic streaming while you go to lunch.
### Deploy
```bash
gcloud services enable [run.googleapis.com](http://run.googleapis.com) [cloudbuild.googleapis.com](http://cloudbuild.googleapis.com) \
[artifactregistry.googleapis.com](http://artifactregistry.googleapis.com) [aiplatform.googleapis.com](http://aiplatform.googleapis.com) \
[speech.googleapis.com](http://speech.googleapis.com) [texttospeech.googleapis.com](http://texttospeech.googleapis.com) \
[firestore.googleapis.com](http://firestore.googleapis.com) [storage.googleapis.com](http://storage.googleapis.com) [secretmanager.googleapis.com](http://secretmanager.googleapis.com)
```
Deploy. The WebSocket drops mid-meeting without `--timeout` and `--session-affinity`:
```bash
gcloud run deploy ai-meeting-assistant \
--source . --region us-central1 --allow-unauthenticated \
--timeout 3600 --session-affinity --min-instances 0 --max-instances 3 \
--cpu-boost --memory 1Gi \
--set-env-vars GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_LOCATION=us-central1,GCS_BUCKET=YOUR_BUCKET,REASONING_MODEL=...,IMAGE_MODEL=...
```
Grant the runtime service account `roles/aiplatform.user`, `roles/datastore.user`,
`roles/storage.objectUser`, `roles/serviceusage.serviceUsageConsumer`. IAM takes minutes to
propagate — if the first call returns 403, wait rather than re-granting.
---
## 13. Build order — STOP AND VERIFY AT EACH CHECKPOINT
**Only steps 1, 4 and 10 involve a deploy.** Everything else is built and verified on
`localhost:8080` per section 12. Do not redeploy between steps; it wastes minutes you need.
1. **Hello world on Cloud Run.** FastAPI returning "ok", deployed, URL responds in a browser.
Prove the deploy pipeline — billing, APIs, IAM, the Dockerfile — before putting anything in
it. This is the only step done cloud-first, deliberately: these failures are slow and they
are fatal if they surface late.
*Checkpoint: paste the working URL. Then switch to local development.*
2. **Mic → WebSocket → STT → text on screen.** No agent, no canvas. Just live transcription.
*Checkpoint: speak a sentence, see it appear.*
3. **Agent with one tool.** `upsert_block` writing instruction + kind to Firestore. Log it; do
not render yet.
*Checkpoint: describe a process out loud, see the instruction and `kind: "flow"` in Firestore.*
4. **The `flow` block end to end.** Registry, schema, generate, renderer, pushed to the
browser.
*Checkpoint: describe three steps out loud and watch the diagram build. This is the
demo-able moment; everything after it is additive. **Redeploy here** and confirm it behaves
the same in the cloud as on localhost — this is the point where a WebSocket or timeout
difference would show up, and you want to find that now rather than at midnight.*
5. **Three more kinds through the registry** — `answer`, `compare`, `checklist` — with the
agent choosing between them unprompted.
*Checkpoint: in one continuous conversation, get all four kinds to appear without ever
naming a block type out loud. This is the whole pitch; rehearse it until it is reliable.*
6. **Command registry**, both paths, plus `highlight` and `undo`.
7. **Clickable content** (section 6b): `data-ref` from every renderer, the delegated listener,
server-side ref resolution, the cache, and attached child blocks.
*Checkpoint: click a process step and get a nested explanation; click it again and it
collapses; click it a third time and it returns instantly from cache.*
8. **TTS replies** with echo suppression, then `flag_contradiction`.
9. **Nano Banana** illustrations. Then `chart` only if time remains.
10. **Final deploy.** README with the architecture diagram, `.gitignore` covering `.env` and any
key files, then redeploy and re-verify the public URL in a fresh browser profile — not the
one you have been developing in, which may be holding a cached asset or a granted mic
permission a judge will not have.
If time runs out, ship after step 5. A canvas that picks its own representation is the
submission. Speech out and pictures are not.

use key GITHUB_TOKEN_REDACTED


 to deploy those and push and pull to github . go ahead 

</USER_REQUEST>
<ADDITIONAL_METADATA>
The current local time is: 2026-10-14T15:45:21+09:00.
</ADDITIONAL_METADATA>