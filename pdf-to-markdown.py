"""
PDF to Markdown converter using local GLM OCR via LM Studio.

Renders each PDF page as an image using pdf2image, converts it to base64, and
sends it concurrently to the local LM Studio server using asyncio and httpx.

Usage:
    python pdf-to-markdown.py <input.pdf> [output.md] [options]
"""

import os
import sys
import asyncio
import base64
import io
import argparse
import httpx
from pdf2image import convert_from_path


def image_to_base64(image) -> str:
    """Convert a PIL Image to a base64 encoded PNG string."""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


async def get_loaded_model(client: httpx.AsyncClient) -> str:
    """Retrieve the name of the loaded model from LM Studio."""
    try:
        response = await client.get("/models")
        response.raise_for_status()
        models = response.json().get("data", [])
        if models:
            return models[0]["id"]
    except Exception as e:
        print(
            f"Warning: Failed to fetch loaded model from LM Studio: {e}",
            file=sys.stderr,
            flush=True,
        )
    return "glm-ocr"  # Default fallback


async def ocr_page(
    client: httpx.AsyncClient,
    image_base64: str,
    page_num: int,
    model_name: str,
    semaphore: asyncio.Semaphore,
    timeout: float,
) -> str:
    """Send a single page image to LM Studio chat completions API for OCR and Markdown conversion."""
    prompt = (
        "Convert this page image to Markdown format. Output ONLY the raw Markdown. "
        "Do not wrap the output in markdown code blocks (e.g. ```markdown ... ```), "
        "do not include any introductory or concluding text, and do not add any comments. "
        "Retain all layout, headings, paragraphs, lists, and mathematical formulas (using LaTeX notation if possible)."
    )

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    },
                ],
            }
        ],
        "temperature": 0.0,
    }

    async with semaphore:
        for attempt in range(1, 4):  # Retry up to 3 times
            try:
                print(
                    f"Processing Page {page_num} (Attempt {attempt})...",
                    file=sys.stderr,
                    flush=True,
                )
                response = await client.post(
                    "/chat/completions",
                    json=payload,
                    timeout=httpx.Timeout(timeout),
                )
                response.raise_for_status()
                data = response.json()
                markdown_text = data["choices"][0]["message"]["content"]

                # Clean up wrapping code blocks if the model ignored prompt instructions
                markdown_text = markdown_text.strip()
                if markdown_text.startswith("```markdown"):
                    markdown_text = markdown_text[len("```markdown") :].strip()
                elif markdown_text.startswith("```"):
                    markdown_text = markdown_text[3:].strip()
                if markdown_text.endswith("```"):
                    markdown_text = markdown_text[:-3].strip()

                return markdown_text
            except httpx.HTTPStatusError as e:
                print(
                    f"HTTP Error on Page {page_num} (Attempt {attempt}): {e.response.status_code} - {e.response.text}",
                    file=sys.stderr,
                    flush=True,
                )
                if attempt == 3:
                    raise
                await asyncio.sleep(2**attempt)
            except Exception as e:
                print(
                    f"Error on Page {page_num} (Attempt {attempt}): {e}",
                    file=sys.stderr,
                    flush=True,
                )
                if attempt == 3:
                    raise
                await asyncio.sleep(2**attempt)
    return ""


async def convert_pdf(
    pdf_path: str,
    base_url: str,
    model_name: str | None,
    concurrency: int,
    timeout: float,
    dpi: int,
) -> str:
    """Convert a PDF to markdown by rendering pages and sending them to LM Studio."""
    print(f"Converting PDF {pdf_path} to images...", file=sys.stderr, flush=True)
    try:
        images = convert_from_path(pdf_path, dpi=dpi)
    except Exception as e:
        print(f"Error converting PDF to images: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

    total_pages = len(images)
    print(
        f"Successfully rendered {total_pages} page images.",
        file=sys.stderr,
        flush=True,
    )

    async with httpx.AsyncClient(base_url=base_url) as client:
        if not model_name:
            model_name = await get_loaded_model(client)
            print(
                f"Auto-detected loaded model: {model_name}",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                f"Using configured model: {model_name}",
                file=sys.stderr,
                flush=True,
            )

        semaphore = asyncio.Semaphore(concurrency)

        tasks = []
        for i, img in enumerate(images, 1):
            img_b64 = image_to_base64(img)
            tasks.append(ocr_page(client, img_b64, i, model_name, semaphore, timeout))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        pages_md = []
        for i, res in enumerate(results, 1):
            if isinstance(res, Exception):
                print(
                    f"Failed to convert page {i}: {res}",
                    file=sys.stderr,
                    flush=True,
                )
                pages_md.append(f"\n\n<!-- Error rendering page {i}: {res} -->\n\n")
            else:
                pages_md.append(res)

        return "\n\n".join(pages_md)


def main():
    parser = argparse.ArgumentParser(
        description="PDF to Markdown converter using local GLM OCR via LM Studio."
    )
    parser.add_argument("input_pdf", help="Path to the input PDF file.")
    parser.add_argument("output_md", nargs="?", help="Path to the output Markdown file (optional).")
    parser.add_argument(
        "--base-url", "-b",
        default=os.environ.get("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
        help="Base URL of the LM Studio server (default: http://localhost:1234/v1)."
    )
    parser.add_argument(
        "--model", "-m",
        default=os.environ.get("LM_STUDIO_MODEL"),
        help="Model name to use (default: auto-detected from active loaded models)."
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=int(os.environ.get("LM_STUDIO_CONCURRENCY", "1")),
        help="Number of concurrent page requests (default: 1 to prevent server overload)."
    )
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=float(os.environ.get("LM_STUDIO_TIMEOUT", "300.0")),
        help="Timeout for requests in seconds (default: 300.0)."
    )
    parser.add_argument(
        "--dpi", "-d",
        type=int,
        default=int(os.environ.get("LM_STUDIO_DPI", "300")),
        help="DPI for rendering PDF pages (default: 300)."
    )

    args = parser.parse_args()

    pdf_path = args.input_pdf
    if not os.path.isfile(pdf_path):
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output_md

    try:
        markdown = asyncio.run(
            convert_pdf(
                pdf_path=pdf_path,
                base_url=args.base_url,
                model_name=args.model,
                concurrency=args.concurrency,
                timeout=args.timeout,
                dpi=args.dpi,
            )
        )
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        sys.exit(1)

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown)
            print(f"Written output to {output_path}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"Failed to write output to {output_path}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(markdown)


if __name__ == "__main__":
    main()
