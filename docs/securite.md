# Sécurité du cluster

Cette page décrit le cloisonnement à mettre en place pour héberger, sur le même
cluster, deux catégories de charges très différentes :

- Les composants de la **plateforme**, décrits dans ce dépôt et revus par la
  Commission Web. Ils sont considérés comme de confiance.
- Les **projets étudiants**, dont les manifestes vivent dans des dépôts GitHub
  que la Commission Web ne contrôle pas et ne relit pas.

Rien de ce qui suit n'est encore appliqué. C'est une proposition.

## Le problème

ArgoCD applique les manifestes avec les droits de son contrôleur, qui est
administrateur du cluster. Une Application ne réduit pas ces droits : elle
applique ce qu'elle trouve dans sa source, avec toute la puissance d'ArgoCD.

Autrement dit, dans la configuration actuelle, **un étudiant qui écrit un
manifeste dans son dépôt écrit un manifeste appliqué en tant qu'administrateur
du cluster**. Rien ne l'empêche de committer ceci :

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: coucou
subjects:
  - kind: ServiceAccount
    name: default
    namespace: son-projet
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: rbac.authorization.k8s.io
```

ou un Pod qui monte la racine du nœud hôte, ou qui lit les Secrets d'ArgoCD, y
compris les identifiants de dépôt privés. Ce n'est pas une hypothèse
malveillante : un copier-coller de tutoriel suffit.

Il faut donc que la limite ne soit pas la bonne volonté de l'étudiant, mais une
barrière posée par le cluster.

## Un principe structurant

**Les objets `Application` restent dans ce dépôt, jamais dans celui de
l'étudiant.**

C'est ce qui rend tout le reste possible. L'étudiant contrôle le *contenu* que
son Application déploie, mais c'est la Commission Web qui décide, dans ce
dépôt, du namespace de destination, du projet ArgoCD associé et des quotas. Ces
trois choix sont hors de sa portée.

En conséquence, il ne faut **pas** activer la fonctionnalité « applications in
any namespace » d'ArgoCD, qui permettrait de créer des Applications ailleurs
que dans le namespace `argocd`.

## Les couches

Chacune couvre ce que la précédente laisse passer.

| Couche | Empêche |
| --- | --- |
| AppProject | de créer des ressources hors du périmètre accordé |
| Pod Security Admission | de s'évader du conteneur vers le nœud |
| ResourceQuota et LimitRange | d'épuiser le cluster ou le pool d'adresses |
| NetworkPolicy | d'atteindre le plan de contrôle et les autres projets |
| RBAC ArgoCD | d'agir sur les applications des autres depuis l'interface |

## Couche 1 : les projets ArgoCD

C'est la barrière principale. Un `AppProject` restreint, pour toutes les
Applications qui lui appartiennent, les dépôts sources autorisés, les
destinations autorisées et les types de ressources autorisés.

Deux projets suffisent au départ.

### Le projet plateforme

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: platform
  namespace: argocd
spec:
  description: Composants de la plateforme, décrits dans ce dépôt.

  # Seuls ce dépôt et les dépôts Helm réellement utilisés.
  # Une faute de frappe dans une URL devient un refus de synchronisation
  # au lieu d'un déploiement de contenu inconnu.
  sourceRepos:
    - https://github.com/Commission-Web-FPMs/k8s-cluster.git
    - https://argoproj.github.io/argo-helm
    - https://metallb.github.io/metallb
    - https://yandex-cloud.github.io/k8s-csi-s3/charts

  destinations:
    - server: https://kubernetes.default.svc
      namespace: '*'

  # La plateforme installe des CRDs et des rôles cluster, elle en a besoin.
  clusterResourceWhitelist:
    - group: '*'
      kind: '*'
```

### Le projet des étudiants

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: students
  namespace: argocd
spec:
  description: Projets étudiants. Contenu non relu.

  # À tenir à jour explicitement. Éviter '*' : cela autoriserait le
  # déploiement de n'importe quel dépôt public de la planète.
  sourceRepos:
    - https://github.com/Commission-Web-FPMs/*

  # Chaque projet est confiné à un namespace préfixé.
  destinations:
    - server: https://kubernetes.default.svc
      namespace: 'projet-*'

  # LA ligne importante. Aucune ressource à portée cluster, jamais.
  # Cela ferme d'un coup ClusterRole, ClusterRoleBinding, CRD, Namespace,
  # PersistentVolume, ValidatingWebhookConfiguration, PriorityClass,
  # et tout ce qui viendra plus tard.
  clusterResourceBlacklist:
    - group: '*'
      kind: '*'

  # Ressources namespacées interdites malgré tout.
  namespaceResourceBlacklist:
    # Sinon un étudiant relève ses propres quotas.
    - group: ''
      kind: ResourceQuota
    - group: ''
      kind: LimitRange
    # Les politiques réseau s'additionnent : une politique permissive
    # écrite par l'étudiant annulerait le refus par défaut posé plus bas.
    # Elles restent donc gérées depuis ce dépôt.
    - group: networking.k8s.io
      kind: NetworkPolicy
```

Le point le plus subtil est le dernier. Les `NetworkPolicy` sont additives :
l'union des règles autorise. Poser un refus par défaut ne sert donc à rien si
la cible peut ajouter sa propre règle permissive dans le même namespace.

## Couche 2 : le namespace et Pod Security Admission

Pod Security Admission est intégré à Kubernetes, il n'y a rien à installer. Il
se pilote par des étiquettes posées sur le namespace.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: projet-exemple
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/enforce-version: latest
    # Signale ce qui échouerait en mode restricted, sans bloquer.
    # Sert à préparer le passage.
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

Le niveau `baseline` refuse les conteneurs privilégiés, les montages
`hostPath`, `hostNetwork`, `hostPID` et l'ajout de capacités dangereuses.
C'est ce qui empêche un Pod de s'évader vers le nœud.

Le niveau `restricted` va plus loin et impose en plus l'exécution sans droits
root, l'abandon de toutes les capacités et un profil seccomp. Il est nettement
plus sûr, mais beaucoup d'images publiques ne le respectent pas telles quelles.
Commencer en `baseline` avec `warn: restricted` permet de voir ce qui casserait
avant de durcir.

Ce namespace doit être **déclaré dans ce dépôt**, pas créé par l'Application de
l'étudiant. Une création automatique par ArgoCD produirait un namespace sans
ces étiquettes, donc sans aucune protection. L'Application de l'étudiant ne doit
donc pas porter l'option de création de namespace.

Ces étiquettes sont hors d'atteinte de l'étudiant, puisqu'un `Namespace` est
une ressource à portée cluster, déjà refusée par la couche précédente.

## Couche 3 : quotas

Trois nœuds, et un pool de dix adresses MetalLB. Sans quota, un seul projet
peut consommer les deux.

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: quota
  namespace: projet-exemple
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 4Gi
    limits.cpu: "4"
    limits.memory: 8Gi
    pods: "20"
    persistentvolumeclaims: "5"
    requests.storage: 20Gi
    # Le pool MetalLB ne contient que dix adresses, de .110 à .119.
    # Sans ce compteur, un projet peut les prendre toutes.
    services.loadbalancers: "1"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: limites
  namespace: projet-exemple
spec:
  limits:
    - type: Container
      # Appliqué aux conteneurs qui ne déclarent rien.
      default:
        cpu: 500m
        memory: 512Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
```

Le `LimitRange` a un second rôle : dès qu'un `ResourceQuota` porte sur des
limites, Kubernetes refuse tout Pod qui n'en déclare pas. Le `LimitRange` en
fournit d'office, ce qui évite que chaque étudiant se heurte à un refus
incompréhensible.

## Couche 4 : politiques réseau

kube-router, le CNI utilisé par le cluster, implémente les `NetworkPolicy`.
Elles sont donc effectives.

Sans politique, tout Pod peut joindre tout Pod, mais aussi les adresses des
nœuds, donc le kubelet sur le port 10250, etcd sur 2380, et l'API sur 6443.

Le patron à appliquer dans chaque namespace de projet :

```yaml
# 1. Tout refuser, dans les deux sens.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: refus-par-defaut
  namespace: projet-exemple
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
# 2. Rouvrir la résolution DNS, sans quoi plus rien ne fonctionne.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: autoriser-dns
  namespace: projet-exemple
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
---
# 3. Rouvrir Internet, mais rien de local.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: autoriser-internet
  namespace: projet-exemple
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              # Couvre le réseau des nœuds (172.17.0.0/24),
              # le réseau des Pods (10.244.0.0/16)
              # et celui des Services (10.96.0.0/12).
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
              - 169.254.0.0/16
```

Un Pod de projet peut alors résoudre des noms et sortir sur Internet, mais ne
peut joindre ni le plan de contrôle, ni les nœuds, ni les Pods d'un autre
projet, ni ArgoCD.

Il reste à rouvrir l'entrée depuis le contrôleur d'entrée le jour où le cluster
en aura un, et la communication entre les Pods d'un même projet, qui est
refusée par la première règle.

Une précision utile : les règles de sortie s'évaluent sur les adresses des
Pods, pas sur celles des Services. C'est pour cela que la règle DNS désigne les
Pods de CoreDNS par leur étiquette, et non l'adresse du Service.

## Couche 5 : accès humain à ArgoCD

C'est un sujet distinct des couches précédentes. Il ne s'agit plus de ce que
les manifestes peuvent faire, mais de ce que les personnes peuvent faire depuis
l'interface d'ArgoCD.

L'état actuel mérite d'être dit franchement : la documentation de ce dépôt
explique comment récupérer le mot de passe du compte `admin`, qui est
administrateur complet du cluster. C'est un identifiant unique, partagé, non
nominatif, et sa rotation n'est prévue nulle part.

La cible :

```yaml
# ConfigMap argocd-rbac-cm
policy.default: role:readonly
policy.csv: |
  p, role:comweb, applications, *, */*, allow
  p, role:comweb, repositories, *, *, allow
  p, role:comweb, projects, get, *, allow

  # Un étudiant ne voit et ne synchronise que son projet.
  p, role:projet-exemple, applications, get,  students/projet-exemple, allow
  p, role:projet-exemple, applications, sync, students/projet-exemple, allow

  g, <groupe ou compte>, role:comweb
```

Deux réglages accompagnent cela. Désactiver le compte `admin` local une fois
les comptes nominatifs en place, via `admin.enabled: false`. Et brancher
l'authentification sur GitHub par Dex, pour que les départs de membres se
gèrent par le retrait du compte de l'organisation plutôt que par un changement
de mot de passe partagé.

## Couche 6 : secrets

Cette section expose le raisonnement. Pour l'usage quotidien — installer
`kubeseal`, sceller un secret, le committer — voir [secrets.md](./secrets.md).

Le composant S3 dépend déjà d'un secret : ses identifiants sont créés à la main,
hors du dépôt. Un cluster reconstruit à partir de ce dépôt n'a donc pas de
stockage.

### Ce que le GitOps impose

ArgoCD rend les manifestes côté serveur. Quel que soit le schéma retenu, **le
cluster doit donc détenir de quoi déchiffrer**. L'idée que les clés restent
chez les personnes ne survit pas au contact d'ArgoCD : il faut de toute façon en
déposer une copie dans le serveur de dépôt.

Deuxième contrainte : git n'oublie rien. Un blob chiffré committé aujourd'hui
reste déchiffrable demain par qui détient la clé, y compris dans l'historique.
La réponse à une fuite n'est donc jamais de réécrire l'historique, c'est de
faire tourner les identifiants eux-mêmes.

| Schéma | Clé de déchiffrement | Perte de la clé | Fuite de la clé |
| --- | --- | --- | --- |
| Sealed Secrets | dans le cluster | secrets illisibles | tout l'historique lisible |
| SOPS + age | chez les gens, et copie dans le cluster | récupérable | tout l'historique lisible |
| External Secrets | aucune, un identifiant vers un coffre | récupérable | rotation de l'identifiant |
| Dépôt privé | aucune, rien n'est chiffré | sans objet | tout, en clair, pour toujours |

### Réduire le problème avant de le résoudre

Un secret peut naître **dans** le cluster, auquel cas il n'y a rien à chiffrer
ni à committer. ArgoCD en est déjà un exemple : son mot de passe administrateur
et sa clé de signature sont générés à l'installation et ne figurent nulle part
dans ce dépôt. Il en va de même des certificats produits par cert-manager, ou
des mots de passe qu'un chart tire au hasard à la première installation.

La règle qui sépare les deux cas :

> Si les deux bouts du secret vivent dans le cluster, il peut être généré.
> Si un bout est à l'extérieur, il doit être fourni.

Un mot de passe entre une application et sa base de données a ses deux bouts
dedans. Les identifiants du NAS, du stockage S3 ou d'une application OAuth ont
un bout dehors, chez un fournisseur qui ne changera pas d'avis parce qu'on a
réinstallé le cluster. Ceux-là doivent entrer par la porte.

### Décision : Sealed Secrets

Le raisonnement qui tranche n'est pas la comparaison des schémas, c'est la
nature de ce qui restera à committer une fois la règle ci-dessus appliquée.

Il ne restera presque que des **identifiants de services externes** : NAS,
stockage S3, interfaces de programmation tierces, application OAuth GitHub.
Or ces identifiants ont tous une propriété commune : **ils sont révocables et
réémissibles à leur source.** On se connecte au service, on en génère un
nouveau, on rescelle.

Cela fait converger les deux modes de défaillance vers la même réparation,
bornée et connue d'avance :

- **Fuite de la clé** : faire tourner chaque identifiant chez son fournisseur.
- **Perte de la clé** : idem, puis rescellé.

La différence tient au moment, pas à la nature. Une fuite laisse choisir
l'instant, une perte survient pendant une reconstruction déjà pénible.

Sealed Secrets l'emporte donc sur SOPS pour une raison pratique et non
théorique : **il ne demande aucune modification d'ArgoCD.** SOPS est plus
agréable à écrire, mais ArgoCD ne le déchiffre pas nativement, et le brancher
suppose de greffer un plugin dans le serveur de dépôt. Cela rend l'installation
non standard pour ceux qui reprendront le cluster.

External Secrets reste le schéma le plus sain, puisqu'il est le seul où une
fuite n'expose pas l'historique. Il suppose un coffre à administrer, à
desceller et à sauvegarder, ce qui est disproportionné pour trois nœuds.

### Ce que cette décision oblige à faire

Le pari ne tient que si ces trois points sont respectés.

- **Tenir l'inventaire des secrets scellés.** Pour chaque secret : à quel
  service il donne accès, et qui peut en émettre un nouveau. Sans cette liste,
  une rotation d'urgence devient une devinette, et c'est précisément la
  situation où l'on ne veut pas deviner. L'inventaire ne contient aucune valeur,
  il peut donc vivre dans ce dépôt.

- **Réduire la portée de chaque identifiant.** Une clé S3 par bucket plutôt
  qu'une clé maîtresse, un compte NAS limité à un partage. Une fuite se répare
  alors service par service, sans tout révoquer d'un coup.

- **Sauvegarder la clé de scellement hors du cluster.** Ce n'est pas
  indispensable au sens strict, puisque tout est réémissible, mais cela
  transforme une reconstruction en restauration. Le renouvellement automatique
  de la clé est désactivé précisément pour que cette sauvegarde se fasse une
  fois et reste valable (voir plus bas).

### Ce qui est installé

Le contrôleur est déployé par `manifests/sealed-secrets/`, sur le même patron
que MetalLB : une Application qui ne porte que le chart. Elle est en **vague
-1**, de sorte que le contrôleur et sa définition de ressource existent avant
tout le reste.

La validation à blanc d'ArgoCD ayant lieu avant la première vague, un
SealedSecret committé dans ce dépôt doit malgré tout porter l'annotation
`SkipDryRunOnMissingResource=true`, sans quoi une reconstruction depuis zéro
échoue sur un type qui n'existe pas encore. Elle est posée par le
`kustomization.yaml` du composant, et non dans le fichier scellé que `kubeseal`
réécrit à chaque rotation. En revanche, rien à écrire du côté
des Pods qui consomment le Secret produit : un Pod dont le Secret manque encore
patiente puis démarre, sans faire échouer la synchronisation.

Deux réglages méritent d'être connus.

Le chart nomme ses ressources d'après la release, alors que `kubeseal` cherche
par défaut un contrôleur nommé `sealed-secrets-controller`. Le nom est donc
aligné sur ce que la ligne de commande attend, et seul le namespace reste à
préciser au scellement. La marche à suivre, l'installation de `kubeseal` et un
exemple complet sont dans [secrets.md](./secrets.md).

Le renouvellement automatique de la clé est **désactivé**. Par défaut le
contrôleur en génère une nouvelle tous les 30 jours en conservant les
anciennes ; les secrets déjà scellés continuent alors de fonctionner, mais une
sauvegarde cesse de couvrir ce qui sera scellé ensuite. Elle périme en silence,
et cela se découvre au moment de restaurer. Le renouvellement n'apporte par
ailleurs presque rien ici, puisque toutes les clés vivent dans le même
namespace : qui obtient l'une obtient les autres. Avec une clé unique, la
sauvegarde se fait une fois, et faire tourner la clé redevient un geste
délibéré, à poser le jour où on la soupçonne compromise — le contrôleur en
génère alors une nouvelle sur réception du signal `SIGUSR1`, sans perdre
l'ancienne. Le contrôleur ne crée une clé que s'il n'en trouve aucune : un
redémarrage ne remet donc pas la sauvegarde en cause.

### Une remarque de cloisonnement

Les Secrets d'ArgoCD, qui contiennent les identifiants d'accès aux dépôts,
vivent dans le namespace `argocd`. Le confinement des projets étudiants à leur
propre namespace est ce qui les met hors de portée.

Le contrôleur Sealed Secrets ajoute une cible du même ordre. Il détient un rôle
de cluster qui lui donne la main sur les Secrets de tous les namespaces, et sa
clé privée vit dans le namespace `sealed-secrets`. Deux conséquences pour les
couches précédentes : ce namespace doit rester hors d'atteinte des projets
étudiants, et le `clusterResourceBlacklist` du projet étudiant est ce qui
empêche un manifeste de se rattacher au compte de service du contrôleur.

## Pour aller plus loin

- **Commits signés.** Un `AppProject` accepte un champ `signatureKeys` qui
  impose que la révision déployée soit signée par une clé GPG connue. Appliqué
  au projet plateforme, cela signifie qu'un accès en écriture au dépôt ne suffit
  plus à déployer.
- **ValidatingAdmissionPolicy.** Intégré à Kubernetes depuis la version 1.30,
  sans composant à installer. Permet d'écrire en CEL des règles du type
  « les images doivent venir de ces registres » ou « l'étiquette `latest` est
  refusée ». C'est l'alternative légère à Kyverno ou Gatekeeper.
- **Jetons de compte de service.** Poser `automountServiceAccountToken: false`
  sur le compte `default` de chaque namespace de projet évite qu'un Pod
  compromis dispose d'emblée d'un jeton d'API.
- **Fenêtres de synchronisation.** Un `AppProject` peut interdire les
  synchronisations sur certaines plages horaires, par exemple pendant une
  démonstration.
- **Ressources orphelines.** Un `AppProject` peut signaler les ressources
  présentes dans ses namespaces sans être gérées par ArgoCD, ce qui révèle les
  manipulations manuelles.

## Où stocker tout cela

Les éléments de sécurité ne se rangent pas tous au même endroit, parce qu'ils
n'ont pas le même cycle de vie. Il y a trois niveaux.

### Niveau 1 : l'amorçage

Certaines choses doivent exister avant qu'ArgoCD ne synchronise quoi que ce
soit. Elles vivent donc dans `manifests/argocd/chart.yaml`, dans les valeurs du
chart, aux côtés de l'Application racine.

C'est le cas de la configuration d'ArgoCD lui-même, qui n'est pas une ressource
séparée mais des valeurs du chart : la politique RBAC, la désactivation du
compte `admin` local, le branchement sur GitHub. Écrire un `ConfigMap`
`argocd-rbac-cm` à la main entrerait en conflit avec celui que le chart produit.

```yaml
    configs:
      cm:
        admin.enabled: false
      rbac:
        policy.default: role:readonly
        policy.csv: |
          ...
```

C'est aussi l'endroit du projet `platform`, si vous décidez de verrouiller le
projet `default`. Voir la remarque plus bas.

### Niveau 2 : la politique globale

Un `AppProject` n'est pas un composant comme MetalLB. Il n'est installé par
aucun chart, c'est une ressource que la racine applique directement. Même chose
pour d'éventuelles `ValidatingAdmissionPolicy`, qui sont à portée cluster et
n'appartiennent à aucun projet.

La règle générale du dépôt s'applique : **ce qui vient d'un chart obtient une
Application, ce que ce dépôt possède en propre est appliqué directement par la
racine.** Emballer trois `AppProject` dans une Application n'ajouterait qu'une
couche de plus susceptible d'échouer.

```text
manifests/
  projects/
    kustomization.yaml
    platform.yaml            AppProject plateforme
    students.yaml            AppProject étudiants
  policies/
    kustomization.yaml       règles d'admission, si vous en ajoutez
```

### Niveau 3 : par projet

Tout ce qui se répète une fois par projet étudiant.

```text
manifests/
  tenants/
    kustomization.yaml       liste des projets accueillis
    projet-exemple/
      kustomization.yaml
      namespace.yaml         namespace + étiquettes PSA
      application.yaml       Application -> dépôt de l'étudiant
```

Les quotas et les politiques réseau sont identiques d'un projet à l'autre, à
un nom près. Les recopier à chaque fois garantit qu'ils divergeront. Kustomize
prévoit exactement ce cas avec les **composants**, qui sont des morceaux de
configuration paramétrables et réutilisables :

```yaml
# manifests/components/tenant/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1alpha1
kind: Component

resources:
  - quota.yaml
  - netpol.yaml
```

```yaml
# manifests/tenants/projet-exemple/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: projet-exemple

resources:
  - namespace.yaml
  - application.yaml

components:
  - ../../components/tenant
```

Le transformateur `namespace` réécrit la destination de tout ce que le composant
apporte. Accueillir un projet revient alors à écrire trois fichiers courts, dont
deux ne contiennent qu'un nom, et le durcissement reste défini à un seul
endroit. À vérifier au moment de l'implémentation : selon les versions,
le transformateur ne renomme pas toujours l'objet `Namespace` lui-même, d'où le
fait de le garder dans le dossier du projet plutôt que dans le composant.

## Ordre de déploiement

Les vagues de synchronisation comptent ici, parce que les dépendances sont
réelles.

| Vague | Contenu |
| ---: | --- |
| -1 | les `AppProject` et les règles d'admission |
| 0 | les namespaces, quotas et politiques réseau |
| 1 | les `Application` des projets |

Un `AppProject` doit exister avant toute Application qui s'y réfère, sinon
celle-ci part en erreur. Un namespace et ses étiquettes doivent exister avant
que le moindre Pod n'y soit créé, sinon les Pods de la première
synchronisation échappent à Pod Security Admission.

### Le cas du projet `default`

Il reste un trou, qui mérite d'être traité en connaissance de cause.

Le projet `default` est créé par ArgoCD et n'impose rien. Une Application qui
ne précise pas son projet y atterrit, donc sans aucune restriction. Une
étourderie échoue ainsi en grand ouvert plutôt qu'en refus.

Le projet `default` peut être réécrit pour ne rien autoriser, ce qui inverse ce
comportement. Mais l'Application racine y appartient aujourd'hui, et elle est
créée à l'amorçage, avant que le contenu de `manifests/projects/` n'existe. La
verrouiller suppose donc de déplacer d'abord le projet `platform` dans les
valeurs du chart ArgoCD, au niveau 1, et d'y rattacher la racine.

Deux étapes, dans cet ordre :

1. Créer `platform` et `students` dans `manifests/projects/`, et y rattacher
   les Applications existantes. Le trou subsiste, mais tout ce qui existe est
   cadré.
2. Déplacer `platform` dans les valeurs du chart, rattacher l'Application
   racine à ce projet, puis réduire `default` à rien.

La première étape apporte l'essentiel de la protection. La seconde ferme la
porte de service.

## Ce que cela ne couvre pas

Trois limites, à connaître plutôt qu'à ignorer.

Les trois nœuds portent le plan de contrôle sans marque de rejet, donc les Pods
des étudiants s'exécutent sur les mêmes machines qu'etcd. Les couches
ci-dessus rendent l'évasion difficile, mais une évasion réussie atterrit
directement sur un nœud du plan de contrôle. Réserver un nœud à la plateforme
supprimerait ce risque, au prix de la capacité.

Les quotas limitent le processeur, la mémoire et le stockage, mais pas la bande
passante ni les entrées-sorties disque. Un projet bruyant peut encore gêner les
autres.

Enfin, tout ceci protège le cluster des projets étudiants. Cela ne protège pas
un projet étudiant de lui-même, ni les données qu'il héberge.
