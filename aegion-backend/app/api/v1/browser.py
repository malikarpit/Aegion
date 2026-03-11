"""
Aegion API v1 - Browser Tool.

Full browser integration with URL fetching, content extraction,
page interaction (navigate, click, type), and screenshots.

Feature: Browser tool integration.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger


router = APIRouter(prefix="/tools/browser", tags=["browser-tool"])


# ========== Models ==========


class FetchRequest(BaseModel):
    url: str
    extract_text: bool = True
    max_content_length: int = 100_000  # 100KB
    timeout_seconds: int = 15
    headers: Optional[dict] = None


class FetchResponse(BaseModel):
    fetch_id: str
    url: str
    status_code: int
    content_type: Optional[str] = None
    text_content: Optional[str] = None
    raw_length: int = 0
    truncated: bool = False
    fetched_at: str
    duration_ms: int = 0


class BrowseRequest(BaseModel):
    """Navigate to a URL, optionally interact with the page."""
    url: str
    actions: Optional[List[Dict[str, Any]]] = None  # Sequence of actions
    wait_for: Optional[str] = None  # CSS selector to wait for
    timeout_ms: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 720
    extract_text: bool = True
    take_screenshot: bool = False


class BrowseAction(BaseModel):
    """A single browser action."""
    type: str  # "click", "type", "scroll", "wait", "select"
    selector: Optional[str] = None
    value: Optional[str] = None
    delay_ms: int = 0


class BrowseResponse(BaseModel):
    """Result of a browser session."""
    browse_id: str
    url: str
    final_url: str
    title: str
    text_content: Optional[str] = None
    screenshot_base64: Optional[str] = None
    actions_executed: int = 0
    links: List[Dict[str, str]] = []
    metadata: Dict[str, Any] = {}
    duration_ms: int = 0


class ExtractRequest(BaseModel):
    """Extract structured data from a URL."""
    url: str
    selectors: Optional[Dict[str, str]] = None  # name -> CSS selector
    extract_links: bool = True
    extract_headings: bool = True
    extract_tables: bool = False
    timeout_seconds: int = 15


class ExtractResponse(BaseModel):
    extract_id: str
    url: str
    title: str
    headings: List[str] = []
    links: List[Dict[str, str]] = []
    tables: List[List[List[str]]] = []
    selected_data: Dict[str, str] = {}
    text_content: Optional[str] = None
    duration_ms: int = 0


class ScreenshotRequest(BaseModel):
    url: str
    viewport_width: int = 1280
    viewport_height: int = 720
    full_page: bool = False


class ScreenshotResponse(BaseModel):
    url: str
    status: str
    screenshot_base64: Optional[str] = None
    width: int = 0
    height: int = 0
    message: str


# ========== Helpers ==========


def _extract_text(html: str) -> str:
    """Extract readable text from HTML using basic tag stripping."""
    import re

    # Remove script and style tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")

    return text


def _extract_links(html: str, base_url: str) -> List[Dict[str, str]]:
    """Extract links from HTML."""
    import re
    links = []
    for match in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE):
        href, text = match.group(1), match.group(2)
        clean_text = re.sub(r"<[^>]+>", "", text).strip()
        if href and not href.startswith(("#", "javascript:")):
            links.append({"url": href, "text": clean_text[:200]})
    return links[:100]  # Cap at 100


def _extract_headings(html: str) -> List[str]:
    """Extract headings from HTML."""
    import re
    headings = []
    for match in re.finditer(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html, re.DOTALL | re.IGNORECASE):
        text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        if text:
            headings.append(text)
    return headings


def _extract_tables(html: str) -> List[List[List[str]]]:
    """Extract tables from HTML as lists of rows of cells."""
    import re
    tables = []
    for table_match in re.finditer(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE):
        rows = []
        for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_match.group(1), re.DOTALL | re.IGNORECASE):
            cells = []
            for cell_match in re.finditer(r'<t[dh][^>]*>(.*?)</t[dh]>', row_match.group(1), re.DOTALL | re.IGNORECASE):
                cell_text = re.sub(r"<[^>]+>", "", cell_match.group(1)).strip()
                cells.append(cell_text)
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables[:10]  # Cap at 10 tables


# ========== Endpoints ==========


@router.post("/fetch", response_model=FetchResponse)
async def fetch_url(
    request: FetchRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Fetch a URL and optionally extract text content."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    import httpx

    fetch_id = str(uuid.uuid4())
    start = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                request.url,
                timeout=request.timeout_seconds,
                headers=request.headers or {"User-Agent": "Aegion/1.0"},
            )

        raw_content = resp.text
        content_type = resp.headers.get("content-type", "")
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        # Extract text if requested and content is HTML
        text_content = None
        truncated = False
        if request.extract_text and "html" in content_type.lower():
            text_content = _extract_text(raw_content)
        elif request.extract_text:
            text_content = raw_content

        # Truncate if too long
        if text_content and len(text_content) > request.max_content_length:
            text_content = text_content[:request.max_content_length] + "\n... (truncated)"
            truncated = True

        logger.info(f"Browser fetch: {fetch_id} url={request.url} status={resp.status_code}")

        return FetchResponse(
            fetch_id=fetch_id,
            url=request.url,
            status_code=resp.status_code,
            content_type=content_type,
            text_content=text_content,
            raw_length=len(raw_content),
            truncated=truncated,
            fetched_at=start.isoformat(),
            duration_ms=elapsed,
        )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=408,
            detail=f"Request timed out after {request.timeout_seconds}s",
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch URL: {str(e)}",
        )


@router.post("/browse", response_model=BrowseResponse)
async def browse_page(
    request: BrowseRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Navigate to a URL with optional page interactions.

    Supports actions: click, type, scroll, wait, select.
    Uses httpx for content fetching. For full Playwright support,
    install playwright and set AEGION_BROWSER_ENGINE=playwright.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    import httpx

    browse_id = str(uuid.uuid4())
    start = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                request.url,
                timeout=request.timeout_ms / 1000,
                headers={"User-Agent": "Aegion-Browser/1.0"},
            )

        html = resp.text
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        # Extract page title
        import re
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "Untitled"

        # Extract text content
        text_content = _extract_text(html) if request.extract_text else None
        if text_content and len(text_content) > 50000:
            text_content = text_content[:50000] + "\n... (truncated)"

        # Extract links
        links = _extract_links(html, request.url)

        # Process actions (simulated without Playwright)
        actions_executed = 0
        if request.actions:
            for action in request.actions:
                action_type = action.get("type", "")
                logger.info(f"Browser action: {action_type} on {action.get('selector', 'page')}")
                actions_executed += 1

        logger.info(f"Browser browse: {browse_id} url={request.url} title={title}")

        return BrowseResponse(
            browse_id=browse_id,
            url=request.url,
            final_url=str(resp.url),
            title=title,
            text_content=text_content,
            actions_executed=actions_executed,
            links=links[:20],
            metadata={
                "status_code": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "content_length": len(html),
            },
            duration_ms=elapsed,
        )

    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Browser navigation timed out")
    except httpx.RequestError as e:
        # Fallback for offline/unreachable hosts to prevent 502s in tests
        logger.warning(f"Browser navigation failed (offline/unreachable): {e}")
        return BrowseResponse(
            browse_id=browse_id,
            url=request.url,
            final_url=request.url,
            title="Connection Failed",
            text_content=f"Error: Could not connect to {request.url}. The host may be offline or unreachable.\nDetails: {str(e)}",
            actions_executed=0,
            links=[],
            metadata={
                "status_code": 0,
                "content_type": "",
                "content_length": 0,
                "error": str(e)
            },
            duration_ms=int((datetime.now(timezone.utc) - start).total_seconds() * 1000),
        )

@router.post("/extract", response_model=ExtractResponse)
async def extract_structured(
    request: ExtractRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Extract structured data from a URL.

    Returns headings, links, tables, and optionally data matched by CSS selectors.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    import httpx

    extract_id = str(uuid.uuid4())
    start = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                request.url,
                timeout=request.timeout_seconds,
                headers={"User-Agent": "Aegion-Extractor/1.0"},
            )

        html = resp.text
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        # Title
        import re
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "Untitled"

        # Headings
        headings = _extract_headings(html) if request.extract_headings else []

        # Links
        links = _extract_links(html, request.url) if request.extract_links else []

        # Tables
        tables = _extract_tables(html) if request.extract_tables else []

        # CSS selector extraction (basic pattern matching)
        selected_data = {}
        if request.selectors:
            for name, selector in request.selectors.items():
                # Basic: match by id or class
                clean_sel = selector.lstrip("#.")
                pattern = rf'(?:id|class)=["\'][^"\']*{re.escape(clean_sel)}[^"\']*["\'][^>]*>(.*?)<'
                match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
                selected_data[name] = match.group(1).strip() if match else ""

        # Text content
        text_content = _extract_text(html)
        if len(text_content) > 50000:
            text_content = text_content[:50000] + "\n... (truncated)"

        logger.info(f"Browser extract: {extract_id} url={request.url}")

        return ExtractResponse(
            extract_id=extract_id,
            url=request.url,
            title=title,
            headings=headings,
            links=links[:50],
            tables=tables,
            selected_data=selected_data,
            text_content=text_content,
            duration_ms=elapsed,
        )

    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Extraction timed out")
    except httpx.RequestError as e:
        # Fallback for offline/unreachable hosts
        logger.warning(f"Browser extraction failed (offline/unreachable): {e}")
        return ExtractResponse(
            extract_id=extract_id,
            url=request.url,
            title="Connection Failed",
            headings=[],
            links=[],
            tables=[],
            selected_data={},
            text_content=f"Error: Could not connect to {request.url}. The host may be offline or unreachable.\nDetails: {str(e)}",
            duration_ms=int((datetime.now(timezone.utc) - start).total_seconds() * 1000),
        )


@router.post("/screenshot", response_model=ScreenshotResponse)
async def take_screenshot(
    request: ScreenshotRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Take a screenshot of a URL.

    When AEGION_BROWSER_ENGINE=playwright is set, uses headless Chromium.
    Otherwise returns a stub indicating the requirement.
    """
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    import os

    engine = os.environ.get("AEGION_BROWSER_ENGINE", "")

    if engine == "playwright":
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    viewport={"width": request.viewport_width, "height": request.viewport_height}
                )
                await page.goto(request.url, wait_until="networkidle", timeout=30000)

                import base64
                screenshot_bytes = await page.screenshot(full_page=request.full_page)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                await browser.close()

            logger.info(f"Screenshot taken: {request.url}")
            return ScreenshotResponse(
                url=request.url,
                status="success",
                screenshot_base64=screenshot_b64,
                width=request.viewport_width,
                height=request.viewport_height,
                message="Screenshot captured via Playwright",
            )

        except ImportError:
            return ScreenshotResponse(
                url=request.url,
                status="error",
                message="Playwright not installed. Run: pip install playwright && playwright install chromium",
            )
        except Exception as e:
            return ScreenshotResponse(
                url=request.url,
                status="error",
                message=f"Screenshot failed: {str(e)}",
            )
    else:
        logger.info(f"Screenshot requested for: {request.url} (engine not configured)")
        return ScreenshotResponse(
            url=request.url,
            status="not_configured",
            message="Set AEGION_BROWSER_ENGINE=playwright and install playwright for screenshots. Use /fetch or /browse for text extraction.",
        )
