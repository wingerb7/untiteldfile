from src.contracts import StageError


class CausalNarrativeError(StageError):
    def __init__(self, code: str):
        super().__init__(code, "causal_narrative_selection")
