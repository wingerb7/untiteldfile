from src.contracts import StageError


class TacticalPatternError(StageError):
    def __init__(self, code: str):
        super().__init__(code, "tactical_pattern")
