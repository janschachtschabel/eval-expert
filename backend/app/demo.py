from fastapi import APIRouter, Depends, Request

from .auth import administrators

router = APIRouter()

EXAMPLES = [
    ("Brüche verstehen", "Bruchrechnung mit interaktiven Aufgaben.", ["math"], ["primary"]),
    ("Geometrie im Alltag", "Formen und Winkel erkennen.", ["math"], ["secondary"]),
    ("Energie und Strom", "Experimente zu Stromkreisen.", ["physics"], ["secondary"]),
    ("Pflanzen erforschen", "Untersuchungen zur Photosynthese.", ["biology"], ["secondary"]),
    ("Zellen im Mikroskop", "Aufbau tierischer Zellen.", ["biology"], ["secondary"]),
    ("Gedichte lesen", "Reime und sprachliche Bilder untersuchen.", ["german"], ["secondary"]),
    ("Geschichte Roms", "Quellen zur römischen Republik.", ["history"], ["secondary"]),
    ("Das Sonnensystem", "Planeten und Umlaufbahnen erkunden.", ["physics"], ["primary"]),
    (
        "Brüche und Energie",
        "Anteile des Energieverbrauchs berechnen.",
        ["math", "physics"],
        ["secondary"],
    ),
    ("Klima und Wetter", "Wetterdaten sammeln und vergleichen.", ["geography"], ["secondary"]),
    ("Lernen lernen", "Allgemeine Lernstrategien.", [], ["secondary"]),
    ("Material ohne Fachannotation", "Ein Beispiel mit fehlender Referenz.", None, ["secondary"]),
]


@router.post("/demo")
def seed(request: Request, user=Depends(administrators)):
    db = request.app.state.db
    for plan in db.list_catalog("plans"):
        if plan["name"] == "Demo · Metadaten prüfen":
            return {"plan_id": plan["id"]}
    service = db.save_catalog(
        "services",
        {
            "name": "Demo · lokaler Klassifikator",
            "kind": "demo",
            "description": "Deterministische Beispielklassifikation mit absichtlichen Fehlern.",
        },
    )
    cases = []
    for i, (title, description, subjects, level) in enumerate(EXAMPLES, 1):
        reference = {"educational_level": level}
        if subjects is not None:
            reference["subject"] = subjects
        cases.append(
            {
                "id": str(i),
                "input": {
                    "title": title,
                    "description": description,
                    "keywords": [],
                    "source": description,
                },
                "reference": reference,
            }
        )
    dataset = db.save_catalog(
        "datasets",
        {
            "name": "Demo · 12 Bildungsmaterialien",
            "description": "Synthetische Beispiele; keine Aussage über reale Dienste.",
            "cases": cases,
            "demo": True,
        },
    )
    db.save_catalog(
        "criteria",
        {
            "name": "Angemessene Beschreibung",
            "description": "Bildungsbezug und Klarheit",
            "steps": [
                "Prüfe, ob die Beschreibung verständlich und sachlich formuliert ist.",
                "Prüfe anhand der Quelle, ob Zielgruppe und Bildungsinhalt "
                "angemessen beschrieben sind.",
                "Bewerte von 0 (ungeeignet) bis 10 (vollständig geeignet); "
                "fehlende Belege begründen.",
            ],
            "threshold": 0.7,
            "output_path": "/description",
            "context_path": "/source",
        },
    )
    fields = [
        {"name": name, "output_path": f"/{name}", "reference_path": f"/{name}", "aliases": {}}
        for name in ("subject", "educational_level")
    ]
    plan = db.save_catalog(
        "plans",
        {
            "name": "Demo · Metadaten prüfen",
            "description": "Erster Referenzbenchmark",
            "service_id": service["id"],
            "dataset_id": dataset["id"],
            "mode": "reference",
            "fields": fields,
            "criterion_ids": [],
            "provider_id": None,
        },
    )
    db.audit(user["id"], "demo.created", plan["id"])
    return {"plan_id": plan["id"]}
