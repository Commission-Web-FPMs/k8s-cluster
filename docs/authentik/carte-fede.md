# Provisionner les accès de carte-fede

Les blueprints peuvent créer un compte de service, définir son token API et
configurer un provider OIDC associé à une application. Les credentials sont
générés avant le déploiement, puis scellés pour Authentik et carte-fede.
Les deux applications consomment ainsi les mêmes valeurs après la synchro.

Ce guide prépare `carte-fede-main`. Les exemples ne sont pas encore activés
dans les manifests et n'ont pas été exécutés sur Authentik.

## Objets à créer

| Objet | Nom ou identifiant |
| --- | --- |
| Groupes applicatifs | `membres`, `comite`, `admin` |
| Compte de service Authentik | `svc-carte-fede-main` |
| Rôle API de l'exemple | `carte-fede-main-api-reader` |
| Token API | `carte-fede-main-api` |
| Application et slug OIDC | `carte-fede-main` |
| Provider OIDC | `carte-fede-main-oidc` |
| Client ID OIDC | `carte-fede-main` |
| Secret dans `authentik` | `carte-fede-credentials` |
| Secret dans `carte-fede-main` | `authentik-credentials` |

Le token API authentifie le backend auprès de l'API Authentik. Le client OIDC
permet aux personnes de se connecter à carte-fede. Le secret OIDC ne remplace
pas le token API et les deux valeurs doivent rester différentes.

Le `ServiceAccount` Kubernetes du chart carte-fede concerne l'accès à
Kubernetes. Il ne crée pas le compte de service Authentik.

Références : [comptes de service](https://docs.goauthentik.io/users-sources/user/account-types/service-accounts/)
et [définition d'une clé de token par blueprint](https://docs.goauthentik.io/customize/blueprints/v1/models).

## Préparer les blueprints

Les exemples sont [groupes.yaml](./exemples/groupes.yaml) et
[carte-fede.yaml](./exemples/carte-fede.yaml). À l'activation, les copier sous
`manifests/authentik/blueprints/` et conserver ces noms d'objets pour les mises
à jour. Aucun UUID ou ID numérique de l'installation actuelle n'est nécessaire.

Le premier fichier crée les groupes sans définir leurs membres. Le second
crée le rôle, le compte technique, son token et le couple application/provider.
Les entrées `metaapplyblueprint` déclarent les dépendances sur les groupes,
les flows intégrés et les scopes système. La numérotation des fichiers ne
garantit pas leur ordre d'application.

Le rôle d'exemple accorde une lecture globale des utilisateurs et groupes.
Il ne permet pas de les créer, de les modifier ou de gérer leurs credentials.
Retirer ces permissions si l'application n'a pas besoin de cet accès global.
Pour gérer seulement certains utilisateurs, définir et tester les permissions
sur les objets concernés avant d'ajouter des droits d'écriture. Un dossier ou
un groupe métier ne restreint pas automatiquement une permission API globale.

L'accès OIDC autorise chacun des trois groupes. Le provider utilise le flow
intégré à consentement implicite pour cette application interne, et les scopes
`openid email profile`. Le mapping `profile` de cette version fournit le claim
`groups`, que carte-fede devra utiliser pour ses autorisations. L'exemple ne
demande pas de refresh token et n'accorde pas le scope d'accès à l'API Authentik.

Avant l'activation, renseigner l'URL exacte de callback depuis la configuration
ou le code OIDC de carte-fede. Son domaine actuel sur `main` est
`https://carte-fede-main.web.magellan.fpms.ac.be`, mais le chemin de callback
n'est pas défini dans ce dépôt. Ne pas inventer `/callback` ou utiliser une
regex pour contourner cette information manquante.

L'exemple suppose un backend qui conserve son secret, avec un client
`confidential` et le grant `authorization_code`. Si le client est exécuté
entièrement dans le navigateur, utiliser un client `public` avec PKCE et
adapter le blueprint et les secrets consommés.

Choisir aussi une paire certificat/clé RSA de signature dans
`System > Certificates`, par exemple le certificat auto-généré d'Authentik
s'il existe. Son nom sera transmis au worker. Le blueprint échoue si la paire
référencée manque ; il ne bascule pas silencieusement vers une signature avec
le secret du client.

Références : [dépendances entre blueprints](https://docs.goauthentik.io/customize/blueprints/v1/meta),
[scopes intégrés en 2026.8.2](https://github.com/goauthentik/authentik/blob/version/2026.8.2/blueprints/system/providers-oauth2.yaml)
et [provider OAuth/OIDC](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/).

## Générer et sceller les credentials

Cette procédure concerne une première création. Pour un service déjà branché,
suivre la section rotation plutôt que régénérer ses deux credentials.

Prérequis : Python 3, `kubectl`, `kubeseal` et un accès au contrôleur Sealed
Secrets. Exécuter ce bloc dans Bash, depuis la racine du dépôt. Il prépare
deux fichiers scellés sans appliquer de ressource au cluster. Les fichiers
en clair restent dans un répertoire temporaire privé, supprimé à la sortie.

```bash
(
set -euo pipefail
umask 077
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

Le scellement strict lie chaque fichier à son nom et son namespace. Copier
le ciphertext du premier dans le second ne fonctionnerait pas. Les fichiers
sources n'ont pas de saut de ligne final afin de préserver les clés exactes.

À l'activation, ajouter les SealedSecrets aux Kustomizations respectives,
créer un guide `.md` à côté de chacun et renseigner
[l'inventaire](../secrets-inventaire.md). Déclarer le namespace
`carte-fede-main` dans Git pour que le secret puisse être créé avant l'application.

## Raccorder Kustomize et le worker

Ajouter à `manifests/authentik/kustomization.yaml` lors de l'activation :

```yaml
configMapGenerator:
  - name: authentik-blueprints
    namespace: authentik
    files:
      - groupes.yaml=blueprints/groupes.yaml
      - carte-fede.yaml=blueprints/carte-fede.yaml
generatorOptions:
  disableNameSuffixHash: true
```

Le nom stable permet au chart Authentik de référencer la ConfigMap. Kustomize
ne réécrit pas automatiquement les noms placés dans les valeurs Helm d'une
Application Argo CD.

Fusionner les valeurs suivantes dans `spec.source.helm.valuesObject` de
l'Application Authentik. Conserver notamment le `worker.envFrom` du bootstrap.
Remplacer les deux valeurs `A_RENSEIGNER` avant le déploiement.

```yaml
blueprints:
  configMaps:
    - authentik-blueprints
worker:
  env:
    - name: CARTE_FEDE_OIDC_REDIRECT_URI
      value: A_RENSEIGNER_URL_HTTPS_COMPLETE_DU_CALLBACK
    - name: CARTE_FEDE_OIDC_SIGNING_KEY_NAME
      value: A_RENSEIGNER_NOM_DE_LA_PAIRE_CERTIFICAT_CLE
  volumes:
    - name: carte-fede-credentials
      secret:
        secretName: carte-fede-credentials
  volumeMounts:
    - name: carte-fede-credentials
      mountPath: /secrets/carte-fede
      readOnly: true
```

Le chart monte les blueprints dans le worker. Le tag `!File` lit les clés
dans le volume Secret distinct. Les références publiques passent ici par
`!Env`. Un changement de ces variables nécessite un redémarrage du worker.

Références : [tags des blueprints](https://docs.goauthentik.io/customize/blueprints/v1/tags)
et [montages du chart 2026.8.2](https://github.com/goauthentik/helm/blob/authentik-2026.8.2/charts/authentik/templates/worker/deployment.yaml).

## Brancher carte-fede

Le chart du dépôt `Commission-Web-FPMs/carte-fede-deployment` ne consomme pas
encore `env` ou `envFrom` dans son Deployment. Il faut ajouter ce support,
puis fournir les références via l'ApplicationSet de ce dépôt.

Le contrat proposé pour le backend est le suivant. Adapter les noms si le
code de carte-fede emploie déjà une autre convention.

| Variable | Valeur ou référence |
| --- | --- |
| `AUTHENTIK_API_URL` | `http://authentik-server.authentik.svc.cluster.local` |
| `AUTHENTIK_API_TOKEN` | Secret `authentik-credentials`, clé du même nom |
| `OIDC_ISSUER_URL` | `https://auth.fede.fpms.ac.be/application/o/carte-fede-main/` |
| `OIDC_CLIENT_ID` | `carte-fede-main` |
| `OIDC_CLIENT_SECRET` | Secret `authentik-credentials`, clé du même nom |
| `OIDC_REDIRECT_URI` | Même callback complet que dans le provider |
| `OIDC_SCOPES` | `openid email profile` |

Pour l'API, ajouter `/api/v3/` et envoyer `Authorization: Bearer <token>`.
Pour OIDC, conserver l'issuer public, y compris dans le backend. La découverte
est disponible sur
`https://auth.fede.fpms.ac.be/application/o/carte-fede-main/.well-known/openid-configuration`.
Utiliser ses endpoints pour les échanges OAuth et la validation des tokens.

Une ConfigMap applicative peut porter les paramètres publics et `envFrom`
charger le Secret. Aucun credential ne doit être intégré au bundle frontend.
La fiche YAML commune qui générera ces paramètres, les URLs et le blueprint
reste à mettre en place. Les valeurs ci-dessus définissent son premier contrat.

L'ApplicationSet utilise tous les noms de branches. Ne pas injecter le secret
de `main` dans tous les environnements : créer une identité et un client par
namespace, ou limiter d'abord l'intégration à `main`. La génération et le
nettoyage automatiques des identités de branches restent à implémenter.

## Contrôler l'activation

Après la synchro Argo CD, vérifier les résultats dans Authentik :

1. Les deux blueprints ont été appliqués sans erreur et les trois groupes
   existent. Une nouvelle application du blueprint préserve leurs membres.
2. Le compte technique est de type service account, avec uniquement le rôle
   de lecture prévu. Son token a l'intention API et la clé scellée attendue.
3. Depuis le backend, le token permet les lectures prévues. Une tentative de
   modification d'un utilisateur échoue avec le profil de cet exemple.
4. La découverte OIDC annonce l'issuer public attendu et une clé de signature
   exploitable. Le callback fonctionne avec la valeur exacte configurée.
5. Une personne appartenant à chaque groupe peut se connecter. Une personne
   sans ces groupes est refusée. Carte-fede applique ensuite ses propres
   droits métier selon les claims validés.
6. Sur une base Authentik neuve de validation, les objets techniques sont
   recréés avec les mêmes noms, client ID et credentials.

La santé des Pods et les sync waves Argo CD ne prouvent pas que les objets
Authentik existent. Prévoir un contrôle du résultat des blueprints et des
reprises de connexion côté carte-fede pour supporter le premier démarrage.

## Rotation et suppression

Le token de l'exemple est non expirant pour conserver la clé déclarée dans
Git. Sa rotation est une opération explicite. Créer un deuxième token avec
un nouvel identifiant et une nouvelle clé, le sceller des deux côtés, attendre
son application dans Authentik, puis redémarrer les consommateurs sur la
nouvelle clé. Supprimer ensuite l'ancien token avec `state: absent` dans le
blueprint. La rotation OIDC nécessite de coordonner le provider et le backend.

Un Secret chargé par `envFrom` ne redémarre pas le Deployment lorsqu'il change.
Le raccordement final devra déclencher ces redémarrages automatiquement.
Un fichier Secret monté est mis à jour par Kubernetes, mais il faut aussi
attendre la réapplication du blueprint pour que la base Authentik change.

Retirer une entrée ou un fichier ne supprime pas les objets Authentik.
Déclarer explicitement leur suppression avant de retirer le blueprint ou
son montage. Évaluer les dépendances avant de supprimer un groupe ou un provider.

Référence : [états des entrées de blueprint](https://docs.goauthentik.io/customize/blueprints/v1/structure).
