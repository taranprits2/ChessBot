import streamlit as st
import chess
import chess.pgn
import chess.svg
import io
import os
import sys
import zipfile
import urllib.request
import subprocess
import shutil
import re
from pathlib import Path

st.set_page_config(page_title="Chess Analyzer", page_icon="♟", layout="wide", initial_sidebar_state="collapsed")

# ============== STOCKFISH ==============

STOCKFISH_DIR = Path(__file__).parent / "stockfish_engine"

def get_stockfish_url():
    if sys.platform == "win32":
        return "https://github.com/official-stockfish/Stockfish/releases/download/sf_17/stockfish-windows-x86-64-avx2.zip"
    elif sys.platform == "darwin":
        return "https://github.com/official-stockfish/Stockfish/releases/download/sf_17/stockfish-macos-x86-64-avx2.tar"
    return "https://github.com/official-stockfish/Stockfish/releases/download/sf_17/stockfish-ubuntu-x86-64-avx2.tar"

def find_exe(directory: Path) -> str | None:
    for root, _, files in os.walk(directory):
        for f in files:
            if "stockfish" in f.lower():
                if sys.platform == "win32" and f.lower().endswith('.exe'):
                    return str(Path(root) / f)
                elif sys.platform != "win32" and not f.endswith(('.txt', '.md', '.nnue')):
                    return str(Path(root) / f)
    return None

def test_engine(path: str) -> tuple[bool, str]:
    try:
        proc = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        proc.stdin.write("uci\n")
        proc.stdin.flush()
        for _ in range(50):
            line = proc.stdout.readline()
            if "uciok" in line:
                proc.stdin.write("quit\n")
                proc.stdin.flush()
                proc.terminate()
                return True, ""
        proc.terminate()
        return False, "No uciok"
    except Exception as e:
        return False, str(e)

@st.cache_resource(show_spinner=False)
def setup_stockfish():
    if STOCKFISH_DIR.exists():
        exe = find_exe(STOCKFISH_DIR)
        if exe:
            ok, _ = test_engine(exe)
            if ok:
                return exe, "Engine ready"
            shutil.rmtree(STOCKFISH_DIR, ignore_errors=True)
    
    STOCKFISH_DIR.mkdir(exist_ok=True)
    archive = STOCKFISH_DIR / "sf.zip"
    
    try:
        urllib.request.urlretrieve(get_stockfish_url(), archive)
        with zipfile.ZipFile(archive, 'r') as z:
            z.extractall(STOCKFISH_DIR)
        archive.unlink(missing_ok=True)
        
        exe = find_exe(STOCKFISH_DIR)
        if exe:
            ok, err = test_engine(exe)
            return (exe, "Engine ready") if ok else (None, err)
        return None, "No exe found"
    except Exception as e:
        return None, str(e)

STOCKFISH_PATH, STOCKFISH_STATUS = setup_stockfish()

# ============== ANALYSIS ==============

def run_stockfish_analysis(boards, depth=16, progress_cb=None):
    if not STOCKFISH_PATH:
        return None
    
    try:
        proc = subprocess.Popen(
            [STOCKFISH_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Init
        proc.stdin.write("uci\n")
        proc.stdin.flush()
        while "uciok" not in proc.stdout.readline():
            pass
        
        proc.stdin.write("setoption name Hash value 128\n")
        proc.stdin.write("isready\n")
        proc.stdin.flush()
        while "readyok" not in proc.stdout.readline():
            pass
        
        evals = []
        bests = []
        
        for i, board in enumerate(boards):
            if progress_cb:
                progress_cb(i / len(boards))
            
            fen = board.fen()
            proc.stdin.write(f"position fen {fen}\n")
            proc.stdin.write(f"go depth {depth}\n")
            proc.stdin.flush()
            
            score_cp = 0
            score_mate = None
            best_uci = None
            
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                
                if line.startswith("info") and " score " in line:
                    # Parse score
                    cp = re.search(r"score cp (-?\d+)", line)
                    mate = re.search(r"score mate (-?\d+)", line)
                    pv = re.search(r" pv (\S+)", line)
                    
                    if cp:
                        score_cp = int(cp.group(1))
                        score_mate = None
                    if mate:
                        score_mate = int(mate.group(1))
                    if pv:
                        best_uci = pv.group(1)
                
                if line.startswith("bestmove"):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] != "(none)":
                        best_uci = parts[1]
                    break
            
            # Convert to eval
            if score_mate is not None:
                ev = 15.0 if score_mate > 0 else -15.0
            else:
                ev = score_cp / 100.0
            
            # Clamp
            ev = max(-15.0, min(15.0, ev))
            evals.append(ev)
            
            # Convert UCI to SAN
            best_san = None
            if best_uci and not board.is_game_over():
                try:
                    move = chess.Move.from_uci(best_uci)
                    if move in board.legal_moves:
                        best_san = board.san(move)
                except:
                    pass
            bests.append(best_san)
        
        proc.stdin.write("quit\n")
        proc.stdin.flush()
        proc.terminate()
        
        # Classifications
        def classify(before, after, is_white):
            if not is_white:
                before, after = -before, -after
            loss = before - after
            
            if loss < -1.5:
                return ("Brilliant", "brilliant", "!!")
            if loss < -0.5:
                return ("Great", "great", "!")
            if loss <= 0.1:
                return ("Best", "best", "")
            if loss <= 0.3:
                return ("Good", "good", "")
            if loss <= 0.7:
                return ("Inaccuracy", "inaccuracy", "?!")
            if loss <= 1.5:
                return ("Mistake", "mistake", "?")
            return ("Blunder", "blunder", "??")
        
        classes = []
        for i in range(1, len(evals)):
            is_white = (i - 1) % 2 == 0
            classes.append(classify(evals[i-1], evals[i], is_white))
        
        # Accuracy calculation
        white_losses = []
        black_losses = []
        for i in range(1, len(evals)):
            is_white = (i - 1) % 2 == 0
            if is_white:
                loss = max(0, evals[i-1] - evals[i])
                white_losses.append(loss)
            else:
                loss = max(0, evals[i] - evals[i-1])
                black_losses.append(loss)
        
        def calc_acc(losses):
            if not losses:
                return 100.0
            avg = sum(losses) / len(losses)
            # Chess.com-like formula
            acc = 103.1668 * (2.71828 ** (-0.04354 * avg * 100)) - 3.1668
            return max(0, min(100, acc))
        
        return {
            "evals": evals,
            "bests": bests,
            "classes": classes,
            "w_acc": calc_acc(white_losses),
            "b_acc": calc_acc(black_losses)
        }
    
    except Exception as e:
        st.error(f"Analysis error: {e}")
        return None

# ============== CSS ==============

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&family=IBM+Plex+Mono:wght@400;600&display=swap');

:root {
    --bg: #0d0d0d;
    --bg2: #161616;
    --text: #fff;
    --text2: #777;
    --red: #fa412d;
    --orange: #f89c35;
    --yellow: #f7c631;
    --green: #81b64c;
    --teal: #5bc0be;
    --blue: #4a9bd9;
    --border: #2a2a2a;
}

.stApp { background: var(--bg); }

.main-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    color: var(--text);
    text-transform: uppercase;
    letter-spacing: -2px;
    font-size: 2rem;
    border-bottom: 3px solid var(--red);
    padding-bottom: 0.3rem;
    margin-bottom: 0.5rem;
}

h3 {
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    color: var(--text) !important;
    text-transform: uppercase;
    letter-spacing: -1px;
    font-size: 0.9rem !important;
    border-left: 3px solid var(--red);
    padding-left: 0.5rem;
    margin-top: 0.8rem !important;
    margin-bottom: 0.4rem !important;
}

/* MOVE LIST */
.move-list {
    font-family: 'IBM Plex Mono', monospace;
    background: var(--bg2);
    padding: 0.5rem;
    max-height: 180px;
    overflow-y: auto;
    border: 1px solid var(--border);
    font-size: 0.75rem;
}

.move-row { display: flex; align-items: center; padding: 2px 0; }
.move-num { color: #444; width: 24px; text-align: right; margin-right: 6px; }
.move-cell { flex: 1; padding: 3px 6px; cursor: pointer; border-radius: 3px; display: flex; align-items: center; gap: 4px; }
.move-cell:hover { background: rgba(255,255,255,0.1); }
.move-cell.active { background: var(--red) !important; color: #000 !important; }

/* Classification badges */
.badge { font-size: 0.65rem; font-weight: 700; padding: 1px 4px; border-radius: 3px; }
.badge-brilliant { background: var(--teal); color: #000; }
.badge-great { background: var(--blue); color: #fff; }
.badge-best { background: var(--green); color: #000; }
.badge-good { background: #555; color: #fff; }
.badge-inaccuracy { background: var(--yellow); color: #000; }
.badge-mistake { background: var(--orange); color: #000; }
.badge-blunder { background: var(--red); color: #fff; }

/* Game info */
.game-info {
    font-family: 'IBM Plex Mono', monospace;
    background: var(--bg2);
    padding: 0.5rem;
    border: 1px solid var(--border);
    font-size: 0.75rem;
}
.game-info-item { color: var(--text2); margin: 2px 0; }
.game-info-value { color: var(--text); font-weight: 600; }

/* Buttons */
.stButton > button {
    font-family: 'Space Grotesk', sans-serif !important;
    background: var(--bg) !important;
    color: var(--text) !important;
    border: 2px solid var(--red) !important;
    border-radius: 0 !important;
    padding: 0.3rem 0.8rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    font-size: 0.75rem !important;
}
.stButton > button:hover { background: var(--red) !important; color: #000 !important; }

.stTextArea textarea {
    font-family: 'IBM Plex Mono', monospace !important;
    background: var(--bg2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 0 !important;
    color: var(--text) !important;
    font-size: 0.7rem !important;
}

/* Accuracy boxes */
.acc-container { display: flex; gap: 8px; margin: 8px 0; }
.acc-box {
    flex: 1;
    background: var(--bg2);
    border: 1px solid var(--border);
    padding: 8px;
    text-align: center;
}
.acc-label { font-family: 'IBM Plex Mono', monospace; color: var(--text2); font-size: 0.65rem; text-transform: uppercase; }
.acc-score { font-family: 'Space Grotesk', sans-serif; font-size: 1.8rem; font-weight: 700; }

/* Vertical eval bar */
.eval-bar-v {
    width: 28px;
    height: 100%;
    background: #333;
    border: 1px solid var(--border);
    position: relative;
    display: flex;
    flex-direction: column;
}
.eval-white-part { background: #fff; transition: height 0.3s; }
.eval-black-part { background: #333; flex: 1; }
.eval-score-v {
    position: absolute;
    width: 100%;
    text-align: center;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.6rem;
    font-weight: 600;
    padding: 2px;
    z-index: 10;
}
.eval-score-top { top: 2px; color: #000; }
.eval-score-bot { bottom: 2px; color: #fff; }

/* Eval graph like chess.com */
.eval-graph {
    width: 100%;
    height: 80px;
    background: var(--bg2);
    border: 1px solid var(--border);
    position: relative;
    overflow: hidden;
}
.eval-graph-white {
    position: absolute;
    bottom: 50%;
    left: 0;
    width: 100%;
    background: rgba(255,255,255,0.8);
}
.eval-graph-black {
    position: absolute;
    top: 50%;
    left: 0;
    width: 100%;
    background: rgba(100,100,100,0.8);
}
.eval-graph-line {
    position: absolute;
    top: 50%;
    left: 0;
    width: 100%;
    height: 1px;
    background: #555;
}
.eval-graph-marker {
    position: absolute;
    width: 2px;
    background: var(--red);
    top: 0;
    height: 100%;
}

.status-bar {
    font-family: 'IBM Plex Mono', monospace;
    padding: 0.3rem 0.6rem;
    font-size: 0.65rem;
    text-transform: uppercase;
    border: 1px solid;
}
.status-ok { background: rgba(129,182,76,0.2); border-color: var(--green); color: var(--green); }
.status-err { background: rgba(250,65,45,0.2); border-color: var(--red); color: var(--red); }

.board-hint {
    text-align: center;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.55rem;
    color: #444;
    margin-top: 4px;
}

[data-testid="stMetricValue"] { font-family: 'Space Grotesk', sans-serif !important; font-size: 1rem !important; }
</style>
""", unsafe_allow_html=True)

# Header
c1, c2 = st.columns([3, 1])
c1.markdown('<div class="main-title">Chess Analyzer</div>', unsafe_allow_html=True)
c2.markdown(f'<div class="status-bar {"status-ok" if STOCKFISH_PATH else "status-err"}">{STOCKFISH_STATUS}</div>', unsafe_allow_html=True)

SAMPLE_PGN = """[Event "Evergreen Game"]
[White "Adolf Anderssen"]
[Black "Jean Dufresne"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O d3 
8. Qb3 Qf6 9. e5 Qg6 10. Re1 Nge7 11. Ba3 b5 12. Qxb5 Rb8 13. Qa4 Bb6 
14. Nbd2 Bb7 15. Ne4 Qf5 16. Bxd3 Qh5 17. Nf6+ gxf6 18. exf6 Rg8 
19. Rad1 Qxf3 20. Rxe7+ Nxe7 21. Qxd7+ Kxd7 22. Bf5+ Ke8 23. Bd7+ Kf8 
24. Bxe7# 1-0"""

for k, v in [('idx', 0), ('game', None), ('moves', []), ('boards', []), ('analysis', None)]:
    if k not in st.session_state:
        st.session_state[k] = v

def parse_pgn(text):
    try:
        game = chess.pgn.read_game(io.StringIO(text))
        if not game:
            return None, [], []
        moves, boards = [], []
        board = game.board()
        boards.append(board.copy())
        for m in game.mainline_moves():
            moves.append(board.san(m))
            board.push(m)
            boards.append(board.copy())
        return game, moves, boards
    except Exception as e:
        st.error(f"Parse error: {e}")
        return None, [], []

def board_html(board, last_move, size, eval_pct=50):
    import base64
    
    svg = chess.svg.board(board, lastmove=last_move, size=size, coordinates=False, colors={
        'square light': '#eeeed2', 'square dark': '#769656',
        'square light lastmove': '#f6f669', 'square dark lastmove': '#baca2b',
    })
    b64 = base64.b64encode(svg.encode()).decode()
    
    # Eval bar display
    if eval_pct >= 50:
        white_h = eval_pct
        score_disp = f"+{(eval_pct - 50) / 5:.1f}" if eval_pct > 50 else "0.0"
        score_pos = "top"
    else:
        white_h = eval_pct
        score_disp = f"{(eval_pct - 50) / 5:.1f}"
        score_pos = "bot"
    
    return f"""
    <div style="display:flex;gap:6px;justify-content:center;align-items:stretch;height:{size}px;">
        <div class="eval-bar-v">
            <div class="eval-black-part" style="height:{100-white_h}%;"></div>
            <div class="eval-white-part" style="height:{white_h}%;"></div>
            <div class="eval-score-v {"eval-score-top" if eval_pct >= 50 else "eval-score-bot"}">{score_disp}</div>
        </div>
        <div id="bwrap" style="width:{size}px;height:{size}px;position:relative;user-select:none;">
            <img src="data:image/svg+xml;base64,{b64}" style="width:100%;height:100%;display:block;" draggable="false">
            <svg id="arr" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;">
                <defs>
                    <marker id="ar" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><polygon points="0 0,4 2,0 4" fill="rgba(250,65,45,0.85)"/></marker>
                    <marker id="ag" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><polygon points="0 0,4 2,0 4" fill="rgba(129,182,76,0.85)"/></marker>
                    <marker id="ab" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><polygon points="0 0,4 2,0 4" fill="rgba(74,155,217,0.85)"/></marker>
                    <marker id="ay" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><polygon points="0 0,4 2,0 4" fill="rgba(247,198,49,0.85)"/></marker>
                </defs>
            </svg>
            <div id="ilayer" style="position:absolute;top:0;left:0;width:100%;height:100%;"></div>
        </div>
    </div>
    <div class="board-hint">Arrow keys: navigate | Right-drag: arrow | Right-click: highlight | Click: clear</div>
    
    <script>
    (function(){{
        const wrap=document.getElementById('bwrap'),svg=document.getElementById('arr'),layer=document.getElementById('ilayer');
        const SIZE={size},SQ=SIZE/8;
        let drawing=false,start=null,tmp=null,items=[],col='r';
        const C={{r:'rgba(250,65,45,0.6)',g:'rgba(129,182,76,0.6)',b:'rgba(74,155,217,0.6)',y:'rgba(247,198,49,0.6)'}};
        
        function sq(x,y){{return{{c:Math.max(0,Math.min(7,Math.floor(x/SQ))),r:Math.max(0,Math.min(7,Math.floor(y/SQ)))}};}}
        function ctr(s){{return{{x:(s.c+0.5)*SQ,y:(s.r+0.5)*SQ}};}}
        function key(a,b){{return a.c+','+a.r+'>'+b.c+','+b.r;}}
        function gcol(e){{return e.shiftKey?'g':e.ctrlKey?'b':e.altKey?'y':'r';}}
        
        layer.oncontextmenu=e=>e.preventDefault();
        
        layer.onmousedown=e=>{{
            if(e.button!==2)return;
            e.preventDefault();
            const r=wrap.getBoundingClientRect();
            start=sq(e.clientX-r.left,e.clientY-r.top);
            col=gcol(e);
            drawing=true;
            const c=ctr(start);
            tmp=document.createElementNS('http://www.w3.org/2000/svg','line');
            tmp.setAttribute('x1',c.x);tmp.setAttribute('y1',c.y);
            tmp.setAttribute('x2',c.x);tmp.setAttribute('y2',c.y);
            tmp.setAttribute('stroke',C[col]);tmp.setAttribute('stroke-width','6');tmp.setAttribute('stroke-opacity','0.4');
            svg.appendChild(tmp);
        }};
        
        layer.onmousemove=e=>{{
            if(!drawing||!tmp)return;
            const r=wrap.getBoundingClientRect();
            const end=sq(e.clientX-r.left,e.clientY-r.top);
            const c=ctr(end);
            tmp.setAttribute('x2',c.x);tmp.setAttribute('y2',c.y);
        }};
        
        layer.onmouseup=e=>{{
            if(e.button!==2||!drawing)return;
            const r=wrap.getBoundingClientRect();
            const end=sq(e.clientX-r.left,e.clientY-r.top);
            if(tmp){{svg.removeChild(tmp);tmp=null;}}
            
            const k=key(start,end);
            const idx=items.findIndex(a=>a.k===k);
            
            if(idx>=0){{svg.removeChild(items[idx].el);items.splice(idx,1);}}
            else{{
                let el;
                if(start.c===end.c&&start.r===end.r){{
                    el=document.createElementNS('http://www.w3.org/2000/svg','rect');
                    el.setAttribute('x',start.c*SQ);el.setAttribute('y',start.r*SQ);
                    el.setAttribute('width',SQ);el.setAttribute('height',SQ);
                    el.setAttribute('fill',C[col]);
                }}else{{
                    const c1=ctr(start),c2=ctr(end);
                    el=document.createElementNS('http://www.w3.org/2000/svg','line');
                    el.setAttribute('x1',c1.x);el.setAttribute('y1',c1.y);
                    el.setAttribute('x2',c2.x);el.setAttribute('y2',c2.y);
                    el.setAttribute('stroke',C[col]);el.setAttribute('stroke-width','6');
                    el.setAttribute('marker-end','url(#a'+col+')');
                }}
                svg.appendChild(el);
                items.push({{k:k,el:el}});
            }}
            drawing=false;start=null;
        }};
        
        layer.onclick=()=>{{items.forEach(a=>svg.removeChild(a.el));items=[];}};
        
        // Keyboard navigation
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'ArrowLeft') {{
                const prevBtn = parent.document.querySelector('[data-testid="stButton"] button[kind="secondary"]');
                // Use Streamlit's rerun mechanism
                if (window.parent.postMessage) {{
                    window.parent.postMessage({{type: 'streamlit:setComponentValue', key: 'nav', value: 'prev'}}, '*');
                }}
            }}
            if (e.key === 'ArrowRight') {{
                if (window.parent.postMessage) {{
                    window.parent.postMessage({{type: 'streamlit:setComponentValue', key: 'nav', value: 'next'}}, '*');
                }}
            }}
        }});
    }})();
    </script>
    """

def eval_to_pct(ev):
    # Map eval (-15 to +15) to percentage (5 to 95)
    clamped = max(-10, min(10, ev))
    return 50 + clamped * 4.5

def render_eval_graph(evals, current_idx):
    if not evals:
        return ""
    
    n = len(evals)
    points_white = []
    points_black = []
    
    for i, ev in enumerate(evals):
        x = (i / max(1, n - 1)) * 100
        # Map eval to height (0-100, where 50 is center)
        h = max(0, min(100, 50 + ev * 4))
        
        if ev >= 0:
            points_white.append(f"{x},{50 - min(ev * 4, 45)}")
        else:
            points_black.append(f"{x},{50 + min(-ev * 4, 45)}")
    
    # Build SVG path for white advantage areas
    svg_parts = []
    
    # Draw filled areas
    for i, ev in enumerate(evals):
        x = (i / max(1, n - 1)) * 100
        if ev > 0:
            h = min(ev * 4, 45)
            svg_parts.append(f'<rect x="{x - 0.5}" y="{50 - h}" width="{100/n + 1}" height="{h}" fill="rgba(255,255,255,0.7)"/>')
        else:
            h = min(-ev * 4, 45)
            svg_parts.append(f'<rect x="{x - 0.5}" y="50" width="{100/n + 1}" height="{h}" fill="rgba(80,80,80,0.7)"/>')
    
    # Current position marker
    marker_x = (current_idx / max(1, n - 1)) * 100
    
    return f"""
    <div class="eval-graph">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" style="width:100%;height:100%;">
            {''.join(svg_parts)}
            <line x1="0" y1="50" x2="100" y2="50" stroke="#555" stroke-width="0.5"/>
            <line x1="{marker_x}" y1="0" x2="{marker_x}" y2="100" stroke="var(--red)" stroke-width="1.5"/>
        </svg>
    </div>
    """

# Layout
bcol, icol = st.columns([2, 1])

with bcol:
    pgn = st.text_area("PGN Input", value=SAMPLE_PGN, height=80, label_visibility="collapsed")
    
    b1, b2, _ = st.columns([1, 1, 2])
    with b1:
        if st.button("LOAD", use_container_width=True):
            g, m, b = parse_pgn(pgn)
            if g:
                st.session_state.game = g
                st.session_state.moves = m
                st.session_state.boards = b
                st.session_state.idx = 0
                st.session_state.analysis = None
                st.rerun()
    with b2:
        if st.button("ANALYZE", use_container_width=True, disabled=not st.session_state.boards or not STOCKFISH_PATH):
            prog = st.progress(0)
            res = run_stockfish_analysis(st.session_state.boards, 16, lambda p: prog.progress(p))
            prog.empty()
            if res:
                st.session_state.analysis = res
                st.rerun()
    
    if st.session_state.boards:
        bd = st.session_state.boards[st.session_state.idx]
        lm = None
        if st.session_state.idx > 0:
            tmp = st.session_state.game.board()
            for i, mv in enumerate(st.session_state.game.mainline_moves()):
                if i == st.session_state.idx - 1:
                    lm = mv
                    break
                tmp.push(mv)
        
        # Get eval for bar
        ev_pct = 50
        if st.session_state.analysis:
            ev = st.session_state.analysis["evals"][st.session_state.idx]
            ev_pct = eval_to_pct(ev)
        
        st.components.v1.html(board_html(bd, lm, 500, ev_pct), height=560)
        
        # Nav buttons
        n1, n2, n3, n4, n5 = st.columns([1, 1, 1, 1, 2])
        with n1:
            if st.button("FIRST", use_container_width=True):
                st.session_state.idx = 0
                st.rerun()
        with n2:
            if st.button("PREV", use_container_width=True) and st.session_state.idx > 0:
                st.session_state.idx -= 1
                st.rerun()
        with n3:
            if st.button("NEXT", use_container_width=True) and st.session_state.idx < len(st.session_state.moves):
                st.session_state.idx += 1
                st.rerun()
        with n4:
            if st.button("LAST", use_container_width=True):
                st.session_state.idx = len(st.session_state.moves)
                st.rerun()
        with n5:
            new_idx = st.slider("Move nav", 0, max(1, len(st.session_state.moves)), st.session_state.idx, label_visibility="collapsed")
            if new_idx != st.session_state.idx:
                st.session_state.idx = new_idx
                st.rerun()

with icol:
    if st.session_state.game:
        h = st.session_state.game.headers
        st.markdown('<div class="game-info">' + ''.join([
            f'<p class="game-info-item">{k}: <span class="game-info-value">{h.get(k,"?")}</span></p>'
            for k in ["White", "Black", "Result"]
        ]) + '</div>', unsafe_allow_html=True)
        
        # ACCURACY - Always show if analysis exists
        if st.session_state.analysis:
            w_acc = st.session_state.analysis["w_acc"]
            b_acc = st.session_state.analysis["b_acc"]
            
            def acc_color(a):
                if a >= 90: return "var(--green)"
                if a >= 70: return "var(--yellow)"
                if a >= 50: return "var(--orange)"
                return "var(--red)"
            
            st.markdown(f"""
            <div class="acc-container">
                <div class="acc-box">
                    <div class="acc-label">White</div>
                    <div class="acc-score" style="color:{acc_color(w_acc)}">{w_acc:.1f}%</div>
                </div>
                <div class="acc-box">
                    <div class="acc-label">Black</div>
                    <div class="acc-score" style="color:{acc_color(b_acc)}">{b_acc:.1f}%</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Eval graph
            st.markdown("### Evaluation")
            st.markdown(render_eval_graph(st.session_state.analysis["evals"], st.session_state.idx), unsafe_allow_html=True)
        
        # MOVES - Clickable
        st.markdown("### Moves")
        if st.session_state.moves:
            moves_html = '<div class="move-list">'
            
            for i in range(0, len(st.session_state.moves), 2):
                move_num = i // 2 + 1
                moves_html += f'<div class="move-row"><span class="move-num">{move_num}.</span>'
                
                # White move
                w_move = st.session_state.moves[i]
                w_class = "active" if st.session_state.idx == i + 1 else ""
                w_badge = ""
                if st.session_state.analysis and i < len(st.session_state.analysis["classes"]):
                    cls_name, cls_type, sym = st.session_state.analysis["classes"][i]
                    if sym:
                        w_badge = f'<span class="badge badge-{cls_type}">{sym}</span>'
                moves_html += f'<div class="move-cell {w_class}" onclick="window.location.href=\'?idx={i+1}\'">{w_move}{w_badge}</div>'
                
                # Black move
                if i + 1 < len(st.session_state.moves):
                    b_move = st.session_state.moves[i + 1]
                    b_class = "active" if st.session_state.idx == i + 2 else ""
                    b_badge = ""
                    if st.session_state.analysis and i + 1 < len(st.session_state.analysis["classes"]):
                        cls_name, cls_type, sym = st.session_state.analysis["classes"][i + 1]
                        if sym:
                            b_badge = f'<span class="badge badge-{cls_type}">{sym}</span>'
                    moves_html += f'<div class="move-cell {b_class}" onclick="window.location.href=\'?idx={i+2}\'">{b_move}{b_badge}</div>'
                else:
                    moves_html += '<div class="move-cell"></div>'
                
                moves_html += '</div>'
            
            moves_html += '</div>'
            st.markdown(moves_html, unsafe_allow_html=True)
        
        # Handle URL params for move clicking
        params = st.query_params
        if "idx" in params:
            try:
                new_idx = int(params["idx"])
                if 0 <= new_idx <= len(st.session_state.moves) and new_idx != st.session_state.idx:
                    st.session_state.idx = new_idx
                    st.query_params.clear()
                    st.rerun()
            except:
                pass
        
        # Current move info
        if st.session_state.analysis and st.session_state.idx > 0:
            i = st.session_state.idx - 1
            if i < len(st.session_state.analysis["classes"]):
                cls_name, cls_type, sym = st.session_state.analysis["classes"][i]
                played = st.session_state.moves[i]
                best = st.session_state.analysis["bests"][i]
                
                st.markdown(f"**Played:** `{played}` <span class='badge badge-{cls_type}'>{cls_name}</span>", unsafe_allow_html=True)
                if best and best != played:
                    st.markdown(f"**Best:** `{best}`")
        
        # Game state
        bd = st.session_state.boards[st.session_state.idx]
        if bd.is_checkmate():
            st.error("CHECKMATE")
        elif bd.is_check():
            st.warning("CHECK")
    else:
        st.info("Load a PGN to begin")
