# ==============================================================
# Terraform — Outputs
# ==============================================================

output "namespace" {
  description = "The Kubernetes namespace used"
  value       = kubernetes_namespace.taskmanager.metadata[0].name
}

output "user_service_cluster_ip" {
  description = "ClusterIP of the user-service"
  value       = kubernetes_service.user_service.spec[0].cluster_ip
}

output "task_service_node_port" {
  description = "NodePort of the task-service for external access"
  value       = kubernetes_service.task_service.spec[0].port[0].node_port
}
