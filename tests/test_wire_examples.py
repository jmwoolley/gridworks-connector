"""Independent serialized review artifacts must agree with the shipped decoder."""

import json
from pathlib import Path

import jsonschema
import pytest

from custom_components.gridworks_connector.protocol import Message, PAYLOADS

ROOT = Path(__file__).resolve().parents[1] / "docs/proposed-sema"


@pytest.mark.parametrize("kind", sorted(PAYLOADS))
def test_review_example_is_valid_wire_artifact(kind):
    stem = "gw.thermal." + kind + ".000"
    example = json.loads((ROOT / (stem + ".example.json")).read_text())
    schema = json.loads((ROOT / (stem + ".schema.json")).read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(example, schema)
    message = Message.model_validate(example)
    assert message.shadow is True and message.kind == kind
    assert message.model_dump(by_alias=True) == example
