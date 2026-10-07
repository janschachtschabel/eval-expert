# Eval Expert Aufgabenplan

> Historische vollständige Roadmap. Die erste Auslieferung folgt dem
> [verfeinerten Umsetzungsplan](2026-10-06-implementation.md). Die unten genannten Dateinamen,
> zusätzlichen Dienste und späteren Ausbaupakete beschreiben den ursprünglichen Vorschlag.
> Verbindliche Start- und Prüfkommandos sowie der tatsächlich implementierte Umfang stehen
> in der [README](../../README.md) und im [Prüfnachweis](../verification.md).

Entwurf zur Abnahme vom 6. Oktober 2026. Grundlage ist [der Architekturplan](2026-10-06-eval-expert-design.md). Die bestätigte Ausrichtung ist eine gemeinsame interne Installation mit lokalen Benutzerkonten und zwei Arbeitsbereichen für Metadaten: Referenzvergleich und LLM-Bewertung.

Die Tabelle beschreibt die Umsetzungspakete und ihre Abnahmen. Vor Beginn werden die Pilot-API und ein Ausschnitt des vorhandenen Referenzdatensatzes konkret zugeordnet. Es wird noch keine Anwendung implementiert und kein Dienst angebunden.

Geplant sind ausschließlich scikit-learn für Referenzmetriken und DeepEval für LLM-Bewertungen. RAGAS, TruLens, Promptfoo und Langfuse werden weder installiert noch integriert. Eine Registry für mehrere Engines oder eine Pluginplattform wird nicht entwickelt. Das Interface `EvaluationEngine` bezeichnet eine einfache interne Grenze zur konkreten DeepEval-Anbindung.

Die b-api-Anbindung verwendet das lokal kopierte Wissen aus [wlo-b-api-llm](../../.agents/skills/wlo-b-api-llm/SKILL.md). Weitere WLO-/edu-sharing-Skills liegen mit ihren Begleitdateien unter `.agents/skills` im Projekt.

## Gemeinsame Verträge

Diese Bezeichnungen gelten über alle Pakete hinweg:

- `EvaluationSample`: Eingabe, normalisierte Target-Ausgabe, Referenzfelder mit Annotationstatus, Quellenartefakte und fachlicher Kontext.
- `EvaluationPlanVersion`: Connector-, Dataset-, Mapping- und Metrikversionen; `evaluation_kind` = `reference`, `judge` oder `combined`; Target-/Judge-Wiederholungen und Budgets.
- `FieldScoringSpecVersion`: Feldpfade, Single-/Multi-Label-Modus, Vokabular, Normalisierung und Aggregationsregeln.
- `FieldComparison`: kanonische erwartete/vorhergesagte Labels, TP/FP/FN, Annotation- und Ausführungsstatus.
- `BenchmarkSummary`: Präzision/Recall/F1 nach Feld und Mittelung, Support, Referenzabdeckung, Target-Erfolgsquote und Aggregationspolicy.
- `MetricResult`: `status`, `score`, `passed`, `reason`, `evidence_refs`, Profil-/Metrikversion; bei Fehlern sind Score und Bestehensentscheidung leer.
- `Run`: eingefrorene Konfiguration, Fälle, Versuche, Fortschritt und technischer Zustand; fachliches Urteil ist getrennt.

Geplante Adapterverträge:

| Vertrag | Aufgabe |
| --- | --- |
| `TargetAdapter.execute(request, connector_version) -> TargetResponse` | Wiederholbarkeit, HTTP-Messwerte und Antwort liefern |
| `SampleMapper.map(test_case, target_response, mapping_version) -> EvaluationSample` | Nur freigegebene Eingabefelder und Ausgabepfade zuordnen |
| `ReferenceEvaluator.compare(sample, field_spec) -> FieldComparison` | Ein Feld gegen seine Referenz vergleichen |
| `ReferenceEvaluator.aggregate(comparisons, scoring_version) -> BenchmarkSummary` | Eindeutige Aggregationsregeln anwenden |
| `JudgeAdapter.generate(messages, schema, profile_version) -> JudgeResponse` | Validierte Ausgabe und verfügbare Usage liefern |
| `EvaluationEngine.evaluate(sample, criterion_version, judge_profile) -> MetricResult` | Framework unabhängig von der App verwenden |
| `ArtifactStore.put/get/delete` | Berechtigten Zugriff auf Quellen und Exporte vermitteln |

Diese Interfaces werden vor ihrer Implementierung mit konkreten Pydantic-/Fachtypen festgelegt. Run-IDs und Datenbanktypen werden einheitlich verwendet.

## Arbeitsweise und Prüfkommandos

Jedes Paket beginnt mit `Step 0: invoke /better-coding-workflow`; bei UI-Arbeit zusätzlich `invoke /better-coding-frontend`. Für jedes Verhalten wird zuerst der fachliche Nachweis formuliert, dann ein sinnvoller fehlschlagender Test, dann die kleinste Implementierung. Reine Styling- und Dokumentationsänderungen benötigen keinen Test, der nur die Implementierung nachzeichnet.

Die folgenden Kommandos sind für die später anzulegenden Projektdateien vorgesehen. Sie wurden in dieser Planungsphase nicht ausgeführt:

- Backend, im Verzeichnis `backend`: `uv run pytest tests/<angegebener_test>.py -q`.
- Backend gesamt: `uv run pytest -q`, `uv run ruff check .`, `uv run mypy app`.
- Frontend, im Verzeichnis `frontend`: `npm run test -- --watch=false`, `npm run build`.
- Browser-Abnahme: `npm run e2e`, für einzelne Szenarien `npm run e2e -- <dateiname>`.
- Echte Provider-Smokes werden explizit separat gestartet, etwa `uv run pytest -m live tests/live -q`; das Markierungskonzept schließt sie aus der normalen Suite aus.

Rollback eines Pakets: Neue Konfigurationen/Adapter über ihre Feature- oder Versionsauswahl deaktivieren, geänderten Code rückgängig machen und vorherige Tests ausführen. Bereits verwendete Versionsobjekte und Messdaten bleiben erhalten. Datenbankänderungen werden nur über getestete Migrationen zurückgenommen; destruktive Änderungen benötigen vorher ein Backup.

## Lieferstufe eins Technischer Pilot

Step 0: invoke `/better-coding-workflow`, bei den UI-Aufgaben zusätzlich `/better-coding-frontend`.

Ziel ist die kleinste durchgehende Messung: Ein Fall kommt aus einem lokalen Testdatensatz, ein Test-Target antwortet mit anderen Metadatenfeldern, die App berechnet Referenzmetriken und zeigt das Ergebnis. Danach wird diese Scheibe um Persistenz, lokale Anmeldung und zwei echte Judge-Zugänge erweitert.

| Nr | Aufgabe und Dateien | Schnittstelle und Nachweis | Abhängigkeit |
| --- | --- | --- | --- |
| 01 | Referenzmessung als vertikale Scheibe: `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/domain/evaluation.py`, `backend/app/benchmarks/reference.py`, `frontend/package.json`, `frontend/src/app/features/benchmarks/pilot-page.ts` | Zuerst Fixture {Mathematik, Physik} gegen {Mathematik, Chemie} prüfen, dann Demo-Route und Ergebnissicht verbinden. P/R/F1 jeweils 0,5; Test `backend/tests/unit/test_reference.py` und UI-Build. Ausschließlich lokales Test-Target. | Abnahme des Plans |
| 02 | Feldvergleich isolieren: `backend/app/benchmarks/field_comparison.py`, `backend/app/benchmarks/aggregation.py` | `FieldComparison` und `BenchmarkSummary`; Tests `tests/unit/test_field_comparison.py`, `tests/unit/test_aggregation.py` prüfen Single-/Multi-Label, Duplikate, Micro/Macro, Nullfälle und unbekannte Labels. | 01 |
| 03 | Versionen speichern: `backend/app/adapters/storage/models.py`, `backend/app/adapters/storage/repositories.py`, `backend/alembic/versions/0001_core.py` | Dataset-, Connector-, Plan- und Run-Versionen; `tests/integration/test_version_persistence.py` bestätigt unveränderte Wiederherstellung nach Neustart. | 02 |
| 04 | Lokale Passwörter: `backend/app/auth/passwords.py`, `backend/app/auth/users.py`, `backend/app/auth/bootstrap.py` | Administrator per CLI anlegen; `tests/unit/test_passwords.py` prüft Argon2id, falsches Passwort, Hashupgrade und deaktivierte Nutzer. | 03 |
| 05 | Sitzungen schützen: `backend/app/auth/sessions.py`, `backend/app/auth/routes.py`, `backend/app/auth/csrf.py`, `frontend/src/app/core/auth/session.service.ts`, `frontend/src/app/features/auth/login-page.ts` | Login, Logout und `GET /session`; `tests/integration/test_auth_sessions.py` sowie `frontend/e2e/auth.spec.ts` prüfen Cookieflags, CSRF, Ablauf und erneuerte Sitzung. | 04 |
| 06 | Zieladapter und Mapping: `backend/app/adapters/http/target.py`, `backend/app/adapters/http/mapping.py`, `backend/app/adapters/http/network_policy.py` | `TargetAdapter` und `SampleMapper`; `tests/unit/test_target_mapping.py` prüft zwei verschachtelte API-Schemata, typgerechte Eingaben und Trennung der Goldlabels. `tests/unit/test_network_policy.py` prüft freigegebene Origins und Redirects. | 05 |
| 07 | Metadaten-Pilotdatensatz übernehmen: `backend/app/datasets/importer.py`, `backend/tests/fixtures/metadata_reference.jsonl`, `docs/operations/pilot-data-contract.md` | Ausschnitt der vorhandenen Daten mit stabilen IDs und Annotationstatus; `tests/unit/test_dataset_import.py` prüft fehlend gegen bestätigte leere Referenz und zeilenbezogene Fehler. | 06 und reale Datenauswahl |
| 08 | OpenAI-/b-api-Zugänge: `backend/app/adapters/llm/profiles.py`, `backend/app/adapters/llm/openai.py`, `backend/app/adapters/llm/b_api.py`, `backend/app/adapters/llm/capabilities.py` | `JudgeAdapter`; `tests/unit/test_judge_adapters.py` prüft `X-API-KEY`, Schemaausgabe, unterstützte Parameter, leeres `content` und begrenzte Retries. `tests/live/test_judge_smoke.py` prüft freigegebene aktuelle Profile. | 06 und echte Provider-Zugänge |
| 09 | DeepEval-Adapter und zwei Kriterien: `backend/app/adapters/evaluation/deepeval_engine.py`, `backend/app/criteria/starter.py` | `EvaluationEngine` für Quellenbezug und Beschreibungsgüte; `tests/unit/test_deepeval_engine.py` prüft versionierte Schritte, Schemafehler und Rückführung ins Fachmodell. | 08 |
| 10 | Antwort einmal auswerten: `backend/app/runs/pipeline.py`, `frontend/src/app/features/runs/pilot-result-page.ts` | `reference`, `judge`, `combined`; `tests/integration/test_combined_run.py` weist genau einen Target-Call pro Versuch und getrennte Resultate nach. | 07 und 09 |

Abnahme der Lieferstufe: Eine autorisierte Person kann den Pilotfall starten und die Antwort samt P/R/F1 beziehungsweise LLM-Befund sehen. Referenzruns funktionieren ohne LLM-Schlüssel. Beide Provider können mit kleinen echten Tests erreicht werden. Es gibt noch keinen unbeaufsichtigten Produktionsbetrieb.

## Lieferstufe zwei Fachliches MVP

Step 0: invoke `/better-coding-workflow` und `/better-coding-frontend`.

| Nr | Aufgabe und Dateien | Schnittstelle und Nachweis | Abhängigkeit |
| --- | --- | --- | --- |
| 11 | OpenAPI importieren: `backend/app/adapters/http/openapi.py`, `backend/app/services/import_routes.py` | Import erstellt nur Beschreibungsversionen; `tests/unit/test_openapi_import.py` prüft 3.0/3.1, lokale Referenzen, verbotene externe Referenzen und erkennbare unsupported Operations. | 10 |
| 12 | Dienstassistent: `frontend/src/app/features/services/service-wizard.ts`, `frontend/src/app/shared/forms/schema-form.ts`, `frontend/src/app/shared/forms/json-editor.ts` | Operation, Auth-Referenz, Eingabe und Ausgabe wählen; `frontend/e2e/service-wizard.spec.ts` richtet beide Fixture-APIs ohne Code ein. JSON-Editor bleibt für unsupported UI-Schemata verfügbar. | 11 |
| 13 | Referenzdaten komfortabel importieren: `backend/app/datasets/routes.py`, `frontend/src/app/features/datasets/import-wizard.ts` | Vorschau mit Trennung zwischen Inputs und Referenzfeldern, Annotationstatus und Split; `frontend/e2e/dataset-import.spec.ts` importiert CSV/JSONL einschließlich ungültiger Zeilen. | 07 und 12 |
| 14 | Vokabulare und Feldmetriken: `backend/app/benchmarks/vocabulary.py`, `backend/app/benchmarks/scoring_specs.py`, `frontend/src/app/features/benchmarks/field-scoring-editor.ts` | Kanonische URI-/Aliaszuordnung und `FieldScoringSpecVersion`; `tests/unit/test_vocabulary.py` und `tests/unit/test_reference_policy.py` prüfen stabile Klassenräume und getrennte bedingte/Gesamtauswertung. | 02 und 13 |
| 15 | Kriterieneditor: `backend/app/criteria/routes.py`, `backend/app/criteria/versioning.py`, `frontend/src/app/features/criteria/criterion-editor.ts` | Definition, Rubrik, Beispiele, nötige Felder und Probe; `tests/unit/test_criterion_versions.py` sowie `frontend/e2e/criterion-editor.spec.ts` prüfen unveränderliche veröffentlichte Versionen. | 09 und 12 |
| 16 | Nutzerverwaltung: `backend/app/auth/admin_routes.py`, `backend/app/auth/password_set_tokens.py`, `frontend/src/app/features/admin/users-page.ts` | Nutzeranlage, Deaktivierung und einmaliger Passwortsetz-Code; `tests/integration/test_user_lifecycle.py` prüft Ablauf, Einmaligkeit und Invalidierung bestehender Sessions. | 05 |
| 17 | Projektrollen und Secrets: `backend/app/auth/permissions.py`, `backend/app/services/secrets.py`, `backend/app/adapters/storage/secret_store.py` | Berechtigte Run-/Export-/Verwaltungsaktionen; `tests/integration/test_project_permissions.py` und `tests/unit/test_secret_redaction.py` prüfen Projektgrenzen und entfernte Credentials. | 16 |
| 18 | Prüfpläne verwalten: `backend/app/runs/plan_versions.py`, `frontend/src/app/features/plans/plan-editor.ts` | Expliziter Modus und getrennte Target-/Judge-Parameter; `tests/unit/test_plan_validation.py` prüft reine Referenzpläne ohne Judge sowie fehlende Pflichtdaten. | 14, 15 und 17 |
| 19 | Hintergrundruns: `backend/app/workers/celery_app.py`, `backend/app/workers/tasks.py`, `backend/app/runs/state_machine.py`, `backend/app/schedules/outbox.py`, `deploy/compose.dev.yml` | Run und Outbox atomar erzeugen, Worker führt aus; `tests/integration/test_run_recovery.py` prüft doppelte Zustellung, Worker-Neustart, Heartbeat und kooperativen Abbruch. | 18 |
| 20 | Getrennte Ergebnisansichten: `frontend/src/app/features/benchmarks/results-page.ts`, `frontend/src/app/features/judge/results-page.ts`, `frontend/src/app/features/runs/run-detail-page.ts` | P/R/F1 und klassenbezogene Fehler beziehungsweise Score/Begründung/Belege; `frontend/e2e/result-workspaces.spec.ts` prüft Fehler, Teilergebnisse, Fallzahl und Referenzabdeckung. | 19 |
| 21 | Datenexporte: `backend/app/reports/data_exports.py`, `backend/app/reports/manifests.py` | CSV, JSON und JSONL mit Versionen; `tests/unit/test_data_exports.py` prüft Formelpräfixe, Secrets, Feldmetriken, Status und Exportmanifest. | 20 |

Abnahme der Lieferstufe: Zwei API-Dienste können per UI angebunden, bestehende Referenzdaten importiert und beide Arbeitsbereiche verwendet werden. Ein Fachnutzer erkennt TP/FP/FN und einzelne LLM-Begründungen. Nutzerrechte schützen Ausführung und Datenzugriff.

## Lieferstufe drei Betriebsfähige erste Version

Step 0: invoke `/better-coding-workflow`, bei den UI-Aufgaben zusätzlich `/better-coding-frontend`.

| Nr | Aufgabe und Dateien | Schnittstelle und Nachweis | Abhängigkeit |
| --- | --- | --- | --- |
| 22 | Dauerhafte Zeitpläne: `backend/app/schedules/rules.py`, `backend/app/schedules/dispatcher.py`, `frontend/src/app/features/schedules/schedule-editor.ts` | Nächste fünf Termine, Pause, Lease und eindeutiger Trigger; `tests/unit/test_schedule_rules.py` und `tests/integration/test_schedule_dispatch.py` prüfen Neustart, Nachholen und beide Berliner Zeitumstellungen. | 19 |
| 23 | Limits und Budgets: `backend/app/runs/budget.py`, `backend/app/adapters/llm/provider_limits.py`, `backend/app/runs/usage.py` | Globale Provider-Slots, Lease, Backoff und Callreservierung; `tests/integration/test_provider_limits.py` prüft zwei Worker und fremde Projekte. `tests/unit/test_budget.py` prüft interne Engine-Calls und unbekannte Preise. | 19 |
| 24 | Webseiten erfassen: `backend/app/workers/browser_tasks.py`, `backend/app/adapters/http/page_capture.py`, `backend/app/adapters/storage/artifacts.py` | DOM, Haupttext, Screenshot, Ladefehler und Erfassungsprofil; `tests/integration/test_page_capture.py` verwendet lokale kontrollierte Fixtures für Banner, Frames, blockierte Inhalte und Redirects. | 17, 19 und 23 |
| 25 | Werbebewertung: `backend/app/criteria/advertising.py`, `frontend/src/app/features/judge/evidence-viewer.ts` | Werbung beobachtet, nicht beobachtet und unzureichende Belege; `tests/unit/test_advertising_evidence.py` prüft erforderliche Modalität und unvollständige Erfassung. `frontend/e2e/evidence-viewer.spec.ts` prüft ungefährliche Anzeige fremder Inhalte. | 24 und 09 |
| 26 | Verläufe und Vergleich: `backend/app/runs/comparability.py`, `backend/app/benchmarks/comparison.py`, `frontend/src/app/features/comparisons/comparison-page.ts`, `frontend/src/app/shared/charts/history-chart.ts` | Signaturen, feldbezogene F1-Reihen, Judge-Reihen, Support und Abdeckung; `tests/unit/test_comparability.py` sowie `frontend/e2e/comparison.spec.ts` prüfen Versionswechsel und fehlende Fälle. | 20 und 22 |
| 27 | Rejudge und Recompare: `backend/app/runs/replay.py`, `frontend/src/app/features/runs/replay-dialog.ts` | Gespeicherte Antworten mit neuen Kriterien oder Scoring-Spezifikationen auswerten; `tests/integration/test_replay.py` weist keine erneuten Target-Calls nach. | 26 |
| 28 | Berichte und Freigabe: `backend/app/reports/facts.py`, `backend/app/reports/report_versions.py`, `frontend/src/app/features/reports/report-page.ts` | Verifizierbare Zahlen, Fallreferenzen und optionaler LLM-Entwurf; `tests/unit/test_report_facts.py` prüft korrekte Nenner und getrennte Referenz-/Judge-Befunde. `tests/integration/test_report_approval.py` prüft Reviewer-Rechte. | 21 und 26 |
| 29 | Dokumentexporte: `backend/app/reports/document_exports.py`, `backend/app/reports/templates/report.html`, `backend/app/reports/templates/report.md` | HTML/Markdown/PDF mit lokalen Assets; `tests/integration/test_report_exports.py` prüft blockierte externe Ressourcen und enthaltene Belegreferenzen. PDF zusätzlich auf Lesbarkeit prüfen. | 28 und 24 |
| 30 | Audit und Aufbewahrung: `backend/app/adapters/storage/audit.py`, `backend/app/workers/retention_tasks.py`, `frontend/src/app/features/admin/retention-page.ts` | Änderungen und Freigaben nachvollziehen, abgelaufene Rohdaten samt Exportbezug löschen; `tests/integration/test_retention.py` prüft Dateien und Datensätze. | 29 |
| 31 | Installation und Wiederherstellung: `deploy/compose.yml`, `deploy/proxy.conf`, `docs/operations/deployment.md`, `docs/operations/backup-restore.md` | Frischer Aufbau, Admin-Bootstrap, Migration und Restore mit bekannten Run-IDs; dokumentierter Probelauf auf einer getrennten Installation. | 30 |

Abnahme der Lieferstufe: Zeitpläne laufen nach Neustarts weiter, ein Worker-Abbruch verliert keine Messung, Grenzen werden eingehalten und Berichte enthalten überprüfbare Aussagen. Verläufe trennen Daten-/Prüfverfahrensänderungen von Änderungen der Dienstleistung.

## Lieferstufe vier Kalibrierung und fachliche Abnahme

Step 0: invoke `/better-coding-workflow`; für UI-Korrekturen zusätzlich `/better-coding-frontend`.

| Nr | Aufgabe und Dateien | Schnittstelle und Nachweis | Abhängigkeit |
| --- | --- | --- | --- |
| 32 | Referenzqualität und Split prüfen: `backend/app/datasets/reference_validation.py`, `backend/tests/fixtures/reference_edge_cases.jsonl`, `docs/operations/reference-dataset.md` | Vokabulare, Annotationstatus, Klassenhäufigkeiten und Materialgruppen prüfen; `tests/unit/test_reference_validation.py` zeigt partielle Labels und Dubletten vor der Auswertung an. | 13 und 14 |
| 33 | Judge kalibrieren: `backend/app/criteria/calibration.py`, `docs/operations/judge-calibration.md` | Vorhandene Bewertungen nutzen, soweit sie zur Rubrik passen; sonst fachlich annotierter Entwicklungs-/Validierungssatz. Auswertung zeigt Übereinstimmung, relevante Fehlklassen und akzeptierte Schwellen. | 25, 28 und fachliche Reviewer |
| 34 | Bedienbarkeit und lokale Assets prüfen: `frontend/e2e/accessibility.spec.ts`, `frontend/e2e/local-assets.spec.ts`, `frontend/src/app/shared/i18n/de.json`, `frontend/src/app/shared/i18n/en.json` | Tastatur/Fokus, Kontrast, Tabellenalternative, Lade-/Fehlerzustände und Netzwerktrace ohne externe UI-Assets. | 31 |
| 35 | Gesamtpilot abnehmen: `docs/operations/pilot-acceptance.md`, `backend/tests/integration/test_pilot_acceptance.py`, `frontend/e2e/pilot.spec.ts` | Zwei APIs, echte Referenzdaten, Referenzrun ohne LLM, kombinierter Run, Zeitplan, Abbruch, Vergleich, Export und Rollenprüfung. Fachliche Grenzen und verbleibende experimentelle Kriterien dokumentieren. | 32, 33 und 34 |

Abnahme der Lieferstufe: Technischer und fachlicher Nachweis liegen getrennt vor. Die App ist funktional abgenommen; die Bewertungskriterien sind entweder kalibriert und freigegeben oder ausdrücklich experimentell gekennzeichnet.

## Reihenfolge und spätere Erweiterungen

Die erste Scheibe verwendet ausschließlich lokale Testantworten. Reale Calls beginnen nach Anmeldung, Secret-Verwaltung und Freigabe der Pilot-Zugänge. Innerhalb der Lieferstufen können unabhängige Komponenten technisch getrennt bearbeitet werden; die Abhängigkeitsliste bleibt maßgeblich.

Nach der ersten Version werden zusätzliche Protokolle nur mit konkretem Anwendungsfall ergänzt. Weitere Evaluationsframeworks, RAG, die eigene Chatbot-Evaluation, öffentliches SaaS und eine umfassende Prompt-Optimierungsplattform gehören nicht zu diesem Auftrag.

## Entscheidungen für die Abnahme

Zur Freigabe stehen der Stack Angular 21/FastAPI/PostgreSQL/Celery/RabbitMQ, lokale Konten und die zwei getrennten Arbeitsbereiche. Die nächsten benötigten Arbeitsgrundlagen sind ein Beispieldatensatz einschließlich seiner Vokabularwerte und eine Pilot-API-Beschreibung. Endgültige Budgets, Aufbewahrungsfristen und fachliche Schwellen werden vor dem produktiven Pilot festgelegt.
