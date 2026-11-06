import re

current_incident = {
    "symptoms":      [],
    "system_type":   None,   # "PROD" | "non-PROD"
    "component":     None,   # e.g. "BC-SRV-ARL"
    "already_tried": [],
}

_SYSTEM_RE = [
    (re.compile(r"\bprod(?:uction)?\b", re.I), "PROD"),
    (re.compile(r"\b(?:non.?prod|dev(?:elopment)?|sandbox|qa[s]?)\b|\btest\s+(?:system|env(?:ironment)?|client)\b", re.I), "non-PROD"),
]

_COMPONENT_RE = re.compile(r"\b([A-Z]{2,6}-[A-Z]{2,6}(?:-[A-Z]{2,6})*)\b")

_TRIED_RE = re.compile(
    r"(?:(?:i|we)\s+)?(?:already\s+)?(?:tried|checked|applied|ran|restarted|tested)\s+([^.,;]+)",
    re.I,
)


def new_incident() -> dict:
    return {"symptoms": [], "system_type": None, "component": None, "already_tried": []}


def update_incident(message: str, incident: dict = None) -> tuple:
    """Returns (incident, should_refresh).
    Pass an explicit incident dict for multi-session use; defaults to module-level current_incident."""
    if incident is None:
        incident = current_incident

    msg = message.strip()
    if not msg:
        return incident, False

    consumed = False
    changed = set()

    # system_type -- first clear mention wins (does not affect retrieval)
    if incident["system_type"] is None:
        for pattern, label in _SYSTEM_RE:
            if pattern.search(msg):
                incident["system_type"] = label
                consumed = True
                break

    # component -- first SAP component code wins (affects boost -> refresh)
    if incident["component"] is None:
        m = _COMPONENT_RE.search(msg)
        if m:
            incident["component"] = m.group(1)
            consumed = True
            changed.add("component")

    # already_tried -- accumulate unique steps (does not affect retrieval)
    for m in _TRIED_RE.finditer(msg):
        step = m.group(1).strip().rstrip(".")
        if step and step not in incident["already_tried"]:
            incident["already_tried"].append(step)
            consumed = True
            changed.add("already_tried")

    # symptom -- only if message was not metadata (affects query -> refresh)
    if not consumed:
        incident["symptoms"].append(msg)
        changed.add("symptoms")

    should_refresh = bool(changed & {"symptoms", "component"})
    return incident, should_refresh


def reset_incident() -> dict:
    current_incident.update(symptoms=[], system_type=None, component=None, already_tried=[])
    return current_incident


if __name__ == "__main__":
    reset_incident()

    turns = [
        ("documents won't upload",             "symptom       -> refresh"),
        ("component is BC-SRV-ARL",            "component     -> refresh"),
        ("I already checked transaction SM21", "already_tried -> no refresh"),
    ]

    for msg, label in turns:
        _, refresh = update_incident(msg)
        print(f"  {'REFRESH' if refresh else 'skip   '}  [{label}]  \"{msg}\"")

    import json
    print(f"\ncurrent_incident:\n{json.dumps(current_incident, indent=2)}")

    assert update_incident("new symptom")[1] is True,  "symptom should refresh"
    reset_incident()
    assert update_incident("it's on PROD")[1] is False, "system_type alone should not refresh"
    reset_incident()
    assert update_incident("already tried SM59")[1] is False, "already_tried alone should not refresh"
    reset_incident()
    assert update_incident("component BC-CCM-PRN")[1] is True, "component should refresh"
    reset_incident()

    # bug fix: "test" as a verb must not trigger non-PROD
    inc, _ = update_incident("archiving works fine when I test it but fails overnight")
    assert inc["system_type"] is None,                  "verb 'test' must not set system_type"
    assert len(inc["symptoms"]) == 1,                   "message should land in symptoms"
    reset_incident()

    # "test system" as a noun phrase still sets non-PROD
    inc, _ = update_incident("this is on the test system")
    assert inc["system_type"] == "non-PROD",            "'test system' should set non-PROD"
    assert len(inc["symptoms"]) == 0,                   "metadata message should not go to symptoms"
    reset_incident()

    print("\nall assertions passed")
