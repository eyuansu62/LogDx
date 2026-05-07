"""
Token counting. Uses tiktoken (cl100k_base) if available, else char-based approximation.

The approximation is calibrated against cl100k_base on English+code corpora:
- Natural English: ~4.0 chars/token
- Code + CI logs:  ~3.3 chars/token (lots of punctuation, short tokens)
We use 3.5 as a middle ground.
"""

CHARS_PER_TOKEN_APPROX = 3.5

_encoder = None
_tried_load = False


def _get_encoder():
    global _encoder, _tried_load
    if _tried_load:
        return _encoder
    _tried_load = True
    try:
        import tiktoken
        _encoder = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _encoder = None
    return _encoder


def count_tokens(text: str) -> int:
    enc = _get_encoder()
    if enc is not None:
        return len(enc.encode(text, disallowed_special=()))
    # Fallback: char-based approximation
    return max(1, int(len(text) / CHARS_PER_TOKEN_APPROX))


def tokenizer_name() -> str:
    enc = _get_encoder()
    return "cl100k_base (tiktoken)" if enc is not None else f"chars/{CHARS_PER_TOKEN_APPROX} (approx)"
