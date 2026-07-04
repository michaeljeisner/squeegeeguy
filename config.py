from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass(frozen=True)
class BusinessProfile:
    name: str = "Squeegee Guy"
    owner_name: str = os.getenv("OWNER_NAME", "Chip")
    services: tuple[str, ...] = ("window cleaning", "pressure washing")
    service_area: str = "Tucson, AZ"
    phone: str = os.getenv("BUSINESS_PHONE", "(520) 580-5700")
    website: str = "https://squeegeeguy.com"
    # CAN-SPAM footer — full street address required on every cold email
    physical_address: str = os.getenv("BUSINESS_ADDRESS", "")
    sending_domain: str = os.getenv("SENDING_DOMAIN", "gosqueegeeguy.com")


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
    from_name: str = os.getenv("FROM_NAME", "Chip from Squeegee Guy")
    from_email: str = os.getenv("SMTP_USER", "")
    warmup_schedule: dict[int, int] = field(default_factory=lambda: {
        1: 5, 2: 10, 3: 20, 4: 30, 5: 50,
    })
    followup_delays_days: tuple[int, ...] = (3, 7)  # followup_1, followup_2 (days after initial)
    inter_email_delay_range: tuple[int, int] = (30, 90)  # seconds


@dataclass(frozen=True)
class AvailabilityConfig:
    """When the owner can take jobs. Used by the appointment-setting agent."""
    timezone: str = "America/Phoenix"          # Tucson — no DST
    workdays: tuple[int, ...] = (0, 1, 2, 3, 4, 5)  # Mon=0 ... Sat=5 (Sunday off)
    day_start_hour: int = 8                    # earliest appointment start
    day_end_hour: int = 17                     # latest appointment END
    slot_minutes: int = 120                    # default job/visit block
    min_notice_hours: int = 18                 # never book sooner than this
    max_days_out: int = 14                     # propose slots within this window
    max_auto_replies_per_lead: int = 4         # after this, escalate to owner


@dataclass(frozen=True)
class LLMConfig:
    scoring_model: str = "claude-haiku-4-5"
    drafting_model: str = "claude-sonnet-4-6"
    reply_model: str = "claude-sonnet-4-6"     # booking replies need the better model


@dataclass(frozen=True)
class DigestConfig:
    owner_email: str = os.getenv("OWNER_EMAIL", "")


BUSINESS = BusinessProfile()
TARGET = TargetConfig()
SEND = SendConfig()
AVAIL = AvailabilityConfig()
LLM = LLMConfig()
DIGEST = DigestConfig()

PLACES_API_KEY: str = os.getenv("GOOGLE_PLACES_API_KEY", "")
