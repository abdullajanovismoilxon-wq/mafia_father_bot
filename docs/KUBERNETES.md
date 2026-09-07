# MAFIA BOT FATHER — PRODUCTION KUBERNETES DEPLOYMENT

## 1. Directory Structure
```
deploy/kubernetes/
├── namespace.yaml
├── configmap.yaml
├── secret.yaml.example
├── backend-deployment.yaml
├── celery-deployment.yaml
├── frontend-deployment.yaml
└── ingress-and-hpa.yaml
```

## 2. Deployment Instructions
```bash
# 1. Create Namespace
kubectl apply -f deploy/kubernetes/namespace.yaml

# 2. Configure Secrets and ConfigMap
cp deploy/kubernetes/secret.yaml.example deploy/kubernetes/secret.yaml
# Edit secrets with real production credentials
kubectl apply -f deploy/kubernetes/configmap.yaml
kubectl apply -f deploy/kubernetes/secret.yaml

# 3. Deploy Workloads
kubectl apply -f deploy/kubernetes/backend-deployment.yaml
kubectl apply -f deploy/kubernetes/celery-deployment.yaml
kubectl apply -f deploy/kubernetes/frontend-deployment.yaml

# 4. Deploy Ingress & HPA
kubectl apply -f deploy/kubernetes/ingress-and-hpa.yaml
```

## 3. Scaling & Self-Healing
- **HPA**: Backend auto-scales between 2 and 10 pods based on 75% CPU and 80% Memory targets.
- **Probes**: Liveness and Readiness probes restart hung pods and stop traffic during migration rollouts.
