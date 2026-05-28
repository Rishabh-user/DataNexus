from app.ai.prompts import QA_PROMPT_TEMPLATE, STRUCTURED_DATA_SECTION, SYSTEM_PROMPT


def build_chat_context(
    context: str,
    structured_data: str,
    chat_history: list[dict],
    question: str,
    max_context_chars: int = 30000,
) -> tuple[str, str]:
    # Truncate context if needed (generous limit — Claude handles large context well)
    if len(context) > max_context_chars:
        context = context[:max_context_chars] + "\n... [truncated]"

    # Format structured data section
    structured_section = ""
    if structured_data:
        structured_section = STRUCTURED_DATA_SECTION.format(
            structured_data=structured_data[:8000]
        )

    # History is now handled as native Claude message turns in chains.py,
    # so we only include the document context and question in the user prompt.
    user_prompt = QA_PROMPT_TEMPLATE.format(
        context=context,
        structured_data_section=structured_section,
        question=question,
    )

    return SYSTEM_PROMPT, user_prompt
