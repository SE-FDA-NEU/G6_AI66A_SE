from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL
from pathlib import Path
from pydantic import Field, SecretStr
from typing import Any, Literal
import ssl


def build_ssl_context(
    ssl_mode: str = "preferred",
    ssl_ca: str = "",
    ssl_cert: str = "",
    ssl_key: str = "",
    ssl_verify_cert: bool | None = None,
    ssl_verify_identity: bool | None = None,
) -> ssl.SSLContext | None:
    mode = (ssl_mode or "preferred").strip().lower()
    ca_file = ssl_ca.strip() or None
    cert_file = ssl_cert.strip() or None
    key_file = ssl_key.strip() or None
    has_explicit_opts = any(
        value is not None and value != ""
        for value in (ca_file, cert_file, key_file, ssl_verify_cert, ssl_verify_identity)
    )
    if mode == "disabled":
        return None
    if mode == "preferred" and not has_explicit_opts:
        return None

    ctx = ssl.create_default_context(cafile=ca_file)
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT

    if ssl_verify_cert is not None:
        verify_cert = bool(ssl_verify_cert)
    else:
        verify_cert = mode in ("verify_ca", "verify_identity") or bool(ca_file)

    if ssl_verify_identity is not None:
        verify_identity = bool(ssl_verify_identity)
    else:
        verify_identity = mode == "verify_identity"

    if not verify_cert:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx.check_hostname = verify_identity
        ctx.verify_mode = ssl.CERT_REQUIRED

    if cert_file:
        ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
    ctx.options |= ssl.OP_NO_SSLv2
    ctx.options |= ssl.OP_NO_SSLv3
    return ctx


class Settings(BaseSettings):
    
    DB_USER: str = "root"
    DB_HOST: str = "localhost"
    DB_PORT: str = "3306"
    DB_NAME: str = "documind_db"
    
    DB_PASSWORD: str 

    DB_SSL_MODE: Literal["disabled", "preferred", "required", "verify_ca", "verify_identity"] = "preferred"
    DB_SSL_CA: str = ""
    DB_SSL_CERT: str = ""
    DB_SSL_KEY: str = ""
    DB_SSL_VERIFY_CERT: bool | None = None
    DB_SSL_VERIFY_IDENTITY: bool | None = None
    DB_CONNECT_TIMEOUT_SECONDS: int = Field(default=10, ge=1, le=300)
    DB_READ_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=600)
    DB_WRITE_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=600)
    DB_POOL_PRE_PING: bool = True
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800, ge=30, le=86400)
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=100)
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=300)
    DB_DROP_EXTRA_TABLES: bool = False

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 # 24 hours
    STORAGE_DIR: Path = Path(__file__).resolve().parents[2] / "data" / "uploads"
    RETENTION_CLEANUP_ENABLED: bool = True
    RETENTION_CLEANUP_INTERVAL_SECONDS: int = Field(default=3600, ge=1, le=86400)
    RETENTION_CLEANUP_BATCH_SIZE: int = Field(default=100, ge=1, le=1000)
    GEMINI_API_KEY: SecretStr = SecretStr('')
    GEMINI_MODEL: str = Field(default='gemini-3.5-flash', pattern=r'^gemini-[a-z0-9.-]+$')
    # Character budget for source excerpts; not an exact tokenizer count.
    GEMINI_MAX_INPUT_CHARS: int = Field(default=24000, ge=500, le=100000)
    GEMINI_MAP_CONCURRENCY: int = Field(default=2, ge=1, le=4)
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=4096, ge=256, le=8192)
    GEMINI_REQUEST_TIMEOUT_SECONDS: int = Field(default=45, ge=1, le=300)
    GEMINI_CACHE_ENABLED: bool = True
    ANALYSIS_PROVIDER: Literal['gemini', 'groq'] = 'gemini'
    GROQ_FALLBACK_ENABLED: bool = False
    GROQ_API_KEY: SecretStr = SecretStr('')
    GROQ_MODEL: str = Field(default='qwen/qwen3.8-27b', min_length=1, max_length=150,
                            pattern=r'^[a-zA-Z0-9][a-zA-Z0-9/_.-]*$')
    GROQ_REQUEST_TIMEOUT_SECONDS: int = Field(default=45, ge=1, le=300)
    GROQ_MAX_INPUT_CHARS: int = Field(default=8000, ge=500, le=100000)
    GROQ_MAX_OUTPUT_TOKENS: int = Field(default=1000, ge=256, le=8192)
    GROQ_REASONING_EFFORT: Literal['none', 'low', 'medium', 'high'] = 'low'
    SEARCH_EMBEDDING_MODEL: str = Field(default='gemini-embedding-001', max_length=100, pattern=r'^gemini-[a-z0-9.-]+$')
    SEARCH_EMBEDDING_DIMENSIONS: int = Field(default=768, ge=128, le=3072)
    SEARCH_EMBEDDING_TIMEOUT_SECONDS: int = Field(default=15, ge=1, le=60)

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", env_file_encoding="utf-8")

    @property
    def DATABASE_URL(self) -> str:
        return URL.create("mysql+pymysql", username=self.DB_USER, password=self.DB_PASSWORD,
                          host=self.DB_HOST, port=int(self.DB_PORT), database=self.DB_NAME,
                          query={"charset": "utf8mb4"}).render_as_string(hide_password=False)

    @property
    def db_connect_args(self) -> dict[str, Any]:
        args: dict[str, Any] = {
            "charset": "utf8mb4",
            "connect_timeout": int(self.DB_CONNECT_TIMEOUT_SECONDS),
            "read_timeout": int(self.DB_READ_TIMEOUT_SECONDS),
            "write_timeout": int(self.DB_WRITE_TIMEOUT_SECONDS),
        }
        if self.DB_SSL_MODE == "disabled":
            args["ssl_disabled"] = True
        else:
            ssl_ctx = build_ssl_context(
                ssl_mode=self.DB_SSL_MODE,
                ssl_ca=self.DB_SSL_CA,
                ssl_cert=self.DB_SSL_CERT,
                ssl_key=self.DB_SSL_KEY,
                ssl_verify_cert=self.DB_SSL_VERIFY_CERT,
                ssl_verify_identity=self.DB_SSL_VERIFY_IDENTITY,
            )
            if ssl_ctx is not None:
                args["ssl"] = ssl_ctx
        return args

    @property
    def engine_options(self) -> dict[str, Any]:
        return {
            "pool_pre_ping": bool(self.DB_POOL_PRE_PING),
            "pool_recycle": int(self.DB_POOL_RECYCLE_SECONDS),
            "pool_size": int(self.DB_POOL_SIZE),
            "max_overflow": int(self.DB_MAX_OVERFLOW),
            "pool_timeout": int(self.DB_POOL_TIMEOUT_SECONDS),
            "connect_args": self.db_connect_args,
        }


settings = Settings()
