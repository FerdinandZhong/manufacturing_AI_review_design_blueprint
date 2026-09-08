"""Program state machine. Legal transitions only; fails fast on illegal ones."""
from enum import Enum


class ProgramState(str, Enum):
    REQUIREMENTS = "REQUIREMENTS"
    DESIGN       = "DESIGN"
    ENGINEERING  = "ENGINEERING"
    VALIDATION   = "VALIDATION"
    GATE_REVIEW  = "GATE_REVIEW"
    RELEASED     = "RELEASED"


_ALLOWED: dict[ProgramState, set] = {
    ProgramState.REQUIREMENTS: {ProgramState.DESIGN},
    ProgramState.DESIGN:       {ProgramState.ENGINEERING},
    ProgramState.ENGINEERING:  {ProgramState.VALIDATION},
    ProgramState.VALIDATION:   {ProgramState.GATE_REVIEW},
    ProgramState.GATE_REVIEW:  {ProgramState.RELEASED},
    ProgramState.RELEASED:     set(),
}


def transition(current: ProgramState, next_state: ProgramState) -> ProgramState:
    assert next_state in _ALLOWED.get(current, set()), \
        f"Illegal transition {current} → {next_state}"
    return next_state


if __name__ == "__main__":
    s = ProgramState.REQUIREMENTS
    s = transition(s, ProgramState.DESIGN)
    s = transition(s, ProgramState.ENGINEERING)
    s = transition(s, ProgramState.VALIDATION)
    s = transition(s, ProgramState.GATE_REVIEW)
    s = transition(s, ProgramState.RELEASED)
    assert s == ProgramState.RELEASED
    try:
        transition(ProgramState.REQUIREMENTS, ProgramState.ENGINEERING)
        assert False, "should have raised"
    except AssertionError as e:
        assert "Illegal" in str(e)
    try:
        transition(ProgramState.RELEASED, ProgramState.REQUIREMENTS)
        assert False, "should have raised"
    except AssertionError as e:
        assert "Illegal" in str(e)
    print("state_machine: OK")
