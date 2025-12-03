import streamlit as st
import chess
import chess.pgn
import chess.svg
import io

# Page config
st.set_page_config(
    page_title="PGN Visualizer",
    page_icon="♟️",
    layout="wide"
)

# Custom CSS for dark theme and styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Outfit:wght@300;500;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    }
    
    h1 {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        background: linear-gradient(90deg, #e94560, #ff6b6b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-size: 3rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    .subtitle {
        font-family: 'Outfit', sans-serif;
        color: #a0a0a0;
        text-align: center;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    .move-list {
        font-family: 'JetBrains Mono', monospace;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1rem;
        max-height: 400px;
        overflow-y: auto;
        border: 1px solid rgba(233, 69, 96, 0.3);
    }
    
    .move-item {
        padding: 0.3rem 0.6rem;
        margin: 0.2rem;
        display: inline-block;
        border-radius: 6px;
        color: #e0e0e0;
        transition: all 0.2s;
    }
    
    .move-item:hover {
        background: rgba(233, 69, 96, 0.2);
    }
    
    .move-current {
        background: linear-gradient(135deg, #e94560, #ff6b6b) !important;
        color: white !important;
        font-weight: 600;
    }
    
    .move-number {
        color: #666;
        margin-right: 0.3rem;
    }
    
    .game-info {
        font-family: 'Outfit', sans-serif;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(233, 69, 96, 0.3);
    }
    
    .game-info-item {
        color: #a0a0a0;
        margin: 0.3rem 0;
    }
    
    .game-info-value {
        color: #ffffff;
        font-weight: 500;
    }
    
    .stButton > button {
        font-family: 'Outfit', sans-serif !important;
        background: linear-gradient(135deg, #e94560, #ff6b6b) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.5rem !important;
        font-weight: 500 !important;
        transition: all 0.3s !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 20px rgba(233, 69, 96, 0.4) !important;
    }
    
    .nav-button {
        font-size: 1.5rem !important;
    }
    
    .stTextArea textarea {
        font-family: 'JetBrains Mono', monospace !important;
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(233, 69, 96, 0.3) !important;
        border-radius: 12px !important;
        color: #e0e0e0 !important;
    }
    
    .board-container {
        display: flex;
        justify-content: center;
        padding: 1rem;
        background: rgba(255, 255, 255, 0.02);
        border-radius: 16px;
        border: 1px solid rgba(233, 69, 96, 0.2);
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown("# ♟️ PGN Visualizer")
st.markdown('<p class="subtitle">Paste your PGN and explore the game move by move</p>', unsafe_allow_html=True)

# Sample PGN for demo
SAMPLE_PGN = """[Event "Casual Game"]
[Site "Berlin"]
[Date "1852.??.??"]
[White "Adolf Anderssen"]
[Black "Jean Dufresne"]
[Result "1-0"]
[ECO "C52"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O d3 
8. Qb3 Qf6 9. e5 Qg6 10. Re1 Nge7 11. Ba3 b5 12. Qxb5 Rb8 13. Qa4 Bb6 
14. Nbd2 Bb7 15. Ne4 Qf5 16. Bxd3 Qh5 17. Nf6+ gxf6 18. exf6 Rg8 
19. Rad1 Qxf3 20. Rxe7+ Nxe7 21. Qxd7+ Kxd7 22. Bf5+ Ke8 23. Bd7+ Kf8 
24. Bxe7# 1-0"""

# Initialize session state
if 'move_index' not in st.session_state:
    st.session_state.move_index = 0
if 'game' not in st.session_state:
    st.session_state.game = None
if 'moves' not in st.session_state:
    st.session_state.moves = []
if 'boards' not in st.session_state:
    st.session_state.boards = []

def parse_pgn(pgn_text: str):
    """Parse PGN text and extract game, moves, and board states."""
    try:
        pgn_io = io.StringIO(pgn_text)
        game = chess.pgn.read_game(pgn_io)
        
        if game is None:
            return None, [], []
        
        moves = []
        boards = []
        board = game.board()
        boards.append(board.copy())
        
        for move in game.mainline_moves():
            moves.append(board.san(move))
            board.push(move)
            boards.append(board.copy())
        
        return game, moves, boards
    except Exception as e:
        st.error(f"Error parsing PGN: {e}")
        return None, [], []

def render_board(board: chess.Board, last_move=None):
    """Render the chess board as SVG."""
    svg = chess.svg.board(
        board,
        lastmove=last_move,
        size=450,
        colors={
            'square light': '#f0d9b5',
            'square dark': '#b58863',
            'square light lastmove': '#cdd26a',
            'square dark lastmove': '#aaa23a',
        }
    )
    return svg

# Layout
col1, col2 = st.columns([1.2, 1])

with col1:
    # PGN Input
    pgn_text = st.text_area(
        "Paste PGN here:",
        value=SAMPLE_PGN,
        height=200,
        key="pgn_input"
    )
    
    if st.button("📥 Load Game", use_container_width=True):
        game, moves, boards = parse_pgn(pgn_text)
        if game:
            st.session_state.game = game
            st.session_state.moves = moves
            st.session_state.boards = boards
            st.session_state.move_index = 0
            st.rerun()

    # Display board
    if st.session_state.boards:
        current_board = st.session_state.boards[st.session_state.move_index]
        
        # Get last move for highlighting
        last_move = None
        if st.session_state.move_index > 0 and st.session_state.game:
            board_temp = st.session_state.game.board()
            for i, move in enumerate(st.session_state.game.mainline_moves()):
                if i == st.session_state.move_index - 1:
                    last_move = move
                    break
                board_temp.push(move)
        
        svg = render_board(current_board, last_move)
        st.markdown(f'<div class="board-container">{svg}</div>', unsafe_allow_html=True)
        
        # Navigation controls
        st.write("")
        nav_cols = st.columns([1, 1, 1, 1, 2])
        
        with nav_cols[0]:
            if st.button("⏮️", help="First move", use_container_width=True):
                st.session_state.move_index = 0
                st.rerun()
        
        with nav_cols[1]:
            if st.button("◀️", help="Previous move", use_container_width=True):
                if st.session_state.move_index > 0:
                    st.session_state.move_index -= 1
                    st.rerun()
        
        with nav_cols[2]:
            if st.button("▶️", help="Next move", use_container_width=True):
                if st.session_state.move_index < len(st.session_state.moves):
                    st.session_state.move_index += 1
                    st.rerun()
        
        with nav_cols[3]:
            if st.button("⏭️", help="Last move", use_container_width=True):
                st.session_state.move_index = len(st.session_state.moves)
                st.rerun()
        
        with nav_cols[4]:
            move_num = st.slider(
                "Move",
                0,
                len(st.session_state.moves),
                st.session_state.move_index,
                key="move_slider",
                label_visibility="collapsed"
            )
            if move_num != st.session_state.move_index:
                st.session_state.move_index = move_num
                st.rerun()

with col2:
    if st.session_state.game:
        # Game info
        headers = st.session_state.game.headers
        st.markdown('<div class="game-info">', unsafe_allow_html=True)
        
        info_items = [
            ("Event", headers.get("Event", "?")),
            ("Date", headers.get("Date", "?")),
            ("White", headers.get("White", "?")),
            ("Black", headers.get("Black", "?")),
            ("Result", headers.get("Result", "?")),
        ]
        
        for label, value in info_items:
            st.markdown(
                f'<p class="game-info-item">{label}: <span class="game-info-value">{value}</span></p>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Move list
        st.markdown("### 📋 Moves")
        
        if st.session_state.moves:
            moves_html = '<div class="move-list">'
            
            for i, move in enumerate(st.session_state.moves):
                move_num = (i // 2) + 1
                is_white = i % 2 == 0
                is_current = i == st.session_state.move_index - 1
                
                current_class = "move-current" if is_current else ""
                
                if is_white:
                    moves_html += f'<span class="move-number">{move_num}.</span>'
                
                moves_html += f'<span class="move-item {current_class}">{move}</span> '
                
                if not is_white:
                    moves_html += '<br>'
            
            moves_html += '</div>'
            st.markdown(moves_html, unsafe_allow_html=True)
        
        # Position info
        st.markdown("### 📊 Position")
        current_board = st.session_state.boards[st.session_state.move_index]
        
        position_col1, position_col2 = st.columns(2)
        with position_col1:
            st.metric("Move", f"{st.session_state.move_index} / {len(st.session_state.moves)}")
        with position_col2:
            turn = "White" if current_board.turn else "Black"
            st.metric("To Play", turn)
        
        # Check/Checkmate status
        if current_board.is_checkmate():
            st.error("♚ Checkmate!")
        elif current_board.is_check():
            st.warning("♚ Check!")
        elif current_board.is_stalemate():
            st.info("½ Stalemate")
        elif current_board.is_insufficient_material():
            st.info("½ Draw - Insufficient material")
    else:
        st.info("👆 Paste a PGN and click 'Load Game' to start exploring!")
        
        st.markdown("""
        ### What is PGN?
        
        **Portable Game Notation (PGN)** is the standard format for recording chess games.
        
        You can get PGN from:
        - ♟️ Chess.com (game archive)
        - ♟️ Lichess.org (game export)
        - ♟️ Any chess database
        
        The sample game loaded is the famous **"Evergreen Game"** (1852) between Adolf Anderssen and Jean Dufresne!
        """)

