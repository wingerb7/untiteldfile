from src.contracts import StageError


class ActionGraphError(StageError):
    def __init__(self, code: str, refs: tuple[str, ...] = ()) -> None:
        super().__init__(code, "action_graph", refs)
