from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass(frozen=True)
class BusinessProfile:
    name: str = "SqueegeeGuy"
    owner_name: str = "Michael"
    services: tuple[str, ...] = ("window cleaning", "pressure washing")
    service_area: str = "Tucson, AZ"
    phone: str = ""
    website: str = "https://squeegeeguy.com"
    physical_address: str = ""   # CAN-SPAM footer — full street address required
    sending_domain: str = ""     # e.g., "gosqueegeeguy.com"


@dataclass(frozen=True)
class TargetConfig:
    categories: tuple[str, ...] = (
        "restaurants",
        "car dealerships",
        "medical offices",
        "dental offices",
        "veterinary clinics",
        "retail stores",
        "hotels",
        "gyms and fitness centers",
        "office buildings",
        "property management companies",
        "real estate offices",
        "banks and credit unions",
        "day care centers",
        "churches",
        "auto repair shops",
    )
    location: str = "Tucson, AZ"
    min_fit_score: int = 60
    max_prospects_per_run: int = 50


@dataclass(frozen=True)
class SendConfig:
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    from_name: str = "Michael from SqueegeeGuy"
    from_email: str = os.getenv("SMTP_USER", "")
    warmup_schedule: dict[int, int] = field(default_factory=lambda: {
        1: 5, 2: 10, 3: 20, 4: 30, 5: 50,
    })
    followup_delays_days: tuple[int, ...] = (3, 7)
    inter_email_delay_range: tuple[int, int] = (30, 90)  # seconds


@dataclass(frozen=True)
class LLMConfig:
    scoring_model: str = "claude-haiku-4-5"
    drafting_model: str = "claude-sonnet-4-6"
    reply_model: str = "claude-haiku-4-5"


@dataclass(frozen=True)
class DigestConfig:
    owner_email: str = os.getenv("OWNER_EMAIL", "")


BUSINESS = BusinessProfile()
TARGET = TargetConfig()
SEND = SendConfig()
LLM = LLMConfig()
DIGEST = DigestConfig()

PLACES_API_KEY: str = os.getenv("GOOGLE_PLACES_API_KEY", "")
