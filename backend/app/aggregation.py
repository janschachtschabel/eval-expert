"""Incremental run summaries; retain counters rather than completed response bodies."""

from .benchmarks import FieldAccumulator


class SummaryAccumulator:
    def __init__(self, saved):
        self.fields = [FieldAccumulator(spec) for spec in saved["plan"]["fields"]]
        self.criteria = len(saved["criteria"])
        self.total = self.success = self.valid = self.passed = self.errors = 0
        self.score = 0.0
        self.usage = {name: 0 for name in ("prompt_tokens", "completion_tokens", "requests")}

    def add(self, result):
        self.total += 1
        self.success += result["status"] == "success"
        for field in self.fields:
            field.add(result)
        for verdict in result["judges"]:
            if verdict["status"] == "success":
                self.valid += 1
                self.passed += verdict["passed"]
                self.score += verdict["score"]
            else:
                self.errors += 1
            for key in self.usage:
                self.usage[key] += verdict.get("usage", {}).get(key, 0)

    def summary(self):
        expected = self.total * self.criteria
        return {
            "reference": [field.summary() for field in self.fields],
            "target_success_rate": self.success / self.total if self.total else 0,
            "target_errors": self.total - self.success,
            "judge": {
                "mean_score": self.score / self.valid if self.valid else None,
                "pass_rate": self.passed / self.valid if self.valid else None,
                "valid": self.valid,
                "expected": expected,
                "coverage": self.valid / expected if expected else None,
                "errors": self.errors,
            },
            "usage": dict(self.usage),
        }
