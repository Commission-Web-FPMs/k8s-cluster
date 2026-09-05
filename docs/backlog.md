# Améliorations prévues

Liste des chantiers identifiés, avec ce qui les motive et ce qui les bloque.
Rien ici n'est urgent au sens où le cluster fonctionne sans, mais plusieurs
points deviennent coûteux à rattraper si on les repousse trop longtemps.

Les dépendances comptent plus que l'ordre de la liste : plusieurs chantiers
attendent le même préalable.

## Ordre suggéré

La gestion des secrets et l'exposition d'ArgoCD débloquent à elles deux la
moitié du reste. Elles méritent de passer en premier même si elles ne sont pas
les plus visibles.

```text
gestion des secrets ──┬──> connexion GitHub ──> désactivation du compte admin
                      │                     └─> rôles par équipe GitHub
                      └──> identifiants S3 dans le dépôt

exposition d'ArgoCD ──┘   (nom de domaine + certificat)

AppProjects ──> namespaces durcis ──> accueil des projets étudiants
```

## Sécurité et accès

- [x] **Choisir une gestion de secrets.** Décidé : **Sealed Secrets**. Le
      raisonnement complet est dans [securite.md](./securite.md), couche 6. En
      résumé, ce qui restera à committer sera presque uniquement des
      identifiants de services externes, tous réémissibles à leur source, ce qui
      borne la réparation en cas de fuite comme de perte de clé. Et contrairement
      à SOPS, cela ne demande aucune modification d'ArgoCD.

- [x] **Installer le contrôleur Sealed Secrets.** Fait, dans
      `manifests/sealed-secrets/`, sur le même patron que MetalLB. L'Application
      est en vague -1, donc le contrôleur et sa définition de ressource existent
      avant tout le reste. Le renouvellement automatique de la clé est
      désactivé, pour qu'une sauvegarde faite une fois reste valable. Reste à
      synchroniser puis à vérifier que le premier scellement fonctionne.

- [x] **Sauvegarder la clé de scellement hors du cluster**, et tester la
      restauration. Sans elle, une reconstruction du cluster oblige à réémettre
      tous les identifiants chez leurs fournisseurs. Le renouvellement étant
      désactivé, il n'y a qu'une clé, donc une sauvegarde à faire une seule
      fois. Marche à suivre, test hors ligne compris, dans
      [secrets.md](./secrets.md), section « Sauvegarder et restaurer la clé ».
      Deux points à ne pas rater : le fichier contient la clé privée et ne va
      pas dans ce dépôt, et il doit être connu d'au moins deux personnes.

- [ ] **Tenir l'inventaire des secrets scellés.** Le patron est en place :
      chaque secret scellé est accompagné d'une fiche voisine, partant de
      [modeles/secret.md](./modeles/secret.md), et
      [secrets-inventaire.md](./secrets-inventaire.md) n'en contient que la
      liste et les liens. Aucune valeur n'y figure, tout vit donc dans ce dépôt.
      C'est ce qui rend une rotation d'urgence mécanique plutôt que devinatoire.

- [ ] **Compléter la fiche S3.** La section « Obtenir de nouveaux identifiants »
      de [s3-credentials.md](../manifests/csi-s3/s3-credentials.md) est vide :
      il faut le chemin réel dans l'interface du fournisseur, écran par écran,
      et le même détail pour la révocation. C'est la seule partie qu'aucune
      documentation générique ne remplace, et elle se perd d'une année sur
      l'autre.

- [ ] **Faire entrer le Secret S3 dans le dépôt.** Aujourd'hui les identifiants
      du stockage sont créés à la main. Un cluster reconstruit depuis ce dépôt
      n'a donc pas de stockage, et personne ne le découvrira avant d'en avoir
      besoin. Débloqué par le contrôleur Sealed Secrets ; la commande exacte
      est dans [secrets.md](./secrets.md), section « Exemple concret ».

- [ ] **Activer la connexion par GitHub.** Le connecteur est déjà écrit et
      commenté dans le chart ArgoCD. L'appartenance à une équipe de
      l'organisation devient la source de vérité des droits.
      *Bloqué par la gestion de secrets et par l'exposition d'ArgoCD.*

- [ ] **Désactiver le compte `admin` partagé.** Identifiant unique, non
      nominatif, administrateur du cluster, sans rotation prévue. Le filet de
      secours reste l'accès par kubeconfig, pas ce compte.
      *Bloqué par la connexion GitHub.*

- [ ] **Raccourcir la durée de vie des jetons.** Par défaut une session dure
      environ une journée, et l'appartenance aux équipes y est figée. Réduire
      cette durée réduit d'autant le délai entre le retrait d'une personne
      d'une équipe GitHub et la perte effective de son accès.

- [ ] **Créer les `AppProject` `platform` et `students`**, et y rattacher les
      Applications existantes. C'est le niveau 2 de [securite.md](./securite.md),
      et la barrière principale contre un manifeste étudiant hostile ou maladroit.

- [ ] **Verrouiller le projet `default`.** Une Application qui oublie de
      préciser son projet y atterrit aujourd'hui sans aucune restriction.
      *Suppose d'avoir d'abord déplacé le projet `platform` dans les valeurs du
      chart et d'y avoir rattaché l'Application racine.*

- [ ] **Poser `Prune=false` sur la ressource Chart d'ArgoCD.** En l'état, un
      renommage ou un déplacement de ce fichier conduit ArgoCD à supprimer sa
      propre installation, et il faut tout réamorcer à la main.

- [ ] **Empêcher l'auto-montage des jetons de compte de service** dans les
      namespaces de projets, pour qu'un Pod compromis ne dispose pas d'emblée
      d'un accès à l'API.

- [ ] **Exiger des commits signés** sur le projet plateforme, via le champ
      `signatureKeys`. Un accès en écriture au dépôt ne suffit alors plus à
      déployer.

- [ ] **Restreindre les registres d'images** avec une `ValidatingAdmissionPolicy`.
      Intégré à Kubernetes, aucun composant à installer.

## Accueil des projets étudiants

- [ ] **Écrire le composant kustomize de durcissement** : quotas, plage de
      limites et politiques réseau, paramétrés par le nom du projet. Sans lui,
      chaque nouveau projet recopie quatre fichiers et ils finiront par diverger.

- [ ] **Déclarer les namespaces avec Pod Security Admission.** À faire depuis ce
      dépôt et non par création automatique, sinon le namespace naît sans les
      étiquettes de sécurité. Commencer en `baseline` avec l'avertissement en
      `restricted` pour voir ce qui casserait.

- [ ] **Aligner les droits ArgoCD sur les équipes GitHub.** Une équipe par
      projet, rattachée à un rôle qui ne peut que consulter et synchroniser son
      application. L'équipe qui peut écrire dans le dépôt du projet devient
      exactement celle qui peut le déployer, et la correspondance se maintient
      seule. *Suppose que les étudiants soient membres de l'organisation : un
      collaborateur externe ne peut pas appartenir à une équipe GitHub.*

- [ ] **Écrire la procédure d'accueil d'un projet**, du dépôt étudiant à
      l'application déployée, pour que ce ne soit pas un savoir oral.

## Exploitation

- [ ] **Exposer ArgoCD durablement** : service de type LoadBalancer, contrôleur
      d'entrée, nom de domaine, certificat. La documentation actuelle passe par
      une redirection de port, ce qui ne convient pas pour une URL de retour
      OAuth. *Préalable à la connexion GitHub.*

- [ ] **Installer un contrôleur d'entrée**, sans quoi chaque projet qui veut
      être joignable consommera une adresse du pool MetalLB, qui n'en compte
      que dix.

- [ ] **Installer cert-manager** pour les certificats.

- [ ] **Sauvegarder etcd**, avec restauration testée au moins une fois. Un
      cluster qu'on ne sait pas restaurer n'est pas sauvegardé.

- [ ] **Mettre en place une supervision**, ne serait-ce que pour savoir qu'un
      nœud est tombé avant qu'un étudiant ne le signale.

- [ ] **Remplacer le stockage S3 par un accès au NAS**, comme prévu dans le
      commentaire du composant.

- [ ] **Exclure la plage MetalLB du DHCP** du réseau du Magellan, si un serveur
      DHCP y distribue des adresses. Un conflit sur ces adresses produirait des
      pannes intermittentes très pénibles à diagnostiquer.

- [ ] **Redémarrer automatiquement les Pods quand un secret change**, par
      exemple avec [stakater/Reloader](https://github.com/stakater/Reloader).
      Loin dans la file : rien ne casse sans, et cela n'a d'intérêt qu'une fois
      plusieurs secrets scellés réellement en service.

      Le problème réel n'est pas la restauration de la clé, qui est un geste
      exceptionnel où l'on tape déjà des commandes à la main. C'est la
      **rotation** : après avoir rescellé un identifiant et committé, ArgoCD met
      le `Secret` à jour, mais les Pods qui le consomment gardent l'ancienne
      valeur. Monté en volume, le contenu finit par se rafraîchir ; injecté en
      variable d'environnement, jamais. On croit donc l'identifiant remplacé
      alors que l'application utilise toujours le précédent, ce qui est
      exactement la situation à éviter le jour d'une fuite. Reloader annote le
      déploiement (`reloader.stakater.com/auto: "true"`) et le redémarre quand
      un `Secret` qu'il référence change.

      À vérifier avant de compter dessus pour le contrôleur Sealed Secrets
      lui-même : il ne monte pas sa clé, il la lit par l'API, donc l'annotation
      `auto` ne la voit pas. Il faudrait la nommer explicitement avec
      `secret.reloader.stakater.com/reload`, or le nom du Secret de clé porte un
      suffixe aléatoire. Le `rollout restart` manuel de la procédure de
      restauration reste donc probablement le bon outil pour ce cas précis.

## Qualité du dépôt

- [ ] **Valider les manifestes en intégration continue** : un rendu kustomize
      suivi d'une validation de schéma. Dans un cercle où les étudiants
      tournent, c'est le filet de sécurité le plus rentable de cette page.

- [ ] **Automatiser le suivi des versions** des charts avec Renovate. Les
      versions sont correctement figées, mais rien ne signale qu'elles vieillissent.

- [ ] **Écrire un guide de contribution** : comment ajouter un composant,
      comment accueillir un projet, quelles conventions respecter. Vu la
      vocation pédagogique du dépôt, c'est probablement l'entrée la plus utile
      de cette liste.

- [ ] **Corriger le namespace de destination de l'Application racine**, qui
      vaut `default` alors que rien n'y atterrit. Ce champ est le repli des
      ressources qui ne déclarent pas leur namespace, donc une erreur future y
      passerait inaperçue.

- [ ] **Remplacer l'inventaire de la racine par un ApplicationSet**, le jour où
      le nombre de composants rendra le gabarit rentable. Prématuré aujourd'hui.

- [ ] **Introduire une séparation d'environnements** si un second cluster
      apparaît. Le cluster actuel s'appelle `comweb-k8s-dev` mais la structure
      du dépôt est plate, et la refonte coûtera plus cher plus tard.

## Décisions à assumer ou à revoir

Ces points ne sont pas des bugs. Ce sont des choix qui méritent d'être
conscients plutôt que subis.

- [ ] **Certificats valables deux siècles.** Cela évite le piège du
      renouvellement annuel de k0s, mais supprime toute rotation. À documenter
      comme une décision, ou à revoir.

- [ ] **Nœuds de plan de contrôle sans marque de rejet.** Les Pods des
      étudiants s'exécuteront sur les mêmes machines qu'etcd. Réserver un nœud
      à la plateforme supprimerait ce risque, au prix de la capacité.
