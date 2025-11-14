"""Agent AsyncAPI avec MCP"""
import asyncio
from mcp.server.fastmcp import FastMCP
from loguru import logger
from tools.confluent_inspector import ConfluentInspector
from tools.schema_analyzer import SchemaAnalyzer
from tools.asyncapi_generator import AsyncAPIGenerator
import config

# Configurer le logging
logger.add("agent.log", rotation="10 MB")

# Créer l'agent MCP
mcp = FastMCP("AsyncAPI Agent")

# Initialiser les tools
inspector = ConfluentInspector()
analyzer = SchemaAnalyzer()
generator = AsyncAPIGenerator()


@mcp.tool()
async def generate_asyncapi_for_topic(topic_name: str) -> str:
    """
    Génère une spécification AsyncAPI complète pour un topic Kafka.
    
    Cette fonction orchestrated'inspection du topic, l'analyse des schemas
    et la génération de la documentation AsyncAPI 3.0.
    """
    logger.info(f"🚀 Génération AsyncAPI pour: {topic_name}")
    
    try:
        # Étape 1: Inspecter le topic
        logger.info("📊 Étape 1: Inspection du topic...")
        topic_config = await inspector.get_topic_config(topic_name)
        
        # Étape 2: Récupérer les schemas
        logger.info("📝 Étape 2: Récupération des schemas...")
        schemas = await inspector.list_schemas_for_topic(topic_name)
        
        if not schemas:
            return f"❌ Aucun schema trouvé pour le topic '{topic_name}'"
        
        logger.info(f"✓ {len(schemas)} schema(s) trouvé(s)")
        
        # Étape 3: Générer des exemples de messages
        logger.info("💡 Étape 3: Génération d'exemples...")
        message_examples = {}
        if schemas:
            message_examples = analyzer.extract_message_examples(schemas[0]["schema"])
        
        # Étape 4: Générer la spec AsyncAPI
        logger.info("📄 Étape 4: Génération de la spec AsyncAPI...")
        spec_yaml = generator.generate_spec(
            topic_name=topic_name,
            topic_config=topic_config,
            schemas=schemas,
            message_examples=message_examples
        )
        
        # Étape 5: Sauvegarder
        filepath = generator.save_spec(spec_yaml, topic_name)
        
        logger.info(f"✅ Documentation générée avec succès!")
        
        return f"""✅ AsyncAPI spec générée avec succès!

📂 Fichier: {filepath}
📊 Topic: {topic_name}
📝 Schemas: {len(schemas)}
🔢 Partitions: {topic_config.get('partitions')}

Spec preview (100 premières lignes):
{chr(10).join(spec_yaml.split(chr(10))[:100])}
"""
    
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return f"❌ Erreur lors de la génération: {str(e)}"


@mcp.tool()
async def list_all_subjects() -> str:
    """Liste tous les subjects disponibles dans le Schema Registry"""
    logger.info("📋 Liste des subjects...")
    
    try:
        subjects = await inspector.get_all_subjects()
        
        if not subjects:
            return "Aucun subject trouvé dans le Schema Registry"
        
        # Grouper par topic potentiel
        topics = {}
        for subject in subjects:
            # Extraire le nom du topic (avant -value/-key)
            topic = subject.replace("-value", "").replace("-key", "")
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(subject)
        
        result = f"✓ {len(subjects)} subject(s) trouvé(s)\n\n"
        result += "📋 Topics détectés:\n"
        
        for topic, subs in topics.items():
            result += f"\n• {topic}\n"
            for sub in subs:
                result += f"  └─ {sub}\n"
        
        return result
    
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return f"❌ Erreur: {str(e)}"


if __name__ == "__main__":
    # Valider la config
    try:
        config.validate_config()
        logger.info("✓ Configuration valide")
    except ValueError as e:
        logger.error(f"❌ {e}")
        exit(1)
    
    # Lancer l'agent en mode interactif
    logger.info("🤖 Agent AsyncAPI démarré en mode interactif")
    logger.info("Commandes disponibles:")
    logger.info("  - generate_asyncapi_for_topic(topic_name)")
    logger.info("  - list_all_subjects()")
    
    mcp.run(transport="stdio")