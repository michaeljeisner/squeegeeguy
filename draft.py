import sys
import db
import llm
from config import BUSINESS, LLM

DRAFTING_SYSTEM_PROMPT = f"""You are writing a short, personalized cold email for {BUSINESS.name}, a professional window
cleaning and pressure washing service in Tucson, AZ, owned by {BUSINESS.owner_name}. The email goes
to a local business owner or manager, written in first person as {BUSINESS.owner_name}.

Rules:
- Keep the initial email under 120 words. Follow-ups under 80 words each.
- Open with the personalization hook — show you know their business.
- Pitch the specific service (windows, pressure washing, or both) naturally.
- Include a clear, low-friction CTA: "Would you be open to a quick quote?" or similar.
- Tone: friendly, professional, local. Not salesy. You're a neighbor, not a corporation.
- NEVER mention pricing in the email — that comes in the conversation.
- Follow-up 1 (sent if no reply): brief, add a new angle (seasonal, before/after, etc.).
- Follow-up 2 (sent if no reply): final touch, very short, "just checking in" energy.
- Each follow-up should feel like a natural continuation, not a repeat.
- Do NOT include any footer, unsubscribe text, or signature — the system adds those."""

DRAFTING_USER_TEMPLATE = """Write a cold email sequence for this prospect:

Business: {name}
Service to pitch: {service_pitch}
Personalization hook: {personalization_hook}
Recurring potential: {recurring_potential}

Write the initial email, then followup_1 and followup_2."""


def draft_emails(lead: dict) -> llm.DraftedEmail:
    return llm.structured_call(
        model=LLM.drafting_model,
        system=DRAFTING_SYSTEM_PROMPT,
        user=DRAFTING_USER_TEMPLATE.format(
            name=lead.get("name", ""),
            service_pitch=lead.get("service_pitch", "both"),
            personalization_hook=lead.get("personalization_hook", ""),
            recurring_potential=lead.get("recurring_potential", "medium"),
        ),
        output_type=llm.DraftedEmail,
        max_tokens=2048,
    )


if __name__ == "__main__":
    lead_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    import sqlite3
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        print(f"Lead ID {lead_id} not found")
        sys.exit(1)
    lead = dict(row)
    result = draft_emails(lead)
    print("=== INITIAL ===")
    print(f"Subject: {result.subject}")
    print(result.body)
    print("\n=== FOLLOWUP 1 ===")
    print(f"Subject: {result.followup_1_subject}")
    print(result.followup_1_body)
    print("\n=== FOLLOWUP 2 ===")
    print(f"Subject: {result.followup_2_subject}")
    print(result.followup_2_body)
