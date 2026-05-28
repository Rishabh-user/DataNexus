import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import generate_chat_response
from app.ai.prompts import REPORT_PROMPT_TEMPLATE
from app.ai.retriever import retrieve_context
from app.core.config import settings
from app.core.logging import get_logger
from app.models.report import Report

logger = get_logger(__name__)


def _extract_json(text: str) -> dict:
    """Robustly extract JSON object from LLM response text."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not extract valid JSON from LLM response: {text[:200]}")


async def generate_report(
    db: AsyncSession,
    user_id: int,
    title: str,
    prompt: str,
    include_charts: bool = True,
) -> Report:
    report = Report(
        user_id=user_id,
        title=title,
        prompt_used=prompt,
        generation_status="generating",
    )
    db.add(report)
    await db.flush()

    try:
        # 1. Retrieve relevant data
        retrieval = await retrieve_context(db=db, query=prompt, user_id=user_id, top_k=10)

        data_context = retrieval["context"]
        if retrieval["structured_data"]:
            data_context += "\n\nStructured Data:\n" + retrieval["structured_data"]

        # 2. Generate slide structure via LLM
        llm_prompt = REPORT_PROMPT_TEMPLATE.format(topic=title, data=data_context[:15000])
        response = await generate_chat_response(
            system_prompt="You are a presentation slide generator. You MUST return ONLY a valid JSON object with a 'title' string and a 'slides' array. No markdown, no explanation, no code fences — just raw JSON.",
            user_prompt=llm_prompt,
        )

        # 3. Parse slide structure (robust extraction)
        slide_data = _extract_json(response)

        # 4. Generate PPT
        from app.ppt.generator import generate_ppt

        output_path = settings.reports_path / f"report_{report.id}.pptx"
        generate_ppt(slide_data, str(output_path), include_charts=include_charts)

        report.file_path = str(output_path)
        report.generation_status = "completed"
        await db.flush()

        logger.info("Report generated: %s (id=%d)", title, report.id)

    except Exception as e:
        report.generation_status = "failed"
        report.error_message = str(e)
        await db.flush()
        logger.error("Report generation failed: %s", str(e))
        raise

    return report
