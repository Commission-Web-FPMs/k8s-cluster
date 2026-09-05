# Inventaire des secrets

| Service | Description |
| --- | --- |
| Stockage objet S3 | [s3-credentials](../manifests/csi-s3/s3-credentials.md) |

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
