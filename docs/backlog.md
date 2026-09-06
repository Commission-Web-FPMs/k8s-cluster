# Améliorations prévues

## Security & access

* [x] **Secret management : Sealed Secrets.** Voir [securite.md](./securite.md), couche 6.

* [x] **Installer le Sealed Secrets controller.** Config dans `manifests/sealed-secrets/`, avec une sync wave `-1`. L'auto-renew de la clé est désactivé.

* [x] **Backup de la clé Sealed Secrets hors du cluster.** Procédure dans [secrets.md](./secrets.md), section « Sauvegarder et restaurer la clé ». La clé privée ne doit pas être stockée dans ce repo et doit être accessible à au moins deux personnes.

* [x] **Maintenir un inventaire des sealed secrets.** Une fiche par secret, sur le modèle de [s3-credentials.md](../manifests/csi-s3/s3-credentials.md). Liste centrale dans [secrets-inventaire.md](./secrets-inventaire.md).

* [x] **Ajouter le Secret S3 au repo.** Utiliser Sealed Secrets. Commande dans [secrets.md](./secrets.md), section « Exemple concret ».

* [x] **Activer le login GitHub sur ArgoCD.** Créer l'OAuth App GitHub, utiliser le Secret déjà scellé et décommenter `url` dans le chart. Voir [github-oauth.md](../manifests/argocd/github-oauth.md).

* [x] **Désactiver le compte `admin` partagé.** Garder le kubeconfig comme accès de secours.

* [x] **Réduire la durée de vie des sessions/tokens ArgoCD.**

* [ ] **Créer les `AppProject` `platform` et `students`.** Y rattacher les Applications existantes. Voir [securite.md](./securite.md), niveau 2.

* [ ] **Lock down le projet `default`.**

  * À faire après migration de l'Application racine vers `platform`.

* [ ] **Mettre `Prune=false` sur l'Application `argocd`.** Éviter qu'un rename/move de son manifest retire sa gestion par ArgoCD.

* [ ] **Désactiver l'auto-mount des ServiceAccount tokens** dans les namespaces étudiants.

* [ ] **Exiger des signed commits** pour le projet `platform` avec `signatureKeys`.

* [ ] **Restreindre les image registries** avec une `ValidatingAdmissionPolicy`.

## Student project onboarding

* [ ] **Créer un composant Kustomize de base pour les projets.** Inclure `ResourceQuota`, `LimitRange` et `NetworkPolicy`, paramétrés par projet.

* [ ] **Créer les namespaces avec Pod Security Admission.** Commencer en `baseline` avec warnings en `restricted`.

* [ ] **Mapper les droits ArgoCD sur les GitHub Teams.** Une team par projet, avec accès `get`/`sync` sur son Application.

  * Les étudiants doivent être membres de l'organisation GitHub pour appartenir à une team.

* [ ] **Écrire la procédure d'onboarding d'un projet.** Du repo étudiant jusqu'au déploiement ArgoCD.

## Operations

* [ ] **Exposer ArgoCD proprement.** `LoadBalancer` + Gateway/Ingress controller + DNS + TLS.

  * Requis pour le callback OAuth GitHub.

* [ ] **Installer un Gateway/Ingress controller.** Éviter un `LoadBalancer` MetalLB par application publique.

* [ ] **Installer cert-manager.**

* [ ] **Backup etcd** et tester un restore au moins une fois.

* [ ] **Installer du monitoring.** Au minimum nodes, control plane et workloads principaux.

* [ ] **Remplacer le storage S3 par le NAS** quand il sera disponible.

* [ ] **Exclure le pool MetalLB du DHCP** sur le réseau Magellan.

* [ ] **Restart automatique des Pods quand un Secret change**, par exemple avec [stakater/Reloader](https://github.com/stakater/Reloader).

  * Utile surtout pour les Secrets injectés en environment variables.
  * Annotation : `reloader.stakater.com/auto: "true"`.
  * Pour la clé du Sealed Secrets controller, garder un `rollout restart` manuel après restore : le nom du Secret contient un suffixe aléatoire et la clé est lue via l'API.

## Repository quality

* [ ] **Valider les manifests en CI.** `kustomize build` + schema validation.

* [ ] **Automatiser les dependency updates** avec Renovate.

* [ ] **Écrire un contribution guide.** Ajouter un composant, onboarder un projet, conventions du repo.

* [ ] **Corriger le destination namespace de l'Application racine.** Il est actuellement à `default`.

* [ ] **Passer à un `ApplicationSet`** quand le nombre de composants le justifiera.

* [ ] **Prévoir une séparation des environments** si un second cluster apparaît. Le cluster actuel est `comweb-k8s-dev`.

## Décisions à revoir

* [ ] **Certificats valables deux siècles.** Soit documenter ce choix, soit remettre une rotation normale.

* [ ] **Control-plane nodes sans taint.** Les workloads étudiants peuvent tourner sur les mêmes nodes qu'etcd. À garder ou à revoir selon la capacité disponible.
