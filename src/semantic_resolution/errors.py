from src.contracts import StageError


class SemanticResolutionError(StageError):
    def __init__(self, code: str, refs: tuple[str, ...] = ()) -> None:
        super().__init__(code, "semantic_resolution", refs)
