# PostgreSQL de carte-fede

Chaque branche possède un dossier `database/<branche normalisée>/` avec
les mêmes ressources qu'Authentik : `DatabaseRole`, `Database` et SealedSecrets.
La seconde source dans `application.yaml` sélectionne ce dossier.
Les branches actuellement déclarées sont `main`,
`codex/frontend-backend-http-routes` et `copilot/rajouter-envfrom-values-yml`.

Chaque rôle possède sa base et peut y créer les tables et effectuer les
migrations. Il ne peut pas créer d'autres bases ou rôles, répliquer ou
contourner les politiques RLS. Les règles `pg_hba` limitent chaque compte
à sa base homonyme et imposent TLS avec SCRAM. La connexion utilise
`sslmode=require`, sans vérifier le certificat serveur.

Chaque dossier contient deux SealedSecrets, scellés séparément avec le même
mot de passe propre à cette branche.

| Namespace | Secret | Clés |
| --- | --- | --- |
| `comweb-db` | `carte-fede-<branche normalisée>-db-credentials` | `username`, `password`, type `kubernetes.io/basic-auth` |
| `carte-fede-<branche normalisée>` | `postgresql-credentials` | `DATABASE_URL` |

Les Secrets précèdent le rôle et la base dans les vagues Argo CD.
Le chart applicatif charge `DATABASE_URL` avec `envFrom` sur chaque branche.
Les paramètres Authentik restent chargés uniquement sur `main`.
La base et le rôle restent conservés après suppression de l'Application.
Les tables et les migrations restent à gérer avec le code de carte-fede.

Pour une nouvelle branche, copier un dossier existant, remplacer les noms
dans `database.yaml`, puis générer ses deux SealedSecrets avec les commandes
ci-dessous. Le nom PostgreSQL remplace les tirets du namespace par des
underscores. Garder des noms distincts et inférieurs à 64 caractères.
Il faut déclarer le dossier avant de déployer cette branche.

Pour recréer ou faire tourner les identifiants d'une branche, adapter
`branch_normalized`, puis exécuter depuis la racine du dépôt :

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
