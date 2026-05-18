"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import json
from pathlib import Path

from sovereign_agent.errors import ToolError
from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolRegistry, ToolResult, _RegisteredTool

from .integrity import _TOOL_CALL_LOG, record_tool_call

_SAMPLE_DATA = Path(__file__).parent / "sample_data"


# ---------------------------------------------------------------------------
# TODO 1 — venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"

    MUST call record_tool_call(...) before returning so the integrity
    check can see what data was produced.
    """
    search_count = sum(1 for r in _TOOL_CALL_LOG if r.tool_name == "venue_search")
    if search_count >= 3:
        return ToolResult(
            success=False,
            output={"error": "too_many_searches", "count": search_count},
            summary="STOP calling venue_search; use the results you already have.",
        )

    path = _SAMPLE_DATA / "venues.json"
    if not path.exists():
        raise ToolError(
            code="SA_TOOL_DEPENDENCY_MISSING",
            message=f"Missing fixture: {path}",
        )

    with path.open() as f:
        venues = json.load(f)

    results = []
    near_lower = near.lower()
    for v in venues:
        if not v.get("open_now", False):
            continue
        area = v.get("area", "").lower()
        address = v.get("address", "").lower()
        if near_lower not in area and area not in near_lower and near_lower not in address:
            continue
        if v.get("seats_available_evening", 0) < party_size:
            continue
        if v.get("hire_fee_gbp", 0) + v.get("min_spend_gbp", 0) > budget_max_gbp:
            continue
        results.append(v)

    output = {
        "near": near,
        "party_size": party_size,
        "results": results,
        "count": len(results),
    }
    record_tool_call(
        "venue_search",
        {"near": near, "party_size": party_size, "budget_max_gbp": budget_max_gbp},
        output,
    )

    return ToolResult(
        success=True,
        output=output,
        summary=f"venue_search({near}, party={party_size}): {len(results)} result(s)",
    )


# ---------------------------------------------------------------------------
# TODO 2 — get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"

    If the city or date is not in the fixture, return success=False with
    a clear ToolError (SA_TOOL_INVALID_INPUT). Do NOT raise.

    MUST call record_tool_call(...) before returning.
    """
    path = _SAMPLE_DATA / "weather.json"
    if not path.exists():
        raise ToolError(
            code="SA_TOOL_DEPENDENCY_MISSING",
            message=f"Missing fixture: {path}",
        )

    with path.open() as f:
        weather_data = json.load(f)

    city_key = city.lower()
    if city_key not in weather_data or date not in weather_data[city_key]:
        err = ToolError(
            code="SA_TOOL_INVALID_INPUT",
            message=f"City '{city}' or date '{date}' not found in fixtures.",
        )
        return ToolResult(
            success=False,
            output={},
            summary=f"get_weather({city}, {date}): city or date not found in fixtures",
            error=err,
        )

    output = weather_data[city_key][date]
    output["city"] = city
    output["date"] = date

    record_tool_call("get_weather", {"city": city, "date": date}, output)

    return ToolResult(
        success=True,
        output=output,
        summary=f"get_weather({city}, {date}): {output['condition']}, {output['temperature_c']}C",
    )


# ---------------------------------------------------------------------------
# TODO 3 — calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking.

    Formula:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers[venue_id]
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * service_charge_percent / 100
      total         = subtotal + service + <venue's hire_fee_gbp + min_spend_gbp>
      deposit_rule  = per deposit_policy thresholds

    Returns:
      output: {
        "venue_id": str,
        "party_size": int,
        "duration_hours": int,
        "catering_tier": str,
        "subtotal_gbp": int,
        "service_gbp": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
      }
      summary: "calculate_cost(<venue>, <party>): total £<N>, deposit £<M>"

    MUST call record_tool_call(...) before returning.
    """
    catering_path = _SAMPLE_DATA / "catering.json"
    venues_path = _SAMPLE_DATA / "venues.json"

    if not catering_path.exists() or not venues_path.exists():
        raise ToolError(
            code="SA_TOOL_DEPENDENCY_MISSING",
            message="Missing catering or venues fixture",
        )

    with catering_path.open() as f:
        catering = json.load(f)
    with venues_path.open() as f:
        venues = json.load(f)

    venue = next((v for v in venues if v["id"] == venue_id), None)
    if not venue:
        return ToolResult(
            success=False,
            output={},
            summary=f"calculate_cost: venue {venue_id} not found",
        )

    base_rates = catering["base_rates_gbp_per_head"]
    venue_modifiers = catering["venue_modifiers"]
    service_charge_pct = catering["service_charge_percent"]

    if catering_tier not in base_rates:
        return ToolResult(
            success=False,
            output={},
            summary=f"calculate_cost: invalid catering tier {catering_tier}",
        )

    base_per_head = base_rates[catering_tier]
    venue_mult = venue_modifiers.get(venue_id, 1.0)

    subtotal = int(base_per_head * venue_mult * party_size * max(1, duration_hours))
    service = int(subtotal * service_charge_pct / 100)

    venue_floor = venue.get("hire_fee_gbp", 0) + venue.get("min_spend_gbp", 0)
    total = subtotal + service + venue_floor

    # Deposit policy
    # under_gbp_300: no_deposit_required
    # gbp_300_to_1000: deposit_20_percent
    # over_gbp_1000: deposit_30_percent
    if total < 300:
        deposit = 0
    elif total <= 1000:
        deposit = int(total * 0.2)
    else:
        deposit = int(total * 0.3)

    output = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
        "subtotal_gbp": subtotal,
        "service_gbp": service,
        "total_gbp": total,
        "deposit_required_gbp": deposit,
    }

    record_tool_call(
        "calculate_cost",
        {
            "venue_id": venue_id,
            "party_size": party_size,
            "duration_hours": duration_hours,
            "catering_tier": catering_tier,
        },
        output,
    )

    return ToolResult(
        success=True,
        output=output,
        summary=f"calculate_cost({venue_id}, {party_size}): total £{total}, deposit £{deposit}",
    )


# ---------------------------------------------------------------------------
# TODO 4 — generate_flyer
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a self-contained HTML flyer (inline CSS, no external assets). Tag every key fact with data-testid="<n>" so the integrity check can parse it.

    Write a formatted HTML flyer with an H1 title, the event
    facts, a weather summary, and the cost breakdown.

    Returns:
      output: {"path": "workspace/flyer.html", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """
    # Fetch recent data from logs to tolerate LLM omissions
    weather_calls = [r for r in _TOOL_CALL_LOG if r.tool_name == "get_weather"]
    cost_calls = [r for r in _TOOL_CALL_LOG if r.tool_name == "calculate_cost"]
    search_calls = [r for r in _TOOL_CALL_LOG if r.tool_name == "venue_search"]

    w_out = weather_calls[-1].output if weather_calls else {}
    c_out = cost_calls[-1].output if cost_calls else {}

    vid = c_out.get("venue_id")
    v_info = {}
    for sc in search_calls:
        for v in sc.output.get("results", []):
            if v["id"] == vid:
                v_info = v
                break

    venue_name = event_details.get("venue_name") or v_info.get("name", "Unknown Venue")
    venue_address = event_details.get("venue_address") or v_info.get("address", "Unknown Address")
    date = event_details.get("date") or w_out.get("date", "Unknown Date")
    time = event_details.get("time") or "19:30"
    party_size = event_details.get("party_size") or c_out.get("party_size", 0)
    condition = event_details.get("condition") or w_out.get("condition", "Unknown")
    temp = event_details.get("temperature_c")
    if temp is None:
        temp = w_out.get("temperature_c", 0)
    total = event_details.get("total_gbp")
    if total is None:
        total = c_out.get("total_gbp", 0)
    deposit = event_details.get("deposit_required_gbp")
    if deposit is None:
        deposit = c_out.get("deposit_required_gbp", 0)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ccc; border-radius: 8px; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; }}
        .fact {{ margin-bottom: 15px; }}
        .label {{ font-weight: bold; color: #7f8c8d; min-width: 120px; display: inline-block; }}
        .value {{ color: #2980b9; }}
        .weather {{ background: #ecf0f1; padding: 15px; border-radius: 4px; margin-top: 20px; }}
        .cost {{ background: #fef9e7; padding: 15px; border-radius: 4px; border-left: 5px solid #f1c40f; margin-top: 20px; }}
    </style>
</head>
<body>
    <h1>Event Flyer: <span data-testid="venue_name">{venue_name}</span></h1>

    <div class="fact">
        <span class="label">Location:</span>
        <span class="value" data-testid="venue_address">{venue_address}</span>
    </div>

    <div class="fact">
        <span class="label">Date:</span>
        <span class="value" data-testid="date">{date}</span>
    </div>

    <div class="fact">
        <span class="label">Time:</span>
        <span class="value" data-testid="time">{time}</span>
    </div>

    <div class="fact">
        <span class="label">Party Size:</span>
        <span class="value" data-testid="party_size">{party_size}</span>
    </div>

    <div class="weather">
        <h3>Weather Report</h3>
        <p>Condition: <span data-testid="condition">{condition}</span></p>
        <p>Temperature: <span data-testid="temperature_c">{temp}</span>°C</p>
    </div>

    <div class="cost">
        <h3>Cost Breakdown</h3>
        <p>Total Cost: <span data-testid="total_gbp">£{total}</span></p>
        <p>Deposit Required: <span data-testid="deposit_required_gbp">£{deposit}</span></p>
    </div>
</body>
</html>"""
    workspace_path = session.workspace_dir / "flyer.html"
    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_path.write_text(html, encoding="utf-8")

    output = {
        "path": "workspace/flyer.html",
        "bytes_written": len(html),
    }

    record_tool_call("generate_flyer", {"event_details": event_details}, output)

    return ToolResult(
        success=True,
        output=output,
        summary=f"generate_flyer: wrote {output['path']} ({output['bytes_written']} chars)",
    )


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            description="Search Edinburgh venues by area, party size, and max budget.",
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description="Compute total cost and deposit for a booking.",
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description="Write an HTML flyer for the event to workspace/flyer.html.",
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]
