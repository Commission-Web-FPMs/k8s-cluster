# Gestion des secrets

Cette page explique comment mettre un mot de passe, une clé d'API ou des
identifiants de service dans ce dépôt sans les publier.

Elle est opérationnelle : elle décrit ce qu'il faut installer et taper. Le
raisonnement qui a conduit à ce choix plutôt qu'à un autre est dans
[securite.md](./securite.md), couche 6.

## Pourquoi ce n'est pas évident

### Un Secret Kubernetes n'est pas chiffré

Kubernetes possède un type d'objet `Secret`, destiné aux mots de passe et aux
clés. Son contenu est encodé en base64, ce qui trompe régulièrement :

```sh
echo -n 'motdepasse' | base64
# bW90ZGVwYXNzZQ==

echo 'bW90ZGVwYXNzZQ==' | base64 -d
# motdepasse
```

Le base64 est un **encodage**, pas un chiffrement. Il n'y a pas de clé, donc
rien à ignorer pour le lire. Un `Secret` committé tel quel dans ce dépôt est un
mot de passe publié, avec une étape de décodage en plus.

### Et git n'oublie rien

Retirer le fichier dans un commit suivant ne suffit pas : la valeur reste dans
l'historique, et le dépôt est public. La seule réparation d'une fuite est de
**changer l'identifiant chez son fournisseur**, jamais de réécrire l'historique.

### Mais tout doit être dans le dépôt

C'est la contrainte du GitOps : ce qui n'est pas dans ce dépôt n'existe pas pour
le cluster. Un secret créé à la main survit tant que personne ne reconstruit le
cluster, puis disparaît sans laisser de trace de ce qu'il contenait. C'est
exactement la situation du stockage S3 aujourd'hui.

Il faut donc pouvoir committer un secret **sous une forme illisible pour qui lit
le dépôt, et lisible pour le cluster seul.**

## Comment Sealed Secrets répond

Un contrôleur tourne dans le cluster, dans le namespace `sealed-secrets`. Il
détient une paire de clés :

- une **clé publique**, que n'importe qui peut récupérer et utiliser pour
  chiffrer ;
- une **clé privée**, qui ne sort jamais du cluster.

On chiffre donc localement avec la clé publique, on obtient un objet
`SealedSecret`, et c'est **lui** qu'on committe. Le contrôleur le voit
apparaître, le déchiffre avec la clé privée, et produit à côté le `Secret`
Kubernetes normal que les applications consomment.

```text
  poste de travail                     dépôt git                cluster
 ┌──────────────────┐              ┌───────────────┐      ┌──────────────────┐
 │ Secret en clair  │              │               │      │                  │
 │        │         │   commit     │  SealedSecret │ sync │   SealedSecret   │
 │        ▼         │ ───────────► │   (chiffré)   │ ───► │        │         │
 │   kubeseal       │              │               │      │        ▼         │
 │  (clé publique)  │              │               │      │   contrôleur     │
 │        │         │              │               │      │  (clé privée)    │
 │        ▼         │              │               │      │        │         │
 │  SealedSecret    │              │               │      │        ▼         │
 └──────────────────┘              └───────────────┘      │ Secret en clair  │
   jamais committé                                        └──────────────────┘
```

Deux propriétés en découlent, qu'il vaut mieux connaître avant de s'en servir.

Le chiffrement est **asymétrique**. Sceller ne demande donc aucun droit sur le
cluster : la clé publique ne permet pas de déchiffrer. N'importe qui peut
préparer un secret, seul le cluster peut le lire.

Un `SealedSecret` est scellé **pour ce cluster, et pour un namespace et un nom
précis**. C'est ce qui empêche quelqu'un de recopier un secret chiffré dans un
namespace qu'il contrôle pour se le faire déchiffrer. Conséquence pratique :
renommer ou déplacer un secret oblige à le resceller.

## Prérequis

### 1. kubectl configuré

Il faut un accès au cluster. Voir la section *Bootstrapping* du
[README](../README.md) : `k0sctl kubeconfig > ~/.kube/config`, plus le tunnel SSH
si vous passez par le bastion.

Vérification :

```sh
kubectl get nodes
```

### 2. Le contrôleur déployé

Il l'est par `manifests/sealed-secrets/`, donc par ArgoCD. Vérification :

```sh
kubectl -n sealed-secrets get pods
# sealed-secrets-controller-xxxxxxxxxx-xxxxx   1/1   Running
```

### 3. kubeseal

C'est l'outil qui chiffre, en local. Prenez la **même version que le
contrôleur** (0.39.1 aujourd'hui) : les versions se suivent.

```sh
# macOS
brew install kubeseal
```

```sh
# Linux, ou si le gestionnaire de paquets n'a pas le bon numéro
VERSION=0.39.1
curl -sSL -o kubeseal.tar.gz \
  "https://github.com/bitnami/sealed-secrets/releases/download/v${VERSION}/kubeseal-${VERSION}-linux-amd64.tar.gz"
tar xzf kubeseal.tar.gz kubeseal
sudo install -m 755 kubeseal /usr/local/bin/kubeseal
```

Sous Windows, l'archive `kubeseal-0.39.1-windows-amd64.tar.gz` de la même page
de [releases](https://github.com/bitnami/sealed-secrets/releases) contient
`kubeseal.exe`, à placer dans un dossier du `PATH`.

Vérification :

```sh
kubeseal --version
```

## Sceller un secret

Le contrôleur vit dans son propre namespace, il faut donc le lui dire. Le nom,
lui, est déjà aligné sur ce que `kubeseal` attend par défaut.

```sh
kubectl create secret generic mon-secret \
  --namespace mon-namespace \
  --from-literal=cle=valeur \
  --dry-run=client -o yaml \
| kubeseal --controller-namespace sealed-secrets --format yaml \
> manifests/mon-composant/mon-secret.sealed.yaml
```

Ce que fait chaque morceau :

| Morceau | Rôle |
| --- | --- |
| `kubectl create secret ... --dry-run=client -o yaml` | fabrique le `Secret` **sans l'envoyer** au cluster, juste pour produire le YAML |
| `--namespace` | le namespace de destination, qui fait partie du scellement |
| `kubeseal --controller-namespace sealed-secrets` | récupère la clé publique auprès du contrôleur et chiffre |
| `--format yaml` | sort du YAML plutôt que du JSON |

Le secret en clair n'existe qu'en mémoire, dans le tube entre les deux
commandes. Il ne touche jamais le disque.

Le résultat ressemble à ceci, et c'est ce fichier qui est committé :

```yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: mon-secret
  namespace: mon-namespace
spec:
  encryptedData:
    cle: AgBv3K9m...   # long blob illisible
  template:
    metadata:
      name: mon-secret
      namespace: mon-namespace
```

### Plusieurs clés dans un même secret

Répétez `--from-literal`, ou lisez un fichier :

```sh
kubectl create secret generic mon-secret \
  --namespace mon-namespace \
  --from-literal=username=admin \
  --from-literal=password='p@ssw0rd' \
  --from-file=config.json=./config.json \
  --dry-run=client -o yaml \
| kubeseal --controller-namespace sealed-secrets --format yaml \
> manifests/mon-composant/mon-secret.sealed.yaml
```

### Sceller sans accès au cluster

`kubeseal` va chercher la clé publique dans le cluster à chaque appel. On peut
l'exporter une fois et travailler hors ligne ensuite :

```sh
kubeseal --controller-namespace sealed-secrets --fetch-cert > cert.pem

# puis, depuis n'importe où
kubeseal --cert cert.pem --format yaml < secret.yaml > secret.sealed.yaml
```

Ce certificat est **public**, il peut circuler sans précaution. Il reste valable
tant que la clé du cluster n'a pas été changée délibérément : le renouvellement
automatique est désactivé, voir [securite.md](./securite.md).

## Committer le résultat

Le fichier scellé vit **à côté du composant qui le consomme**, pas dans
`manifests/sealed-secrets/`, qui ne contient que le contrôleur.

Deux choses à faire.

**Ajouter l'annotation.** ArgoCD valide toutes les ressources à blanc avant la
première vague de synchronisation. Sur un cluster reconstruit depuis zéro, le
type `SealedSecret` n'existe pas encore à ce moment-là, et la validation échoue.
L'annotation lui dit de ne pas valider ce qu'il ne connaît pas encore :

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
```

**Le déclarer dans le kustomization du composant :**

```yaml
resources:
  - application.yaml
  - mon-secret.sealed.yaml
```

Rien à écrire en revanche du côté des Pods qui attendent le `Secret` produit :
un Pod dont le secret manque encore patiente puis démarre. Il n'y a pas
d'ordonnancement à décrire pour chaque consommateur.

## Vérifier

```sh
# le SealedSecret est arrivé
kubectl -n mon-namespace get sealedsecret

# le Secret a été produit
kubectl -n mon-namespace get secret mon-secret

# en cas de doute, les journaux du contrôleur
kubectl -n sealed-secrets logs deploy/sealed-secrets-controller
```

Le message d'erreur le plus fréquent est `no key could decrypt secret`. Il
signifie presque toujours que le secret a été scellé pour un autre namespace ou
un autre nom que celui sous lequel il est déposé.

## Exemple concret : les identifiants S3

C'est le premier cas réel, encore à faire (voir [backlog.md](./backlog.md)).
Le composant `csi-s3` attend aujourd'hui un `Secret` nommé `csi-s3-secret` dans
le namespace `csi-s3`, créé à la main, avec quatre clés :

```sh
kubectl create secret generic csi-s3-secret \
  --namespace csi-s3 \
  --from-literal=accessKeyID='...' \
  --from-literal=secretAccessKey='...' \
  --from-literal=endpoint='https://...' \
  --from-literal=region='' \
  --dry-run=client -o yaml \
| kubeseal --controller-namespace sealed-secrets --format yaml \
> manifests/csi-s3/secret.sealed.yaml
```

Il reste ensuite à ajouter l'annotation, à déclarer le fichier dans
`manifests/csi-s3/kustomization.yaml`, et à retirer le commentaire de
`application.yaml` qui signale que ce secret échappe au GitOps.

## Sauvegarder et restaurer la clé

### Pourquoi

La clé privée du contrôleur est la seule chose capable de déchiffrer les
`SealedSecret` de ce dépôt. Si le cluster disparaît sans qu'elle ait été
sauvegardée, tous les fichiers scellés committés deviennent illisibles, et il
faut réémettre chaque identifiant chez son fournisseur avant de pouvoir
reconstruire. Ce n'est pas une catastrophe — tout est réémissible, c'est le pari
assumé dans [securite.md](./securite.md) — mais c'est une soirée perdue au pire
moment, pendant une reconstruction déjà pénible.

Le renouvellement automatique étant désactivé, il n'y a **qu'une seule clé**.
La sauvegarde se fait donc une fois et reste valable indéfiniment.

### Sauvegarder

```sh
kubectl -n sealed-secrets get secret \
  -l sealedsecrets.bitnami.com/sealed-secrets-key \
  -o yaml > sealed-secrets-key.yaml
```

Vérifiez que le fichier n'est pas vide — une erreur de namespace ou de label
produit une liste vide sans message d'erreur :

```sh
grep -c 'tls.key' sealed-secrets-key.yaml   # doit renvoyer 1
```

**Ce fichier contient la clé privée.** Il ne va ni dans ce dépôt, ni dans un
canal de discussion, ni dans un dossier partagé ouvert. Sa place est le
gestionnaire de mots de passe du cercle, ou une archive chiffrée hors ligne.

Et il doit être accessible à **au moins deux personnes**. Une sauvegarde connue
d'une seule personne disparaît avec elle, ce qui est le mode de défaillance le
plus probable dans un cercle où les membres tournent chaque année.

### Tester la sauvegarde sans reconstruire le cluster

Une sauvegarde jamais testée n'est pas une sauvegarde. `kubeseal` sait
déchiffrer hors ligne, en lisant directement le fichier produit ci-dessus :

```sh
kubeseal --recovery-unseal \
  --recovery-private-key sealed-secrets-key.yaml \
  < manifests/mon-composant/mon-secret.sealed.yaml
```

La commande affiche le `Secret` en clair. Si c'est le cas, la sauvegarde est
bonne. Aucun accès au cluster n'est nécessaire.

Attention : **cette sortie est le secret en clair.** Faites-le dans un
répertoire temporaire, sans rediriger vers un fichier du dépôt.

### Restaurer

Le cas idéal est de remettre la clé **avant** que le contrôleur ne démarre pour
la première fois. En pratique ArgoCD l'aura déjà lancé, ce qui n'est pas grave :

```sh
kubectl apply -f sealed-secrets-key.yaml
kubectl -n sealed-secrets rollout restart deployment sealed-secrets-controller
```

Le redémarrage est nécessaire : le contrôleur ne lit les clés qu'au démarrage,
il ne les recharge pas à chaud.

Si le contrôleur avait déjà généré une clé de son côté, les deux coexistent
sans conflit. Il essaie toutes les clés qu'il connaît pour déchiffrer, donc les
anciens secrets scellés repassent, et les nouveaux scellements utilisent la plus
récente. Il n'y a rien à nettoyer.

Vérification, sur un composant qui possède déjà un secret scellé :

```sh
kubectl -n mon-namespace get secret mon-secret
```

### Si la clé est perdue pour de bon

L'ordre est le même que pour une fuite : révoquer chaque identifiant chez son
fournisseur, en émettre un nouveau, le resceller avec la nouvelle clé du
cluster, committer. C'est là que l'inventaire des secrets scellés paie, en
transformant une rotation d'urgence en liste à dérouler plutôt qu'en fouille du
dépôt.

## Les règles à ne pas contourner

**Ne jamais committer le secret en clair,** même « temporairement, pour tester ».
Le dépôt est public et l'historique est définitif. Utilisez toujours le tube
avec `--dry-run=client`, qui évite d'avoir un fichier en clair sur le disque.

**Réduire la portée de chaque identifiant.** Une clé S3 par bucket plutôt qu'une
clé maîtresse, un compte NAS limité à un partage. Une fuite se répare alors
service par service, sans tout révoquer d'un coup.

**Noter ce qui est scellé.** Pour chaque secret : à quel service il donne accès,
et qui peut en émettre un nouveau. Aucune valeur n'y figure, cette liste vit
donc dans le dépôt. C'est ce qui rend une rotation d'urgence mécanique plutôt
que devinatoire.

**En cas de fuite,** l'ordre est : révoquer l'identifiant chez son fournisseur,
en émettre un nouveau, le resceller, committer. Réécrire l'historique git ne
répare rien, puisqu'on ne sait pas qui a déjà lu.
