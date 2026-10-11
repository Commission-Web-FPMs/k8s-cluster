# Carte Fédé DEV

DEV est public sur https://carte-dev.fede.fpms.ac.be, avec authentification OIDC. La production main conserve Flask. La base/rôle dédiés carte_fede_dev utilisent PostgreSQL18, UTF8 et ICU déterministe en-US. Le frontend public ne donne aucun accès anonyme aux données métier.

## Identité et permissions

Authentik gère exclusivement l'identité et l'authentification. Les groupes, notamment membres, servent au contrôle d'accès et ne déterminent jamais les rôles métier. ADMIN Carte Fédé ne confère aucun privilège administratif Authentik. Aucun rôle Carte Fédé n'est synchronisé vers Authentik.

Le backend vérifie RS256, issuer DEV exact, audience/client, exp/iat/azp, nonce, state et PKCE. Un mapping privé vérifié associe sub à l'UUID métier, dans le périmètre de cet issuer exact. Lorsqu’il est présent, le claim UUID doit correspondre au mapping et à un utilisateur existant en PostgreSQL. Une identité active existante approuvée localement peut conserver un claim vide : son association issuer+sub vérifiée en PostgreSQL suffit, sans mutation de ses attributs globaux. Aucun rapprochement par email, nom ou matricule, aucune création automatique MEMBER. Un utilisateur Authentik actif sans association vérifiée est refusé. Les comptes désactivés et rôles ATTENTE sont refusés.

Les rôles ADMIN, VERIFIER et MEMBER proviennent exclusivement de PostgreSQL, rechargés à chaque requête. Le backend contrôle les endpoints sensibles : administration ADMIN uniquement, vérification des cartes ADMIN/VERIFIER, données personnelles du compte authentifié. L'administrateur peut modifier les rôles avec les fonctionnalités existantes ; promotion, rétrogradation et mise en attente prennent effet pendant les sessions existantes. Toutes ces écritures restent dans carte_fede_dev.

La politique Authentik DEV accepte les identités actives ; elle ne remplace pas le contrôle d'association métier du backend. Les inscriptions non validées importées dans default restent désactivées. Trois comptes de recette synthétiques possèdent désormais des profils DEV distincts ADMIN/VERIFIER/MEMBER, associés uniquement à leurs propres UUID. Les autres identités sans association restent refusées.

## Données et sécurité

La copie réelle PROD → DEV du11 octobre2026 a été explicitement autorisée. Snapshot cohérent chiffré, production en lecture seule, DEV fermé et à zéro réplique pendant la restauration transactionnelle. Comparaison de toutes les lignes des neuf tables, UUID, hashes, cartes, relations et rôles. Les rôles d'origine sont conservés, dont ADMIN pour230466. Les sauvegardes et mappings privés sont chiffrés hors Git ; ne jamais publier les données ou leurs archives déchiffrées.

DEV_DATA_MODE=production_copy, devInitialization.enabled=false, AUTO_CREATE_DB=0. Le script synthétique refuse ce mode avant tout SQL, y compris --reset-synthetic-dev. Aucune réinitialisation synthétique autorisée sur cette copie. Une nouvelle copie nécessite fermeture DEV, arrêt des writers DEV, sauvegarde chiffrée préalable et validation du mapping autoritaire.

Les paramètres et QR EPC DEV utilisent exclusivement la configuration de démonstration id=2, avec IBAN fictif fixe, BIC vide et textes TEST. La configuration bancaire copiée id=1 reste intacte et n’est jamais utilisée par ces routes DEV ; aucun transport de paiement n’est activé. SMTP est neutralisé en DEV et interdit par NetworkPolicy. Authentification locale, inscription et reset locaux sont bloqués. Origin HTTPS DEV exact exigé pour les écritures. Sessions serveur privées cinq minutes, cookies __Host Secure/HttpOnly/SameSite=Lax, userinfo à chaque requête, logout avec révocation du token. Une panne Authentik ferme l'accès.

## Publication, validation et rollback

develop publie des images DEV à SHA immutable et met à jour seulement develop du chart. Main, NPM production et les ressources PostgreSQL/Authentik de production restent inchangés. Argo réconcilie normalement, sans synchronisation globale forcée.

Recette : signatures/claims forgés, identités sans mapping, attente/désactivation, refus anonymes, permissions positives/négatives des trois rôles et promotion/rétrogradation pendant session. Les tests de rôle utilisant des fixtures ont été réalisés avant la copie ; aucune identité synthétique ne doit être associée à une personne réelle pour tester.

Incident : fermer uniquement DEV via son guard NPM, remettre ses deux Deployments à zéro via chart develop, puis diagnostiquer. Ne jamais revenir à une image d'auto-provisionnement MEMBER avec les données réelles. Pour annuler la copie, restaurer uniquement la sauvegarde DEV préalable chiffrée, remettre son ancien mapping vérifié et une image compatible, puis refaire la recette avant ouverture. Ne jamais restaurer globalement Authentik/NPM/PostgreSQL. Conserver les archives et laboratoires ; aucune suppression automatique des bases retain.

## Inscription DEV et approbation

Le flow natif `carte-fede-dev-enrollment` collecte et conserve le mot de passe exclusivement dans Authentik. Il crée une identité inactive dans `default`, sans rôle administratif. Seules les informations métier et l'identifiant natif signé sont transmis au backend par un hook HMAC horodaté. Les nouvelles identités portent un marqueur serveur et un chemin propres au flow DEV. Une identité active existante utilise OIDC avec une session d'inscription séparée, sans création ni modification de son compte Authentik.

La table DEV `dev_identity_binding` lie issuer DEV exact + sub à une demande puis à un UUID métier. Les matricules/emails servent à détecter les collisions, jamais à rapprocher automatiquement des identités. Une demande ne confère aucun accès aux données métier. L'approbation ADMIN crée d'abord un utilisateur local ATTENTE avec UUID durable ; seules les nouvelles identités appartenant au flow DEV peuvent être activées et recevoir `membres`. Après confirmation API, l'utilisateur devient MEMBER et son mapping devient approved. Les rôles sont toujours lus dans PostgreSQL à chaque requête.

En cas d'erreur API, la demande reste activating et l'utilisateur ATTENTE : réessayer la même approbation reprend le même UUID sans duplication. Un refus supprime uniquement la demande DEV et conserve l'identité inactive ; aucune désactivation d'une identité existante n'est autorisée. Les quatre inscriptions historiques restent soumises à une activation opérateur séparée, avec approbation automatique bloquée côté backend et frontend. Ne pas restaurer globalement Authentik pour annuler DEV.

Le compte API dédié n'a aucune permission globale. Il reçoit view_user/change_user uniquement sur les nouvelles identités de son flow ; pas de création, suppression, reset de mot de passe ou gestion de rôles. Les tokens expirent le 9 janvier 2027 : les renouveler avant cette échéance via les Secrets chiffrés. Origin HTTPS exact, signature et fraîcheur du hook, refus des comptes désactivés et absence d'auto-MEMBER sont obligatoires. Les mots de passe locaux sont bloqués par le backend et les interfaces OIDC renvoient vers Authentik.

Recette synthétique : tests PostgreSQL 18 des deux QR, GET/PUT/PATCH administrateur, collisions, historique, approbation/reprise/refus, absence d'écriture API pour identité existante ; validation du flow Authentik natif et des permissions API dans le laboratoire conservé. Une recette HTTPS sur DEV est nécessaire avant déclaration de déploiement terminé. Aucun compte réel importé n'est utilisé pour tester une création ou une approbation.

Les noms et erreurs affichés lors de la vérification des cartes sont échappés avant insertion HTML. Les écrans QR et les réponses de vérification DEV portent TEST DEV ; les tokens expirent après 400 jours et conservent la période de la carte. Les signatures DEV sont refusées avec la clé et le salt de production.

Recette HTTPS du 11 octobre 2026 réussie : GET/PUT/PATCH ADMIN et refus MEMBER/VERIFIER, QR EPC TEST, carte historique synthétique, création native inactive, approbation idempotente, première connexion et carte, identité active existante sans modification globale, rejet conservant l’identité inactive, refus des signatures expirées/altérées/hors environnement. Toutes les lignes et définitions des neuf tables copiées restent inchangées ; les seuls ajouts sont le journal, la configuration de démonstration et les données synthétiques de recette. Les quatre demandes historiques demeurent intactes et désactivées.

### Native DEV registration completion

The isolated `carte-fede-dev-register` entry flow routes anonymous users to inactive native enrollment and already authenticated identities to a business-only native prompt. Existing identities are not recreated, activated, deactivated or assigned groups by that prompt or local approval. The HMAC hook attests the immutable UUID; collision checks never infer identity from email/matricule.

The final native redirect uses the backend-issued signed confirmation URL. Its opaque nonce expires after five minutes and is consumed exactly once in the DEV confirmation journal. It returns to the homepage without an authorized business session. Both native flows contain no login, mail or notification stage. The four historical pending identities remain inactive and require separate operator activation.

Deploy only after the additive `dev_enrollment_confirmation` table and the compatible develop image are verified. During this coordinated rollout, hold only DEV replicas at zero through chart develop; do not modify NPM. Restore DEV replicas only after the blueprint provision hook succeeds and then validate native HTTPS registration, approval and card requests with owned synthetic accounts. Production OIDC remains disabled.

DEV session renewal: only the carte-fede-dev provider enables refresh_token and the built-in offline_access mapping. Access tokens remain five minutes; refresh tokens are limited to eight hours. Other providers, mappings, login/password stages and applications stay unchanged. Local inactivity (30 minutes) and absolute lifetime (eight hours) are enforced in the application, not by global Authentik settings. This infrastructure main exception was explicitly approved; application/chart continue on develop.
