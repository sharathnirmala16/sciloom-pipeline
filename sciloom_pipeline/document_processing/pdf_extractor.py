from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import TYPE_CHECKING, Any

import PIL.Image
import pdf2image
from google import genai
from google.genai import types

if TYPE_CHECKING:
    pass

SYSTEM_PROMPT = """
You are an advanced, multimodal academic document parser. Your task is to perform high-fidelity OCR and structural de-rendering on the provided research paper pages. Convert the visual input into clean, highly structured GitHub-Flavored Markdown. Do not summarize, skip, or paraphrase any text. Transcribe the contents exactly while applying the strict structural rules below.

### 1. Document Structure & Text
- Maintain the exact hierarchical structure of the paper using markdown headers (`#`, `##`, `###`).
- Preserve bulleted and numbered lists exactly as they appear in the layout.
- Format standard text tables using standard Markdown table notation.

### 2. Mathematical Equations
- Convert all mathematical notations, variables, and equations into precise LaTeX format.
- Use single dollar signs ($) for inline math (e.g., $E = mc^2$).
- Use double dollar signs ($$) on separate lines for standalone block equations. 
- Ensure all Greek letters, symbols, sub/superscripts, and matrices are perfectly formatted in LaTeX.

### 3. Visual Elements (Graphs, Charts, Diagrams)
When you encounter a visual chart, graph, or diagram, do not skip it or simply copy the caption. You must de-render the image into a structured text block directly within the markdown flow where the figure is positioned. Use this exact template:

#### [Visual Element: Figure X]
**Caption:** [Exact transcription of the figure caption]
**Reconstructed Data Table:**
[If the graph displays plot points, bars, or lines with readable axes, reconstruct the visual data points into a valid Markdown Table. If the visual element is a flowchart or diagram where a table does not apply, write "N/A - Structural Diagram".]
**Visual Description:** [Provide a granular analysis of the graphic. Specify the type of graph (e.g., dual-axis line graph, stacked bar chart), label the X and Y axes with their units, describe the core trends, highlight any explicit data markers, anomalies, or shaded error bands, and explain the visual relationship between data series.]

---
## Examples of Expected Output

### Example 1: Text & Equation Conversion
#### 3.2 Theoretical Framework
The relationship between mass-energy equivalence and velocity in a relativistic framework is defined by the Lorentz factor. When the system transitions to a non-zero momentum state, the energy equation scales dynamically.

The total relativistic energy of the particle is expressed as:
$$E^2 = (pc)^2 + (m_0c^2)^2$$

Where $p$ represents the relativistic momentum vector and $m_0$ denotes the invariant rest mass.

### Example 2: Graph De-rendering Conversion
#### 5.1 Empirical Performance Results
The scalability of our distributed clustering algorithm was evaluated against baseline frameworks across varying cluster sizes.

#### [Visual Element: Figure 4]
**Caption:** Figure 4: Runtime latency (ms) vs. Node Count for Batch Processing workloads.
**Reconstructed Data Table:**
| Node Count | Baseline Framework (ms) | Our Algorithm (ms) |
| :--- | :--- | :--- |
| 16 | 1250 | 800 |
| 32 | 2400 | 950 |
| 64 | 4800 | 1100 |
| 128 | 9600 | 1350 |
**Visual Description:** A log-linear line graph comparing processing latency. The X-axis represents the Node Count on a logarithmic scale (16 to 128 nodes). The Y-axis measures Runtime Latency in milliseconds on a linear scale (0 to 10,000 ms). The 'Baseline Framework' is represented by a red dashed line showing a strict linear explosion in latency, scaling from 1250ms up to 9600ms. 'Our Algorithm' is shown as a solid blue line with circular data markers, demonstrating sub-linear scaling that flattens significantly after 64 nodes, topping out at only 1350ms at 128 nodes. There is a gray shaded area representing the 95% confidence interval around our algorithm's line, showing very low variance.

As demonstrated in Figure 4, our architecture introduces O(log N) complexity overhead...
"""

# Model used for all OCR chat sessions.
_OCR_MODEL = "gemini-3-flash-preview"

# DPI used when rasterising PDF pages.  300 is a good balance of quality vs. size.
_RASTER_DPI = 300

# Maximum number of retry attempts per page on transient failures.
_MAX_RETRIES = 3


def _page_to_bytes(page_image: PIL.Image.Image, fmt: str = "PNG") -> bytes:
    """Encode a PIL image to raw bytes."""
    buf = io.BytesIO()
    page_image.save(buf, format=fmt)
    return buf.getvalue()


class PDFExtractor:
    """PDF OCR extractor backed by the Gemini multimodal API.

    The SDK's own async context managers handle all resource lifecycles:
    - ``async with genai.Client(...)`` manages the shared HTTP connection pool
        for the duration of a single :meth:`extract` call.
    - ``async with client.aio.chats.create(...)`` manages each per-page chat
        session, ensuring clean teardown after every page response.

    Usage::

        extractor = PDFExtractor(api_key)
        md_path = await extractor.extract("paper.pdf", output_dir="outputs/")
    """

    def __init__(self, gemini_api_key: str, model: str = _OCR_MODEL) -> None:
        self.__gemini_api_key = gemini_api_key
        self.model = model
        self.system_prompt = SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract(
        self,
        pdf_path: str | Path,
        output_dir: str | Path | None = None,
        dpi: int = _RASTER_DPI,
    ) -> Path:
        """Convert a PDF to a single Markdown file via parallel per-page OCR.

        Args:
            pdf_path:   Path to the source PDF.
            output_dir: Directory where the ``.md`` file will be written.
                        Defaults to the same directory as the PDF.
            dpi:        Resolution used when rasterising pages.

        Returns:
            Path to the generated Markdown file.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.is_file():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # ── 1. Rasterise every page ────────────────────────────────────
        print(f"[PDFExtractor] Rasterising '{pdf_path.name}' at {dpi} DPI …")
        page_images: list[PIL.Image.Image] = pdf2image.convert_from_path(
            str(pdf_path), dpi=dpi
        )
        n_pages = len(page_images)
        print(f"[PDFExtractor] {n_pages} page(s) found — launching parallel OCR …")

        # ── 2. OCR all pages in parallel ──────────────────────────────
        async with genai.Client(api_key=self.__gemini_api_key).aio as client:
            tasks = [
                self._ocr_page(client, page_index=i, image=img)
                for i, img in enumerate(page_images)
            ]
            page_texts: list[str] = await asyncio.gather(*tasks)

        # ── 3. Merge into one ordered Markdown document ───────────────
        markdown = self._merge(pdf_path.stem, page_texts)

        # ── 4. Write output ───────────────────────────────────────────
        out_dir = Path(output_dir) if output_dir else pdf_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "RESEARCH_PAPER.md"
        out_path.write_text(markdown, encoding="utf-8")

        print(f"[PDFExtractor] ✓ Markdown written to '{out_path}'")
        return out_path

    async def _ocr_page(
        self,
        client: Any,  # AsyncClient returned by `async with genai.Client(...).aio`
        page_index: int,
        image: PIL.Image.Image,
    ) -> str:
        """Send a single page image to its own Gemini chat session and return
        the extracted Markdown text.

        On transient failures each attempt opens a fresh ``client.chats.create(...)``
        session, so a broken chat object can never bleed into the next try.
        After ``_MAX_RETRIES`` failed attempts the last exception is re-raised.
        """
        image_bytes = await asyncio.to_thread(_page_to_bytes, image)

        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        # chat.send_message() accepts parts directly — NOT a types.Content wrapper.
        message_parts = [
            image_part,
            types.Part.from_text(
                text=(
                    f"This is page {page_index + 1} of the document. "
                    "Apply the system instructions and return only the "
                    "structured Markdown for this page. "
                    "Do not add any preamble or closing remarks."
                )
            ),
        ]

        last_exc: Exception
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                # `AsyncClient.chats.create()` returns an AsyncChat — not
                # a context manager, so a plain assignment is correct here.
                chat = client.chats.create(
                    model=self.model,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.1,
                    ),
                )
                response = await chat.send_message(message_parts)
                text: str = response.text or ""

                print(
                    f"[PDFExtractor] ✓ Page {page_index + 1} OCR complete"
                    f" ({len(text)} chars)"
                )
                return text

            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    wait = 2**attempt  # 2 s, 4 s, 8 s
                    print(
                        f"[PDFExtractor] ✗ Page {page_index + 1} attempt"
                        f" {attempt}/{_MAX_RETRIES} failed: {exc!r}"
                        f" — retrying in {wait}s …"
                    )
                    await asyncio.sleep(wait)
                else:
                    print(
                        f"[PDFExtractor] ✗ Page {page_index + 1} failed after"
                        f" {_MAX_RETRIES} attempts: {exc!r}"
                    )

        raise last_exc

    @staticmethod
    def _merge(document_title: str, page_texts: list[str]) -> str:
        """Join per-page Markdown blocks into a single coherent document."""
        separator = "\n\n---\n\n"  # horizontal rule between pages
        body = separator.join(page_texts)
        return body
