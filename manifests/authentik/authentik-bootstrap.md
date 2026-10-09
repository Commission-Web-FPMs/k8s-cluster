# Bootstrap Authentik

Le SealedSecret `authentik-bootstrap`, dans le namespace `authentik`, fournit
au worker le hash du mot de passe initial de `akadmin` et l'adresse
`commission.web.fpms@gmail.com`. Le mot de passe est conservé dans le gestionnaire
de mots de passe de l'équipe. Aucun token API n'est créé.

Sur une base neuve, le bootstrap intégré crée le compte `akadmin` avec ces
identifiants. Il ne met pas à jour un compte existant. Modifier ce secret ne
réinitialise donc pas un mot de passe déjà enregistré en base.

## Génération et scellement

Depuis la racine du dépôt, avec un worker Authentik 2026.8.2 disponible et un
accès au contrôleur Sealed Secrets :

```sh
set -eu
set -o pipefail
umask 077
bootstrap_dir=$(mktemp -d)
trap 'rm -rf "$bootstrap_dir"' EXIT

# Saisir le mot de passe conservé dans le gestionnaire de mots de passe.
python3 - "$bootstrap_dir/password" <<'PY'
import getpass
import sys
from pathlib import Path

password = getpass.getpass("Mot de passe initial de akadmin : ")
confirmation = getpass.getpass("Confirmer le mot de passe : ")
if not password or password != confirmation:
    raise SystemExit("Mot de passe vide ou confirmation différente.")
Path(sys.argv[1]).write_text(password)
PY

kubectl -n authentik exec -i deployment/authentik-worker -- \
  ak hash_password \
  < "$bootstrap_dir/password" \
| tr -d '\r\n' > "$bootstrap_dir/password-hash"

printf '%s' 'commission.web.fpms@gmail.com' > "$bootstrap_dir/email"

kubectl create secret -n authentik generic authentik-bootstrap \
  --from-file=AUTHENTIK_BOOTSTRAP_PASSWORD_HASH="$bootstrap_dir/password-hash" \
  --from-file=AUTHENTIK_BOOTSTRAP_EMAIL="$bootstrap_dir/email" \
  --dry-run=client -o yaml \
| kubeseal \
    --controller-namespace sealed-secrets \
    --scope strict \
    --format yaml \
> "$bootstrap_dir/authentik-bootstrap.sealed.yaml"

mv "$bootstrap_dir/authentik-bootstrap.sealed.yaml" \
  manifests/authentik/authentik-bootstrap.sealed.yaml
```

Seul le fichier scellé est enregistré dans Git. Le scellement est lié au nom
`authentik-bootstrap` et au namespace `authentik` du cluster cible.

Pour préparer une installation neuve sans worker existant, la même commande
`hash_password` est disponible dans l'image `ghcr.io/goauthentik/server:2026.8.2` :

```sh
docker run --rm -i ghcr.io/goauthentik/server:2026.8.2 hash_password \
  < "$bootstrap_dir/password" \
| tr -d '\r\n' > "$bootstrap_dir/password-hash"
```

Les variables de bootstrap ne servent pas à la rotation ultérieure du mot
de passe. Une rotation du compte se fait dans Authentik. Si le secret est
modifié avant le premier bootstrap, redémarrer le worker pour charger les
nouvelles variables d'environnement.

Références : [installation automatisée](https://docs.goauthentik.io/install-config/automated-install)
et [bootstrap intégré de la version 2026.8.2](https://github.com/goauthentik/authentik/blob/version/2026.8.2/blueprints/system/bootstrap.yaml).
