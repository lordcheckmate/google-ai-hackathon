import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig, ax = plt.subplots(figsize=(14, 8), dpi=200, facecolor='#0b0f19')
ax.set_facecolor('#0b0f19')
ax.set_xlim(0, 14)
ax.set_ylim(0, 8)
ax.axis('off')

# Title
ax.text(7, 7.5, 'AEGIS // Architecture & Google Cloud Integration', color='#38bdf8', fontsize=18, fontweight='bold', ha='center')
ax.text(7, 7.1, 'Real-time Autonomous Meeting Co-Pilot (5th Agentic AI Hackathon with Google Cloud)', color='#94a3b8', fontsize=11, ha='center')

def draw_card(ax, x, y, w, h, title, subtitle, color, items):
    rect = patches.FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.2', facecolor='#131c31', edgecolor=color, linewidth=2)
    ax.add_patch(rect)
    ax.text(x + w/2, y + h - 0.4, title, color=color, fontsize=11, fontweight='bold', ha='center')
    ax.text(x + w/2, y + h - 0.75, subtitle, color='#94a3b8', fontsize=8, ha='center', style='italic')
    for i, itm in enumerate(items):
        ax.text(x + 0.3, y + h - 1.2 - i*0.4, f'- {itm}', color='#e2e8f0', fontsize=8.5)

# Layer 1: Client
draw_card(ax, 0.6, 2.0, 3.4, 4.6, 'Client Layer (Browser)', 'Vanilla JS + HTML5 + Web Audio', '#38bdf8', [
    'AudioWorklet 16kHz PCM Stream',
    'Bidirectional WebSocket Client',
    'Interactive Dark OLED HUD',
    'Multi-Tab Workflow History',
    'Click & Voice Command Parity',
    'Dynamic Avatar Expression Engine',
    'Multilingual UI (en-US / ja-JP)'
])

# Layer 2: Cloud Run Backend
draw_card(ax, 4.4, 1.6, 4.6, 5.0, 'Application Layer (Cloud Run)', 'FastAPI + Google ADK + Pure Python', '#22c55e', [
    'FastAPI WebSockets & REST APIs',
    'HTTP Basic Auth & Cookie Middleware',
    'Adaptive Silence & 15s Debouncer',
    'Google ADK Multi-Tool Runner',
    'Pydantic Deterministic Validation',
    'Pure Python SVG/HTML Rendering',
    'In-Memory Session & Drilldown Cache',
    'Active TTS Echo Cancellation'
])

# Layer 3: Google Cloud Services & Vertex AI
draw_card(ax, 9.4, 1.6, 4.0, 5.0, 'Google Cloud AI & Platform', 'Native Google Cloud Stack', '#a855f7', [
    'Cloud Speech-to-Text v2 (Streaming)',
    'Vertex AI Gemini 2.5 Flash',
    'Gemini 3.1 Flash Image (Nano Banana)',
    'Cloud Text-to-Speech (Neural2)',
    'Google Cloud Run (Scale-to-Zero)',
    'Google Cloud Storage (Assets)',
    'Cloud Firestore (Meeting Sessions)',
    'Cloud Logging & Monitoring'
])

# Connection arrows
ax.annotate('', xy=(4.4, 4.2), xytext=(4.0, 4.2),
            arrowprops=dict(arrowstyle='<->', color='#38bdf8', lw=2.5))
ax.text(4.2, 4.5, 'WS / WSS\n16kHz Audio', color='#38bdf8', fontsize=7.5, ha='center')

ax.annotate('', xy=(9.4, 4.2), xytext=(9.0, 4.2),
            arrowprops=dict(arrowstyle='<->', color='#a855f7', lw=2.5))
ax.text(9.2, 4.5, 'gRPC / REST\nVertex ADC', color='#a855f7', fontsize=7.5, ha='center')

# Bottom footer badge
ax.text(7, 0.7, 'Key Principle: No Markup from Models -- LLMs emit typed JSON deltas; deterministic Python renders SVG.', 
        color='#f59e0b', fontsize=9.5, ha='center', bbox=dict(boxstyle='round,pad=0.4', facecolor='#1e293b', edgecolor='#f59e0b', lw=1.2))

plt.tight_layout()
plt.savefig('architecture_diagram.png', dpi=200, facecolor='#0b0f19')
print('Architecture diagram successfully saved as architecture_diagram.png')
