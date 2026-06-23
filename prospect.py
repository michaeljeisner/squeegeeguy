import json
import httpx
from config import TARGET, PLACES_API_KEY

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.websiteUri,places.nationalPhoneNumber,places.rating,places.types"
)
MAX_PAGES = 3


def search_category(category: str, location: str, api_key: str) -> list[dict]:
    """Search Google Places for `category in location`. Follows pagination (max 3 pages)."""
    results: list[dict] = []
    next_page_token: str | None = None

    for _ in range(MAX_PAGES):
        body: dict = {"textQuery": f"{category} in {location}", "maxResultCount": 20}
        if next_page_token:
            body["pageToken"] = next_page_token

        with httpx.Client(timeout=15) as client:
            response = client.post(
                PLACES_URL,
                headers={
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": FIELD_MASK,
                    "Content-Type": "application/json",
                },
                json=body,
            )
        response.raise_for_status()
        data = response.json()

        for place in data.get("places", []):
            results.append({
                "place_id": place.get("id", ""),
                "name": place.get("displayName", {}).get("text", ""),
                "address": place.get("formattedAddress", ""),
                "website": place.get("websiteUri", ""),
                "phone": place.get("nationalPhoneNumber", ""),
                "rating": place.get("rating"),
                "types": place.get("types", []),
            })

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    # Dedup within this category call
    seen: set[str] = set()
    unique: list[dict] = []
    for r in results:
        if r["place_id"] and r["place_id"] not in seen:
            seen.add(r["place_id"])
            unique.append(r)
    return unique


def search_all_categories() -> list[dict]:
    """Search all configured categories; return combined deduped list."""
    seen: set[str] = set()
    all_leads: list[dict] = []
    api_call_count = 0

    for category in TARGET.categories:
        try:
            leads = search_category(category, TARGET.location, PLACES_API_KEY)
            api_call_count += 1
            for lead in leads:
                if lead["place_id"] and lead["place_id"] not in seen:
                    seen.add(lead["place_id"])
                    all_leads.append(lead)
        except httpx.HTTPError as e:
            print(f"[prospect] HTTP error for category '{category}': {e}")
        except Exception as e:
            print(f"[prospect] Error for category '{category}': {e}")

    print(f"[prospect] Places API calls this run: {api_call_count}")
    return all_leads


if __name__ == "__main__":
    leads = search_category("restaurants", TARGET.location, PLACES_API_KEY)
    print(f"Found {len(leads)} results")
    for lead in leads[:5]:
        print(json.dumps(lead, indent=2))
