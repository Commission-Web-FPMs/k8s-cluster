# Carte Fédé DEV

DEV est public sur https://carte-dev.fede.fpms.ac.be, avec authentification OIDC. La production main conserve Flask. La base/rôle dédiés carte_fede_dev utilisent PostgreSQL18, UTF8 et ICU déterministe en-US. Le frontend public ne donne aucun accès anonyme aux données métier.

## Identité et permissions

Authentik gère exclusivement l'identité et l'authentification. Les groupes, notamment membres, servent au contrôle d'accès et ne déterminent jamais les rôles métier. ADMIN Carte Fédé ne confère aucun privilège administratif Authentik. Aucun rôle Carte Fédé n'est synchronisé vers Authentik.

Le backend vérifie RS256, issuer DEV exact, audience/client, exp/iat/azp, nonce, state et PKCE. Un mapping privé vérifié associe sub à l'UUID métier, dans le périmètre de cet issuer exact. Le claim UUID doit correspondre au mapping et à un utilisateur existant en PostgreSQL. Aucun rapprochement par email, nom ou matricule, aucune création automatique MEMBER. Un utilisateur Authentik actif sans association vérifiée est refusé. Les comptes désactivés et rôles ATTENTE sont refusés.

Les rôles ADMIN, VERIFIER et MEMBER proviennent exclusivement de PostgreSQL, rechargés à chaque requête. Le backend contrôle les endpoints sensibles : administration ADMIN uniquement, vérification des cartes ADMIN/VERIFIER, données personnelles du compte authentifié. L'administrateur peut modifier les rôles avec les fonctionnalités existantes ; promotion, rétrogradation et mise en attente prennent effet pendant les sessions existantes. Toutes ces écritures restent dans carte_fede_dev.

La politique Authentik DEV accepte les identités actives ; elle ne remplace pas le contrôle d'association métier du backend. Les inscriptions non validées importées dans default restent désactivées. Les anciens comptes de recette synthétiques restent présents dans Authentik, mais n'ont plus de profil métier après la copie PROD et sont refusés.

## Données et sécurité

La copie réelle PROD → DEV du11 octobre2026 a été explicitement autorisée. Snapshot cohérent chiffré, production en lecture seule, DEV fermé et à zéro réplique pendant la restauration transactionnelle. Comparaison de toutes les lignes des neuf tables, UUID, hashes, cartes, relations et rôles. Les rôles d'origine sont conservés, dont ADMIN pour230466. Les sauvegardes et mappings privés sont chiffrés hors Git ; ne jamais publier les données ou leurs archives déchiffrées.

DEV_DATA_MODE=production_copy, devInitialization.enabled=false, AUTO_CREATE_DB=0. Le script synthétique refuse ce mode avant tout SQL, y compris --reset-synthetic-dev. Aucune réinitialisation synthétique autorisée sur cette copie. Une nouvelle copie nécessite fermeture DEV, arrêt des writers DEV, sauvegarde chiffrée préalable et validation du mapping autoritaire.

Les paiements et réglages bancaires sont refusés par le backend, même si leur configuration est présente dans la copie intégrale. SMTP est neutralisé en DEV et interdit par NetworkPolicy. Authentification locale, inscription et reset locaux sont bloqués. Origin HTTPS DEV exact exigé pour les écritures. Sessions serveur privées cinq minutes, cookies __Host Secure/HttpOnly/SameSite=Lax, userinfo à chaque requête, logout avec révocation du token. Une panne Authentik ferme l'accès.

## Publication, validation et rollback

develop publie des images DEV à SHA immutable et met à jour seulement develop du chart. Main, NPM production et les ressources PostgreSQL/Authentik de production restent inchangés. Argo réconcilie normalement, sans synchronisation globale forcée.

Recette : signatures/claims forgés, identités sans mapping, attente/désactivation, refus anonymes, permissions positives/négatives des trois rôles et promotion/rétrogradation pendant session. Les tests de rôle utilisant des fixtures ont été réalisés avant la copie ; aucune identité synthétique ne doit être associée à une personne réelle pour tester.

Incident : fermer uniquement DEV via son guard NPM, remettre ses deux Deployments à zéro via chart develop, puis diagnostiquer. Ne jamais revenir à une image d'auto-provisionnement MEMBER avec les données réelles. Pour annuler la copie, restaurer uniquement la sauvegarde DEV préalable chiffrée, remettre son ancien mapping vérifié et une image compatible, puis refaire la recette avant ouverture. Ne jamais restaurer globalement Authentik/NPM/PostgreSQL. Conserver les archives et laboratoires ; aucune suppression automatique des bases retain.
