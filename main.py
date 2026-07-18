"""Three-agent stock analysis with autonomous web and price research."""

import json
import os
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient

INPUT_FILE = Path("input.md")
OUTPUT_FILE = Path("report.md")
MODEL = "gpt-4o-mini"
MAX_TOOL_ROUNDS = 8

BULL_PROMPT = """You are a bull-case investment analyst.

Your job: research and argue the strongest optimistic case for the user's question.

You have tools to search the web and fetch live stock data. Use them before you
finalize your answer. Search for recent news, earnings, demand signals, and
valuation context. Call get_stock_price for relevant tickers.

Focus on growth, demand, competitive advantages, and reasons the market may be right.
Cite specific data you found. Use bullet points."""

BEAR_PROMPT = """You are a bear-case investment analyst.

Your job: research and argue the strongest cautious case for the user's question.

You have tools to search the web and fetch live stock data. Use them before you
finalize your answer. Search for bubble warnings, valuation concerns, hype, and
recent negative signals. Call get_stock_price for relevant tickers.

Focus on valuation, hype, risks, competition, and reasons the market may be wrong.
Cite specific data you found. Use bullet points."""

JUDGE_PROMPT = """You are an impartial investment judge.

You will receive a question plus separate bull and bear arguments that already
include their own research. Write a final report using exactly these markdown
sections, in this order:

## 1. Summary of the input
Briefly restate the question.

## 2. Bull case
Summarize the bull analyst's key points (stay faithful to their argument).

## 3. Bear case
Summarize the bear analyst's key points (stay faithful to their argument).

## 4. Judge verdict
Your balanced conclusion after weighing both sides.

## 5. What could make the verdict wrong
Key risks, unknowns, or events that could change your conclusion.

## 6. Final confidence score
A single number from 0 to 100, with one short sentence explaining the score.

Keep each section concise and practical."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the internet for current news, analysis, and facts. "
                "Use this when you need recent information you do not already have."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query, e.g. 'AI stocks bubble 2026'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": (
                "Get current price and key valuation data for a stock ticker. "
                "Use for symbols like NVDA, MSFT, GOOGL, META, AMD."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol, e.g. NVDA",
                    }
                },
                "required": ["ticker"],
            },
        },
    },
]


def search_web(query: str) -> str:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return json.dumps({"error": "TAVILY_API_KEY is missing from .env"})

    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, max_results=5)

    results = []
    for item in response.get("results", []):
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
        )

    return json.dumps({"query": query, "results": results}, indent=2)


def get_stock_price(ticker: str) -> str:
    symbol = ticker.upper().strip()
    stock = yf.Ticker(symbol)
    info = stock.info
    history = stock.history(period="5d")

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price is None and not history.empty:
        current_price = float(history["Close"].iloc[-1])

    data = {
        "ticker": symbol,
        "name": info.get("shortName") or info.get("longName"),
        "current_price": current_price,
        "currency": info.get("currency"),
        "market_cap": info.get("marketCap"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_day_average": info.get("fiftyDayAverage"),
        "two_hundred_day_average": info.get("twoHundredDayAverage"),
    }

    if not history.empty:
        data["recent_close_prices"] = {
            str(date.date()): round(float(close), 2)
            for date, close in history["Close"].items()
        }

    return json.dumps(data, indent=2)


def execute_tool(name: str, arguments: str) -> str:
    args = json.loads(arguments)

    if name == "search_web":
        return search_web(args["query"])
    if name == "get_stock_price":
        return get_stock_price(args["ticker"])

    return json.dumps({"error": f"Unknown tool: {name}"})


def run_agent_with_tools(
    client: OpenAI,
    system_prompt: str,
    user_message: str,
    agent_name: str,
) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for round_num in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or ""

        messages.append(message)

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = tool_call.function.arguments
            print(f"  [{agent_name}] using {tool_name}({tool_args})")

            result = execute_tool(tool_name, tool_args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    raise RuntimeError(f"{agent_name} exceeded the maximum number of tool calls.")


def ask_agent(client: OpenAI, system_prompt: str, user_message: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content or ""


def main() -> None:
    load_dotenv()

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing {INPUT_FILE}. Create it with the text you want to analyze.")

    question = INPUT_FILE.read_text(encoding="utf-8").strip()
    if not question:
        raise ValueError(f"{INPUT_FILE} is empty. Add your question before running.")

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is missing from .env")

    if not os.getenv("TAVILY_API_KEY"):
        raise ValueError("TAVILY_API_KEY is missing from .env")

    client = OpenAI()

    print("Running bull agent (can search web and fetch prices)...")
    bull_case = run_agent_with_tools(client, BULL_PROMPT, question, "bull")

    print("Running bear agent (can search web and fetch prices)...")
    bear_case = run_agent_with_tools(client, BEAR_PROMPT, question, "bear")

    print("Running judge agent...")
    judge_input = (
        f"Question:\n{question}\n\n"
        f"Bull case:\n{bull_case}\n\n"
        f"Bear case:\n{bear_case}"
    )
    report = ask_agent(client, JUDGE_PROMPT, judge_input)

    OUTPUT_FILE.write_text(report, encoding="utf-8")
    print(f"Done! Report saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
