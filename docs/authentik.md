# Authentik, fournisseur d'identité de la Fédération

URL publique : **https://auth.web.magellan.fpms.ac.be/**.

Cette modification reprend une installation existante en GitOps.
L’inspection live via SSH a confirmé que l’Application Argo CD
`authentik` est Synced/Healthy en **2026.8.2** ; la base CNPG `authentik` et les Secrets
`authentik/authentik-secret` et `comweb-db/authentik-db-credentials` existent
depuis dix jours. La cible est une mise à jour en **2026.8.3**, sans rotation
de credentials, réinitialisation de compte ou recréation de base.

```text
Navigateur HTTPS -> NPM (172.17.0.1, terminaison TLS hors cluster)
                -> HTTP 172.17.0.110:80 (MetalLB / Traefik)
                -> Gateway traefik/public, listener http (8000)
                -> HTTPRoute authentik/authentik, chemin /
                -> Service authentik-server:80 -> serveur:9000
                -> comweb-db-rw.comweb-db.svc.cluster.local:5432
                   base authentik, propriétaire authentik
Worker Authentik -> même base PostgreSQL
```

## Choix vérifiés

Le [chart officiel](https://github.com/goauthentik/helm/releases/tag/authentik-2026.8.3)
est figé à **2026.8.3**, comme son application, après consultation de l'index
officiel le 26 septembre 2026. Le Service `authentik-server`, son port 80 et
sa cible 9000 sont vérifiés sur le rendu Helm avec le nom de release explicite
`authentik`. Le chart ne produit ni Ingress ni HTTPRoute ; la route est dans Git.

Un serveur et un worker sont déployés avec les probes natives du chart. Chaque
Pod demande 100m CPU et 512Mi de RAM, avec des plafonds de 1 CPU et 1Gi : 1Gi
réservé au total, hors PostgreSQL. Mesurer la consommation et les OOM après les
migrations de mise à jour et sous charge ; ce dimensionnement n'est pas une mesure
de capacité. Un seul serveur implique une interruption possible lors d'une
panne de son nœud, même si ses données survivent.

[Redis a été supprimé depuis 2025.10](https://docs.goauthentik.io/releases/2025.10/).
Le worker reste nécessaire aux tâches de fond. Aucun RBAC d'outpost géré ni
token de ServiceAccount n'est attribué aux Pods. La configuration non sensible
est dans `global.env` et les deux valeurs sensibles dans des `secretKeyRef`
obligatoires vers `authentik-secret`. `authentik.existingSecret.secretName`
charge également ses autres clés existantes ; `authentik.enabled: false`
désactive seulement la génération
du Secret de configuration par Helm, pas les Deployments.

Selon l'[architecture actuelle](https://docs.goauthentik.io/core/architecture/),
les comptes et la configuration persistent dans PostgreSQL. `/data` est
facultatif : sans montage, utiliser des URL externes pour les icônes et fonds,
sans fichiers téléversés ni rapports CSV persistants locaux. Aucun `emptyDir`
n'est utilisé comme faux stockage durable. Avant d'activer ces usages, ajouter
un stockage partagé durable ou le backend S3 natif, avec sa sauvegarde.
Les certificats externes et templates d'email personnalisés ne sont pas montés.

L'opérateur CNPG existant est **1.30.0** (chart 0.29.0). Le rôle est déclaré
dans `comweb-db.spec.managed.roles`, sans superuser, CREATEDB ou CREATEROLE.
La ressource `Database` reprend la base existante avec le même nom,
`owner: authentik` et une politique `retain`. Le rôle existant est réconcilié
avec le mot de passe actuel de `authentik-db-credentials` ; aucun nouveau
mot de passe n’est fourni. Le bootstrap implicite de `app` et les trois volumes existants restent
inchangés. Les droits SQL ne constituent pas à eux seuls une isolation réseau
entre toutes les bases du cluster.

Références : [rôles CNPG 1.30](https://cloudnative-pg.io/docs/1.30/declarative_role_management/),
[bases CNPG 1.30](https://cloudnative-pg.io/docs/1.30/declarative_database_management/).

## Proxies, DNS et TLS

`AUTHENTIK_WEB__BASE_URL` fixe l'URL externe, option introduite en
[2026.8](https://docs.goauthentik.io/releases/2026.8/). Traefik fait confiance
aux headers de **172.17.0.1/32 seulement**. Ce réglage de l'entrypoint `web`
est partagé avec les autres routes : elles conservent aussi les headers HTTPS
émis par NPM. `externalTrafficPolicy: Local` reste en place.

Authentik fait confiance au réseau des Pods `10.244.0.0/16`. Une NetworkPolicy
limite l'entrée du serveur aux Pods Traefik du namespace `traefik`, port 9000 ;
elle laisse les sorties, notamment SQL et DNS, inchangées. Vérifier son
application par kube-router sur le cluster réel. Les probes provenant du nœud
restent possibles.

NPM et le Gateway `public` ne sont pas modifiés. Vérifications manuelles :

- Le DNS du nom public doit arriver sur l'entrée publique de NPM, pas sur une
  adresse de Pod ni sur l'IP privée MetalLB depuis Internet.
- Si le Proxy Host n'existe pas, l'administrateur NPM doit le créer pour ce
  domaine, cible **HTTP 172.17.0.110:80**, avec le certificat TLS côté NPM.
- Conserver `Host`, écraser les headers fournis par le client et transmettre
  `X-Forwarded-Proto: https`, `X-Forwarded-For`, ainsi que les upgrades WebSocket.
- Vérifier que l'IP source réellement vue par Traefik est `172.17.0.1`.

Voir [reverse proxy Authentik](https://docs.goauthentik.io/install-config/reverse-proxy)
et [confiance Traefik](https://doc.traefik.io/traefik/reference/install-configuration/entrypoints/#forwarded-headers).

## Reprise GitOps et mise à jour 2026.8.2 -> 2026.8.3

Avant synchronisation, sauvegarder la base et les credentials existants selon
la procédure ci-dessous. Ne pas restaurer de dump pendant cette reprise : la
base live reste en place. Ne pas exécuter de setup initial ni de commande de
changement du mot de passe administrateur.

1. Comparer l’Application live au manifeste proposé : même nom `authentik`,
   namespace `argocd`, destination `authentik` et release Helm `authentik`.
   Comparer aussi les volumes, les variables et les ressources actuelles : si
   l’existant utilise `/data`, S3, SMTP ou des templates supplémentaires, les
   conserver dans les valeurs avant synchronisation. Ne pas supprimer un
   stockage existant sur la seule base du dimensionnement proposé ici.
2. Les deux Secrets ont été rescellés avec toutes leurs données actuelles et
   activés dans Kustomize. Leur mot de passe commun a été vérifié sans affichage.
   Ils sont déjà détenus par les SealedSecrets correspondants : aucune annotation
   live n’est nécessaire. Voir [la procédure reproductible](../manifests/authentik/secrets.md).
3. Vérifier que la ressource `Database` live désigne déjà `comweb-db`, la base
   `authentik` et son propriétaire `authentik`. Conserver son UID et celui du
   Cluster. `spec.managed.roles` reprend ce rôle via le Secret SQL existant.
   Ne lancer ni DELETE, ni DROP/CREATE DATABASE, ni bootstrap initdb.
4. Faire relire le diff Argo CD : aucune suppression/remplacement de Secret,
   Database, Cluster ou PVC. Si ces ressources sont suivies par une autre
   Application GitOps, retirer leur ancienne déclaration en préservant les
   ressources (`Prune=false`) avant de transférer leur gestion à la racine.
   Ne pas conserver deux sources GitOps concurrentes. Les annotations live de
   protection doivent aussi être préservées dans l’ancienne source jusqu’au transfert.
5. Après revue et fusion manuelle, laisser l’application racine reprendre
   l’Application existante et passer son chart de 2026.8.2 à 2026.8.3. Ne pas
   désinstaller/réinstaller Authentik et ne pas faire de `helm upgrade` parallèle.
   L’HTTPRoute peut être activée directement pour cette instance déjà initialisée.

```bash
# Inspection sans afficher les valeurs Helm, susceptibles de contenir des secrets.
kubectl -n argocd get application authentik \
  -o jsonpath='{.metadata.uid}{" "}{.spec.source.targetRevision}{" "}{.spec.source.helm.releaseName}{"\n"}'
kubectl -n comweb-db get database authentik \
  -o jsonpath='{.metadata.uid}{" "}{.spec.cluster.name}{" "}{.spec.name}{" "}{.spec.owner}{"\n"}'
kubectl -n comweb-db get cluster comweb-db -o jsonpath='{.metadata.uid}{"\n"}'
kubectl -n authentik get secret authentik-secret -o jsonpath='{.metadata.uid}{"\n"}'
kubectl -n comweb-db get secret authentik-db-credentials -o jsonpath='{.metadata.uid}{"\n"}'
# Après fusion manuelle et activation des fichiers scellés dans Kustomize :
kubectl -n argocd annotate application root argocd.argoproj.io/refresh=hard --overwrite
kubectl -n authentik wait sealedsecret/authentik-secret --for=condition=Synced --timeout=120s
kubectl -n comweb-db wait sealedsecret/authentik-db-credentials --for=condition=Synced --timeout=120s
kubectl -n authentik rollout status deployment/authentik-server --timeout=600s
kubectl -n authentik rollout status deployment/authentik-worker --timeout=600s
```

Comparer les UID avant/après et vérifier la connexion avec un compte existant
sur **https://auth.web.magellan.fpms.ac.be/**. Ne pas utiliser
`/if/flow/initial-setup/` pour cette installation déjà initialisée. Un
port-forward reste possible pour diagnostiquer l’instance sans changer ses comptes :

```bash
kubectl -n authentik port-forward svc/authentik-server 9000:80
```

Les vagues 0/1/2/3 ordonnent le rescellement, la gestion du rôle et de la base,
puis l’Application et la route. Les Secrets live restent utilisables avant le merge. Les vagues ne constituent pas une transaction avec les Applications
filles ; vérifier les statuts après réconciliation.

## Validation sur le cluster

```bash
kubectl -n argocd get application authentik \
  -o jsonpath='{.status.sync.status}{" "}{.status.health.status}{"\n"}'
kubectl get pods -n authentik
kubectl get svc -n authentik
kubectl get httproute -n authentik
kubectl -n authentik get httproute authentik -o yaml
kubectl -n traefik get gateway public -o yaml
kubectl -n authentik logs deployment/authentik-server -c server --tail=100
kubectl -n authentik logs deployment/authentik-worker -c worker --tail=100
kubectl -n authentik get events --sort-by=.lastTimestamp
kubectl -n traefik logs daemonset/traefik --tail=100
kubectl -n comweb-db get cluster comweb-db -o jsonpath='{.status.managedRolesStatus}{"\n"}'
kubectl -n comweb-db get database authentik \
  -o jsonpath='{.status.applied}{" "}{.status.observedGeneration}{" "}{.metadata.generation}{"\n"}'
```

Attendre `Synced Healthy`, les deux Pods Ready, `status.applied: true` avec
génération observée à jour pour la base, et `Accepted=True` / `ResolvedRefs=True`
pour le parent `traefik/public` de la route. Contrôler le protocole et l'accès SQL
avec les identifiants réellement utilisés par Authentik, sans les afficher :

```bash
kubectl -n authentik exec deployment/authentik-server -c server -- \
  ak shell -c 'from django.db import connection; c=connection.cursor(); c.execute("SELECT current_database(), current_user"); print(c.fetchone())'
curl -fsS https://auth.web.magellan.fpms.ac.be/-/health/ready/
curl -sS -D - -o /dev/null https://auth.web.magellan.fpms.ac.be/
# Diagnostic depuis le réseau privé : ne teste pas la terminaison TLS NPM.
curl -sS -D - -o /dev/null -H 'Host: auth.web.magellan.fpms.ac.be' http://172.17.0.110/
```

La requête SQL doit retourner `('authentik', 'authentik')`. Dans un navigateur,
tester connexion, déconnexion et reconnexion ; aucun redirect absolu ne doit
pointer vers HTTP, localhost ou un nom de Service. Vérifier l'IP client dans
les événements Authentik, le cookie de session sécurisé et l'absence de contenu
mixte ou de boucle de redirection. Un header HTTPS envoyé par `curl` depuis un
poste autre que NPM ne prouve rien : Traefik doit justement le refuser.

Relever un utilisateur et une configuration déjà existants, sans les modifier,
puis, pendant une fenêtre de test :

```bash
kubectl -n authentik rollout restart deployment/authentik-server deployment/authentik-worker
kubectl -n authentik rollout status deployment/authentik-server --timeout=600s
kubectl -n authentik rollout status deployment/authentik-worker --timeout=600s
```

Retrouver l'utilisateur et la configuration, puis répéter la connexion. Cela
vérifie la persistance au redémarrage, pas une restauration de sauvegarde.

## Sauvegarde et restauration

Les trois instances CNPG sont des réplicas, **pas une sauvegarde**. L'archivage
WAL/Barman hors site est encore un TODO du cluster ; ce changement ne prétend
pas l'avoir installé. En attendant, effectuer un dump logique hors dépôt dans
un emplacement protégé, puis le chiffrer et le copier hors des trois VM :

```bash
umask 077
backup_dir=$(mktemp -d /tmp/authentik-backup.XXXXXX)
primary=$(kubectl -n comweb-db get cluster comweb-db -o jsonpath='{.status.currentPrimary}')
kubectl -n comweb-db exec "$primary" -c postgres -- \
  pg_dump -U postgres -d authentik -Fc > "$backup_dir/authentik.dump"
test -s "$backup_dir/authentik.dump"
```

Contrôler le code retour du dump avant transfert. Un dump est cohérent pendant
les écritures ; pour une sauvegarde avant mise à jour, arrêter aussi les
écritures. Conserver avec lui la version du chart/image, les deux secrets
dans le gestionnaire de mots de passe, le Git correspondant et la clé privée
Sealed Secrets ([sauvegarde commune](secrets.md#sauvegarder-et-restaurer-la-clé)).
Les exports de blueprints seuls ne remplacent pas une sauvegarde de la base.

Tester d'abord la restauration dans un environnement isolé, avec la **même
version Authentik** et PostgreSQL compatible. Pour une restauration en place,
prévoir une maintenance et sauvegarder l'état courant avant de l'écraser :

1. Dans Git, mettre `server.replicas` et `worker.replicas` à 0, retirer
   temporairement la route des ressources, faire synchroniser Argo CD et
   attendre l'arrêt des Pods. Un `kubectl scale` seul serait annulé par selfHeal.
2. Restaurer si nécessaire la clé Sealed Secrets, puis les deux Secrets et leur
   **clé Authentik d'origine**. Attendre rôle et base CNPG ; ne pas supprimer
   le Cluster ni toucher à la base `app`.
3. Restaurer le dump Authentik uniquement :

```bash
# Définir backup_dir vers la sauvegarde récupérée, hors du dépôt.
primary=$(kubectl -n comweb-db get cluster comweb-db -o jsonpath='{.status.currentPrimary}')
kubectl -n comweb-db exec -i "$primary" -c postgres -- \
  pg_restore -U postgres -d authentik --role=authentik --no-owner \
  --no-privileges --clean --if-exists --single-transaction --exit-on-error \
  < "$backup_dir/authentik.dump"
```

4. Remettre les deux réplicas à 1 par Git, conserver la version correspondant
   au dump, vérifier SQL, utilisateurs et configuration par port-forward, puis
   réactiver la route. Répéter les tests HTTPS. Un retour à un ancien chart après
   migration SQL exige la sauvegarde correspondante, pas simplement un rollback
   de l'image. L'option `retain` de la base ne protège pas d'une suppression du
   Cluster CNPG lui-même.

## Mise à jour et vérification locale

Lire les notes de version officielles, sauvegarder et tester la restauration.
Parcourir chaque version majeure intermédiaire imposée par Authentik. Modifier
`targetRevision` dans l'Application, vérifier les valeurs et le rendu du nouveau
chart, puis passer par revue et GitOps. Ne pas lancer un `helm upgrade` parallèle
à Argo CD. Les migrations sont exécutées au démarrage ; contrôler les logs des
deux composants et répéter les tests précédents.

Le contrôle local nécessite Helm, kubectl et Python 3 avec PyYAML :

```bash
helm repo add authentik https://charts.goauthentik.io
helm repo update authentik
helm pull authentik/authentik --version 2026.8.3 --destination /tmp
python3 manifests/authentik/check.py /tmp/authentik-2026.8.3.tgz
git diff --check
```

Le contrôle rend le chart et Kustomize sans accès au cluster, vérifie les
références du Service, les secrets obligatoires, les probes et l'absence de
PostgreSQL embarqué / RBAC supplémentaire. Il ne prouve pas l'état live.

Validation réalisée lors de l'ajout : ce contrôle et `helm lint` passent,
les manifests Cluster/Database respectent les schémas officiels CNPG 1.30.0,
et le rendu Traefik 41.4.0 contient
`--entryPoints.web.forwardedHeaders.trustedIPs=172.17.0.1/32`.
La syntaxe Bash des procédures et `git diff --check` ont également été vérifiées.
L’inspection SSH en lecture seule confirme trois nœuds Ready, Authentik
2026.8.2 Synced/Healthy, les deux Pods Running, aucun volume monté, et la base
`authentik` appliquée avec `retain`. Les Secrets appartiennent déjà aux
SealedSecrets de mêmes noms ; leurs ciphertexts ont été rescellés puis validés
par le contrôleur, sans modifier le live. Les données et UID sont inchangés.
Les ressources CPU/mémoire étaient absentes des Deployments live ; cette branche
les ajoute, ainsi que la NetworkPolicy, la désactivation des droits d’outposts
gérés, l’URL externe et la route. `sslmode=require` est explicitement conservé.
La connexion SQL du Pod actuel a été validée : base `authentik`, utilisateur
`authentik` et TLS actif (`pg_stat_ssl.ssl=true`). Aucune HTTPRoute n’existe
actuellement dans ce namespace. Le déploiement 2026.8.3, la route et HTTPS
après merge restent à vérifier.

Le rôle live est LOGIN, INHERIT, sans privilèges élevés, sans appartenance à
un autre rôle, sans expiration, avec connectionLimit=-1. Cela correspond au
manifeste proposé. Le code [CNPG 1.30.0](https://github.com/cloudnative-pg/cloudnative-pg/blob/v1.30.0/internal/management/controller/roles/roles.go)
réconcilie un rôle trouvé par ALTER ROLE ; CREATE ne concerne que les rôles absents,
et DROP exige `ensure: absent`. L’adoption peut réécrire le vérificateur SCRAM
avec un nouveau sel en utilisant **le même mot de passe** du Secret : cela ne
change pas le credential applicatif. Ce comportement est explicite dans
[Update](https://github.com/cloudnative-pg/cloudnative-pg/blob/v1.30.0/internal/management/controller/roles/postgres.go).
Aucune modification SQL n’a été exécutée ici.

UID de référence pour les vérifications après merge :

| Ressource | UID |
| --- | --- |
| Application authentik | `697ab95c-0519-4cda-9879-6197c40cce46` |
| Cluster comweb-db | `6f0a455a-b180-4797-926f-9fe8409cd030` |
| Database authentik | `fcaa1680-e09b-46ed-b434-48fade374a99` |
| Secret authentik/authentik-secret | `a8c1b766-4c6b-4d52-b859-0f4dc98e7f77` |
| Secret comweb-db/authentik-db-credentials | `e55f0d7e-5aa2-41c2-a339-0aedc2978eff` |

## Future intégration OIDC, sans migration maintenant

```text
Application -> OIDC Authorization Code Flow -> Authentik
Application locale <- sub stable du token validé <- Authentik

Authentik : username = 230466, sub = abc123
Carte     : authentik_sub = abc123
```

Chaque application aura son propre couple Provider/Application OIDC, son
client et ses URI de retour strictes. Utiliser Authorization Code avec PKCE,
valider signature, issuer, audience, state et nonce. Fixer le mode de génération
du `sub` sur une valeur immuable ; ne pas utiliser username/email comme clé de
liaison. Sa stabilité dépend aussi de la conservation de la clé Authentik et
du paramétrage du Provider. Une application qui accepte plusieurs issuers doit
identifier le compte par `(iss, sub)`.

Les permissions métier restent locales : `ADMIN`, `MEMBER`, `VERIFIER`, etc.
de Carte ne sont pas transférés. Aucun Provider Carte/CAP, aucune modification
de `carte-fede` et aucune migration utilisateur ne sont inclus.

Avant cette migration : valider HTTPS et headers, MFA et récupération admin,
dimensionnement, redémarrage, sauvegarde hors site et restauration testée ;
préparer SMTP pour les emails de récupération, puis valider un client OIDC de
test et le choix du `sub`. Le checkout local `authentik-server` ne contient
actuellement qu'un README de titre ; aucune configuration Compose n'a été copiée.
