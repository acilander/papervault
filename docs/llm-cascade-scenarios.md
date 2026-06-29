# Blueprints: LLM Cascade & Agentic Routing Scenarios

This document serves as the architectural blueprint for scaling **PaperVault**'s local LLM inference pipeline once the dedicated GPU (**NVIDIA RTX 3060 12GB**) is installed. It outlines three scenarios for combining a small, fast CPU-bound model (e.g., *Qwen-2.5-1.5B-Instruct*) with a larger, highly intelligent GPU-bound model (e.g., *Qwen-2.5-7B-Instruct* or *Llama-3-8B-Instruct*).

---

## Architectural Context
Local LLM inference faces two constraints:
1.  **CPU Inference** is slow but consumes almost 0% GPU VRAM, keeping the system lightweight and quiet during trivial tasks.
2.  **GPU Inference** is extremely fast and cognitively superior, but consumes valuable VRAM and power. 

By designing an **Agentic Cascade**, we leverage the speed of small models for simple tasks and escalate to larger models only when cognitive depth is required.

---

## Scenario 1: The Triage & Escalation Cascade (Dynamic Routing)
*Focus: Maximum speed and battery/resource conservation.*

```text
       [ PDF Ingestion ]
               │
               ▼
   ┌───────────────────────┐
   │ Stufe 0: Rules Match  ├──────► [Success Exit] (Exact match & Pinned category)
   └───────────┬───────────┘
               │ (No deterministic rule match)
               ▼
   ┌───────────────────────┐
   │ Stufe 1: Small LLM    │ (Fast CPU-only 1.5B run)
   └───────────┬───────────┘
               │
               ├──────► [Success Exit] (Passes semantic validation & text grounding)
               │
               ▼ (Validation fails / Hallucination detected)
   ┌───────────────────────┐
   │ Stufe 2: Large LLM    │ (GPU-bound 7B/8B execution on RTX 3060)
   └───────────────────────┘
```

### Workflow:
1.  **Stage 0 (Rules):** Scans raw text for exact known senders/aliases. If matched with a pinned category, it bypasses heavy LLM reasoning.
2.  **Stage 1 (Triage):** If unknown, the fast 1.5B model runs on the CPU.
3.  **Stage 2 (Validation):** Our custom semantic validation checker verifies if the predicted fields exist in the PDF.
4.  **Stage 3 (Escalation):** If validation fails, the task is escalated to the 7B/8B model running fully in VRAM on the RTX 3060 to perform a high-precision re-classification.

---

## Scenario 2: Specialized Role Division (Collaborative Agents)
*Focus: VRAM conservation, high-speed structured extraction.*

Small models are excellent at simple, explicit text searches. Large models excel at contextual comprehension, logical synthesis, and German summarization.

### Workflow:
1.  **The "Text Scanner Agent" (1.5B on CPU):**
    *   Finds explicit text matches: extracts raw date strings, identifies IBANs, tax IDs, and lists 10 raw keywords from the text.
    *   Executes instantly without occupying GPU VRAM.
2.  **The "Analyst Agent" (7B on GPU / RTX 3060):**
    *   Receives the compact metadata pre-extracted by the 1.5B model along with the briefkopf (`header_zone`).
    *   Resolves the canonical sender, classifies the category based on the extracted keywords, and formulates a single-sentence German summary.
3.  **The Exit:** Since the 7B model only processes a small, pre-filtered context window, it consumes minimal VRAM and executes in milliseconds.

---

## Scenario 3: The Critic & Reviewer (Adversarial Double-Check)
*Focus: 100% Accuracy, Hallucination-free indexing.*

In a private document archiver, processing latency (2 seconds vs. 5 seconds) is negligible compared to the importance of accurate search indexes.

### Workflow:
1.  **The "Drafting Agent" (1.5B on CPU):**
    *   Processes the document and creates an initial JSON draft of all fields (`sender`, `date`, `category`, `summary`, `keywords`).
2.  **The "Reviewer Agent" (7B on GPU / RTX 3060):**
    *   Loads the raw text, the draft, and analyzes them side-by-side.
    *   Checks if the draft contains errors, corrects any mismatched names, normalizes spelling, and signs off.
3.  **The Exit:** The document is saved only after the Critic Agent approves the classification.

---

## Evaluation Strategy
To determine which scenario is the absolute best fit for your archive, we will gather empirical data using your current CPU-only setup:
*   We will calculate and write a **Confidence Score** (`[Vertrauen: HIGH/MEDIUM/LOW]`) directly to the document `notes` database column.
*   After you process ~50 PDFs, we will analyze the logs:
    *   If most documents are **HIGH** or **MEDIUM**, **Scenario 1 (Triage)** is sufficient.
    *   If many documents slip to **LOW**, **Scenario 2 (Role Division)** or **Scenario 3 (The Critic)** will be implemented to ensure stable processing.
