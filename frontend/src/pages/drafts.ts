import { Item } from "../api";
export const DRAFTS: Record<string, Item> = {
  services: {
    kind: "http",
    method: "POST",
    url: "",
    timeout: 60,
    auth_header: "Authorization",
    auth_prefix: "Bearer ",
  },
  datasets: {},
  criteria: {
    threshold: 0.7,
    output_path: "/description",
    context_path: "/source",
    context_source: "input",
    require_context: false,
  },
  providers: {
    kind: "openai",
    base_url: "https://api.openai.com/v1",
    model: "",
    token_parameter: "max_completion_tokens",
    max_tokens: 4096,
    temperature: null,
    json_mode: false,
  },
  plans: {
    mode: "reference",
    fields: [
      {
        name: "subject",
        output_path: "/subject",
        reference_path: "/subject",
        aliases: {},
      },
    ],
    criterion_ids: [],
    provider_id: null,
  },
  schedules: {
    cron: "0 8 * * 1",
    timezone: "Europe/Berlin",
    enabled: true,
  },
};
