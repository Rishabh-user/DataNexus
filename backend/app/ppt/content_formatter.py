def format_bullet_points(text, max_points: int = 8) -> list[str]:
    if isinstance(text, list):
        return [str(p) for p in text[:max_points]]
    if not isinstance(text, str):
        return [str(text)]
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    points = []
    for line in lines:
        cleaned = line.lstrip("•-*123456789. ")
        if cleaned:
            points.append(cleaned)
    return points[:max_points]


def truncate_text(text: str, max_length: int = 200) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_table_data(data: dict) -> tuple[list[str], list[list[str]]]:
    if not isinstance(data, dict):
        return [], []

    headers = data.get("headers", [])
    rows = data.get("rows", [])

    if not isinstance(headers, list):
        headers = []
    if not isinstance(rows, list):
        rows = []

    # Ensure headers are strings
    headers = [str(h) for h in headers]

    # Truncate cell values and ensure rows are lists
    formatted_rows = []
    for row in rows[:10]:
        if isinstance(row, (list, tuple)):
            formatted_rows.append([truncate_text(str(cell), 50) for cell in row])
        elif isinstance(row, dict):
            # LLM sometimes returns rows as dicts — extract values
            formatted_rows.append([truncate_text(str(v), 50) for v in row.values()])
        else:
            formatted_rows.append([truncate_text(str(row), 50)])

    return headers, formatted_rows
