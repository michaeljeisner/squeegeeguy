import time
import json
import anthropic
from pydantic import BaseModel

client = anthropic.Anthropic()


class LeadScore(BaseModel):
    fit_score: int
    service_pitch: str        # "window_cleaning" | "pressure_washing" | "both"
    recurring_potential: str  # "high" | "medium" | "low"
    personalization_hook: str
    reasoning: str


class DraftedEmail(BaseModel):
    subject: str
    body: str
    followup_1_subject: str
    followup_1_body: str
    followup_2_subject: str
    followup_2_body: str


class ReplyClassification(BaseModel):
    category: str   # "interested" | "not_interested" | "unsubscribe" | "out_of_office" | "question" | "other"
    summary: str
    urgent: bool


def structured_call(
    model: str,
    system: str,
    user: str,
    output_type: type[BaseModel],
    max_tokens: int = 1024,
) -> BaseModel:
    """
    Call Claude with structured output via tool-use extraction.
    Retries once on rate-limit or connection error.
    """
    tool_name = output_type.__name__
    schema = output_type.model_json_schema()
    # Remove unsupported JSON Schema keys that Anthropic rejects
    schema.pop("title", None)

    tools = [
        {
            "name": tool_name,
            "description": f"Return a {tool_name} result.",
            "input_schema": schema,
        }
    ]

    def _call() -> BaseModel:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=tools,
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return output_type.model_validate(block.input)
        raise ValueError(f"Claude did not call {tool_name}. Response: {response}")

    try:
        return _call()
    except (anthropic.RateLimitError, anthropic.APIConnectionError):
        time.sleep(5)
        return _call()
