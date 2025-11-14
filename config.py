"""Configuration de l'agent AsyncAPI"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"

# Créer les dossiers si nécessaires
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

# Confluent Cloud
CONFLUENT_CLOUD_API_KEY = os.getenv("CONFLUENT_CLOUD_API_KEY")
CONFLUENT_CLOUD_API_SECRET = os.getenv("CONFLUENT_CLOUD_API_SECRET")

# Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
KAFKA_API_KEY = os.getenv("KAFKA_API_KEY")
KAFKA_API_SECRET = os.getenv("KAFKA_API_SECRET")

# Schema Registry
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
SCHEMA_REGISTRY_API_KEY = os.getenv("SCHEMA_REGISTRY_API_KEY")
SCHEMA_REGISTRY_API_SECRET = os.getenv("SCHEMA_REGISTRY_API_SECRET")

# Cluster info
KAFKA_CLUSTER_ID = os.getenv("KAFKA_CLUSTER_ID")
ENVIRONMENT_ID = os.getenv("ENVIRONMENT_ID")

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:latest")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Validation
def validate_config():
    """Vérifie que les credentials essentiels sont présents"""
    required = {
        "KAFKA_BOOTSTRAP_SERVERS": KAFKA_BOOTSTRAP_SERVERS,
        "KAFKA_API_KEY": KAFKA_API_KEY,
        "KAFKA_API_SECRET": KAFKA_API_SECRET,
        "SCHEMA_REGISTRY_URL": SCHEMA_REGISTRY_URL,
    }
    
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(f"Variables manquantes dans .env: {', '.join(missing)}")
    
    return True