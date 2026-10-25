import assert from "node:assert/strict";
import { bindAdnexPanel } from "../frontend/app/adnex.js";

const panel = bindAdnexPanel({ querySelector: () => null }, {});

assert.doesNotThrow(() => panel.disable());
assert.doesNotThrow(() => panel.destroy());
assert.doesNotThrow(() => panel.resetForSide("R"));
assert.doesNotThrow(() => panel.setEditable(false));

console.log("PASS: viewer without ADNEX keeps the lease-loss interface safe");
