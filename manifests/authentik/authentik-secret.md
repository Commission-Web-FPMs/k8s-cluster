# Secrets Authentik

```sh
secret_dir=$(mktemp -d)
trap 'rm -rf "$secret_dir"' EXIT

openssl rand -base64 60 | tr -d '\n' | dd of="$secret_dir/authentik-secret-key" status=none
openssl rand -base64 48 | tr -d '\n' | dd of="$secret_dir/database-password" status=none

kubectl create secret -n authentik generic authentik-secret \
  --from-file=AUTHENTIK_SECRET_KEY="$secret_dir/authentik-secret-key" \
  --from-file=AUTHENTIK_POSTGRESQL__PASSWORD="$secret_dir/database-password" \
  --dry-run=client -o yaml \
| kubectl label --local -f - --dry-run=client -o yaml \
    app.kubernetes.io/part-of=argocd \
| kubeseal \
    --controller-namespace sealed-secrets \
    --format yaml \
> manifests/authentik/authentik-secret.sealed.yaml

kubectl create secret -n comweb-db generic authentik-db-credentials \
  --type=kubernetes.io/basic-auth \
  --from-literal=username=authentik \
  --from-file=password="$secret_dir/database-password" \
  --dry-run=client -o yaml \
| kubectl label --local -f - --dry-run=client -o yaml \
    cnpg.io/reload=true \
| kubeseal \
    --controller-namespace sealed-secrets \
    --format yaml \
> manifests/authentik/authentik-db-credentials.sealed.yaml
```
