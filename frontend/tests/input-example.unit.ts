import { test } from "node:test";
import assert from "node:assert/strict";
import { inputExample } from "../src/pages/input-example.ts";

test("URL mappings ask for URL only, leaving request constants out", () => {
  assert.deepEqual(
    inputExample({
      url: { $input: "/url" },
      lang: "auto",
      options: ["simple"],
    }),
    { url: "" },
  );
});

test("nested and repeated pointers share one input object", () => {
  assert.deepEqual(
    inputExample({
      title: { $input: "/meta/title" },
      text: { $input: "/meta/text" },
      duplicate: { $input: "/meta/title" },
    }),
    { meta: { title: "", text: "" } },
  );
});

test("whole input substitutions and static requests do not invent fields", () => {
  assert.deepEqual(inputExample({ $input: "" }), {});
  assert.deepEqual(inputExample({ lang: "de" }), {});
  assert.deepEqual(inputExample({ $input: "/ignored", constant: true }), {});
});

test("pointer escaping and substitutions nested inside arrays are supported", () => {
  assert.deepEqual(inputExample([{ $input: "/a~1b/~0value" }]), {
    "a/b": { "~value": "" },
  });
});

test("parent and child pointers do not erase each other", () => {
  for (const mapping of [
    [{ $input: "/meta" }, { $input: "/meta/title" }],
    [{ $input: "/meta/title" }, { $input: "/meta" }],
  ]) {
    assert.deepEqual(inputExample(mapping), { meta: { title: "" } });
  }
});

test("prototype names are ordinary data fields", () => {
  const result = inputExample([
    { $input: "/__proto__/title" },
    { $input: "/constructor/prototype/name" },
  ]);
  assert.deepEqual(
    result,
    JSON.parse(
      '{"__proto__":{"title":""},"constructor":{"prototype":{"name":""}}}',
    ),
  );
  assert.equal(({} as Record<string, unknown>)["title"], undefined);
});
