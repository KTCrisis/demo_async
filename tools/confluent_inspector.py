"""Tool MCP pour inspecter Confluent Cloud"""
import base64
import requests
from typing import Dict, List, Any
from loguru import logger
import config

class ConfluentInspector:
    """Inspecte les resources Confluent Cloud"""
    
    def __init__(self):
        self.sr_url = config.SCHEMA_REGISTRY_URL
        self.sr_auth = self._make_auth(
            config.SCHEMA_REGISTRY_API_KEY,
            config.SCHEMA_REGISTRY_API_SECRET
        )
    
    def _make_auth(self, key: str, secret: str) -> str:
        """Créer l'header Authorization Basic"""
        credentials = f"{key}:{secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    async def get_topic_config(self, topic_name: str) -> Dict[str, Any]:
        """
        Récupère la configuration d'un topic
        Note: Nécessite l'API Kafka REST ou Admin API
        Pour l'instant, on retourne des infos basiques
        """
        logger.info(f"Inspection du topic: {topic_name}")
        
        # TODO: Implémenter via Kafka Admin API ou REST Proxy
        # Pour la démo, on retourne une structure simulée
        return {
            "name": topic_name,
            "partitions": 3,
            "replication_factor": 3,
            "config": {
                "retention.ms": "604800000",  # 7 jours
                "cleanup.policy": "delete",
                "compression.type": "gzip"
            }
        }
    
    async def list_schemas_for_topic(self, topic_name: str) -> List[Dict[str, Any]]:
        """Liste les schemas Avro/JSON associés à un topic"""
        logger.info(f"Recherche de schemas pour: {topic_name}")
        
        try:
            # Essayer les conventions de nommage standards
            subjects_to_check = [
                f"{topic_name}-value",
                f"{topic_name}-key",
                topic_name
            ]
            
            schemas = []
            for subject in subjects_to_check:
                schema = await self._get_schema(subject)
                if schema:
                    schemas.append(schema)
            
            return schemas
        
        except Exception as e:
            logger.error(f"Erreur récupération schemas: {e}")
            return []
    
    async def _get_schema(self, subject: str) -> Dict[str, Any] | None:
        """Récupère un schema par son subject name"""
        url = f"{self.sr_url}/subjects/{subject}/versions/latest"
        
        try:
            response = requests.get(
                url,
                headers={"Authorization": self.sr_auth},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✓ Schema trouvé: {subject}")
                return {
                    "subject": subject,
                    "version": data["version"],
                    "id": data["id"],
                    "schema": data["schema"],
                    "schemaType": data.get("schemaType", "AVRO")
                }
            elif response.status_code == 404:
                logger.debug(f"Schema non trouvé: {subject}")
                return None
            else:
                logger.warning(f"Erreur {response.status_code} pour {subject}")
                return None
        
        except Exception as e:
            logger.error(f"Exception lors de la récupération du schema {subject}: {e}")
            return None
    
    async def get_all_subjects(self) -> List[str]:
        """Liste tous les subjects du Schema Registry"""
        url = f"{self.sr_url}/subjects"
        
        try:
            response = requests.get(
                url,
                headers={"Authorization": self.sr_auth},
                timeout=10
            )
            
            if response.status_code == 200:
                subjects = response.json()
                logger.info(f"✓ {len(subjects)} subjects trouvés")
                return subjects
            else:
                logger.error(f"Erreur listing subjects: {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"Exception listing subjects: {e}")
            return []