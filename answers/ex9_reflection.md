# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

In session sess_be3d00d3a9db, the planner made an interesting decision. After the venue_search tool triggered its safety mechanism (following 4 failed attempts to find a venue matching the LLM's hallucinated parameters), the executor hit the STOP calling venue_search instruction. 

The planner then called handoff_to_structured. The planner then attempted to hand off the "search attempts" data to the structured half trying to find a resolution. This shows that the "handoff bridge" works as a safety valve when an agent fails to work as expected.

### Citation

- sessions/sess_be3d00d3a9db/logs/trace.jsonl
- The venue_search summary in trace line 6: "STOP calling venue_search; use the results you already have."

---

## Q2 — Dataflow integrity catch

### Your answer

During my manual testing of Exercise 5, I followed the instructions to perform the "fabrication" on session sess_239b73852a7b, editing the flyer.html file to change the price to £9999. 

The verify_dataflow check correctly failed with ok=False and flagged ['£9999'] as an unverified fact. While in this specific case perhaps a human reviewer would notice the excessive price, the point is that the dataflow is able to keep track of facts and detect when they are not verified.

In this case all the facts in the citation are shown as unverified because the check performed with the python -c command does not have access to the session's memory, and therefore cannot verify the facts.

### Citation

```bash
uv run python -c "
from starter.edinburgh_research.integrity import verify_dataflow
from pathlib import Path
result = verify_dataflow(Path('$(make logs)/workspace/flyer.html').read_tex
t())
print(result.summary)
"
dataflow FAIL: 4 unverified fact(s): ['£9999', '£0', '12', 'cloudy']
```

---

## Q3 — Expected production failure

### Your answer

The first production failure I'd expect is a "hallucinated commitment," where the LLM persona accepts an impossible booking (like a negative party size or a non-existent date) to stay in character. I saw this in my Ex8 interaction with the Alasdair persona in session sess_069600fbf662. When I requested a booking for "-2 people," the persona this was evidently understood as "two people" and the response was "Aye, we can do that... I'll pencil you in."

### Citation

- sessions/sess_069600fbf662/logs/trace.jsonl
