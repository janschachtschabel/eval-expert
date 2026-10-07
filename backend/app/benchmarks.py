"""Reference metrics: target errors remain in the primary denominator."""

from collections import Counter

from sklearn.metrics import precision_recall_fscore_support

from .pointers import MISSING, get_pointer


def labels(value, aliases=None):
    if value is MISSING or value is None:
        return set()
    values = value if isinstance(value, list) else [value]
    if any(not isinstance(item, (str, int)) or isinstance(item, bool) for item in values):
        raise ValueError("Classification outputs must be strings, integers or lists of labels.")
    aliases = aliases or {}
    return {
        str(aliases.get(str(item).strip(), str(item).strip()))
        for item in values
        if str(item).strip()
    }


def scores(tp, fp, fn):
    # scikit-learn calculates standard binary metrics; null preserves undefined scores.
    if not tp + fp + fn:
        return {"precision": None, "recall": None, "f1": None}
    p, r, f, _ = precision_recall_fscore_support(
        [1, 0, 1], [1, 1, 0], sample_weight=[tp, fp, fn], average="binary", zero_division=0
    )
    return {
        "precision": float(p) if tp + fp else None,
        "recall": float(r) if tp + fn else None,
        "f1": float(f) if 2 * tp + fp + fn else None,
    }


def compare_fields(results: list[dict], specs: list[dict]) -> list[dict]:
    return [_compare(results, spec) for spec in specs]


def _compare(results, spec):
    accumulator = FieldAccumulator(spec)
    for result in results:
        accumulator.add(result)
    return accumulator.summary()


class FieldAccumulator:
    def __init__(self, spec):
        self.spec = spec
        self.total, self.annotated = 0, 0
        self.tp, self.fp, self.fn = Counter(), Counter(), Counter()
        self.universe = set()
        self.successful = [0, 0, 0]

    def add(self, result):
        self.total += 1
        gold = get_pointer(result["reference"], self.spec["reference_path"])
        if gold is MISSING or gold is None:
            return
        self.annotated += 1
        expected = labels(gold, self.spec.get("aliases"))
        actual = (
            set()
            if self.spec["name"] in result.get("field_errors", {})
            else labels(
                get_pointer(result.get("output"), self.spec["output_path"]),
                self.spec.get("aliases"),
            )
        )
        additions = (expected | actual) - self.universe
        if len(self.universe) + len(additions) > 10_000:
            raise ValueError("Classification label budget exceeded (10,000 per field).")
        self.universe.update(additions)
        parts = (expected & actual, actual - expected, expected - actual)
        for counter, part in zip((self.tp, self.fp, self.fn), parts, strict=True):
            counter.update(part)
        if result["status"] == "success":
            self.successful = [n + len(p) for n, p in zip(self.successful, parts, strict=True)]

    def summary(self):
        classes = []
        for label in sorted(self.universe):
            tp, fp, fn = self.tp[label], self.fp[label], self.fn[label]
            classes.append(
                {
                    "label": label,
                    "support": tp + fn,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "precision": tp / (tp + fp) if tp + fp else None,
                    "recall": tp / (tp + fn) if tp + fn else None,
                    "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
                }
            )
        macro = {}
        for metric in ("precision", "recall", "f1"):
            values = [c[metric] or 0 for c in classes if c["support"]]
            macro[metric] = sum(values) / len(values) if values else None
        tp, fp, fn = self.tp.total(), self.fp.total(), self.fn.total()
        return {
            "name": self.spec["name"],
            "annotated": self.annotated,
            "total": self.total,
            "coverage": self.annotated / self.total if self.total else 0,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "micro": scores(tp, fp, fn),
            "macro": macro,
            "successful_micro": scores(*self.successful),
            "classes": classes,
        }
