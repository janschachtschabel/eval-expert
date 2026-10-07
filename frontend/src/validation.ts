import type { AbstractControl } from "@angular/forms";

export function controlError(control?: AbstractControl): string {
  const errors = control?.errors || {};
  if (errors["required"]) return "requiredField";
  if (errors["minlength"]) return "shortPassword";
  if (errors["min"] || errors["max"]) return "invalidRange";
  if (errors["pattern"]) return "invalidPointer";
  return "invalidValue";
}

const messages: Record<string, string> = {
  judge_provider_required: "missingProvider",
  judge_criteria_required: "missingCriteria",
  reference_fields_required: "missingFields",
  missing: "requiredField",
  string_too_short: "invalidValue",
  greater_than_equal: "invalidRange",
  less_than_equal: "invalidRange",
  string_pattern_mismatch: "invalidPointer",
};

const known: Record<string, string> = {
  "Judge evaluations require a provider and criteria.": "missingJudgeSetup",
  "Reference evaluations require at least one field.": "missingFields",
  "Configure credentials for the judge provider.": "missingCredential",
  "The judge provider requires an API key.": "missingCredential",
  "Unknown IANA time zone.": "invalidSchedule",
  "Use a five-field cron expression.": "invalidSchedule",
  "Resource not found.": "resourceMissing",
  "Run not found.": "runMissing",
  "Invalid cron expression or time zone.": "invalidSchedule",
};

export function apiMessage(
  detail: unknown,
  status: number,
  tr: (key: string) => string,
): string {
  if (Array.isArray(detail))
    return detail
      .map((issue) => {
        const path = (issue.loc || [])
          .filter((part: unknown) => part !== "body")
          .join(".");
        return (
          (path ? path + ": " : "") + tr(messages[issue.type] || "invalidValue")
        );
      })
      .join(" · ");
  if (typeof detail === "string" && known[detail]) return tr(known[detail]);
  if (typeof detail === "string" && detail.startsWith("Resource is used by "))
    return tr("resourceInUse") + detail.slice("Resource is used by ".length);
  if (status === 403) return tr("permission");
  if (status === 404) return tr("resourceMissing");
  if (status === 422 && typeof detail !== "string") return tr("invalidValue");
  return typeof detail === "string"
    ? detail
    : tr("error") + " (HTTP " + status + ")";
}
