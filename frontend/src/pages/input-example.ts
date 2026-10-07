/** Build editable placeholders from input pointers; mappings cannot reveal field types. */
export function inputExample(mapping: unknown): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  const insert = (path: string) => {
    const tokens = path
      .slice(1)
      .split("/")
      .map((token) => token.replace(/~1/g, "/").replace(/~0/g, "~"));
    let node = result;
    tokens.forEach((token, index) => {
      if (
        !Object.hasOwn(node, token) ||
        (index < tokens.length - 1 && typeof node[token] !== "object")
      ) {
        // defineProperty keeps names such as __proto__ as data, not prototype setters.
        Object.defineProperty(node, token, {
          value: index === tokens.length - 1 ? "" : {},
          enumerable: true,
          writable: true,
          configurable: true,
        });
      }
      node = node[token] as Record<string, unknown>;
    });
  };
  const visit = (value: unknown) => {
    if (!value || typeof value !== "object") return;
    if (
      !Array.isArray(value) &&
      Object.keys(value).length === 1 &&
      "$input" in value
    ) {
      if (typeof value.$input === "string" && value.$input.startsWith("/"))
        insert(value.$input);
      return;
    }
    Object.values(value).forEach(visit);
  };
  visit(mapping);
  return result;
}
