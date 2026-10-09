# Inventaire des secrets

| Service | Description |
| --- | --- |
| Stockage objet S3 | [s3-credentials](../manifests/csi-s3/s3-credentials.md) |
| Connexion GitHub d'ArgoCD | [github-oauth](../manifests/argocd/github-oauth.md) |
| App GitHub ArgoCD | [github-oauth](../manifests/argocd/github-app.md) |
| GitHub Webhook ArgoCD | [github-oauth](../manifests/argocd/github-webhook.md) |
| Administrateur initial Authentik | [authentik-bootstrap](../manifests/authentik/authentik-bootstrap.md) |
| Provisionnement Authentik de carte-fede main | [carte-fede-credentials](../manifests/authentik/carte-fede-credentials.md) |
| Backend carte-fede main vers Authentik | [authentik-credentials](../manifests/projects/carte-fede/authentik-credentials-main.md) |
| PostgreSQL de carte-fede main | [postgresql-credentials](../manifests/projects/carte-fede/postgresql-credentials.md) |

## Ajouter un secret

```sh
kubectl create secret generic mon-secret \
  --namespace mon-namespace \
  --from-literal=cle='valeur' \
  --dry-run=client -o yaml \
| kubeseal --controller-namespace sealed-secrets --format yaml \
> manifests/mon-composant/mon-secret.sealed.yaml
```

Écrire à côté un `mon-secret.md` : comment recréer l'identifiant. Ajouter à la liste comme ça on sait ce qu'il faut changer si la clé fuite.
