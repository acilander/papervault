from db.tax_years_repo import get_all as get_all_tax_years
from db.tax_positions_repo import (
    get_all_for_year as get_tax_positions_for_year,
    get_development,
)
from llm import llm_completion

SYSTEM_PROMPT = """Du bist ein datenschutzorientierter Steuer-Assistent innerhalb von PaperVault.
Du hilfst dem Nutzer, seine eigenen Steuerdaten zu verstehen, die lokal in PaperVault gespeichert sind.
Du gibst keine steuerliche oder rechtliche Beratung.
Antworte präzise, verständlich und kurz.
Wenn du Zahlen nennst, gib den Betrag in Euro an.
Wenn du es nicht weißt, sag es ehrlich."""


def _collect_context() -> str:
    """Collect a concise summary of all tax data for the LLM context."""
    years = get_all_tax_years()
    year_by_id = {y["id"]: y["year"] for y in years}
    positions = []
    for year in years:
        positions.extend(get_tax_positions_for_year(year["id"]))
    development = get_development()

    lines = []
    lines.append(f"Anzahl Steuerjahre: {len(years)}")
    for year in years:
        status_map = {
            "draft": "Entwurf",
            "submitted": "Abgegeben",
            "assessed": "Bescheid erhalten",
            "final": "Abgeschlossen",
        }
        notes = year.get('notes')
        notes_part = f" (Notizen: {notes})" if notes else ""
        lines.append(
            f"- {year['year']}: Status {status_map.get(year['status'], year['status'])}{notes_part}"
        )

    lines.append("\nWichtige Positionen (geprüfte und ungeprüfte):")
    summary: dict[tuple[int, str], dict[str, float]] = {}
    for pos in positions:
        year = year_by_id.get(pos["tax_year_id"])
        if year is None:
            continue
        key = (year, pos["category"])
        if key not in summary:
            summary[key] = {"export": 0.0, "assessed": 0.0}
        amount = (pos["amount"] if pos["source_type"] == "tax_program_export" else pos["amount_assessed"]) or 0.0
        if pos["source_type"] == "assessment_notice":
            summary[key]["assessed"] += amount
        else:
            summary[key]["export"] += amount

    for (year, category), amounts in sorted(summary.items()):
        diff = amounts["export"] - amounts["assessed"]
        lines.append(
            f"- {year} / {category}: Steuerprogramm {amounts['export']:.2f} €, "
            f"Bescheid {amounts['assessed']:.2f} €, Differenz {diff:.2f} €"
        )

    lines.append("\nEntwicklung ausgewählter Kategorien über Jahre:")
    for row in development:
        lines.append(
            f"- {row['category']} in {row['year']}: {row['total_amount'] or 0:.2f} € "
            f"(Programm) / {row['total_assessed'] or 0:.2f} € (Bescheid)"
        )

    return "\n".join(lines)


def answer_tax_question(question: str) -> str:
    context = _collect_context()
    user_prompt = f"""Hier ist die Zusammenfassung der Steuerdaten aus PaperVault:

{context}

Frage des Nutzers:
{question}

Antworte auf Deutsch."""

    answer = llm_completion(SYSTEM_PROMPT, user_prompt, max_tokens=2048, temperature=0.3)
    if answer is None:
        return "Der Assistent konnte die Frage leider nicht beantworten."
    return answer
