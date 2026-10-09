# Provisionnement Authentik de carte-fede

Le dépôt prépare le compte de service, son token API et le client OIDC de
`carte-fede-main`. Le code et le chart de carte-fede restent à adapter pour
consommer ces accès. Aucun utilisateur humain n'est déclaré dans le blueprint.

## Ressources gérées par Git

| Ressource | Définition |
| --- | --- |
| Groupes `membres`, `comite`, `admin`, `par défaut`, rôle API, SA, token, provider, application et bindings | [Blueprint fede.yaml](../../manifests/authentik/blueprints/fede.yaml) |
| URLs, issuer, callback, scopes et client ID | [Configuration commune](../../manifests/authentik/integrations/carte-fede-main/base/config.env) |
| Credentials montés dans Authentik | [SealedSecret et procédure](../../manifests/authentik/carte-fede-credentials.md) |
| Credentials préparés pour le backend | [SealedSecret et procédure](../../manifests/projects/carte-fede/authentik-credentials-main.md) |
| Validation et application à la synchronisation | [Job PostSync](../../manifests/authentik/provisioning-job.yaml) |

Kustomize génère la ConfigMap `authentik-config` dans les namespaces
`authentik` et `carte-fede-main` depuis le même fichier `config.env`.
Le worker monte sa copie sous `/config/carte-fede` et le Secret sous
`/secrets/carte-fede`. Le blueprint utilise `!File` pour lire ces paramètres.
La ConfigMap `authentik-blueprints` contient le fichier YAML monté par le chart.

Les groupes et l'intégration sont dans un seul blueprint. Les références aux
flows et scopes intégrés utilisent `metaapplyblueprint`, `!Find` et des noms
stables. Les objets liés dans ce fichier utilisent `!KeyOf`. Aucun UUID de la
base actuelle n'est nécessaire pour les recréer.

Le Job PostSync utilise la même image 2026.8.2 et les mêmes montages. Il
valide puis applique le blueprint et échoue si une étape échoue. Argo CD
peut donc signaler une erreur de provisionnement, même si les Pods sont sains.
Le worker conserve aussi sa découverte et sa réconciliation natives.
Conserver la version de l'image du Job alignée avec le chart Authentik lors
d'une mise à jour. Le Job reprend après un échec pendant au plus 15 minutes.

Références : [blueprints](https://docs.goauthentik.io/customize/blueprints),
[tags YAML](https://docs.goauthentik.io/customize/blueprints/v1/tags)
et [dépendances](https://docs.goauthentik.io/customize/blueprints/v1/meta).

## Compte de service et autorisations

Le compte `svc-carte-fede-main`, rangé sous `service-accounts/carte-fede`,
possède le rôle `carte-fede-main-api-reader`. Ce rôle accorde une lecture
globale des utilisateurs et groupes. Il ne permet ni leur création ni leur
modification. Le token `carte-fede-main-api` a l'intention `api`.

Pour permettre la gestion de certains utilisateurs, définir les objets et
les opérations autorisés avant d'étendre les permissions. Le dossier d'un
utilisateur ou son appartenance à un groupe ne limite pas automatiquement
une permission API globale. Les droits d'écriture seront un changement
séparé, testé avec des requêtes acceptées et refusées.

Les groupes applicatifs ont `is_superuser: false`. Ils ne définissent pas
leurs membres, afin que la réconciliation préserve les personnes ajoutées
via l'interface ou l'API. Le compte technique n'appartient à aucun de ces
groupes et n'obtient pas d'accès OIDC interactif par leurs bindings.

Référence : [comptes de service](https://docs.goauthentik.io/users-sources/user/account-types/service-accounts/).

## Contrat pour la future adaptation de carte-fede

Le backend pourra charger la ConfigMap `authentik-config` et le Secret
`authentik-credentials` de son namespace avec `envFrom`.

| Variable | Usage |
| --- | --- |
| `AUTHENTIK_API_URL` | Base interne `http://authentik-server.authentik.svc.cluster.local` ; ajouter `/api/v3/` pour les appels |
| `AUTHENTIK_API_TOKEN` | Bearer token API du compte de service |
| `OIDC_ISSUER_URL` | `https://auth.fede.fpms.ac.be/application/o/carte-fede-main/` |
| `OIDC_CLIENT_ID` | `carte-fede-main` |
| `OIDC_CLIENT_SECRET` | Secret du client confidentiel |
| `OIDC_REDIRECT_URI` | `https://carte-fede-main.web.magellan.fpms.ac.be/api/auth/oidc/callback` |
| `OIDC_SCOPES` | `openid email profile` |

Le callback `/api/auth/oidc/callback` est réservé pour la future implémentation.
Il n'existe pas dans le backend actuel. Si cette implémentation retient un
autre chemin, modifier `config.env` ; le provider et les deux ConfigMaps
utiliseront alors cette nouvelle valeur. Vérifier le support de `envFrom`
dans le chart et prévoir un redémarrage des Pods après les changements de
configuration ou de secrets chargés en environnement.

L'intégration utilise un client `confidential`, le grant `authorization_code`
et une comparaison stricte du callback. Le secret reste dans le backend.
La signature utilise la paire RSA `authentik Self-signed Certificate`, créée
par l'installation Authentik. Une paire absente fait échouer le provisionnement.
La découverte OIDC est accessible à l'URL publique :

```text
https://auth.fede.fpms.ac.be/application/o/carte-fede-main/.well-known/openid-configuration
```

Le mapping `profile` intégré transmet les groupes. Les bindings autorisent
une personne appartenant à `par défaut`, `membres`, `comite` ou `admin`. Carte-fede devra
valider les tokens et appliquer ses droits métier à partir de ces claims.
L'issuer reste public, y compris dans le backend. L'exemple ne demande pas de
refresh token et ne donne pas le scope d'accès à l'API Authentik aux personnes.

Références : [provider OIDC](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/)
et [scopes de la version 2026.8.2](https://github.com/goauthentik/authentik/blob/version/2026.8.2/blueprints/system/providers-oauth2.yaml).

## Première génération des credentials

Les credentials sont déjà scellés dans ce dépôt. Pour reconstruire, conserver
ces fichiers et restaurer la clé privée du contrôleur. La procédure suivante
sert seulement à créer une nouvelle intégration sans credentials existants.
Elle refuse de remplacer les fichiers actuels.

Avec Python 3, kubectl et kubeseal, exécuter depuis la racine dans Bash.
Les valeurs en clair ne sont pas affichées et leur répertoire temporaire
est supprimé à la sortie. Les deux secrets utilisent les mêmes valeurs,
chacune scellée pour son propre nom et namespace.

```bash
(
set -euo pipefail
umask 077
if [ -e manifests/authentik/carte-fede-credentials.sealed.yaml ] || \
   [ -e manifests/projects/carte-fede/authentik-credentials-main.sealed.yaml ]; then
  echo 'Credentials existants : utiliser une rotation coordonnée.' >&2
  exit 1
fi
credentials_dir=$(mktemp -d)
trap 'rm -rf "$credentials_dir"' EXIT

python3 - "$credentials_dir" <<'PY'
import secrets
import sys
from pathlib import Path

directory = Path(sys.argv[1])
for key in ("AUTHENTIK_API_TOKEN", "OIDC_CLIENT_SECRET"):
    (directory / key).write_text(secrets.token_urlsafe(64), encoding="utf-8")
PY

kubectl create secret generic carte-fede-credentials \
  --namespace authentik \
  --from-file=AUTHENTIK_API_TOKEN="$credentials_dir/AUTHENTIK_API_TOKEN" \
  --from-file=OIDC_CLIENT_SECRET="$credentials_dir/OIDC_CLIENT_SECRET" \
  --dry-run=client -o yaml \
| kubeseal --controller-namespace sealed-secrets --scope strict --format yaml \
> "$credentials_dir/authentik.sealed.yaml"

kubectl create secret generic authentik-credentials \
  --namespace carte-fede-main \
  --from-file=AUTHENTIK_API_TOKEN="$credentials_dir/AUTHENTIK_API_TOKEN" \
  --from-file=OIDC_CLIENT_SECRET="$credentials_dir/OIDC_CLIENT_SECRET" \
  --dry-run=client -o yaml \
| kubeseal --controller-namespace sealed-secrets --scope strict --format yaml \
> "$credentials_dir/carte-fede.sealed.yaml"

mv "$credentials_dir/authentik.sealed.yaml" \
  manifests/authentik/carte-fede-credentials.sealed.yaml
mv "$credentials_dir/carte-fede.sealed.yaml" \
  manifests/projects/carte-fede/authentik-credentials-main.sealed.yaml
)
```

Le scellement strict ne permet pas de copier le ciphertext entre namespaces.
Conserver les fichiers `.md` associés et [l'inventaire](../secrets-inventaire.md)
à jour. Les valeurs n'ont pas de saut de ligne final.

## Rotation et suppression

Le token est non expirant pour conserver la clé déclarée par Git. Pour le
remplacer sans interrompre un consommateur, déclarer un deuxième token avec
un nouvel identifiant et une nouvelle clé. Sceller la nouvelle clé pour les
deux namespaces, attendre l'application dans Authentik, puis basculer et
redémarrer le backend. Déclarer ensuite l'ancien token avec `state: absent`.
La rotation du secret OIDC doit aussi coordonner le provider et le backend.

Ne pas changer ces credentials seulement dans l'interface Authentik : une
réconciliation rétablirait les valeurs versionnées. Retirer une entrée ou un
fichier ne supprime pas les objets ; déclarer leur suppression explicitement
avant de retirer leur blueprint ou ses montages.

Les autres branches de carte-fede restent indépendantes. Chaque nouvelle
intégration doit avoir son propre client, SA, token et Secret applicatif.
La création automatique des identités à partir de l'ApplicationSet n'est pas
incluse dans ce premier lot.

Référence : [états des objets](https://docs.goauthentik.io/customize/blueprints/v1/structure).

## Validation avant livraison

Le test [test_blueprint.py](../../manifests/authentik/tests/test_blueprint.py)
s'exécute avec `ak shell` sur la version cible. Il reçoit un JSON contenant
`blueprint` et `configuration`, crée des credentials de test et annule sa
transaction. Il vérifie la création, la réapplication, la conservation des
appartenances humaines, les permissions, le token et les paramètres OIDC.
Il ne constitue pas un test de connexion de carte-fede, encore à adapter.

Depuis la racine, avec Python 3 et un accès kubectl au worker :

```sh
python3 manifests/authentik/tests/run.py
```

Le lanceur vérifie aussi le rendu Kustomize et l'identité des deux configurations
publiques. Les credentials de validation sont temporaires et ne remplacent
pas les valeurs scellées.

Le rendu des manifests peut être vérifié avec `kubectl kustomize manifests`.
Une restauration complète doit aussi tester les dépendances sur une base
neuve, avec la sauvegarde de la clé Sealed Secrets. Les utilisateurs humains
et leurs credentials restent des données PostgreSQL à sauvegarder.
