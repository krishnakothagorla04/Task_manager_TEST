# ==============================================================
# Terraform — Variables
# ==============================================================

variable "kube_config_path" {
  description = "Path to the kubeconfig file"
  type        = string
  default     = "~/.kube/config"
}

variable "namespace" {
  description = "Kubernetes namespace for Task Manager"
  type        = string
  default     = "taskmanager"
}

variable "dockerhub_username" {
  description = "Docker Hub username for image registry"
  type        = string
}

variable "user_service_image_tag" {
  description = "Docker image tag for user-service"
  type        = string
  default     = "latest"
}

variable "task_service_image_tag" {
  description = "Docker image tag for task-service"
  type        = string
  default     = "latest"
}

variable "mongo_storage_size" {
  description = "Storage size for MongoDB PVC"
  type        = string
  default     = "1Gi"
}
