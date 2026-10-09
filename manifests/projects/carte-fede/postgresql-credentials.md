# PostgreSQL de carte-fede

Seule la branche `main` possède une base PostgreSQL. Le dossier `database/main/`
contient les mêmes ressources qu'Authentik : `DatabaseRole`, `Database` et
SealedSecrets. Le `kustomization.yaml` du projet les inclut directement.

Le rôle possède sa base et peut y créer les tables et effectuer les
migrations. Il ne peut pas créer d'autres bases ou rôles, répliquer ou
contourner les politiques RLS. Les règles `pg_hba` limitent le compte
à sa base homonyme et imposent TLS avec SCRAM. La connexion utilise
`sslmode=require`, sans vérifier le certificat serveur.

Le dossier contient deux SealedSecrets, scellés séparément avec le même
mot de passe.

| Namespace | Secret | Clés |
| --- | --- | --- |
| `comweb-db` | `carte-fede-main-db-credentials` | `username`, `password`, type `kubernetes.io/basic-auth` |
| `carte-fede-main` | `postgresql-credentials` | `DATABASE_URL` |

Les Secrets précèdent le rôle et la base dans les vagues Argo CD.
Le chart applicatif charge `DATABASE_URL` et les paramètres Authentik avec
`envFrom` uniquement sur `main`.
La base et le rôle restent conservés après suppression de l'Application.
Les tables et les migrations restent à gérer avec le code de carte-fede.

Pour recréer ou faire tourner les identifiants de `main`, exécuter depuis
la racine du dépôt :

```sh
branch_normalized=main
app_namespace="carte-fede-$branch_normalized"
database_name=$(printf '%s' "$app_namespace" | tr '-' '_')
destination="manifests/projects/carte-fede/database/$branch_normalized/postgresql-credentials.sealed.yaml"

umask 077
secret_dir=$(mktemp -d)
trap 'rm -rf "$secret_dir"' EXIT
openssl rand -hex 48 | tr -d '\n' > "$secret_dir/password"
printf 'postgresql+psycopg://%s:%s@comweb-db-rw.comweb-db.svc.cluster.local:5432/%s?sslmode=require' \
  "$database_name" "$(cat "$secret_dir/password")" "$database_name" \
  > "$secret_dir/database-url"

kubectl create secret generic "$app_namespace-db-credentials" \
  --namespace comweb-db \
  --type=kubernetes.io/basic-auth \
  --from-literal=username="$database_name" \
  --from-file=password="$secret_dir/password" \
  --dry-run=client -o yaml \
| kubectl label --local -f - --dry-run=client -o yaml cnpg.io/reload=true \
| kubeseal --controller-namespace sealed-secrets --format yaml \
> "$secret_dir/database.sealed.yaml"

kubectl create secret generic postgresql-credentials \
  --namespace "$app_namespace" \
  --from-file=DATABASE_URL="$secret_dir/database-url" \
  --dry-run=client -o yaml \
| kubeseal --controller-namespace sealed-secrets --format yaml \
> "$secret_dir/application.sealed.yaml"

cat "$secret_dir/database.sealed.yaml" > "$destination"
printf '\n---\n' >> "$destination"
cat "$secret_dir/application.sealed.yaml" >> "$destination"
```

Après rotation, synchroniser Argo CD, attendre l'application du mot de passe
par CloudNativePG et redémarrer le Deployment pour recharger `DATABASE_URL`.
Une reconstruction réutilise les fichiers scellés et la sauvegarde de la
clé privée Sealed Secrets.
