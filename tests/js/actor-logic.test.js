"use strict";

// Tests for the dashboard's pure actor identity logic (actor-logic.js). Runs
// under node's built-in test runner — zero npm deps, no package.json. Bridged
// into pytest via tests/test_dashboard/test_js_actor_logic.py so
// `uv run pytest` stays the single entrypoint. Run standalone with:
//   node --test tests/js/actor-logic.test.js
//
// Actor fields carry three shapes (legacy "prefix:id" strings, structured
// ActorIdentity dicts, null) — see src/lattice/core/actors.py. The contract
// under test: every shape normalizes to one canonical key, nothing throws on
// junk, and the filter-matching rule (incl. the unassigned sentinel) is total.

const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const actor = require(
  path.join(__dirname, "..", "..", "src", "lattice", "dashboard", "static", "actor-logic.js")
);
const {
  ACTOR_UNASSIGNED,
  normalizeActor,
  actorKind,
  actorDisplayName,
  actorTooltip,
  actorHue,
  actorMatchesFilter,
} = actor;

// A realistic structured ActorIdentity as serialized into task payloads.
const AGENT_DICT = {
  name: "Meridian-1",
  base_name: "Meridian",
  serial: 1,
  session: "sess_01KH00000000000000000000",
  model: "claude-opus-4",
  framework: "claude-code",
};
const HUMAN_DICT = { name: "Atin-1", base_name: "Atin", serial: 1, session: "s", model: "human" };

// --- normalizeActor: three shapes → one canonical key ------------------------------

test("normalizeActor: legacy strings pass through as-is", () => {
  assert.strictEqual(normalizeActor("agent:claude"), "agent:claude");
  assert.strictEqual(normalizeActor("human:atin"), "human:atin");
  assert.strictEqual(normalizeActor("team:core"), "team:core");
  // No prefix stripping, no reformatting — the string IS the key.
  assert.strictEqual(normalizeActor("dashboard:web"), "dashboard:web");
  assert.strictEqual(normalizeActor("freeform"), "freeform");
});

test("normalizeActor: dicts key on serialized name, human iff model === 'human'", () => {
  assert.strictEqual(normalizeActor(AGENT_DICT), "agent:Meridian-1");
  assert.strictEqual(normalizeActor(HUMAN_DICT), "human:Atin-1");
  // Any non-"human" model is an agent — mirrors ActorIdentity.is_human.
  assert.strictEqual(normalizeActor({ name: "X-1", model: "gpt-5" }), "agent:X-1");
  assert.strictEqual(normalizeActor({ name: "X-1" }), "agent:X-1");
});

test("normalizeActor: null / undefined / junk → null, never throws", () => {
  assert.strictEqual(normalizeActor(null), null);
  assert.strictEqual(normalizeActor(undefined), null);
  assert.strictEqual(normalizeActor(""), null);
  assert.strictEqual(normalizeActor(42), null);
  assert.strictEqual(normalizeActor(true), null);
  assert.strictEqual(normalizeActor([]), null);
  assert.strictEqual(normalizeActor(["agent:x"]), null);
  // Dict without a usable name has no identity to key on.
  assert.strictEqual(normalizeActor({}), null);
  assert.strictEqual(normalizeActor({ name: "" }), null);
  assert.strictEqual(normalizeActor({ name: 7, model: "human" }), null);
});

test("normalizeActor: canonical-key equality unifies string and dict shapes", () => {
  // The same mind seen as a legacy string on one task and a dict on another
  // must land on the same key, or filters silently split one actor in two.
  assert.strictEqual(normalizeActor("agent:Meridian-1"), normalizeActor(AGENT_DICT));
  assert.strictEqual(normalizeActor("human:Atin-1"), normalizeActor(HUMAN_DICT));
  // But a human dict never collides with an agent string of the same name.
  assert.notStrictEqual(normalizeActor("agent:Atin-1"), normalizeActor(HUMAN_DICT));
});

// --- actorKind: prefix classification ------------------------------------------------

test("actorKind: known prefixes classify; everything else is 'other'", () => {
  assert.strictEqual(actorKind("human:atin"), "human");
  assert.strictEqual(actorKind("agent:claude"), "agent");
  assert.strictEqual(actorKind("team:core"), "team");
  // dashboard: is a valid Lattice prefix but has no bucket of its own.
  assert.strictEqual(actorKind("dashboard:web"), "other");
  assert.strictEqual(actorKind("robot:r2d2"), "other");
  assert.strictEqual(actorKind("no-prefix"), "other");
  assert.strictEqual(actorKind(":empty-prefix"), "other");
  assert.strictEqual(actorKind(""), "other");
  assert.strictEqual(actorKind(null), "other");
  assert.strictEqual(actorKind(undefined), "other");
  assert.strictEqual(actorKind(123), "other");
});

// --- actorDisplayName ----------------------------------------------------------------

test("actorDisplayName: strings drop the prefix, dicts use name, null → ''", () => {
  assert.strictEqual(actorDisplayName("agent:claude"), "claude");
  assert.strictEqual(actorDisplayName("human:atin"), "atin");
  // Only the first colon splits — identifiers may contain colons themselves.
  assert.strictEqual(actorDisplayName("agent:ns:sub"), "ns:sub");
  assert.strictEqual(actorDisplayName("no-prefix"), "no-prefix");
  assert.strictEqual(actorDisplayName(":x"), ":x");
  assert.strictEqual(actorDisplayName(AGENT_DICT), "Meridian-1");
  assert.strictEqual(actorDisplayName(HUMAN_DICT), "Atin-1");
  assert.strictEqual(actorDisplayName(null), "");
  assert.strictEqual(actorDisplayName(undefined), "");
  assert.strictEqual(actorDisplayName({}), "");
  assert.strictEqual(actorDisplayName(9), "");
});

// --- actorTooltip --------------------------------------------------------------------

test("actorTooltip: strings unchanged; dicts join name/model/framework; null → ''", () => {
  assert.strictEqual(actorTooltip("agent:claude"), "agent:claude");
  assert.strictEqual(actorTooltip(AGENT_DICT), "Meridian-1 · claude-opus-4 · claude-code");
  assert.strictEqual(actorTooltip(HUMAN_DICT), "Atin-1 · human");
  assert.strictEqual(actorTooltip({ name: "Solo-1" }), "Solo-1");
  assert.strictEqual(actorTooltip(null), "");
  assert.strictEqual(actorTooltip(undefined), "");
  assert.strictEqual(actorTooltip({}), "");
});

// --- actorHue ------------------------------------------------------------------------

test("actorHue: deterministic, in [0, 360), null-safe", () => {
  const keys = ["agent:claude", "human:atin", "team:core", "agent:Meridian-1", "x"];
  keys.forEach((k) => {
    const h = actorHue(k);
    assert.strictEqual(h, actorHue(k), "same key must hash to the same hue");
    assert.ok(Number.isInteger(h) && h >= 0 && h < 360, `hue out of range for ${k}: ${h}`);
  });
  // Distinct keys should (for these fixtures) get distinct hues — the dot
  // color is only useful if it separates the common cases.
  assert.notStrictEqual(actorHue("agent:claude"), actorHue("human:atin"));
  assert.strictEqual(actorHue(null), 0);
  assert.strictEqual(actorHue(undefined), 0);
  assert.strictEqual(actorHue(""), 0);
});

test("actorHue: long keys stay in uint32 (no negative hues from overflow)", () => {
  const long = "agent:" + "x".repeat(500);
  const h = actorHue(long);
  assert.ok(h >= 0 && h < 360);
});

// --- actorMatchesFilter ---------------------------------------------------------------

test("actorMatchesFilter: no filter matches everything", () => {
  assert.strictEqual(actorMatchesFilter("agent:claude", null), true);
  assert.strictEqual(actorMatchesFilter(null, null), true);
  assert.strictEqual(actorMatchesFilter(AGENT_DICT, ""), true);
});

test("actorMatchesFilter: canonical-key comparison across shapes", () => {
  assert.strictEqual(actorMatchesFilter("agent:Meridian-1", "agent:Meridian-1"), true);
  // Dict actor matches the canonical key its normalization produces.
  assert.strictEqual(actorMatchesFilter(AGENT_DICT, "agent:Meridian-1"), true);
  assert.strictEqual(actorMatchesFilter(HUMAN_DICT, "human:Atin-1"), true);
  assert.strictEqual(actorMatchesFilter(AGENT_DICT, "agent:other"), false);
  assert.strictEqual(actorMatchesFilter(null, "agent:claude"), false);
});

test("actorMatchesFilter: unassigned sentinel matches only null-normalized actors", () => {
  assert.strictEqual(actorMatchesFilter(null, ACTOR_UNASSIGNED), true);
  assert.strictEqual(actorMatchesFilter(undefined, ACTOR_UNASSIGNED), true);
  assert.strictEqual(actorMatchesFilter("", ACTOR_UNASSIGNED), true);
  assert.strictEqual(actorMatchesFilter({}, ACTOR_UNASSIGNED), true);
  assert.strictEqual(actorMatchesFilter("agent:claude", ACTOR_UNASSIGNED), false);
  assert.strictEqual(actorMatchesFilter(AGENT_DICT, ACTOR_UNASSIGNED), false);
  // A task literally assigned the sentinel string is pathological; the rule
  // still treats the sentinel filter as "no assignee", not a key equality.
  assert.strictEqual(actorMatchesFilter(ACTOR_UNASSIGNED, ACTOR_UNASSIGNED), false);
});
