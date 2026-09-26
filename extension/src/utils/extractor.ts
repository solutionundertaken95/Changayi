/**
 * extractor.ts — Extracts readable text content from the current webpage.
 *
 * --- WHY NOT JUST SEND document.body.innerHTML? ---
 *
 *   HTML markup is mostly noise for a text embedding model:
 *     <div class="nav-item"><a href="/about">About</a></div>
 *   That produces the embedding for "About" — completely useless context.
 *
 *   We want the actual readable content — paragraphs, headings, lists —
 *   the text a human would read when visiting the page.
 *
 * --- THE EXTRACTION STRATEGY ---
 *
 *   Step 1: Try to find the "main content" area using semantic HTML.
 *     Modern well-structured pages use <main>, <article>, or role="main"
 *     to mark their primary content. These are almost never navbars or footers.
 *
 *   Step 2: Fall back to <body> if no semantic landmark is found.
 *
 *   Step 3: Use .innerText (not .textContent) on the target element.
 *
 *     innerText vs textContent:
 *       - textContent: Returns ALL text including <script>, <style> content.
 *                      Ignores CSS — extracts text from hidden elements too.
 *       - innerText:   Returns only VISIBLE rendered text. Automatically
 *                      excludes <script>, <style>, display:none elements.
 *                      Respects line breaks and whitespace as rendered.
 *
 *     innerText is what we want — it's what a human sees on the page.
 *
 *   Step 4: The backend's cleaner.py handles further noise removal
 *     (repeated blank lines, short nav-like lines, unicode normalization).
 *     The extension's job is simply to get the right text region.
 *
 * --- CONTENT SELECTORS (priority order) ---
 *
 *   We try semantic elements first because they're the most reliable
 *   signal for "this is the main content":
 *
 *     <main>           → the primary content of the document (HTML5 spec)
 *     <article>        → a self-contained piece of content (blog post, news)
 *     [role="main"]    → ARIA landmark for non-semantic main content
 *     .main-content    → common CSS class convention
 *     #content         → common CSS ID convention
 *     <body>           → last resort — everything visible
 */

export interface ExtractedPage {
  text: string;
  title: string;
  url: string;
  wordCount: number;
  extractedFrom: string;   // Which selector found the content (for debugging)
}

// Selectors tried in order — first match wins
const CONTENT_SELECTORS = [
  'main',
  'article',
  '[role="main"]',
  '.main-content',
  '.article-content',
  '.article-body',
  '.post-content',
  '.post-body',
  '.entry-content',
  '.content-body',
  '.page-content',
  '#main-content',
  '#content',
  '#main',
];

export function extractPageContent(): ExtractedPage {
  const title = document.title || 'Untitled Page';
  const url = window.location.href;

  // ── Find the best content container ──────────────────────────────────
  let contentEl: Element | null = null;
  let extractedFrom = 'body';

  for (const selector of CONTENT_SELECTORS) {
    const el = document.querySelector(selector);
    if (el && (el as HTMLElement).innerText.trim().length > 200) {
      // Only use this selector if it actually has meaningful content
      contentEl = el;
      extractedFrom = selector;
      break;
    }
  }

  // Fall back to body if no semantic content element found
  if (!contentEl) {
    contentEl = document.body;
    extractedFrom = 'body (fallback)';
  }

  // ── Extract visible text ──────────────────────────────────────────────
  // innerText gives us what the user can actually read — no scripts, no
  // hidden elements, proper line breaks from block-level elements.
  const text = (contentEl as HTMLElement).innerText || '';

  const wordCount = text.trim().split(/\s+/).filter(Boolean).length;

  return {
    text,
    title,
    url,
    wordCount,
    extractedFrom,
  };
}
