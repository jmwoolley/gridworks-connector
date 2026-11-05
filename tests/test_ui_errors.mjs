import test from "node:test";
import assert from "node:assert/strict";
import { describeApiError } from "../custom_components/gridworks_connector/frontend/errors.mjs";

test("HA nested HTTP error produces readable text", () => {
  assert.equal(describeApiError({status_code:500,message:{message:"Server got itself in trouble"}}), "Home Assistant request failed (HTTP 500): Server got itself in trouble");
});
test("unknown objects never become object Object", () => {
  assert.match(describeApiError({}), /could not be completed/);
  assert.ok(!describeApiError({}).includes("[object Object]"));
});
test("ordinary errors preserve their explanation", () => {
  assert.equal(describeApiError(new Error("Session expired")), "Session expired");
});
