# Architecture

Plain-English map of how this project works.

**Keep this file updated** whenever the project structure or flow changes.

---

## 1. What each file does

| File | What it does |
|------|----------------|
| `main.py` | The program. Runs three AI agents (bull, bear, judge) and saves the final report. Bull and bear can search the web and fetch stock prices on their own. |
| `input.md` | Your question. Edit this to change what gets analyzed. |
| `report.md` | The output. Created or overwritten each time you run the program. |
| `.env` | Your secret API keys (not shared in git). |
| `requirements.txt` | List of Python packages to install. |
| `.gitignore` | Tells git which files to skip (`.env`, virtualenv, cache files). |
| `.venv/` | Your local Python environment (packages installed here). Not part of the logic. |
| `ARCHITECTURE.md` | This file. Explains how everything fits together. |

---

## 2. Which file starts the program

**`main.py`** is the entry point.

You start it from Terminal with:

```bash
python main.py
```

That runs the `main()` function at the bottom of `main.py`.

---

## 3. What calls what, in order

```
You run: python main.py
    │
    ▼
main()                              ← starts in main.py
    │
    ├─ load_dotenv()                 ← reads API keys from .env
    │
    ├─ read input.md                 ← loads your question
    │
    ├─ OpenAI()                      ← creates API client
    │
    ├─ run_agent_with_tools(BULL)    ← bull agent
    │       ├─ may call search_web()      → Tavily API
    │       ├─ may call get_stock_price() → yfinance
    │       └─ returns bull_case text
    │
    ├─ run_agent_with_tools(BEAR)    ← bear agent
    │       ├─ may call search_web()      → Tavily API
    │       ├─ may call get_stock_price() → yfinance
    │       └─ returns bear_case text
    │
    ├─ ask_agent(JUDGE)              ← judge agent (no tools)
    │       └── gets question + bull_case + bear_case
    │       └── returns final report text
    │
    └─ write report.md               ← saves judge output to disk
```

**Call chain in one line:**

`main()` → bull (with tools) → bear (with tools) → judge → write `report.md`

---

## 4. Where data enters and exits

### Data enters here

| Entry point | What goes in |
|-------------|--------------|
| `input.md` | Your investment question (plain text) |
| `.env` | `OPENAI_API_KEY` and `TAVILY_API_KEY` |
| **Internet** (via tools) | Live web search results and stock prices — fetched by bull/bear agents when they decide they need them |

### Data moves inside the program

| Step | Data |
|------|------|
| After reading `input.md` | `question` (string) |
| During bull/bear runs | Tool results (search snippets, stock data) passed back into the agent loop |
| After bull agent | `bull_case` (string with researched arguments) |
| After bear agent | `bear_case` (string with researched arguments) |
| Before judge agent | `judge_input` = question + bull_case + bear_case |
| After judge agent | `report` (string) |

### Data exits here

| Exit point | What comes out |
|------------|----------------|
| `report.md` | Final 6-section markdown report |
| Terminal | Progress messages and tool usage (`[bull] using search_web(...)`) |

---

## 5. Where the OpenAI API is called

OpenAI is called in two functions:

| Function | Used by | Has tools? |
|----------|---------|------------|
| `run_agent_with_tools()` | Bull, Bear | Yes — loops until the agent is done researching |
| `ask_agent()` | Judge | No — one call, weighs both sides |

Both call:

```python
client.chat.completions.create(...)
```

**External APIs used by tools (not OpenAI):**

| Tool | API / library | Purpose |
|------|---------------|---------|
| `search_web()` | Tavily | Web search for news and analysis |
| `get_stock_price()` | yfinance | Live stock price and valuation data |

**Model used:** `gpt-4o-mini` (set by the `MODEL` variable in `main.py`)

---

## 6. What to edit to change behavior

| If you want to… | Edit this |
|-----------------|-----------|
| Change the question | `input.md` |
| Change how the bull agent thinks | `BULL_PROMPT` in `main.py` |
| Change how the bear agent thinks | `BEAR_PROMPT` in `main.py` |
| Change the report format or judge logic | `JUDGE_PROMPT` in `main.py` |
| Use a different OpenAI model | `MODEL` in `main.py` |
| Add or change agent tools | `TOOLS`, `search_web()`, `get_stock_price()` in `main.py` |
| Change where input is read from | `INPUT_FILE` in `main.py` |
| Change where output is saved | `OUTPUT_FILE` in `main.py` |
| Add or update Python packages | `requirements.txt` |
| Set up your API keys | Create `.env` with `OPENAI_API_KEY` and `TAVILY_API_KEY` |

**Most common edit:** change `input.md` only.

---

## 7. Workflow diagram

```
┌─────────────┐
│  input.md   │  ← you write the question here
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│   main.py   │────▶│    .env      │  ← API keys loaded here
└──────┬──────┘     └──────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│              Bull agent                      │
│   thinks → search_web / get_stock_price    │──┐
│   (loops until ready)                        │  │
└──────────────────────┬───────────────────────┘  │
                       │                          │
┌──────────────────────▼───────────────────────┐  │  Tavily + yfinance
│              Bear agent                      │  │  (called by tools)
│   thinks → search_web / get_stock_price    │──┘
│   (loops until ready)                        │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
                ┌─────────────┐
                │    Judge    │  ← no tools, weighs both sides
                └──────┬──────┘
                       │
                       ▼
                ┌─────────────┐
                │  report.md  │
                └─────────────┘
```

---

## Current limitations

- **Search quality depends on Tavily** and the queries the agent chooses.
- **Stock data may be delayed** (yfinance is free, not a live trading feed).
- **More API calls** than before — bull and bear each search independently (slower, higher cost).
- **No scheduling.** You run it manually with `python main.py`.
- **Judge does not search** — it relies on bull and bear research.
