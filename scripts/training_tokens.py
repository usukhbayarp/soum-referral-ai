"""Shared tokenization checks for preflight and the bounded MLX experiment."""

TEMPLATE_POLICY = "ollama-qwen3-single-turn-1"


class NonThinkingTokenizer:
    """Match the preserved Ollama template's single-turn, think:false rendering.

    Ollama inserts a second newline after the system header and appends
    ' /no_think' to the final user turn. Canonical messages remain unchanged.
    This policy is intentionally limited to this application's three roles.
    """

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def __getattr__(self, name):
        return getattr(self.tokenizer, name)

    def apply_chat_template(self, messages, **kwargs):
        roles = [message["role"] for message in messages]
        if roles not in (["system", "user"], ["system", "user", "assistant"]):
            raise ValueError(
                "Only the pinned single-turn extraction template is supported"
            )
        messages = [dict(message) for message in messages]
        messages[0]["content"] = "\n" + messages[0]["content"]
        messages[1]["content"] += " /no_think"
        kwargs["enable_thinking"] = False
        return self.tokenizer.apply_chat_template(messages, **kwargs)


def checked_tokens(record, tokenizer, max_length=None):
    from mlx_lm.tuner.datasets import ChatDataset

    messages = record["messages"]
    if [m["role"] for m in messages] != ["system", "user", "assistant"]:
        raise ValueError(
            "Expected exactly the canonical system/user/assistant exchange"
        )
    if "<think>" in messages[-1]["content"]:
        raise ValueError("Extraction targets must not contain reasoning")
    wrapped = NonThinkingTokenizer(tokenizer)
    tokens, offset = ChatDataset([record], wrapped, mask_prompt=True).process(record)
    prefix = wrapped.apply_chat_template(
        messages[:-1], add_generation_prompt=True, return_dict=False
    )
    text_prefix = wrapped.apply_chat_template(
        messages[:-1], add_generation_prompt=True, tokenize=False
    )
    if not text_prefix.endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Non-thinking generation prefix changed")
    expected_prefix = (
        "<|im_start|>system\n\n" + messages[0]["content"] + "<|im_end|>\n"
        "<|im_start|>user\n" + messages[1]["content"] + " /no_think<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )
    if text_prefix != expected_prefix:
        raise ValueError("Pinned Ollama single-turn rendering differs")
    if tokens[:offset] != prefix or len(prefix) != offset:
        raise ValueError("Training/inference token prefix mismatch")
    expected = messages[-1]["content"] + "<|im_end|>\n"
    if tokenizer.decode(tokens[offset:]) != expected:
        raise ValueError("Mask must begin at JSON and include only completion/EOS")
    if max_length is not None and len(tokens) > max_length:
        raise ValueError(
            f"Full sequence {len(tokens)} exceeds {max_length}; refusing truncation"
        )
    return tokens, offset


def completion_loss(model, batch, lengths):
    """MLX-LM 0.30.7 loss with an exclusive real-token end, excluding padding."""
    import mlx.core as mx
    import mlx.nn as nn

    targets = batch[:, 1:]
    positions = mx.arange(1, batch.shape[1])
    mask = (positions >= lengths[:, 0:1]) & (positions < lengths[:, 1:])
    count = mask.sum()
    loss = nn.losses.cross_entropy(model(batch[:, :-1]), targets)
    return (loss * mask).astype(mx.float32).sum() / count, count
