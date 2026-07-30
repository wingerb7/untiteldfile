from src.contracts import StageError


class ActionContinuationError(StageError):
    def __init__(self, code: str, refs: tuple[str, ...] = ()) -> None:
        super().__init__(code, "action_continuation", refs)
