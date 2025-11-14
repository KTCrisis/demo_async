"""Vérifier la connectivité à Confluent Cloud"""
import requests
import base64
from loguru import logger
import config

def check_schema_registry():
    """Vérifie l'accès au Schema Registry"""
    print("\n" + "="*60)
    print("🔍 DIAGNOSTIC SCHEMA REGISTRY")
    print("="*60)
    
    url = config.SCHEMA_REGISTRY_URL
    print(f"\n📍 URL: {url}")
    
    # Créer l'auth
    credentials = f"{config.SCHEMA_REGISTRY_API_KEY}:{config.SCHEMA_REGISTRY_API_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    headers = {"Authorization": f"Basic {encoded}"}
    
    # Test 1: Endpoint principal
    print("\n[Test 1] Connexion au Schema Registry...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"✓ Status: {response.status_code}")
        if response.status_code == 200:
            print(f"✓ Schema Registry accessible")
        else:
            print(f"⚠ Réponse: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False
    
    # Test 2: Lister les subjects
    print("\n[Test 2] Liste des subjects...")
    try:
        response = requests.get(f"{url}/subjects", headers=headers, timeout=10)
        print(f"✓ Status: {response.status_code}")
        if response.status_code == 200:
            subjects = response.json()
            print(f"✓ {len(subjects)} subject(s) trouvé(s)")
            if subjects:
                print("\nSubjects disponibles:")
                for s in subjects:
                    print(f"  • {s}")
            else:
                print("\n⚠ Schema Registry vide - aucun schema créé")
        else:
            print(f"❌ Erreur {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False
    
    # Test 3: Compatibilité
    print("\n[Test 3] Configuration du Schema Registry...")
    try:
        response = requests.get(f"{url}/config", headers=headers, timeout=10)
        if response.status_code == 200:
            config_data = response.json()
            print(f"✓ Compatibilité: {config_data.get('compatibilityLevel', 'N/A')}")
        else:
            print(f"⚠ Config inaccessible: {response.status_code}")
    except Exception as e:
        print(f"⚠ Erreur config: {e}")
    
    return True

def check_kafka_cluster():
    """Vérifie l'accès au cluster Kafka (via Admin API si disponible)"""
    print("\n" + "="*60)
    print("🔍 DIAGNOSTIC KAFKA CLUSTER")
    print("="*60)
    
    print(f"\n📍 Bootstrap servers: {config.KAFKA_BOOTSTRAP_SERVERS}")
    print(f"🔑 API Key: {config.KAFKA_API_KEY[:8]}...")
    
    # Pour tester vraiment la connexion Kafka, il faut utiliser confluent-kafka
    from confluent_kafka.admin import AdminClient
    
    try:
        admin_config = {
            'bootstrap.servers': config.KAFKA_BOOTSTRAP_SERVERS,
            'security.protocol': 'SASL_SSL',
            'sasl.mechanism': 'PLAIN',
            'sasl.username': config.KAFKA_API_KEY,
            'sasl.password': config.KAFKA_API_SECRET,
        }
        
        print("\n[Test 1] Connexion au cluster Kafka...")
        admin = AdminClient(admin_config)
        
        # Lister les topics avec timeout
        print("[Test 2] Liste des topics...")
        metadata = admin.list_topics(timeout=10)
        
        topics = list(metadata.topics.keys())
        print(f"✓ {len(topics)} topic(s) trouvé(s)")
        
        if topics:
            print("\nTopics disponibles:")
            for topic in topics[:10]:  # Afficher les 10 premiers
                if not topic.startswith('_'):  # Ignorer les topics internes
                    print(f"  • {topic}")
        else:
            print("\n⚠ Aucun topic trouvé - cluster vide")
        
        return True
    
    except Exception as e:
        print(f"❌ Erreur connexion Kafka: {e}")
        return False

if __name__ == "__main__":
    print("🔍 DIAGNOSTIC CONFLUENT CLOUD")
    print("="*60)
    
    try:
        config.validate_config()
        print("✓ Configuration .env valide\n")
    except ValueError as e:
        print(f"❌ Configuration invalide: {e}")
        exit(1)
    
    # Tests
    sr_ok = check_schema_registry()
    kafka_ok = check_kafka_cluster()
    
    print("\n" + "="*60)
    print("📊 RÉSUMÉ")
    print("="*60)
    print(f"Schema Registry: {'✅' if sr_ok else '❌'}")
    print(f"Kafka Cluster:   {'✅' if kafka_ok else '❌'}")
    
    if not sr_ok or not kafka_ok:
        print("\n💡 ACTIONS REQUISES:")
        if not sr_ok:
            print("  - Vérifier les credentials Schema Registry dans .env")
            print("  - Vérifier l'URL du Schema Registry")
        if not kafka_ok:
            print("  - Vérifier les credentials Kafka dans .env")
            print("  - Vérifier le bootstrap server")