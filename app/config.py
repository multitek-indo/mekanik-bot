from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "production"
    log_level: str = "INFO"
    data_dir: str = "/app/data"

    # PostgreSQL
    database_url: str

    # Owner
    owner_wa_number: str
    owner_api_token: str

    # GOWA
    gowa_url: str = "http://gowa:3000"
    gowa_basic_auth_user: str
    gowa_basic_auth_password: str
    gowa_device_id: str = "multitek-main"
    gowa_webhook_secret: str

    # Hybrid AI: Gemini primary, Groq GPT-OSS fallback.
    ai_enabled: bool = False
    ai_primary: str = "gemini"
    ai_fallback: str = "groq"
    ai_confidence_threshold: float = 0.78
    ai_timeout_seconds: int = 30

    # Gemini - primary language/NLU provider
    gemini_enabled: bool = True
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"

    # Groq - fallback / second opinion
    groq_enabled: bool = True
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    # Legacy compatibility. Existing deployments may still use these.
    ai_base_url: str = "https://api.groq.com/openai/v1"
    ai_api_key: str = ""
    ai_model: str = "openai/gpt-oss-120b"

    # Payment / bank information shown to customers.
    payment_bank_name: str = "BCA"
    payment_bank_account: str = ""
    payment_bank_holder: str = "MULTITEK INDONESIA"
    qris_image_path: str = "/app/data/qris.png"

    # Cheap booking/travel-fee tiers. The fee is credited against successful labour.
    booking_fee_0_5km: int = 20000
    booking_fee_5_10km: int = 30000
    booking_fee_10_20km: int = 40000
    booking_fee_20_30km: int = 50000
    booking_manual_over_km: float = 30.0

    # Matching
    technician_offer_timeout_seconds: int = 600
    technician_offer_batch_size: int = 3
    technician_min_skill_level: int = 3
    technician_current_location_max_age_hours: int = 12
    max_match_distance_km: float = 50.0

    # Settlement. Only ledger calculation; transfers/refunds remain manual in MVP.
    success_platform_percent: int = 10
    fail_customer_refund_percent: int = 60
    fail_technician_percent: int = 30
    fail_platform_percent: int = 10

    # UX / safety limits
    max_machines_per_order: int = 20
    max_message_length: int = 12000


settings = Settings()
