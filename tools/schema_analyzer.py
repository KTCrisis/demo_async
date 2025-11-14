"""Analyse les schemas Avro/JSON pour AsyncAPI"""
import json
from typing import Dict, Any
from loguru import logger

class SchemaAnalyzer:
    """Analyse et convertit les schemas pour AsyncAPI"""
    
    @staticmethod
    def avro_to_asyncapi_schema(avro_schema_str: str) -> Dict[str, Any]:
        """Convertit un schema Avro en schema AsyncAPI (JSON Schema)"""
        try:
            avro = json.loads(avro_schema_str)
            
            # Conversion basique Avro → JSON Schema
            json_schema = {
                "type": "object",
                "description": avro.get("doc", ""),
                "properties": {},
                "required": []
            }
            
            # Parcourir les fields
            for field in avro.get("fields", []):
                field_name = field["name"]
                field_type = field["type"]
                
                # Convertir le type Avro
                json_type = SchemaAnalyzer._convert_avro_type(field_type)
                
                json_schema["properties"][field_name] = {
                    "type": json_type["type"],
                    "description": field.get("doc", "")
                }
                
                # Ajouter enum si présent
                if isinstance(field_type, dict) and field_type.get("type") == "enum":
                    json_schema["properties"][field_name]["enum"] = field_type.get("symbols", [])
                
                # Gérer les valeurs par défaut
                if "default" in field:
                    json_schema["properties"][field_name]["default"] = field["default"]
                else:
                    json_schema["required"].append(field_name)
            
            return json_schema
        
        except Exception as e:
            logger.error(f"Erreur conversion Avro→AsyncAPI: {e}")
            return {"type": "object", "description": "Schema conversion error"}
    
    @staticmethod
    def _convert_avro_type(avro_type: Any) -> Dict[str, Any]:
        """Convertit un type Avro en type JSON Schema"""
        # Type simple (string)
        if isinstance(avro_type, str):
            type_mapping = {
                "string": {"type": "string"},
                "int": {"type": "integer"},
                "long": {"type": "integer", "format": "int64"},
                "float": {"type": "number", "format": "float"},
                "double": {"type": "number", "format": "double"},
                "boolean": {"type": "boolean"},
                "bytes": {"type": "string", "contentEncoding": "base64"},
                "null": {"type": "null"}
            }
            return type_mapping.get(avro_type, {"type": "string"})
        
        # Type union (ex: ["null", "string"])
        if isinstance(avro_type, list):
            # Simplification: prendre le premier type non-null
            non_null_types = [t for t in avro_type if t != "null"]
            if non_null_types:
                return SchemaAnalyzer._convert_avro_type(non_null_types[0])
            return {"type": "null"}
        
        # Type complexe (record, enum, etc.)
        if isinstance(avro_type, dict):
            avro_complex_type = avro_type.get("type")
            
            if avro_complex_type == "enum":
                return {
                    "type": "string",
                    "enum": avro_type.get("symbols", [])
                }
            
            if avro_complex_type == "array":
                items_type = SchemaAnalyzer._convert_avro_type(avro_type.get("items"))
                return {
                    "type": "array",
                    "items": items_type
                }
            
            if avro_complex_type == "record":
                # Pour un record nested, on retourne un object
                return {"type": "object"}
            
            # Logical types (timestamp, etc.)
            if "logicalType" in avro_type:
                logical = avro_type["logicalType"]
                if logical in ["timestamp-millis", "timestamp-micros"]:
                    return {"type": "string", "format": "date-time"}
                if logical == "date":
                    return {"type": "string", "format": "date"}
        
        return {"type": "string"}
    
    @staticmethod
    def extract_message_examples(avro_schema_str: str) -> Dict[str, Any]:
        """Génère un exemple de message depuis le schema"""
        try:
            avro = json.loads(avro_schema_str)
            example = {}
            
            for field in avro.get("fields", []):
                field_name = field["name"]
                field_type = field["type"]
                
                # Utiliser default si présent
                if "default" in field:
                    example[field_name] = field["default"]
                else:
                    example[field_name] = SchemaAnalyzer._generate_example_value(field_type)
            
            return example
        
        except Exception as e:
            logger.error(f"Erreur génération exemple: {e}")
            return {}
    
    @staticmethod
    def _generate_example_value(avro_type: Any) -> Any:
        """Génère une valeur d'exemple pour un type Avro"""
        if isinstance(avro_type, str):
            examples = {
                "string": "example-string",
                "int": 42,
                "long": 1234567890,
                "float": 3.14,
                "double": 3.14159,
                "boolean": True,
                "bytes": "base64-encoded-data",
                "null": None
            }
            return examples.get(avro_type, "example")
        
        if isinstance(avro_type, list):
            non_null = [t for t in avro_type if t != "null"]
            if non_null:
                return SchemaAnalyzer._generate_example_value(non_null[0])
            return None
        
        if isinstance(avro_type, dict):
            avro_complex_type = avro_type.get("type")
            
            if avro_complex_type == "enum":
                symbols = avro_type.get("symbols", [])
                return symbols[0] if symbols else "ENUM_VALUE"
            
            if avro_complex_type == "array":
                return []
            
            if avro_complex_type == "record":
                return {}
            
            if "logicalType" in avro_type:
                logical = avro_type["logicalType"]
                if logical in ["timestamp-millis", "timestamp-micros"]:
                    return "2024-01-01T12:00:00Z"
                if logical == "date":
                    return "2024-01-01"
        
        return "example"