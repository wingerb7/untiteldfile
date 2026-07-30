from src.contracts import StageError

class RecognitionError(StageError):
    def __init__(self, code: str, refs: tuple[str, ...] = ()) -> None:
        super().__init__(code, "recognition", refs)
