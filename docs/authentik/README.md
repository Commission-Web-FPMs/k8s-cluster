# Gestion d'Authentik

Authentik est accessible sur <https://auth.fede.fpms.ac.be>. Ces guides
décrivent la gestion des personnes et le provisionnement des accès de carte-fede.

- [Créer et gérer les utilisateurs](./utilisateurs.md).
- [Provisionner les groupes, le compte de service et le client OIDC de carte-fede](./carte-fede.md).
- [Bootstrap du compte initial](../../manifests/authentik/authentik-bootstrap.md).
- [Scellement et sauvegarde des secrets](../secrets.md).

## Répartition des données

| Données | Source de vérité |
| --- | --- |
| Utilisateurs humains, mots de passe, MFA, appartenances aux groupes | Authentik, via son interface ou l'API |
| Groupes `membres`, `comite`, `admin` | Blueprints versionnés |
| Comptes de service, permissions, définition des tokens | Blueprints versionnés |
| Applications et providers OIDC, URLs et client IDs | Configuration versionnée |
| Clés des tokens API et secrets des clients OIDC | SealedSecrets versionnés |

Les blueprints ne doivent déclarer aucun utilisateur humain, ni remplacer
les membres des groupes. Les comptes de service sont les seules entrées
`authentik_core.user` prévues dans les exemples.

La reconstruction depuis Git recrée la configuration technique. Les personnes
et leurs credentials nécessitent une sauvegarde PostgreSQL. La restauration
des SealedSecrets nécessite aussi la clé privée du contrôleur, conservée hors
Git suivant la [procédure de sauvegarde](../secrets.md).

## État de ces guides

Les fichiers dans `exemples/` sont des modèles pour Authentik 2026.8.2.
Ils ne sont pas référencés par les Kustomizations et ne sont pas déployés.
Le raccordement à Argo CD, l'injection dans carte-fede et la validation sur
une base neuve restent à réaliser. Les procédures ci-dessous distinguent la
préparation des fichiers de leur activation.

Le premier environnement décrit est `carte-fede-main`. L'ApplicationSet actuel
déploie aussi les autres branches. Chaque environnement devra disposer de
son propre client, compte de service, token et Secret dans son namespace.

## Convention des groupes

| Groupe | Usage proposé dans carte-fede |
| --- | --- |
| `membres` | Accès membre |
| `comite` | Fonctions du comité |
| `admin` | Administration de l'application |

Ces groupes sont indépendants, sans hiérarchie implicite. Une personne peut
appartenir à plusieurs groupes. Le code de carte-fede doit interpréter ces
appartenances pour autoriser ses opérations.

Le groupe `admin` n'accorde aucun droit d'administration d'Authentik. Les
trois groupes ont `is_superuser: false` et aucun rôle d'administration associé.
L'administration de l'identité reste un accès distinct de l'administration
de l'application.
