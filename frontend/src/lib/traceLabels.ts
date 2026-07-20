export const TRACE_STEP_LABELS: Record<string, string> = {
  ingest: 'Datei-Import (Ingest)',
  text_extraction: 'Text-Extraktion / OCR',
  duplicate_check: 'Duplikat-Prüfung',
  pre_analysis: 'Merkmals-Analyse',
  llm_classification: 'LLM-Klassifizierung',
  document_type_approval: 'Dokumenttyp-Freigabe',
  approval: 'Entscheidungs-Prüfung',
  archiving: 'Datei-Archivierung',
  contract_extraction: 'Vertrags-Extraktion',
  tax_linker: 'Steuer-Verknüpfung',
  items_extraction: 'Artikel-Extraktion',
  services_extraction: 'Dienstleistungs-Extraktion'
}

export function getTraceStepLabel(stepName: string): string {
  return TRACE_STEP_LABELS[stepName] || stepName
}
