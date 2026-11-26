"""Steam Direct decision shared by the FAQ and the launch dashboard.

This reads the owner's recorded assessment, not the test data itself.
Never silently count an omitted gate, a booked test or an old unqualified
Gate B pass as a positive observation.
"""

GATE_NAMES = {"0": "Gate 0 · Posizionamento", "A": "Gate A · Qualità percepita",
              "B": "Gate B · Test reale", "C": "Gate C · Capsule"}


def assess(raw):
    """Canonical gates first; additional project gates can block, never replace one."""
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for code in dict.fromkeys((*GATE_NAMES, *raw)):
        gate = raw.get(code)
        gate = gate if isinstance(gate, dict) else {}
        state = gate.get("state")
        state = state if state in ("pass", "fail", "pending") else "unknown"
        reason = ""
        if code == "B":
            stage = gate.get("test_stage")
            evidence = gate.get("evidence")
            if stage == "scheduled":
                state, reason = "pending", "Test fissato: raccogliere le sessioni e confrontarle con le soglie concordate."
            elif stage == "collected":
                if not isinstance(evidence, str) or not evidence.strip():
                    state, reason = "pending", "Test raccolto, ma manca il riferimento alle misure della build."
                elif state not in ("pass", "fail"):
                    state, reason = "pending", "Misure raccolte: esito rispetto alle soglie ancora da registrare."
                else:
                    reason = "Misure raccolte e confrontate con le soglie del test."
            elif state in ("pass", "fail"):
                state, reason = "unknown", "Esito dichiarato senza prova del test raccolto: verificare prima di decidere."
        if state == "unknown" and not reason:
            reason = "Esito non documentato: registrare la prova e la decisione."
        result[code] = {"state": state, "note": " ".join(filter(None, (reason, str(gate.get("note") or ""))))}
    return result
