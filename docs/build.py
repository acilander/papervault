"""Build a complete static HTML documentation site from Markdown sources."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterable

try:
    import markdown
    from markdown.extensions import fenced_code, tables, toc
except ImportError as exc:
    raise SystemExit(
        "Missing dependencies. Run: .venv\\Scripts\\python -m pip install -r docs\\requirements.txt"
    ) from exc


DOCS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = DOCS_ROOT.parent
OUT_DIR = DOCS_ROOT / "html"

# Collect all markdown sources: docs/ + root-level blueprints
root_blueprints = [
    PROJECT_ROOT / name
    for name in [
        "blueprint_tax_module.md",
        "cline_blueprint_kv_extraction.md",
        "cline_blueprint_vision_logo.md",
    ]
    if (PROJECT_ROOT / name).exists()
]

# docs/ markdowns, excluding the generated html/ tree and root blueprint copies
docs_md = [
    p for p in DOCS_ROOT.rglob("*.md")
    if "html" not in p.relative_to(DOCS_ROOT).parts
    and p.name not in {bp.name for bp in root_blueprints}
]

# Blueprints are development planning documents; keep the source .md files
# but do not include them in the generated HTML documentation.
DOC_SOURCES = docs_md

MD = markdown.Markdown(
    extensions=[
        fenced_code.FencedCodeExtension(),
        tables.TableExtension(),
        toc.TocExtension(title="Inhalt"),
        "fenced_code",
        "tables",
        "toc",
    ],
    extension_configs={
        "toc": {"title": "Inhalt", "permalink": False},
    },
)


def relative_url(source: Path, target: Path) -> str:
    """Compute a relative URL from source HTML file to target HTML file."""
    rel = Path(source).parent.relative_to(OUT_DIR) if source.parent != OUT_DIR else Path(".")
    target_rel = target.relative_to(OUT_DIR)
    parts = [".."] * len(rel.parts) if rel.parts else ["."]
    return "/".join(parts + list(target_rel.parts))


NAV_ORDER: list[tuple[str | None, str]] = [
    ("index.html", "Übersicht"),
    ("USER_GUIDE.html", "Bedienungsanleitung"),
    ("FEATURES.html", "Feature-Liste"),
    ("ARCHITECTURE.html", "Systemarchitektur"),
]

TECHNICAL_CHAPTERS: list[tuple[str, str]] = [
    ("technical/01-pipeline-and-import.html", "01 Pipeline & Import"),
    ("technical/02-documents-search-and-filter.html", "02 Suche & Filter"),
    ("technical/03-ignore-lock.html", "03 Ignore / Lock"),
    ("technical/04-low-value-rules.html", "04 Low-Value-Rules"),
    ("technical/05-duplicates.html", "05 Duplikate"),
    ("technical/06-senders.html", "06 Absender"),
    ("technical/07-tax-module.html", "07 Steuer-Modul"),
    ("technical/08-collections.html", "08 Sammlungen"),
    ("technical/09-chat-and-llm.html", "09 KI-Suche"),
    ("technical/10-monitor.html", "10 Monitor"),
    ("technical/11-feedback.html", "11 Feedback"),
    ("technical/12-settings-and-config.html", "12 Einstellungen"),
    ("technical/13-inventory-contracts-services.html", "13 Inventar / Verträge / Ausgaben"),
]

FEATURE_DOCS: list[tuple[str, str]] = [
    ("feature-ignore-lock.html", "Ignore / Lock"),
    ("feature-low-value-rules.html", "Low-Value-Rules"),
]

BLUEPRINTS: list[tuple[str, str]] = [
    ("blueprints/blueprint_tax_module.html", "Steuer-Modul Blueprint"),
    ("blueprints/cline_blueprint_kv_extraction.html", "KV-Extraction Blueprint"),
    ("blueprints/cline_blueprint_vision_logo.html", "Vision/Logo Blueprint"),
]

OTHER: list[tuple[str, str]] = [
    ("llm-cascade-scenarios.html", "LLM-Cascade-Szenarien"),
    ("DOCUMENTATION_STRUCTURE.html", "Doku-Struktur"),
]

ORDERED_PAGES = NAV_ORDER + FEATURE_DOCS + TECHNICAL_CHAPTERS + BLUEPRINTS + OTHER

NAV_GROUPS: list[tuple[str, list[tuple[str | None, str]]]] = [
    ("Einstieg", [
        ("index.html", "Übersicht"),
        ("USER_GUIDE.html", "Bedienungsanleitung"),
        ("FEATURES.html", "Feature-Liste"),
    ]),
    ("System", [
        ("ARCHITECTURE.html", "Systemarchitektur"),
        ("DOCUMENTATION_STRUCTURE.html", "Doku-Struktur"),
    ]),
    ("Features", [
        ("feature-ignore-lock.html", "Ignore / Lock"),
        ("feature-low-value-rules.html", "Low-Value-Rules"),
    ]),
    ("Tiefe", [
        ("technical/index.html", "Technische Tiefe"),
    ]),
    ("Sonstiges", [
        ("llm-cascade-scenarios.html", "LLM-Cascade-Szenarien"),
    ]),
]


def _lookup_title(rel: str) -> str:
    # Check NAV_GROUPS first for friendly titles
    for _, links in NAV_GROUPS:
        for pattern, title in links:
            if pattern and rel == pattern:
                return title
    for pattern, title in ORDERED_PAGES:
        if pattern and rel == pattern:
            return title
    return Path(rel).stem.replace("-", " ").replace("_", " ").title()


def page_sort_key(rel: str) -> tuple[int, int]:
    """Sort a page relative path by its group position and link position."""
    for group_idx, (_, links) in enumerate(NAV_GROUPS):
        for link_idx, (pattern, _) in enumerate(links):
            if pattern and rel == pattern:
                return (group_idx, link_idx)
    return (len(NAV_GROUPS), 0)


def _build_group(current_html: Path, present: set[str], group_title: str, links: list[tuple[str | None, str]]) -> str:
    """Build one navigation group."""
    group_links: list[str] = []
    for pattern, title in links:
        if pattern not in present:
            continue
        href = relative_url(current_html, OUT_DIR / pattern)
        active = " active" if Path(pattern).name == current_html.name else ""
        group_links.append(f'<a class="nav-link{active}" href="{href}">{title}</a>')
    if not group_links:
        return ""
    return f'<div class="nav-group"><h3>{group_title}</h3>\n' + "\n".join(group_links) + '\n</div>'


def build_nav(current_html: Path, pages: Iterable[Path]) -> str:
    """Build a grouped sidebar navigation linking all generated HTML pages."""
    present: set[str] = {p.relative_to(OUT_DIR).as_posix() for p in pages}
    items: list[str] = []

    # Main navigation
    for group_title, links in NAV_GROUPS:
        group_html = _build_group(current_html, present, group_title, links)
        if group_html:
            items.append(group_html)

    # Sub-navigation for technical chapters when viewing a technical page
    current_rel = current_html.relative_to(OUT_DIR).as_posix()
    if current_rel.startswith("technical/"):
        tech_group = _build_group(current_html, present, "Kapitel", TECHNICAL_CHAPTERS)
        if tech_group:
            items.append(tech_group)

    return "\n".join(items)


def html_head(title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title} – PaperVault Doku</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css" id="light-hljs" />
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css" id="dark-hljs" disabled />
  <style>
    :root {{
      --bg: #f8fafc;
      --surface: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --accent: #2563eb;
      --border: #e2e8f0;
      --code-bg: #f1f5f9;
      --nav-bg: #ffffff;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0f172a;
        --surface: #1e293b;
        --text: #f8fafc;
        --muted: #94a3b8;
        --accent: #60a5fa;
        --border: #334155;
        --code-bg: #0f172a;
        --nav-bg: #1e293b;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.65;
      display: flex;
      min-height: 100vh;
    }}
    aside {{
      width: 280px;
      background: var(--nav-bg);
      border-right: 1px solid var(--border);
      padding: 1.5rem;
      position: fixed;
      top: 0; left: 0; bottom: 0;
      overflow-y: auto;
    }}
    aside h1 {{
      font-size: 1.25rem;
      margin: 0 0 1.5rem;
      display: flex;
      align-items: center;
      gap: .5rem;
    }}
    .nav-link {{
      display: block;
      padding: .45rem .6rem;
      border-radius: .4rem;
      color: var(--text);
      text-decoration: none;
      font-size: .92rem;
      margin-bottom: .15rem;
    }}
    .nav-link:hover {{ background: var(--bg); }}
    .nav-link.active {{ background: var(--accent); color: #fff; }}
    .nav-group {{ margin-bottom: 1rem; }}
    .nav-group h3 {{
      font-size: .75rem;
      text-transform: uppercase;
      letter-spacing: .05em;
      color: var(--muted);
      margin: 0 0 .4rem .6rem;
      font-weight: 600;
    }}
    main {{
      margin-left: 280px;
      flex: 1;
      max-width: 900px;
      padding: 2.5rem;
    }}
    h1 {{ font-size: 2rem; margin-top: 0; }}
    h2 {{ border-bottom: 1px solid var(--border); padding-bottom: .35rem; margin-top: 2.2rem; }}
    h3 {{ margin-top: 1.6rem; }}
    a {{ color: var(--accent); }}
    code, pre {{
      background: var(--code-bg);
      border-radius: .35rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: .9em;
    }}
    code {{ padding: .15rem .35rem; }}
    pre {{
      padding: 1rem;
      overflow-x: auto;
      border: 1px solid var(--border);
    }}
    pre code {{ padding: 0; background: transparent; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1rem 0;
    }}
    th, td {{
      border: 1px solid var(--border);
      padding: .55rem .75rem;
      text-align: left;
    }}
    th {{ background: var(--surface); }}
    blockquote {{
      border-left: 4px solid var(--accent);
      margin: 1rem 0;
      padding: .5rem 1rem;
      background: var(--surface);
      border-radius: 0 .4rem .4rem 0;
    }}
    .mermaid {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: .5rem;
      padding: 1rem;
      margin: 1rem 0;
    }}
    .mermaid svg {{ max-width: 100%; }}
    .toc {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: .5rem;
      padding: 1rem 1.25rem;
      margin: 1.5rem 0;
    }}
    .toc ul {{ padding-left: 1.2rem; }}
    .toc > ul {{ padding-left: 0; list-style: none; }}
    footer {{
      margin-top: 4rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border);
      color: var(--muted);
      font-size: .875rem;
    }}
    @media (max-width: 900px) {{
      aside {{ display: none; }}
      main {{ margin-left: 0; padding: 1.5rem; }}
    }}
  </style>
</head>"""


def html_body(title: str, content: str, nav: str) -> str:
    return f"""<body>
  <aside>
    <h1>📚 PaperVault Doku</h1>
    <nav>
{nav}
    </nav>
  </aside>
  <main>
{content}
    <footer>
      PaperVault Dokumentation · Generiert aus Markdown
    </footer>
  </main>
  <script>
    mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    // Toggle highlight.js theme based on dark mode
    const darkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.getElementById('light-hljs').disabled = darkMode;
    document.getElementById('dark-hljs').disabled = !darkMode;
  </script>
</body>
</html>"""


def title_from_content(html: str, fallback: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return fallback


def out_path_for(src: Path) -> Path:
    """Compute the output HTML path for a markdown source."""
    if src.parent == PROJECT_ROOT:
        return OUT_DIR / "blueprints" / (src.stem + ".html")
    rel = src.relative_to(DOCS_ROOT)
    return OUT_DIR / rel.with_suffix(".html")


def build() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    # Pre-compute all output pages so every page can link to every other page.
    pages = [out_path_for(src) for src in DOC_SOURCES]
    index_out = OUT_DIR / "index.html"
    pages.append(index_out)

    # Generate content pages
    for src in DOC_SOURCES:
        out = out_path_for(src)
        out.parent.mkdir(parents=True, exist_ok=True)

        md_text = src.read_text(encoding="utf-8")
        html_content = MD.convert(md_text)
        MD.reset()

        title = title_from_content(html_content, src.stem.replace("-", " ").replace("_", " ").title())
        page_nav = build_nav(out, pages)
        full = html_head(title) + "\n" + html_body(title, html_content, page_nav)
        out.write_text(full, encoding="utf-8")
        print(f"  wrote {out.relative_to(PROJECT_ROOT)}")

    # Generate index.html cards only for top-level pages defined in NAV_GROUPS
    present: set[str] = {p.relative_to(OUT_DIR).as_posix() for p in pages}
    cards = []
    top_level: set[str] = set()
    for _, links in NAV_GROUPS:
        for pattern, _ in links:
            if pattern:
                top_level.add(pattern)
    for rel in sorted(top_level, key=page_sort_key):
        if rel not in present:
            continue
        href = rel
        title = _lookup_title(rel)
        cards.append(
            f'<a class="card" href="{href}"><h3>{title}</h3></a>'
        )

    index_content = f"""
<div class="hero">
  <h1>PaperVault Dokumentation</h1>
  <p>Vollständige Bedienungsanleitung, Systemarchitektur und technische Tiefe.</p>
</div>
<div class="grid">
{chr(10).join(cards)}
</div>

<div class="diagram">
  <h2>Datenfluss beim Import</h2>
  <pre class="mermaid">
flowchart TD
    A[PDF landet in Inbox] --> B[Textextraktion]
    B --> C{{OCR nötig?}}
    C -->|Ja| D[OCR mit Tesseract]
    C -->|Nein| E[Nativer Text]
    D --> F[SHA256-Hash]
    E --> F
    F --> G{{Hash geschützt?}}
    G -->|Ignored| H[Nach ignored/ verschieben]
    G -->|Locked| I[Nach duplicates/ verschieben]
    G -->|Bekannt| I
    G -->|Neu| J[LLM-Klassifikation]
    J --> K[Metadaten extrahieren]
    K --> L[Datei archivieren]
    L --> M[(SQLite-Eintrag)]
  </pre>
</div>

<div class="diagram">
  <h2>Systemarchitektur</h2>
  <pre class="mermaid">
flowchart LR
    subgraph Frontend
        React["React + Vite"]
    end
    subgraph Backend
        FastAPI["FastAPI"]
        SQLite[(SQLite DB)]
    end
    subgraph Pipeline
        OCR["OCR / Text"]
        LLM["Lokales LLM"]
    end
    React -->|REST| FastAPI
    FastAPI --> SQLite
    FastAPI -->|startet| Pipeline
  </pre>
</div>

<div class="diagram">
  <h2>Duplikat-Check</h2>
  <pre class="mermaid">
flowchart TD
    A[Hash berechnen] --> B{{Geschützter Hash?}}
    B -->|Ignored| C[Status: ignored]
    B -->|Locked| D[Status: duplicate]
    B -->|Nein| E{{Dokument mit Hash vorhanden?}}
    E -->|Ja| D
    E -->|Nein| F[Weiter zur Klassifikation]
  </pre>
</div>

<style>
  .hero {{ text-align: center; margin-bottom: 2rem; }}
  .hero h1 {{ font-size: 2.5rem; }}
  .hero p {{ color: var(--muted); font-size: 1.125rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: .5rem;
    padding: 1rem;
    text-decoration: none;
    color: var(--text);
    transition: transform .15s, box-shadow .15s;
  }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,.08); }}
  .card h3 {{ margin: 0; font-size: 1rem; }}
  .diagram {{ background: var(--surface); border: 1px solid var(--border); border-radius: .5rem; padding: 1.5rem; margin: 2rem 0; }}
  .diagram h2 {{ margin-top: 0; }}
  .diagram .mermaid {{ background: transparent; border: none; padding: 0; }}
</style>
"""
    index_nav = build_nav(index_out, pages)
    full_index = html_head("Übersicht") + "\n" + html_body("Übersicht", index_content, index_nav)
    index_out.write_text(full_index, encoding="utf-8")
    print(f"  wrote {index_out.relative_to(PROJECT_ROOT)}")
    print(f"\nBuild complete. Open {OUT_DIR / 'index.html'} in your browser.")


if __name__ == "__main__":
    build()
