"""
应用配置 - 基于 pydantic-settings
统一从 .env 文件和环境变量加载

⚠️ 关键说明：
1. 嵌套 BaseSettings 在 pydantic-settings v2 中默认不继承父级的 env_file
   所以每个子配置类都需要显式设置 model_config 才能从 .env 读取
2. pydantic-settings 的 env_file 路径是相对路径，相对于 CWD（uvicorn 启动目录）。
   当 uvicorn 在 backend/ 启动、.env 在项目根时，env_file=".env" 找不到。
   解决：在模块顶部显式 load_dotenv()，让 .env 里的所有变量都进入 os.environ，
   然后 pydantic-settings 通过 os.environ 读取（不依赖文件路径）
"""
import os
from typing import List, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

# 显式加载项目根目录的 .env 文件（不依赖 CWD）
# config.py 位于 backend/app/core/config.py
# 4 层 parent 才能回到项目根
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    # override=True 确保 .env 优先级高于系统环境变量（避免 OS 残留污染）
    from dotenv import load_dotenv
    load_dotenv(_ENV_FILE, override=True)


# 统一子配置基类：让所有嵌套子配置都能从 .env 读取
class _EnvBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


class CloudLLMConfig(_EnvBaseSettings):
    """阿里云百炼平台（云端 LLM）配置"""
    api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="DASHSCOPE_BASE_URL",
    )
    model: str = Field(default="qwen-vl-max", alias="DASHSCOPE_MODEL")
    timeout: int = Field(default=60, alias="LLM_TIMEOUT_SEC")


class LocalLLMConfig(_EnvBaseSettings):
    """本地大模型配置（LoongArch 降级方案）"""
    model_path: str = Field(default="/opt/models/Qwen2-VL-7B-Instruct", alias="LOCAL_MODEL_PATH")
    backend: Literal["transformers", "vllm"] = Field(default="transformers", alias="LOCAL_MODEL_BACKEND")
    device: Literal["cpu", "cuda", "npu"] = Field(default="cpu", alias="LOCAL_MODEL_DEVICE")


class PostgresConfig(_EnvBaseSettings):
    """PostgreSQL 数据库配置"""
    host: str = Field(default="localhost", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    user: str = Field(default="a1_user", alias="POSTGRES_USER")
    password: str = Field(default="a1_password", alias="POSTGRES_PASSWORD")
    db: str = Field(default="a1_maintenance", alias="POSTGRES_DB")

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def sync_url(self) -> str:
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class MilvusConfig(_EnvBaseSettings):
    """Milvus 向量库配置"""
    host: str = Field(default="localhost", alias="MILVUS_HOST")
    port: int = Field(default=19530, alias="MILVUS_PORT")
    user: str = Field(default="root", alias="MILVUS_USER")
    password: str = Field(default="milvus", alias="MILVUS_PASSWORD")
    db: str = Field(default="default", alias="MILVUS_DB")


class Neo4jConfig(_EnvBaseSettings):
    """Neo4j 知识图谱配置"""
    uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    user: str = Field(default="neo4j", alias="NEO4J_USER")
    password: str = Field(default="neo4j_password", alias="NEO4J_PASSWORD")


class MinioConfig(_EnvBaseSettings):
    """MinIO 对象存储配置"""
    endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    access_key: str = Field(default="minio_user", alias="MINIO_ACCESS_KEY")
    secret_key: str = Field(default="minio_password", alias="MINIO_SECRET_KEY")
    bucket: str = Field(default="a1-uploads", alias="MINIO_BUCKET")
    secure: bool = Field(default=False, alias="MINIO_SECURE")


class EmbeddingConfig(_EnvBaseSettings):
    """Embedding 模型配置（BGE-M3）"""
    model: str = Field(default="BAAI/bge-m3", alias="EMBEDDING_MODEL")
    device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")
    dim: int = Field(default=1024, alias="EMBEDDING_DIM")
    batch_size: int = Field(default=16, alias="EMBEDDING_BATCH_SIZE")


class AppSettings(_EnvBaseSettings):
    """应用主配置"""
    # 基础
    APP_NAME: str = "A1-Maintenance-System"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_SECRET_KEY: str = "change-me"

    # LLM 模式
    LLM_MODE: Literal["cloud", "local"] = "cloud"
    CLOUD_LLM: CloudLLMConfig = Field(default_factory=CloudLLMConfig)
    LOCAL_LLM: LocalLLMConfig = Field(default_factory=LocalLLMConfig)

    # 数据存储
    POSTGRES: PostgresConfig = Field(default_factory=PostgresConfig)
    MILVUS: MilvusConfig = Field(default_factory=MilvusConfig)
    NEO4J: Neo4jConfig = Field(default_factory=Neo4jConfig)
    MINIO: MinioConfig = Field(default_factory=MinioConfig)

    # Embedding
    EMBEDDING: EmbeddingConfig = Field(default_factory=EmbeddingConfig)

    # 文件上传
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_IMAGE_TYPES: str = "jpg,jpeg,png,bmp,webp"
    ALLOWED_DOC_TYPES: str = "pdf,docx,doc,txt,md"

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # 业务参数
    RETRIEVAL_TOP_K: int = 50
    RERANK_TOP_K: int = 5
    RERANK_MODEL: str = "gte-rerank"        # U2: 百炼 rerank 模型
    RERANK_ENABLED: bool = True              # 关掉即降级到 cosine 顺序

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_image_ext_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_IMAGE_TYPES.split(",")]

    @property
    def allowed_doc_ext_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_DOC_TYPES.split(",")]


# 全局配置实例
settings = AppSettings()

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 内置数据目录（统一来源 - 避免 path 字符串在多处重复）
DATA_DIR: Path = BASE_DIR / "data" / "raw"
MANUALS_DIR: Path = DATA_DIR / "manuals"
CASES_FILE: Path = DATA_DIR / "cases" / "fault_cases.json"
SOPS_FILE: Path = DATA_DIR / "sops" / "sop_library.json"

# 故障图谱存储（NetworkX 持久化，JSON 格式与 Neo4j node_link 兼容）
GRAPH_FILE: Path = BASE_DIR / "data" / "indexed" / "graph.json"
