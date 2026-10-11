# Carte Fédé DEV — 11 octobre 2026

Environnement permanent : https://carte-dev.fede.fpms.ac.be. Publication réseau publique demandée par l’opérateur ; connexion métier exclusivement OIDC via les identités synthétiques du groupe `carte-fede-dev-testers`. Production conserve Flask et ses données PG18. Aucune bascule OIDC en production.

## GitOps et CI

- Application `develop`, issue de main `585a287eaa0f56b6001d879bc31a2a517cf9f944` : `f30f06c5` (OIDC/CI), `544eca3c` (documentation), `bb6c99d9` (ACL), `835ef6f9eea8a2b0db52acebc8b651b90ae2ffeb` (guards avant tout accès SQL). Main distant conservé.
- Chart `develop`, issu de main `16f5ca85d093510016147dc4f07eb4e4fc0bcfd2` : `8c600a6`, `82f59b3`, `a95adc5`, mises à jour CI `200a514` puis `1d49fd71806b12c68fd38c08dc7b246c85a041c3`. Main conservé.
- Infrastructure main : `1ea5f07` limite l’ApplicationSet historique à main ; `219a42a0c237cd034df0c1e997f37ce61a5016d1` ajoute DEV isolé. Argo ne génère pas d’application de production depuis develop.
- Trois workflows application réussis : [38141602821](https://github.com/Commission-Web-FPMs/carte-fede/actions/runs/38141602821), [38142342202](https://github.com/Commission-Web-FPMs/carte-fede/actions/runs/38142342202), [38142679515](https://github.com/Commission-Web-FPMs/carte-fede/actions/runs/38142679515).
- Push application develop → tests → packages `carte-fede-dev` et `carte-fede-dev-frontend` étiquetés SHA → commit des valeurs chart develop → réconciliation Argo normale. Les deux images déployées portent `835ef6f9eea8a2b0db52acebc8b651b90ae2ffeb`. Aucun hard refresh ou sync globale.

## Ressources et isolation

Namespace/AppProject/Application `carte-fede-dev`, backend et frontend 1/1. Quota requests512Mi/500m, limits1Gi/2CPU, huit Pods, aucun PVC. Backend requests64Mi/50m limits256Mi/500m ; frontend16Mi/10m limits64Mi/200m. NetworkPolicies : entrée Traefik seulement ; sortie DNS, PostgreSQL et HTTPS NPM nécessaires ; aucun SMTP. Secrets DEV distincts, chiffrés par SealedSecrets, récupération AES256 hors Git.

Base/rôle `carte_fede_dev`, PG18 UTF8/template0/ICU déterministe en-US, propriétaire dédié, aucun flag privilégié. PUBLIC n’a plus CONNECT/TEMPORARY ni privilège sur le schéma DEV. Zéro privilège de ce rôle sur les tables Carte Fédé production et Authentik, vérifié par inspection des catalogues avec postgres ; DEV n’a jamais connecté ses credentials à main. Neuf tables, quatre utilisateurs synthétiques (ADMIN/VERIFIER/MEMBER/ATTENTE), trois cartes et une inscription en attente. Pas de dump/import de données personnelles. Tous les objets DEV appartiennent au rôle dédié. IBAN/BIC vides, montant null ; emails neutralisés et routes de paiement refusées. Les CR base/rôle ont retention et protection prune/delete.

Authentik : application/provider/client/scope DEV distincts, callback HTTPS strict, issuer par provider, signatures RS256, audience/state/nonce/expiration vérifiés, Authorization Code + PKCE S256. `sub` user_uuid est lié à un UUID métier par un mapping privé autoritaire indépendant du claim. Quatre comptes synthétiques, trois actifs ; ATTENTE désactivé. Groupe non privilégié, aucun accès DEV ajouté aux 290 identités importées. Session serveur limitée, cookie __Host Secure/HttpOnly/SameSite=Lax ; contrôle utilisateur/groupe à chaque requête, refus en cas d’indisponibilité Authentik. Logout révoque le token et la session Carte Fédé ; la session SSO Authentik peut permettre une nouvelle connexion explicite.

## NPM et protections

DNS public 193.190.211.21 vers NPM ; Proxy Host dédié32 → http://172.17.0.110:80, certificat45 couvrant le domaine, Force SSL activé. Le Proxy Host production n’a pas été modifié. Traefik ne change que l’ajout du namespace DEV surveillé : RBAC/Gateway identiques, rollout maxSurge1/maxUnavailable0, trois endpoints disponibles.

Écart détecté avant ouverture : le template NPM protégeait uniquement l’hôte2. DEV est resté fermé jusqu’à correction. Le template est désormais protégé aussi pour l’hôte32, avec comparaison des rendus des 24 autres hôtes identiques (23 actifs). Headers Host/X-Forwarded-Host fixés au domaine, X-Forwarded-For à remote_addr, confiance real_ip limitée aux sockets Unix, Forwarded/prefix entrants supprimés. Logs uniquement méthode/statut/durée, error_log /dev/null ; marqueurs query/cookie/referer/agent et requêtes malformées absents des logs.

Persistance sans recréation NPM : fichier public `/home/magellan/reverse-proxy/carte-fede-dev-proxy-template.conf`, monté read-only à `/app/templates/proxy_host.conf` dans Compose lors des recréations futures ; copie identique déjà active dans le conteneur courant. L’image actuelle ne change pas. Tous les autres paramètres Compose sont identiques ; `docker compose config --quiet` passe. Aucun redémarrage NPM. Toute nouvelle recréation partagée doit conserver ce montage et être préparée avec rollback/fenêtre appropriée.

## Recette et preuve de préservation

Douze tests unitaires OIDC, six tests backend de confidentialité, deux frontend et tests CI PostgreSQL18 réussis. Recette réelle des trois rôles actifs : authentification native synthétique, callback signé, permissions administrateur, mauvais Origin refusé, cookie sécurisé, logout et invalidation de session. ATTENTE refusé, anonymes refusés sur les APIs sensibles, auth locale et paiements interdits. Recette adverse : callback rejoué refusé, désactivation et retrait du groupe invalidant les sessions, claim UUID signé falsifié refusé ; seules identités synthétiques possédées modifiées puis rétablies. Connexion directe Traefik avec XFF usurpé refusée403.

46 sondes HTTP/TLS sur les 23 Proxy Hosts existants, sans erreur de transport, identiques avant/après. Le premier inventaire contenait quatre URLs wildcard invalides : conservé comme historique, remplacé par une preuve distincte avec noms de sonde wildcard résolus. Surveillance initiale : 165 échantillons en898,23s, zéro échec Carte Fédé/Authentik. Contrôle control-plane cinq minutes : zéro marqueur etcd/API négatif.

Les configs/Secrets de production, métadonnées PostgreSQL, routes et autres hôtes NPM correspondent au baseline privé. Les 290 comptes importés conservent UUID/verifiers conformes au journal. Exception opérateur explicitement confirmée : connexion personnelle à15:18:13 CEST, rehash natif d’un compte préexistant PBKDF2→Argon2, aucun autre champ/date de changement du mot de passe modifié. Baseline original conservé, exception exacte enregistrée séparément ; toute autre dérive bloque. Aucun hash individuel affiché ni réinitialisé.

## Sauvegardes et récupération

Répertoire laptop privé0700 `/home/theau/.local/share/carte-fede-migration-backups`, archives AES256, passphrase privée0600 séparée dans `/home/theau/.local/share/carte-fede-migration-keys/export-20261010.passphrase`. Ne pas afficher/déchiffrer vers stdout ni placer ces fichiers dans Git.

- `carte-fede-dev-recovery-20261011T125525Z.json.gpg`,1190 octets, SHA256 `94c14e8ae936212c2f4e0c1646edeecdc90ea3a557e6502634c3e692c5b8bdb9` : credentials DEV et comptes synthétiques, déchiffrement comparé en mémoire à l’original.
- `npm-before-carte-dev-20261011T130214Z.json.gpg`,6727101 octets, SHA256 `13b08acb362aa5a40ab897586f14973c99d75d4e4252bb5fa2dd71be8f56b32a` : snapshot SQLite cohérent et intègre, Compose/runtime/configs/certificats, déchiffrement identique en mémoire. Capture précédant les ajouts DEV ; sert de référence pour récupération sélective, jamais de restauration globale automatique.
- Sauvegardes/labs historiques conservés ; Job de validation Authentik isolé `carte-fede-dev-blueprint-validation` terminé et conservé dans le namespace de répétition.

## Exploitation et rollback limité

Fermer uniquement DEV en cas d’incident :

```sh
cd /home/theau/Documents/ChatGPT/k8s-cluster
python3 migration/npm-dev-host.py close
python3 migration/dev-preflight.py --compare
python3 migration/dev-npm-regression.py --compare
```

Maintenir les protections NPM pendant un rollback applicatif. Revenir à une SHA DEV précédemment validée dans les deux `image.tag` du chart develop, committer/pousser uniquement develop puis attendre la réconciliation normale. Arrêter les pushes application pendant ce rollback pour éviter une nouvelle mise à jour CI. Préserver main et les ressources PostgreSQL/Auth existantes. Aucun rollback global NPM, Authentik ou PG ; aucune suppression automatique de base/lab.

Initialisation idempotente via le Job PreSync à chaque livraison. Reset destructif des seuls fixtures DEV après décision explicite : fermer DEV, suspendre les écritures et exécuter `python scripts/init_dev_data.py --reset-synthetic-dev` avec l’image/Secret DEV dans le namespace DEV ; le programme vérifie APP_ENV/base/rôle avant tout SQL. Ne jamais adapter cette commande à main. Une réinitialisation conserve le mapping fixe des identités synthétiques.

Pour accéder aux credentials de test, déchiffrer l’archive DEV uniquement dans un outil local privé/en mémoire ; aucun affichage ici. Avant OIDC production, reprendre ETAPE8B-PREPARATION.md : nouveau GO, inventaire/synchronisation sous gel autorisé, mapping autoritaire des290 identités et états pending, tests métier et capacité Authentik. Le pic historique960Mi sous1Gi ne valide pas une ouverture générale.

## Décision ultérieure : accès de tous les comptes actifs

La limitation synthétique décrite dans la recette initiale est remplacée sur décision explicite de l’opérateur. Tous les comptes actifs Authentik peuvent se connecter ; chaque compte existant obtient uniquement un profil pseudonyme MEMBER dans DEV au premier login. UUID dérivé de sub signé, recalculé indépendamment côté RP et scope, aucune copie de données personnelles/cartes/rôles main, aucun ajout de groupes ni modification des utilisateurs Authentik existants. Comptes désactivés refusés ; fixtures ADMIN/VERIFIER/MEMBER/ATTENTE conservées pour recette. CI application57fb78af réussie, quatorze tests OIDC ; blueprint validé dans un nouveau Job de laboratoire conservé. Une deuxième connexion opérateur à15:50:11 CEST a rehashé un verifier importé scrypt→Argon2 ; comparaison agrégée prouve tous les autres champs inchangés, date de changement identique, journal original conservé.

Protection supplémentaire : developf976611b79bf5772177627dd5903f4784a37dee4 vérifie aussi le rôle MEMBER des profils existants à chaque requête, CI38145659695 réussie et15 tests OIDC. Les deux marqueurs ponctuels etcd185ms/109ms ont conduit à différer la politique ; une fenêtre cinq minutes sans marqueur a ensuite passé à16:07 CEST, sans échec HTTP observé.

## Correction architecturale du11 octobre2026 — état courant

La création automatique de profils MEMBER est abandonnée. Copie PROD → DEV explicitement autorisée et réalisée, toutes les lignes identiques au snapshot chiffré :286 utilisateurs,366 cartes,4 inscriptions en attente,9 tables. Rôles7 ADMIN/9 VERIFIER/270 MEMBER,230466 ADMIN. Les286 bindings proviennent du journal d'import vérifié contre UUID/attributs/run et comptes Authentik existants ; aucune modification de ces comptes. Les quatre inscriptions non approuvées restent default et désactivées.

Backend ef56604e : aucun auto-provisionnement, rôles PostgreSQL rechargés chaque requête, administration ADMIN, vérification ADMIN/VERIFIER. Recette intégrée complète sur fixtures avant copie : permissions des trois rôles, claims admin/superuser forgés sans effet, promotion/rétrogradation en cours de session, mise en attente401, auto-élévation MEMBER403. Seize tests unitaires avec le verrou de réinitialisation avant SQL. DEV fermé et0/0 pendant la copie et la publication du mapping ; PreSync synthétique désactivé. Cette section remplace les anciens critères de MEMBER automatique et données synthétiques uniquement.
