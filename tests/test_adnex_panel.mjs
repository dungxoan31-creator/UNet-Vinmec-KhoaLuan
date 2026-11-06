import assert from "node:assert/strict";
import test from "node:test";
import {
  bindAdnexPanel,
  isRenderableAdnexEvaluation,
} from "../frontend/app/adnex.js";

const validEvaluation = () => ({
  model: "IOTA ADNEX",
  status: "EVALUATED_RUO",
  eligibility_status: "ELIGIBLE",
  model_variant: "WITHOUT_CA125",
  probabilities: {
    benign: 0.8,
    borderline: 0.1,
    stage_i_primary_malignancy: 0.05,
    stage_ii_iv_primary_malignancy: 0.03,
    secondary_metastatic: 0.02,
  },
  total_malignancy_probability: 0.2,
});

test("viewer without ADNEX keeps lease-loss controls safe", () => {
  const panel = bindAdnexPanel({ querySelector: () => null }, {});
  assert.doesNotThrow(() => panel.disable());
  assert.doesNotThrow(() => panel.destroy());
  assert.doesNotThrow(() => panel.resetForSide("R"));
  assert.doesNotThrow(() => panel.setEditable(false));
});

test("ADNEX renders only a complete, bounded, internally consistent probability vector", () => {
  assert.equal(isRenderableAdnexEvaluation(validEvaluation()), true);
});

test("ADNEX output is withheld for malformed or inconsistent probabilities", () => {
  const invalidCases = [
    (value) => { value.probabilities.benign = 1.01; },
    (value) => { value.probabilities.benign = Number.NaN; },
    (value) => { value.probabilities.benign = 0.7; },
    (value) => { delete value.probabilities.secondary_metastatic; },
    (value) => { value.probabilities.unexpected = 0; },
    (value) => { value.total_malignancy_probability = 0.9; },
    (value) => { value.total_malignancy_probability = -0.1; },
    (value) => { value.total_malignancy_probability = Number.POSITIVE_INFINITY; },
    (value) => { value.eligibility_status = "NOT_ELIGIBLE"; },
    (value) => { value.model_variant = "UNKNOWN"; },
  ];

  for (const corrupt of invalidCases) {
    const value = validEvaluation();
    corrupt(value);
    assert.equal(isRenderableAdnexEvaluation(value), false);
  }
});
