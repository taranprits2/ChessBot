# ♟️ PGN Visualizer

A sleek chess game visualizer built with Python and Streamlit. Paste any PGN and explore games move by move with a beautiful interactive board.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)

## Features

- 📥 **PGN Parser** - Paste any valid PGN and load the game instantly
- ♟️ **Interactive Board** - Beautiful chess board with move highlighting
- ⏮️ **Move Navigation** - Step through games with buttons or slider
- 📋 **Move List** - See all moves with current position highlighted
- 📊 **Position Info** - Check/checkmate/stalemate detection

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the App

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Coming Soon

- 🤖 **Stockfish Analysis** - Engine evaluation for each move
- 📈 **Evaluation Graph** - Visual advantage chart
- 💡 **Best Move Suggestions** - See what the engine recommends
- 🎯 **Blunder Detection** - Identify mistakes and missed opportunities

## Getting PGN

You can export PGN from:
- **Chess.com**: Game Archive → Click game → Download PGN
- **Lichess**: Any game → Tools menu → Download PGN
- **Any chess database or app**

## Tech Stack

- **[python-chess](https://python-chess.readthedocs.io/)** - Chess library for PGN parsing, move validation, and board rendering
- **[Streamlit](https://streamlit.io/)** - Web app framework
- **[Stockfish](https://stockfishchess.org/)** - Chess engine (coming soon)
