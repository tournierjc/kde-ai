import json

from training.chat_normalize import normalize_message, normalize_record


def test_tool_arguments_parsed_to_mapping():
    msg = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "1",
                "type": "function",
                "function": {"name": "system_info", "arguments": "{}"},
            }
        ],
    }
    out = normalize_message(msg)
    assert out["tool_calls"][0]["function"]["arguments"] == {}


def test_dpo_record_normalizes_chosen():
    rec = {
        "messages": [{"role": "user", "content": "hi"}],
        "chosen": {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "run_readonly_cmd",
                        "arguments": json.dumps({"name": "id"}),
                    }
                }
            ],
        },
        "rejected": {"role": "assistant", "content": "guess"},
    }
    out = normalize_record(rec)
    args = out["chosen"]["tool_calls"][0]["function"]["arguments"]
    assert args == {"name": "id"}
