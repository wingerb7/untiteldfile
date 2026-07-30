from src.contracts import StageError


class NarrativeAdapterError(StageError):
    def __init__(self, code: str, refs: tuple[str, ...] = ()) -> None:
        super().__init__(code, "narrative_adapter", refs)
