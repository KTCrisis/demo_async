#!/usr/bin/env python3
"""
Schema Purge UI - Flask Backend
Simple web interface for Schema Registry management
"""
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
import os
import json
import logging
import asyncio
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
import requests
import json

# Configuration Ollama

load_dotenv()

import sys
sys.path.append('../agent-asyncapi-local')

import config as agent_config
from tools.confluent_inspector import ConfluentInspector
from tools.schema_analyzer import SchemaAnalyzer
from tools.asyncapi_generator import AsyncAPIGenerator
from tools.schema_checker import SchemaHealthChecker
from tools.schema_purger import SchemaPurger


OLLAMA_URL="http://127.0.0.1:11434"
OLLAMA_MODEL="qwen3:14b"

# Initialize Flask app
app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Helper pour exécuter du code async dans un contexte sync
def run_async(coro):
    """Execute async coroutine in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# Configuration
ENVIRONMENTS = {
    'default': {
        'endpoint': "xxxx",
        'api_key': "xxxx",
        'api_secret': "xxxxx"
    }
}

# Simple authentication
API_USERNAME = os.getenv('API_USERNAME', 'xxxx')
API_PASSWORD = os.getenv('API_PASSWORD', 'xxxx')

# Store operation history
operation_history = []

def check_auth(username, password):
    """Check if username/password is valid"""
    return username == API_USERNAME and password == API_PASSWORD

def requires_auth(f):
    """Decorator for routes requiring authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            response = jsonify({'error': 'Authentication required'})
            response.status_code = 401
            response.headers['WWW-Authenticate'] = 'Basic realm="Login Required"'
            return response
        return f(*args, **kwargs)
    return decorated

def log_operation(env, operation, details, status):
    """Log an operation to history"""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'environment': env,
        'operation': operation,
        'details': details,
        'status': status,
        'user': request.authorization.username if request.authorization else 'unknown'
    }
    operation_history.append(entry)
    logger.info(f"Operation logged: {operation} on {env} - {status}")

# ============================================================================
# Routes - Static files
# ============================================================================

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('static', 'index.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

# ============================================================================
# Routes - Environment & Configuration
# ============================================================================

@app.route('/api/environments')
@requires_auth
def get_environments():
    """Get list of available environments"""
    envs = []
    for env_name, config in ENVIRONMENTS.items():
        envs.append({
            'name': env_name,
            'configured': bool(config['endpoint'] and config['api_key'] and config['api_secret']),
            'endpoint': config['endpoint'] if config['endpoint'] else 'Not configured'
        })
    return jsonify({'environments': envs})

# ============================================================================
# Routes - Health Check
# ============================================================================

@app.route('/api/check/<env>', methods=['POST'])
@requires_auth
def run_health_check(env):
    """Run health check on specified environment"""
    if env not in ENVIRONMENTS:
        return jsonify({'error': f'Invalid environment: {env}'}), 400
    
    config = ENVIRONMENTS[env]
    if not all([config['endpoint'], config['api_key'], config['api_secret']]):
        return jsonify({'error': f'Environment {env} is not configured'}), 400
    
    try:
        logger.info(f"Running health check on {env}")
        checker = SchemaHealthChecker(
            config['endpoint'],
            config['api_key'],
            config['api_secret']
        )
        results = checker.check_all()
        
        log_operation(env, 'health_check', {'status': results['summary']['status']}, 'success')
        
        return jsonify(results)
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        log_operation(env, 'health_check', {'error': str(e)}, 'failed')
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Routes - Schema Management
# ============================================================================

@app.route('/api/schemas/<env>', methods=['GET'])
@requires_auth
def get_schemas(env):
    """Get all schemas for an environment"""
    if env not in ENVIRONMENTS:
        return jsonify({'error': f'Invalid environment: {env}'}), 400
    
    config = ENVIRONMENTS[env]
    if not all([config['endpoint'], config['api_key'], config['api_secret']]):
        return jsonify({'error': f'Environment {env} is not configured'}), 400
    
    try:
        purger = SchemaPurger(
            config['endpoint'],
            config['api_key'],
            config['api_secret']
        )
        
        include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
        min_versions = request.args.get('min_versions', type=int)
        pattern = request.args.get('pattern')
        
        if min_versions or pattern:
            subjects = purger.get_subjects_by_filter(min_versions, pattern)
        else:
            subjects = purger.get_all_subjects(include_deleted)
        
        detailed_subjects = []
        for subject in subjects[:100]:
            details = purger.get_subject_details(subject)
            detailed_subjects.append(details)
        
        return jsonify({
            'environment': env,
            'total_count': len(subjects),
            'returned_count': len(detailed_subjects),
            'subjects': detailed_subjects
        })
    except Exception as e:
        logger.error(f"Failed to get schemas: {str(e)}")
        return jsonify({'error': str(e)}), 500



# ============================================================================
# Routes - AsyncAPI
# ============================================================================

@app.route('/api/asyncapi/topics/<env>', methods=['GET'])
@requires_auth
def get_topics(env):
    """Get all Kafka topics for an environment"""
    if env not in ENVIRONMENTS:
        return jsonify({'error': f'Invalid environment: {env}'}), 400
    
    try:
        async def _get_topics():
            inspector = ConfluentInspector()
            subjects = await inspector.get_all_subjects()
            
            topics = set()
            for subject in subjects:
                topic = subject.replace('-value', '').replace('-key', '')
                topics.add(topic)
            
            topics_data = []
            for topic in topics:
                topic_config = await inspector.get_topic_config(topic)
                schemas = await inspector.list_schemas_for_topic(topic)
                
                topics_data.append({
                    'name': topic,
                    'partitions': topic_config.get('partitions', 'N/A'),
                    'schemas_count': len(schemas),
                    'has_value_schema': any(s['subject'].endswith('-value') for s in schemas),
                    'has_key_schema': any(s['subject'].endswith('-key') for s in schemas)
                })
            
            return topics_data
        
        topics_data = run_async(_get_topics())
        
        return jsonify({
            'environment': env,
            'topics': sorted(topics_data, key=lambda x: x['name'])
        })
    
    except Exception as e:
        logger.error(f"Failed to get topics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/asyncapi/generate/<env>/<topic>', methods=['POST'])
@requires_auth
def generate_asyncapi(env, topic):
    """Generate AsyncAPI specification for a topic"""
    if env not in ENVIRONMENTS:
        return jsonify({'error': f'Invalid environment: {env}'}), 400
    
    try:
        logger.info(f"Generating AsyncAPI for {topic} in {env}")
        
        async def _generate():
            inspector = ConfluentInspector()
            analyzer = SchemaAnalyzer()
            generator = AsyncAPIGenerator()
            
            topic_config = await inspector.get_topic_config(topic)
            schemas = await inspector.list_schemas_for_topic(topic)
            
            if not schemas:
                raise ValueError(f'No schemas found for topic {topic}')
            
            examples = analyzer.extract_message_examples(schemas[0]["schema"])
            spec_yaml = generator.generate_spec(topic, topic_config, schemas, examples)
            filepath = generator.save_spec(spec_yaml, topic)
            
            return spec_yaml, filepath, len(schemas)
        
        spec_yaml, filepath, schemas_count = run_async(_generate())
        
        log_operation(env, 'generate_asyncapi', {
            'topic': topic,
            'schemas_count': schemas_count,
            'filepath': str(filepath)
        }, 'success')
        
        return jsonify({
            'success': True,
            'topic': topic,
            'spec': spec_yaml,
            'filepath': str(filepath),
            'schemas_count': schemas_count
        })
    
    except Exception as e:
        logger.error(f"AsyncAPI generation failed: {str(e)}")
        log_operation(env, 'generate_asyncapi', {'topic': topic, 'error': str(e)}, 'failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/asyncapi/specs', methods=['GET'])
@requires_auth
def list_asyncapi_specs():
    """List all generated AsyncAPI specs"""
    try:
        import glob
        import yaml
        from pathlib import Path
        
        specs = []
        for filepath in glob.glob("../demo-async/data/output/*.yaml"):
            with open(filepath) as f:
                spec = yaml.safe_load(f)
            
            specs.append({
                'filename': Path(filepath).name,
                'title': spec.get('info', {}).get('title', 'Unknown'),
                'version': spec.get('info', {}).get('version', '1.0.0'),
                'channels': len(spec.get('channels', {})),
                'created': datetime.fromtimestamp(Path(filepath).stat().st_mtime).isoformat()
            })
        
        return jsonify({
            'count': len(specs),
            'specs': sorted(specs, key=lambda x: x['created'], reverse=True)
        })
    
    except Exception as e:
        logger.error(f"Failed to list specs: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/asyncapi/specs/<filename>', methods=['GET'])
@requires_auth
def get_asyncapi_spec(filename):
    """Get a specific AsyncAPI spec"""
    try:
        import yaml
        filepath = f"../demo-async/data/output/{filename}"
        
        with open(filepath) as f:
            if request.args.get('format') == 'yaml':
                return Response(f.read(), mimetype='text/yaml')
            else:
                spec = yaml.safe_load(f)
                return jsonify(spec)
    
    except FileNotFoundError:
        return jsonify({'error': 'Spec not found'}), 404
    except Exception as e:
        logger.error(f"Failed to get spec: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/asyncapi/download/<filename>', methods=['GET'])
@requires_auth
def download_asyncapi_spec(filename):
    """Download an AsyncAPI spec"""
    try:
        directory = "../demo-async/data/output"
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Failed to download spec: {str(e)}")
        return jsonify({'error': str(e)}), 500
# ============================================================================
# Routes - History
# ============================================================================


# Stockage conversations en mémoire (Redis en prod)
chat_sessions = {}

@app.route('/api/chat/start', methods=['POST'])
@requires_auth
def start_chat_session():
    """Créer une nouvelle session de chat"""
    import uuid
    session_id = str(uuid.uuid4())
    
    chat_sessions[session_id] = {
        'messages': [],
        'context': {},
        'created_at': datetime.now().isoformat()
    }
    
    return jsonify({
        'session_id': session_id,
        'message': 'Chat session started'
    })


@app.route('/api/chat/message', methods=['POST'])
@requires_auth
def send_chat_message():
    """Envoyer un message au chatbot"""
    data = request.json
    session_id = data.get('session_id')
    user_message = data.get('message')
    env = data.get('environment', 'default')
    
    if not session_id or session_id not in chat_sessions:
        return jsonify({'error': 'Invalid session'}), 400
    
    try:
        # Récupérer le contexte (schemas disponibles)
        async def _get_context():
            inspector = ConfluentInspector()
            subjects = await inspector.get_all_subjects()
            return subjects[:10]  # Limiter pour ne pas surcharger
        
        available_schemas = run_async(_get_context())
        
        # Construire le contexte
        context = f"""Tu es un assistant expert en Kafka et AsyncAPI.
        
Environnement actuel: {env}
Schemas disponibles: {', '.join(available_schemas)}

Tu peux aider l'utilisateur à :
- Comprendre les schemas Kafka
- Générer des specs AsyncAPI
- Analyser les topics
- Expliquer les messages

Réponds de manière concise et technique."""

        # Historique de conversation
        session = chat_sessions[session_id]
        session['messages'].append({
            'role': 'user',
            'content': user_message
        })
        
        # Construire le prompt complet
        messages = [
            {'role': 'system', 'content': context}
        ] + session['messages'][-10:]  # Garder les 10 derniers messages
        
        # Appeler Ollama
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                'model': OLLAMA_MODEL,
                'messages': messages,
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'top_p': 0.9
                }
            },
            timeout=60
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama error: {response.status_code}")
        
        ai_response = response.json()['message']['content']
        
        # Sauvegarder la réponse
        session['messages'].append({
            'role': 'assistant',
            'content': ai_response
        })
        
        log_operation(env, 'chat_message', {
            'session_id': session_id,
            'message_length': len(user_message)
        }, 'success')
        
        return jsonify({
            'response': ai_response,
            'session_id': session_id
        })
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/history/<session_id>', methods=['GET'])
@requires_auth
def get_chat_history(session_id):
    """Récupérer l'historique d'une session"""
    if session_id not in chat_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify({
        'session_id': session_id,
        'messages': chat_sessions[session_id]['messages']
    })

# ============================================================================
# Routes - History
# ============================================================================

@app.route('/api/history', methods=['GET'])
@requires_auth
def get_history():
    """Get operation history"""
    limit = request.args.get('limit', 100, type=int)
    env = request.args.get('env')
    
    filtered_history = operation_history
    if env:
        filtered_history = [h for h in filtered_history if h['environment'] == env]
    
    return jsonify({
        'total': len(filtered_history),
        'history': list(reversed(filtered_history[-limit:]))
    })

# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    
    logger.info(f"Starting Schema Purge UI on port {port}")
    logger.info(f"Debug mode: {debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
