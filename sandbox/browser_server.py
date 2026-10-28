"""
Server HTTP FastAPI + Playwright per l'ambiente isolato Sandbox di CoworkerOS.
Gira all'interno del container Docker e risponde su 0.0.0.0:9333.
Fornisce navigazione sicura con alberi di accessibilità a riferimenti numerici [ref].
"""

import os
import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

# Configurazione sessione singola e percorsi
DOWNLOADS_DIR = os.getenv("SANDBOX_DOWNLOADS_DIR", "/app/downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
TIMEOUT_MS = 15000  # 15 secondi per azione


class BrowserSession:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.lock = asyncio.Lock()

    async def ensure_page(self) -> Page:
        if self.page and not self.page.is_closed():
            return self.page

        if not self.playwright:
            self.playwright = await async_playwright().start()

        if not self.browser or not self.browser.is_connected():
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
            )

        if not self.context:
            self.context = await self.browser.new_context(
                accept_downloads=True,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 CoworkerOS-Sandbox/1.0"
            )

        self.page = await self.context.new_page()
        self.page.set_default_timeout(TIMEOUT_MS)
        return self.page

    async def close(self):
        async with self.lock:
            try:
                if self.page and not self.page.is_closed():
                    await self.page.close()
            except Exception:
                pass
            self.page = None

            try:
                if self.context:
                    await self.context.close()
            except Exception:
                pass
            self.context = None

            try:
                if self.browser:
                    await self.browser.close()
            except Exception:
                pass
            self.browser = None

            try:
                if self.playwright:
                    await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None


session = BrowserSession()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await session.close()


app = FastAPI(title="CoworkerOS Sandbox Browser Server", lifespan=lifespan)


class OpenRequest(BaseModel):
    url: str


class ClickRequest(BaseModel):
    ref: Any


class TypeRequest(BaseModel):
    ref: Any
    text: str


@app.post("/open")
async def open_url(req: OpenRequest):
    """Apre l'URL specificato nella sessione unica del browser (timeout 15s)."""
    async with session.lock:
        try:
            url = req.url.strip()
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url

            page = await session.ensure_page()
            await page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
            title = await page.title()
            return {
                "status": "ok",
                "url": page.url,
                "title": title,
                "message": f"Pagina caricata con successo: {title}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Errore apertura URL '{req.url}': {str(e)}"
            }


@app.get("/snapshot")
async def get_snapshot():
    """
    Restituisce l'albero di accessibilità semantico con riferimenti numerici [ref].
    Non esegue screenshot, ottimizzando tempi e consumo di token.
    """
    async with session.lock:
        try:
            page = await session.ensure_page()
            # Script di annotazione e generazione gerarchica dell'albero di accessibilità
            js_script = """
            () => {
                let refCounter = 1;
                document.querySelectorAll('[data-sandbox-ref]').forEach(el => el.removeAttribute('data-sandbox-ref'));

                const isVisible = (el) => {
                    if (!el.getBoundingClientRect) return false;
                    const r = el.getBoundingClientRect();
                    const s = window.getComputedStyle(el);
                    return s && s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0' && r.width > 0 && r.height > 0;
                };

                const interactiveSelectors = 'a[href], button, input, textarea, select, [role="button"], [role="link"], [role="textbox"], [role="checkbox"], [role="combobox"], [role="menuitem"], [role="tab"], [tabindex]:not([tabindex="-1"])';
                const interactiveElements = Array.from(document.querySelectorAll(interactiveSelectors)).filter(isVisible);

                interactiveElements.forEach(el => {
                    el.setAttribute('data-sandbox-ref', String(refCounter++));
                });

                function buildTree(node, depth = 0) {
                    if (!node) return [];
                    let lines = [];
                    const indent = '  '.repeat(depth);

                    if (node.nodeType === Node.ELEMENT_NODE) {
                        if (!isVisible(node)) return [];
                        const tag = node.tagName.toLowerCase();
                        const ref = node.getAttribute('data-sandbox-ref');
                        const role = node.getAttribute('role') || '';
                        const ariaLabel = node.getAttribute('aria-label') || '';
                        const title = node.getAttribute('title') || '';
                        const placeholder = node.getAttribute('placeholder') || '';
                        const text = (node.innerText || '').trim();

                        let descriptor = '';
                        if (tag === 'a') {
                            const name = ariaLabel || text || title || 'Link';
                            descriptor = `link "${name}" href="${node.getAttribute('href') || ''}"`;
                        } else if (tag === 'button' || role === 'button') {
                            const name = ariaLabel || text || title || node.value || 'Pulsante';
                            descriptor = `button "${name}"`;
                        } else if (tag === 'input') {
                            const type = node.getAttribute('type') || 'text';
                            const name = ariaLabel || placeholder || title || '';
                            descriptor = `input[${type}] "${name}" value="${node.value || ''}"`;
                        } else if (tag === 'textarea') {
                            const name = ariaLabel || placeholder || title || '';
                            descriptor = `textarea "${name}" value="${node.value || ''}"`;
                        } else if (tag === 'select') {
                            descriptor = `select "${ariaLabel || title || ''}"`;
                        } else if (['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag)) {
                            descriptor = `heading[${tag}] "${text}"`;
                        } else if (role) {
                            descriptor = `[${role}] "${ariaLabel || text || title}"`;
                        }

                        if (descriptor) {
                            const prefix = ref ? `[${ref}] ` : '';
                            lines.push(`${indent}${prefix}${descriptor}`);
                        }

                        if (['button', 'select', 'textarea', 'input'].includes(tag) || (tag === 'a' && !node.querySelector('button, input'))) {
                            return lines;
                        }

                        for (const child of node.childNodes) {
                            lines = lines.concat(buildTree(child, depth + 1));
                        }
                    } else if (node.nodeType === Node.TEXT_NODE) {
                        const txt = node.textContent.trim();
                        if (txt && txt.length > 2 && depth > 0) {
                            const parent = node.parentElement;
                            const parentTag = parent ? parent.tagName.toLowerCase() : '';
                            if (!['script', 'style', 'noscript', 'a', 'button', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(parentTag)) {
                                lines.push(`${indent}text "${txt}"`);
                            }
                        }
                    }
                    return lines;
                }

                const treeLines = buildTree(document.body);
                return {
                    title: document.title,
                    url: window.location.href,
                    tree: treeLines.join('\\n'),
                    total_refs: refCounter - 1
                };
            }
            """
            result = await page.evaluate(js_script)
            return {
                "status": "ok",
                "url": result.get("url"),
                "title": result.get("title"),
                "snapshot": result.get("tree", ""),
                "total_refs": result.get("total_refs", 0)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Errore generazione snapshot: {str(e)}"
            }


@app.post("/click")
async def click_element(req: ClickRequest):
    """Esegue un clic sull'elemento identificato dal riferimento [ref] (timeout 15s)."""
    async with session.lock:
        try:
            ref_str = str(req.ref).strip()
            page = await session.ensure_page()
            selector = f"[data-sandbox-ref='{ref_str}']"
            locator = page.locator(selector).first

            await locator.click(timeout=TIMEOUT_MS)
            # Breve attesa per consentire eventuali reazioni DOM o navigazioni
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass

            return {
                "status": "ok",
                "message": f"Clic eseguito con successo sull'elemento [{ref_str}]",
                "current_url": page.url,
                "current_title": await page.title()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Errore clic su [{req.ref}]: {str(e)}"
            }


@app.post("/type")
async def type_element(req: TypeRequest):
    """Inserisce testo nell'elemento di input identificato dal riferimento [ref] (timeout 15s)."""
    async with session.lock:
        try:
            ref_str = str(req.ref).strip()
            page = await session.ensure_page()
            selector = f"[data-sandbox-ref='{ref_str}']"
            locator = page.locator(selector).first

            await locator.fill(req.text, timeout=TIMEOUT_MS)
            return {
                "status": "ok",
                "message": f"Testo inserito con successo nell'elemento [{ref_str}]",
                "current_url": page.url
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Errore inserimento testo su [{req.ref}]: {str(e)}"
            }


@app.post("/close")
async def close_browser():
    """Chiude la sessione corrente del browser e libera le risorse."""
    await session.close()
    return {
        "status": "ok",
        "message": "Sessione browser isolato chiusa con successo."
    }
