output "topic_name" {
  description = "Created topic name"
  value       = confluent_kafka_topic.order_created.topic_name
}

output "schema_subject" {
  description = "Schema subject name"
  value       = confluent_schema.order_created_value.subject_name
}

output "schema_id" {
  description = "Schema ID"
  value       = confluent_schema.order_created_value.id
}

# Infos de connexion (déjà dans ton .env)
output "kafka_bootstrap_servers" {
  description = "Kafka bootstrap servers"
  value       = data.confluent_kafka_cluster.demo_cluster.bootstrap_endpoint
}

output "schema_registry_url" {
  description = "Schema Registry URL"
  value       = data.confluent_schema_registry_cluster.demo_sr.rest_endpoint
}