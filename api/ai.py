import os
from typing import Any

import anthropic

SUBMIT_ORDER_TOOL: dict[str, Any] = {
    "name": "submit_order",
    "description": (
        "Submit one trading order to the matching engine. "
        "Call this tool once per order the user wants to place."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "side": {
                "type": "string",
                "enum": ["buy", "sell"],
                "description": "Direction of the order.",
            },
            "order_type": {
                "type": "string",
                "enum": ["limit", "market"],
                "description": (
                    "Use 'market' when no price is specified or the user says "
                    "'at market'. Use 'limit' when a price is given."
                ),
            },
            "quantity": {
                "type": "number",
                "description": "Number of units to trade. Must be positive.",
            },
            "price": {
                "type": "number",
                "description": (
                    "Limit price per unit. Required for limit orders; "
                    "omit for market orders."
                ),
            },
            "reasoning": {
                "type": "string",
                "description": (
                    "One sentence explaining how you interpreted the instruction "
                    "into this order."
                ),
            },
        },
        "required": ["side", "order_type", "quantity", "reasoning"],
    },
}

_SYSTEM_PROMPT = """\
You are a trading assistant that converts natural-language instructions into \
structured orders for a simulated limit order book.

Rules
-----
1. Extract every order the user intends to place; call submit_order once per order.
2. Interpret relative prices against the current mid-price provided in the user turn.
   Examples:
     • "1% above mid"  → price = mid * 1.01
     • "at market"     → order_type = "market", omit price
     • "at 102.50"     → price = 102.50
3. If the instruction is ambiguous (e.g. no quantity given), use a sensible \
default (quantity = 1) and note it in the reasoning field.
4. Never decline a plausible trading instruction — always call submit_order at \
least once.
5. Do NOT output any text outside of tool calls.\
"""

_client: anthropic.AsyncAnthropic | None = None

def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
        _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


def is_configured() -> bool:
    """Return True if the API key is present in the environment."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))

def _build_context(snapshot: dict) -> str:
    """Format the live book snapshot into a compact string for the user turn."""
    bids = snapshot.get("bids", [])
    asks = snapshot.get("asks", [])
    spread = snapshot.get("spread")

    best_bid = bids[0]["price"] if bids else None
    best_ask = asks[0]["price"] if asks else None

    if best_bid and best_ask:
        mid = round((best_bid + best_ask) / 2, 4)
    elif best_bid:
        mid = best_bid
    elif best_ask:
        mid = best_ask
    else:
        mid = None

    lines = ["Current order book:"]
    if mid is not None:
        lines.append(f"  mid-price : {mid}")
    if best_bid is not None:
        lines.append(f"  best bid  : {best_bid}")
    if best_ask is not None:
        lines.append(f"  best ask  : {best_ask}")
    if spread is not None:
        lines.append(f"  spread    : {spread}")
    lines.append(f"  bid levels: {len(bids)}   ask levels: {len(asks)}")

    return "\n".join(lines)

async def interpret_instruction(
    instruction: str,
    snapshot: dict,
) -> list[dict]:
    """
    Parse a natural-language trading instruction and return a list of order dicts.

    Each dict has the shape:
        {
            "side": "buy" | "sell",
            "order_type": "limit" | "market",
            "quantity": float,
            "price": float | None,
            "reasoning": str,
        }

    Raises RuntimeError if ANTHROPIC_API_KEY is not configured.
    Raises anthropic.APIError on network / API failures.
    """
    client = _get_client()
    context = _build_context(snapshot)

    response = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        thinking={"type": "adaptive"},
        tools=[
            {
                **SUBMIT_ORDER_TOOL,
                # Cache the static tool definition across requests
                "cache_control": {"type": "ephemeral"},
            }
        ],
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                # Cache the system prompt — it never changes
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"{context}\n\nInstruction: {instruction}",
            }
        ],
        tool_choice={"type": "auto"},
    )

    orders: list[dict] = []
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_order":
            inp = block.input
            orders.append(
                {
                    "side": inp["side"],
                    "order_type": inp["order_type"],
                    "quantity": float(inp["quantity"]),
                    "price": float(inp["price"]) if inp.get("price") is not None else None,
                    "reasoning": inp.get("reasoning", ""),
                }
            )

    return orders
