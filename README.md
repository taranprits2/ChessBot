# Chess Analyzer

A chess game analyzer that lets you paste PGN and analyze games with Stockfish.

## What it does

- Parse and visualize chess games from PGN
- Step through moves with an interactive board
- Stockfish engine analysis with evaluation bar
- Move classifications (brilliant, blunder, etc.)
- Accuracy scores for both players
- Draw arrows and highlights on the board

## Tech Stack

- **Python** - Core language
- **Streamlit** - Web framework
- **python-chess** - PGN parsing and board rendering
- **Stockfish** - Chess engine (auto-downloaded)

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```
