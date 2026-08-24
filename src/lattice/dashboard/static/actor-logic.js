"use strict";

// --- Actor identity logic (normalize / classify / display) ---
// Pure actor parsing for the dashboard's assignee/creator filters and chips.
// Task actor fields (`assigned_to`, `created_by`) carry one of three shapes:
//   - legacy "prefix:identifier" strings (e.g. "agent:claude", "human:atin"),
//   - structured ActorIdentity dicts (src/lattice/core/actors.py) — human iff
//     model === "human", display key is the serialized `name`,
//   - null/undefined (unassigned / unknown).
// Every shape is normalized here to one canonical key string, which is what
// filter options, equality tests, and the ?assigned= / ?created= URL params
// use everywhere. None of these functions may throw on junk input — a
// malformed actor on one task must never blank the whole board.
//
// Like lane-logic.js, this is a classic browser script loaded WITHOUT defer
// before the inline IIFE (names become globals), with a CommonJS export guard
// so node:test can require it (tests/js/actor-logic.test.js, bridged into
// pytest). Keep it ES5-flavored (var, function expressions) to match.

// Sentinel filter value meaning "match tasks with no assignee". Lives here so
// the matching rule (actorMatchesFilter) and its tests own the semantics.
var ACTOR_UNASSIGNED = "__unassigned__";

// Normalize any actor shape to a canonical key string, or null.
// Strings pass through as-is (empty/blank → null). Dicts mirror
// ActorIdentity.to_legacy_actor() but key on the serialized `name`:
// model === "human" → "human:<name>", anything else → "agent:<name>".
function normalizeActor(a) {
  if (a == null) return null;
  if (typeof a === "string") return a === "" ? null : a;
  if (typeof a === "object" && !Array.isArray(a)) {
    var name = (typeof a.name === "string") ? a.name : "";
    if (!name) return null;
    return (a.model === "human" ? "human" : "agent") + ":" + name;
  }
  return null;
}

// Classify a canonical key by its prefix. Valid Lattice prefixes are
// {agent, human, team, dashboard} (src/lattice/core/ids.py) but actor ids are
// free-form — anything unrecognized (including no prefix at all) buckets as
// "other", never throws.
function actorKind(key) {
  if (typeof key !== "string") return "other";
  var idx = key.indexOf(":");
  if (idx <= 0) return "other";
  var prefix = key.slice(0, idx);
  if (prefix === "human" || prefix === "agent" || prefix === "team") return prefix;
  return "other";
}

// Short display name: dicts use their `name` field; strings drop the
// "prefix:" (only when a non-empty prefix exists); null/junk → "".
function actorDisplayName(a) {
  if (a == null) return "";
  if (typeof a === "object" && !Array.isArray(a)) {
    return (typeof a.name === "string") ? a.name : "";
  }
  if (typeof a !== "string") return "";
  var idx = a.indexOf(":");
  return idx > 0 ? a.slice(idx + 1) : a;
}

// Full identity string for tooltips and detail-panel text. Strings pass
// through unchanged (the legacy id IS the full identity); dicts join
// name · model · framework (whichever are present); null/junk → "". For human
// dicts (model === "human") the model segment is omitted — the chip's dot
// shape already conveys kind, and "Atin-1 · human" reads as noise.
function actorTooltip(a) {
  if (a == null) return "";
  if (typeof a === "string") return a;
  if (typeof a === "object" && !Array.isArray(a)) {
    var parts = [];
    if (typeof a.name === "string" && a.name) parts.push(a.name);
    if (typeof a.model === "string" && a.model && a.model !== "human") parts.push(a.model);
    if (typeof a.framework === "string" && a.framework) parts.push(a.framework);
    return parts.join(" · ");
  }
  return "";
}

// Deterministic hue (0–359) from a canonical key, for the chip's colored dot.
// Classic 31-multiplier string hash, kept in uint32 via >>> 0.
function actorHue(key) {
  if (typeof key !== "string") return 0;
  var h = 0;
  for (var i = 0; i < key.length; i++) {
    h = (h * 31 + key.charCodeAt(i)) >>> 0;
  }
  return h % 360;
}

// The one filter-matching rule: no filter matches everything; the unassigned
// sentinel matches tasks whose actor normalizes to null; otherwise compare
// canonical keys. Used for both the assignee and creator filters.
function actorMatchesFilter(actorValue, filterKey) {
  if (!filterKey) return true;
  var key = normalizeActor(actorValue);
  if (filterKey === ACTOR_UNASSIGNED) return key === null;
  return key === filterKey;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { ACTOR_UNASSIGNED, normalizeActor, actorKind,
    actorDisplayName, actorTooltip, actorHue, actorMatchesFilter };
}
