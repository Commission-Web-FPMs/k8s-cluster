# Créer et gérer les utilisateurs

Les utilisateurs humains restent dans Authentik. L'interface suffit pour
les opérations ponctuelles et évite de maintenir un script avec un token
administratif. Les blueprints provisionnent les groupes et les accès techniques.

## Créer une personne

Avec un compte autorisé à gérer les utilisateurs, ouvrir
<https://auth.fede.fpms.ac.be/if/admin/>.

1. Dans `Directory > Users`, choisir `New User`, puis `Internal User`.
2. Renseigner un username stable et unique, le nom et l'email. Utiliser
   `users/fede` comme dossier pour les personnes de la Fédération.
3. Créer le compte actif. Ouvrir sa fiche, puis l'onglet `Groups` pour
   ajouter les groupes existants nécessaires : `par défaut`, `membres`,
   `comite`, `admin`. Le groupe `par défaut` autorise la connexion à carte-fede
   sans attribuer de rôle métier particulier.
4. Utiliser `Reset password` pour définir un mot de passe initial unique.
   Le transmettre par un canal privé. La personne peut ensuite le changer
   depuis son interface utilisateur.

Les groupes doivent déjà exister après le provisionnement. S'ils manquent,
réparer l'application du blueprint plutôt que créer des variantes de leur nom.
L'adresse email n'est pas nécessairement unique dans Authentik ; utiliser le
username pour retrouver le compte.

Pour utiliser un lien de récupération au lieu d'un mot de passe initial,
configurer d'abord un recovery flow sur la Brand. L'envoi automatique du lien
demande en plus une configuration SMTP. Le bootstrap actuel ne configure pas
ces parcours.

Référence : [gestion des utilisateurs](https://docs.goauthentik.io/users-sources/user/user_basic_operations/).

## Lister et modifier les personnes

Dans `Directory > Users`, ouvrir le dossier `users/fede` et rechercher le
username ou le nom. Les comptes techniques sont rangés séparément dans
`service-accounts/carte-fede`.

Pour changer une appartenance, ouvrir la fiche de la personne et l'onglet
`Groups`, puis ajouter ou retirer le groupe concerné. Ne pas modifier le
blueprint pour cette opération. Un nouveau login OIDC permet à carte-fede de
recevoir les claims mis à jour ; une session applicative existante peut conserver
les anciennes valeurs jusqu'à son renouvellement.

Pour un départ, désactiver le compte depuis sa fiche. Contrôler aussi les
sessions conservées par carte-fede, dont le cycle de vie est distinct.

## Automatiser plus tard via l'API

Un CLI pourra utiliser les endpoints suivants, avec un compte de service
dédié à l'outil d'administration et distinct du compte de carte-fede :

| Opération | Endpoint |
| --- | --- |
| Rechercher une personne | `GET /api/v3/core/users/?username=<username>` |
| Résoudre un groupe par son nom | `GET /api/v3/core/groups/?name=<groupe>` |
| Créer une personne | `POST /api/v3/core/users/` |
| Modifier ses données ou groupes | `PATCH /api/v3/core/users/<pk>/` |
| Définir un mot de passe | `POST /api/v3/core/users/<pk>/set_password/` |

L'outil devra demander le token et le mot de passe sans les afficher, résoudre
les groupes dans la base cible, suivre la pagination et refuser de recréer un
username existant. Les IDs numériques ne doivent pas être conservés entre
deux installations. Une modification du champ `groups` transmet la liste
désirée complète ; elle doit préserver les appartenances non concernées.

Le dossier `users/fede` facilite le classement. Il ne constitue pas une limite
d'autorisation pour l'API. Les permissions nécessaires et leur périmètre
devront être définis avant de donner des droits d'écriture au CLI.

Référence des champs et opérations :
[API utilisateurs de la version 2026.8.2](https://github.com/goauthentik/authentik/blob/version/2026.8.2/authentik/core/api/users.py).
