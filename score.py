import sys
import db
import llm
from config import LLM

SCORING_SYSTEM_PROMPT = """You are a lead-scoring assistant for SqueegeeGuy, a window cleaning and pressure washing
business in Tucson, AZ. Score how well this business fits as a potential commercial client.

Scoring criteria (fit_score 0-100):
- 80-100: Ideal client — customer-facing storefront with lots of glass, food service,
  medical/dental (hygiene-critical), car dealership, hotel. High likelihood of recurring need.
- 60-79: Good fit — office building, gym, retail store, property manager with multiple
  units. Moderate recurring potential.
- 40-59: Possible fit — service business with modest exterior, church, daycare.
  One-time or seasonal need likely.
- 0-39: Poor fit — home-based business, no physical storefront, already has cleaning
  service mentioned on site, outside Tucson metro.

For service_pitch: choose "window_cleaning" if the business has significant glass/windows,
"pressure_washing" if they have parking lots/sidewalks/exterior surfaces but minimal glass,
"both" if both apply.

For personalization_hook: reference something SPECIFIC you can see from their business info —
their name, location, type of business, rating, or anything that shows this isn't a mass email.
One sentence max."""

SCORING_USER_TEMPLATE = """Business: {name}
Address: {address}
Website: {website}
Phone: {phone}
Rating: {rating}
Type: {types}

Score this business as a potential window cleaning / pressure washing client."""


def score_lead(lead: dict) -> llm.LeadScore:
    return llm.structured_call(
        model=LLM.scoring_model,
        system=SCORING_SYSTEM_PROMPT,
        user=SCORING_USER_TEMPLATE.format(
            name=lead.get("name", ""),
            address=lead.get("address", ""),
            website=lead.get("website", ""),
            phone=lead.get("phone", ""),
            rating=lead.get("rating", "N/A"),
            types=lead.get("types", ""),
        ),
        output_type=llm.LeadScore,
    )


if __name__ == "__main__":
    lead_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    leads = db.get_leads_by_status("enriched")
    lead = next((l for l in leads if l["id"] == lead_id), None)
    if not lead:
        # Try any status
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        lead = dict(row) if row else None
    if not lead:
        print(f"Lead ID {lead_id} not found")
        sys.exit(1)
    result = score_lead(lead)
    print(f"Score: {result.fit_score}")
    print(f"Pitch: {result.service_pitch}")
    print(f"Recurring: {result.recurring_potential}")
    print(f"Hook: {result.personalization_hook}")
    print(f"Reasoning: {result.reasoning}")
