import time
import json
import anthropic
from typing import TypeVar
from pydantic import BaseModel

client = anthropic.Anthropic()

T = TypeVar("T", bound=BaseModel)


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


class BookingAction(BaseModel):
    """Decision made by the booking agent for one inbound reply."""
    action: str            # "reply" | "book" | "escalate" | "unsubscribe" | "ignore"
    summary: str           # one-line summary of the prospect's message
    reply_subject: str = ""
    reply_body: str = ""   # the email to send back (for "reply" and "book")
    # For action == "book": which slot they agreed to (must be one of the offered slots)
    slot_starts_at: str = ""   # "YYYY-MM-DDTHH:MM"
    slot_ends_at: str = ""
    service: str = ""          # what they want done
    urgent: bool = False


def structured_call(
    model: str,
    system: str,
    user: str,
    output_type: type[T],
    max_tokens: int = 1024,
) -> T:
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

    def _call() -> T:
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
