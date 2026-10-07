import csv
import html
import io
import json


def safe_cell(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def csv_export(run):
    return "".join(stream_csv(run["results"]))


def stream_csv(results):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["case_id", "status", "target_duration_ms", "input", "output", "reference", "judges"]
    )
    yield "\ufeff" + output.getvalue()
    for result in results:
        output.seek(0)
        output.truncate(0)
        cells = [result["case_id"], result["status"], result.get("target_duration_ms", "")]
        cells += [
            json.dumps(result.get(key), ensure_ascii=False)
            for key in ("input", "output", "reference", "judges")
        ]
        writer.writerow([safe_cell(cell) for cell in cells])
        yield output.getvalue()


def stream_json(run, results):
    run = {k: v for k, v in run.items() if k != "results"}
    yield json.dumps(run, ensure_ascii=False)[:-1] + ',"results":['
    for index, result in enumerate(results):
        yield ("," if index else "") + json.dumps(result, ensure_ascii=False)
    yield "]}"


def percent(value):
    return "—" if value is None else f"{value * 100:.1f}%"


def report(run):
    return "".join(stream_report(run, run["results"]))


def stream_report(run, results):
    def esc(value):
        return html.escape(str(value))

    summary = run["summary"]
    rows = "".join(
        f"<tr><td>{esc(f['name'])}</td><td>{percent(f['micro']['precision'])}</td>"
        f"<td>{percent(f['micro']['recall'])}</td><td>{percent(f['micro']['f1'])}</td>"
        f"<td>{f['annotated']}/{f['total']}</td><td>{f['tp']}/{f['fp']}/{f['fn']}</td></tr>"
        for f in summary.get("reference", [])
    )
    judge = summary.get("judge", {})
    snapshot = dict(run["snapshot"])
    snapshot["dataset"] = {k: v for k, v in snapshot["dataset"].items() if k != "cases"}
    dataset_note = (
        "Synthetischer Demonstrationsdatensatz."
        if snapshot["dataset"].get("demo")
        else "Konfigurierter Referenzdatensatz."
    )
    config = esc(json.dumps(snapshot, ensure_ascii=False, indent=2))
    yield f"""<!doctype html><html lang="de"><meta charset="utf-8">
    <title>Eval Expert Prüfprotokoll</title>
    <style>
    body{{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 24px;color:#172a2b}}
    table{{border-collapse:collapse;width:100%}}
    td,th{{padding:12px;text-align:left;border-bottom:1px solid #ccd8d7}}
    pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:12px monospace}}details{{margin:16px 0}}
    @media print{{body{{margin:0}}details{{display:block}}}}</style>
    <h1>Prüfprotokoll · {esc(snapshot["plan"]["name"])}</h1>
    <p>Lauf {esc(run["id"])} · {esc(run["status"])} · {esc(run["created"])}</p>
    <p>{dataset_note}
    Abgeschlossen: {run["progress"]} von {run["total"]} Fällen.
    Technisch erfolgreiche Antworten: {percent(summary.get("target_success_rate"))}.</p>
    <h2>Referenzvergleich</h2><p>Technische Fehler bleiben im primären Recall enthalten.
    Macro-Mittel berücksichtigt Klassen mit Referenzsupport;
    unbekannte Vorhersagen zählen als False Positives.
    Fehlende Annotationen werden ausgeschlossen; undefinierte Werte erscheinen als —.</p>
    <table><tr><th>Feld</th><th>Precision</th><th>Recall</th><th>F1</th>
    <th>Annotation</th><th>TP/FP/FN</th></tr>{rows}</table>
    <h2>LLM-Bewertung</h2><p>Durchschnitt: {percent(judge.get("mean_score"))};
    gültige Urteile: {judge.get("valid", 0)} von {judge.get("expected", 0)}.
    LLM-Urteile sind probabilistische Bewertungen der bereitgestellten Evidenz.
    Ohne Webseiteninhalt ist keine belastbare Aussage über Werbung auf einer Webseite möglich.</p>
    <h2>Konfiguration und Versionen</h2><pre>{config}</pre>
    <h2>Einzelergebnisse und Begründungen</h2>"""
    for r in results:
        yield (
            f"<details open><summary>{esc(r['case_id'])} · {esc(r['status'])}</summary>"
            f"<pre>{esc(json.dumps(r, ensure_ascii=False, indent=2))}</pre></details>"
        )
    yield "</html>"
