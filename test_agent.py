"""Tests simples de l'agent"""
import asyncio
from loguru import logger
from tools.confluent_inspector import ConfluentInspector
from tools.schema_analyzer import SchemaAnalyzer
from tools.asyncapi_generator import AsyncAPIGenerator
import config

async def test_inspector():
    """Test de l'inspecteur Confluent"""
    print("\n" + "="*50)
    print("TEST 1: Confluent Inspector")
    print("="*50)
    
    inspector = ConfluentInspector()
    
    # Test 1: Lister tous les subjects
    print("\n📋 Liste des subjects...")
    subjects = await inspector.get_all_subjects()
    print(f"✓ {len(subjects)} subjects trouvés")
    for subject in subjects[:5]:  # Afficher les 5 premiers
        print(f"  - {subject}")
    
    if subjects:
        # Test 2: Récupérer un schema
        print(f"\n📝 Récupération du schema: {subjects[0]}")
        schema = await inspector._get_schema(subjects[0])
        if schema:
            print(f"✓ Schema ID: {schema['id']}, Version: {schema['version']}")
        
        # Test 3: Schemas pour un topic
        topic_name = subjects[0].replace("-value", "").replace("-key", "")
        print(f"\n🔍 Schemas pour le topic: {topic_name}")
        topic_schemas = await inspector.list_schemas_for_topic(topic_name)
        print(f"✓ {len(topic_schemas)} schema(s) trouvé(s)")

async def test_schema_analyzer():
    """Test de l'analyseur de schemas"""
    print("\n" + "="*50)
    print("TEST 2: Schema Analyzer")
    print("="*50)
    
    # Schema Avro exemple
    avro_schema = '''{
        "type": "record",
        "name": "TestMessage",
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "amount", "type": "double"},
            {"name": "status", "type": {"type": "enum", "name": "Status", "symbols": ["PENDING", "DONE"]}}
        ]
    }'''
    
    analyzer = SchemaAnalyzer()
    
    # Test conversion
    print("\n🔄 Conversion Avro → AsyncAPI...")
    json_schema = analyzer.avro_to_asyncapi_schema(avro_schema)
    print("✓ Schema converti:")
    print(f"  Properties: {list(json_schema['properties'].keys())}")
    
    # Test génération exemple
    print("\n💡 Génération d'exemple...")
    example = analyzer.extract_message_examples(avro_schema)
    print(f"✓ Exemple généré: {example}")

async def test_full_generation():
    """Test de la génération complète"""
    print("\n" + "="*50)
    print("TEST 3: Génération complète AsyncAPI")
    print("="*50)
    
    inspector = ConfluentInspector()
    
    # Récupérer le premier topic disponible
    subjects = await inspector.get_all_subjects()
    if not subjects:
        print("❌ Aucun subject disponible pour le test")
        return
    
    topic_name = subjects[0].replace("-value", "").replace("-key", "")
    print(f"\n🎯 Génération pour: {topic_name}")
    
    # Simuler la génération
    topic_config = await inspector.get_topic_config(topic_name)
    schemas = await inspector.list_schemas_for_topic(topic_name)
    
    if schemas:
        analyzer = SchemaAnalyzer()
        examples = analyzer.extract_message_examples(schemas[0]["schema"])
        
        generator = AsyncAPIGenerator()
        spec = generator.generate_spec(topic_name, topic_config, schemas, examples)
        
        # Sauvegarder
        filepath = generator.save_spec(spec, f"test_{topic_name}")
        print(f"\n✅ Spec générée: {filepath}")
        print(f"\nPreview (50 premières lignes):")
        print("-" * 50)
        print("\n".join(spec.split("\n")[:50]))

async def main():
    """Lance tous les tests"""
    print("🧪 Tests de l'Agent AsyncAPI")
    print("="*50)
    
    # Valider config
    try:
        config.validate_config()
        print("✓ Configuration OK\n")
    except ValueError as e:
        print(f"❌ Configuration invalide: {e}")
        return
    
    # Lancer les tests
    try:
        await test_inspector()
        await test_schema_analyzer()
        await test_full_generation()
        
        print("\n" + "="*50)
        print("✅ TOUS LES TESTS PASSÉS")
        print("="*50)
    
    except Exception as e:
        logger.error(f"❌ Erreur lors des tests: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())