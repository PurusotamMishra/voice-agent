"""Number formatting for speech (F4). The only place display strings for numbers are made."""


def group_indian(n: int) -> str:
    """1,25,000-style grouping."""
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join([*parts, tail])


def format_price(amount: int) -> str:
    # Listing prices are multiples of 5,000, so two decimals of a lakh are exact.
    if amount >= 100_000 and amount % 1_000 == 0:
        lakhs = f"{amount / 100_000:.2f}".rstrip("0").rstrip(".")
        return f"₹{lakhs} lakh"
    return f"₹{group_indian(amount)}"


def format_km(km: int) -> str:
    return f"{group_indian(km)} km"


def format_kg(kg: int) -> str:
    return f"{group_indian(kg)} kg"
