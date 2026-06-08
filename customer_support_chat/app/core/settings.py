from os import environ
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENAI_API_KEY: str = environ.get("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = environ.get("OPENAI_BASE_URL", "")
    
    # Model configuration for cost optimization
    OPENAI_MODEL: str = environ.get("OPENAI_MODEL", "gpt-4o")
    MAX_TOKENS: int = int(environ.get("MAX_TOKENS", "1000"))  # Limit tokens to control costs
    
    DATA_PATH: str = "./customer_support_chat/data"
    LOG_LEVEL: str = environ.get("LOG_LEVEL", "DEBUG")
    SQLITE_DB_PATH: str = environ.get(
        "SQLITE_DB_PATH", "./customer_support_chat/data/travel2.sqlite"
    )
    QDRANT_URL: str = environ.get("QDRANT_URL", "http://localhost:6333")
    QDRANT_KEY: str = environ.get("QDRANT_KEY", "")
    RECREATE_COLLECTIONS: bool = environ.get("RECREATE_COLLECTIONS", "False")
    LIMIT_ROWS: int = environ.get("LIMIT_ROWS", "100")
    
    # WooCommerce API Settings
    # WOOCOMMERCE_API_URL should be the WordPress base URL (e.g., "https://yourstore.com")
    # The system will automatically append "/wp-json/wc/v3" to create the full API endpoint
    WOOCOMMERCE_CONSUMER_KEY: str = environ.get("WOOCOMMERCE_CONSUMER_KEY", "ck_765a8cd93905a33d316d9c38b3e76ba29b507b90")
    WOOCOMMERCE_CONSUMER_SECRET: str = environ.get("WOOCOMMERCE_CONSUMER_SECRET", "cs_41958dc3244fa0684cb477167f7e4c3c5187da90")
    WOOCOMMERCE_API_URL: str = environ.get("WOOCOMMERCE_API_URL", "https://ecom-jackson01080888-teozf.wpcomstaging.com/wp-json/wc/v3")
    
    # Form Submission API Settings
    FORM_SUBMISSION_API_URL: str = environ.get("FORM_SUBMISSION_API_URL", "")
    
    # Blog Search API Settings
    BLOG_SEARCH_API_URL: str = environ.get("BLOG_SEARCH_API_URL", "")

def get_settings():
    return Config()