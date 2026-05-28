SYSTEM_PROMPT = """You are DataNexus AI, an intelligent assistant that helps users query and analyze their uploaded documents.

You have access to:
1. Extracted document content (from PDFs, Excel, Word, etc.)
2. Structured data (tables, key-value pairs)
3. The user's conversation history (provided as prior messages in this conversation)

Guidelines:
- Answer based ONLY on the provided document context. Do not make up information.
- If you cannot find the answer in the context, say so clearly and suggest what the user could try instead.
- When referencing specific data, cite the source document name and page number.
- For numerical queries, show your calculations step by step.
- Format tables in markdown when presenting tabular data.
- Use bullet points and headings for readability when the answer is long.
- Be concise but thorough. Provide complete answers without unnecessary padding.
- If the user asks a follow-up question, use the conversation history to understand what they are referring to."""

QA_PROMPT_TEMPLATE = """Here is the relevant context retrieved from the user's uploaded documents:

---
{context}
---

{structured_data_section}

User question: {question}

Provide a helpful, accurate answer based on the document context above. Cite source documents when possible. If the context doesn't contain enough information to fully answer, say so clearly."""

STRUCTURED_DATA_SECTION = """Structured data (tables/key-value pairs) from documents:
---
{structured_data}
---
"""

REPORT_PROMPT_TEMPLATE = """Based on the following data and analysis, create a structured report outline for a PowerPoint presentation.

Topic: {topic}

Available data:
{data}

IMPORTANT: Return ONLY a valid JSON object. No markdown fences, no extra text. Just the JSON.

The JSON must follow this exact structure:
{{
    "title": "Presentation Title",
    "slides": [
        {{
            "title": "Slide Title",
            "type": "title",
            "bullet_points": ["Subtitle text"]
        }},
        {{
            "title": "Slide Title",
            "type": "content",
            "bullet_points": ["point 1", "point 2", "point 3"],
            "notes": "Speaker notes"
        }},
        {{
            "title": "Chart Title",
            "type": "chart",
            "chart_data": {{"type": "bar", "labels": ["A", "B", "C"], "values": [10, 20, 30]}},
            "notes": "Speaker notes"
        }},
        {{
            "title": "Table Title",
            "type": "table",
            "table_data": {{"headers": ["Col1", "Col2"], "rows": [["val1", "val2"]]}},
            "notes": "Speaker notes"
        }},
        {{
            "title": "Summary & Key Takeaways",
            "type": "summary",
            "bullet_points": ["takeaway 1", "takeaway 2"]
        }}
    ]
}}

Rules:
- Create 5-10 slides. Always start with a "title" slide and end with a "summary" slide.
- Use "content" type for text slides with bullet_points (3-6 points per slide).
- Use "chart" type when data has numeric values that can be visualized. Chart values MUST be numbers, not strings.
- Use "table" type when data has structured rows and columns.
- Keep bullet points concise (under 15 words each).
- Ensure chart labels and values arrays are the same length.
- All values in chart_data.values must be numbers (integers or floats), never strings."""

TITLE_GENERATION_PROMPT = """Based on this user message, generate a short (5-8 word) title for this chat session:

Message: {message}

Return only the title, nothing else."""
