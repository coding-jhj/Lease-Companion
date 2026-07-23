from lease_companion_ai.providers.gemini_schema import clean_gemini_response_schema


def test_clean_gemini_response_schema_removes_unsupported_keys_recursively():
    source = {
        "title": "Root",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "value": {
                "title": "Value",
                "type": "string",
                "default": "example",
            },
            "items": [
                {"type": "integer", "additionalProperties": True},
            ],
        },
    }

    cleaned = clean_gemini_response_schema(source)

    assert cleaned == {
        "type": "object",
        "properties": {
            "value": {"type": "string"},
            "items": [{"type": "integer"}],
        },
    }
    assert source["title"] == "Root"
