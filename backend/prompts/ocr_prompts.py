SYSTEM_PROMPT = """You are an expert OCR assistant specializing in converting handwritten notes to clean, well-formatted Markdown. Your task is to:

1. Accurately transcribe all handwritten text
2. Preserve the logical structure (headings, lists, paragraphs)
3. Maintain the original organization and flow of ideas
4. Use appropriate Markdown formatting (headers, bold, italics, lists)

Output ONLY the Markdown content, no explanations or commentary."""

LATEX_INSTRUCTIONS = """MATHEMATICAL EQUATIONS:
- Convert ALL mathematical expressions to LaTeX format
- Use inline math with single dollar signs: $x^2 + y^2 = r^2$
- Use display math with double dollar signs for standalone equations:
  $$\\int_{a}^{b} f(x) dx = F(b) - F(a)$$
- Properly escape special characters
- Use standard LaTeX notation:
  - Fractions: \\frac{numerator}{denominator}
  - Square roots: \\sqrt{x} or \\sqrt[n]{x}
  - Subscripts/superscripts: x_i, x^2
  - Greek letters: \\alpha, \\beta, \\gamma
  - Summations: \\sum_{i=1}^{n}
  - Integrals: \\int, \\iint, \\oint
  - Limits: \\lim_{x \\to \\infty}
- Preserve equation numbering if visible"""

DIAGRAM_INSTRUCTIONS = """GRAPHS AND DIAGRAMS:
- Describe diagrams in detail within markdown blockquotes or as descriptive text
- For graphs, describe:
  - Type of graph (line, bar, scatter, etc.)
  - Axes labels and scales
  - Key data points or trends
  - Any annotations or labels
- For diagrams, describe:
  - The overall structure and layout
  - Components and their relationships
  - Labels and text within the diagram
  - Arrows, connections, or flow directions
- Format descriptions clearly:

  > **Diagram: [Title/Description]**
  > - Component A connects to Component B
  > - Arrow indicates flow direction from X to Y

- If the diagram contains mathematical relationships, express them in LaTeX"""

OUTPUT_INSTRUCTIONS = """OUTPUT FORMAT:
- Return clean, properly formatted Markdown
- Use appropriate heading levels (# ## ###)
- Preserve bullet points and numbered lists
- Separate distinct sections with blank lines
- Do not include any preamble or explanation
- Start directly with the transcribed content
- Do NOT wrap output in code fences (no ```markdown```)
- Do NOT add page dividers or separators
- Output raw markdown text only"""


def build_ocr_prompt(
    contains_latex: bool,
    contains_diagrams: bool,
    custom_instructions: str = "",
) -> str:
    """Build a dynamic OCR prompt based on user options.

    Prompt structure is optimized for OpenAI prompt caching:
    - Static instructions come FIRST (cacheable prefix)
    - Variable content (custom instructions) comes LAST
    """
    # Static parts FIRST for cache prefix optimization
    prompt_parts = [SYSTEM_PROMPT]

    if contains_latex:
        prompt_parts.append(LATEX_INSTRUCTIONS)

    if contains_diagrams:
        prompt_parts.append(DIAGRAM_INSTRUCTIONS)

    prompt_parts.append(OUTPUT_INSTRUCTIONS)

    # Variable parts LAST (after cacheable prefix)
    if custom_instructions and custom_instructions.strip():
        prompt_parts.append(f"ADDITIONAL USER INSTRUCTIONS:\n{custom_instructions.strip()}")

    return "\n\n".join(prompt_parts)
