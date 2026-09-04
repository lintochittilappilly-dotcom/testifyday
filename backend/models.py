import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, EmailStr


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def gen_id(prefix: str = ""):
    return f"{prefix}{uuid.uuid4().hex[:16]}"


# ---------- Auth ----------
class RegisterInput(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class GoogleSessionInput(BaseModel):
    credential: str  # Google ID token (JWT) from Google Identity Services


class ForgotPasswordInput(BaseModel):
    email: EmailStr


class ResetPasswordInput(BaseModel):
    token: str
    password: str = Field(min_length=6)


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None


# ---------- Workspace ----------
class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    button_color: Optional[str] = None


class OnboardingInput(BaseModel):
    business_name: str
    primary_color: Optional[str] = "#ff5722"
    logo_url: Optional[str] = None
    collection_name: Optional[str] = "Customer Testimonials"


# ---------- Collection ----------
class CollectionInput(BaseModel):
    name: str
    slug: Optional[str] = None
    headline: Optional[str] = "We'd love to hear from you!"
    description: Optional[str] = "Your feedback helps us help more people."
    logo_url: Optional[str] = None
    brand_color: Optional[str] = "#ff5722"
    background_color: Optional[str] = "#0a0a0a"
    welcome_video_url: Optional[str] = None
    allow_video: bool = True
    allow_text: bool = True
    require_email: bool = True
    require_company: bool = False
    require_role: bool = False
    collect_rating: bool = True
    custom_questions: List[str] = []
    thank_you_message: Optional[str] = "Thank you! Your testimonial has been submitted successfully."
    redirect_url: Optional[str] = None
    published: bool = False


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    headline: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    brand_color: Optional[str] = None
    background_color: Optional[str] = None
    welcome_video_url: Optional[str] = None
    allow_video: Optional[bool] = None
    allow_text: Optional[bool] = None
    require_email: Optional[bool] = None
    require_company: Optional[bool] = None
    require_role: Optional[bool] = None
    collect_rating: Optional[bool] = None
    custom_questions: Optional[List[str]] = None
    thank_you_message: Optional[str] = None
    redirect_url: Optional[str] = None
    published: Optional[bool] = None


# ---------- Testimonial ----------
class TestimonialSubmit(BaseModel):
    first_name: str
    last_name: Optional[str] = ""
    email: Optional[str] = ""
    company: Optional[str] = ""
    role: Optional[str] = ""
    avatar_url: Optional[str] = None
    website: Optional[str] = ""
    text: Optional[str] = ""
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    video_thumbnail_url: Optional[str] = None
    rating: Optional[int] = None
    consent: bool = False
    custom_answers: Dict[str, str] = {}
    recaptcha_token: Optional[str] = None
    honeypot: Optional[str] = ""  # spam trap


class TestimonialUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    text: Optional[str] = None
    image_url: Optional[str] = None
    rating: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    featured: Optional[bool] = None
    tags: Optional[List[str]] = None


class StatusInput(BaseModel):
    status: str


class TagInput(BaseModel):
    tag: str


# ---------- Widget ----------
class WidgetInput(BaseModel):
    name: str
    type: str = "grid"  # grid | carousel | single | masonry | video_wall
    configuration: Dict[str, Any] = {}


class WidgetUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None


class AnalyticsEventInput(BaseModel):
    event_type: str
    widget_id: Optional[str] = None
    collection_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ManualImportInput(BaseModel):
    first_name: str
    last_name: Optional[str] = ""
    company: Optional[str] = ""
    role: Optional[str] = ""
    avatar_url: Optional[str] = None
    text: str
    rating: Optional[int] = None
    source: Optional[str] = "Imported"
    featured: bool = False


class GoogleImportInput(BaseModel):
    query: str


class SettingsInput(BaseModel):
    recaptcha_site_key: Optional[str] = None
    recaptcha_secret_key: Optional[str] = None
    resend_api_key: Optional[str] = None
    sender_email: Optional[str] = None
    google_places_api_key: Optional[str] = None
    checkout_coupon_id: Optional[str] = None
    promo_banner: Optional[str] = None
    plans_override: Optional[List[Dict[str, Any]]] = None
    video_limits: Optional[Dict[str, Any]] = None
    admin_notify_mode: Optional[Literal["instant", "daily", "off"]] = None


class CheckoutInput(BaseModel):
    lookup_key: str
    origin_url: str


class PortalInput(BaseModel):
    origin_url: str


class InviteInput(BaseModel):
    email: EmailStr
    role: str = "member"  # admin | member


class SwitchWorkspaceInput(BaseModel):
    workspace_id: str


class DomainInput(BaseModel):
    domain: str
