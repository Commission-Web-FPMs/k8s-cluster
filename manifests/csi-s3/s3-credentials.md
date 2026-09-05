---
service:      Stockage objet S3 (fournisseur externe)
secret:       csi-s3-secret
namespace:    csi-s3
portee:       lecture et écriture sur les buckets accessibles à cette clé
reemission:   Responsable infrastructure de la Comm Web
consomme_par: manifests/csi-s3/application.yaml
---

# Identifiants du stockage S3

## À quoi ça sert

Le pilote `csi-s3` monte des buckets S3 comme volumes persistants. Ces
identifiants sont ceux avec lesquels le pilote se connecte au fournisseur.
Sans eux, aucun `PersistentVolumeClaim` en classe de stockage `s3` ne se lie,
et les Pods qui en demandent un restent bloqués en attente de volume.

> **Ce service est externe.** Il n'a rien à voir avec le NAS du cercle ni avec
> l'infrastructure du Magellan, qui héberge seulement les machines du cluster.
> C'est un fournisseur S3 tiers, joint par Internet, avec son propre compte et
> sa propre facturation. Ne cherchez pas ces identifiants dans la console du
> Magellan, ils n'y sont pas.

L'endpoint est :

```text
https://s3dupauvre.6700067.xyz
```

Ce stockage a vocation à être remplacé par un accès au NAS du cercle, comme
indiqué dans `application.yaml` et dans [backlog.md](../../docs/backlog.md).
Cette fiche disparaîtra avec lui.

## Obtenir de nouveaux identifiants

Demander au gestionnaire de `6700067.xyz` de s'en occuper.

## Sceller et committer

La procédure générale et l'installation de `kubeseal` sont dans
[secrets.md](../../docs/secrets.md). Pour ce secret précis, les quatre clés
attendues par le chart sont `accessKeyID`, `secretAccessKey`, `endpoint` et
`region` :

```sh
kubectl create secret generic csi-s3-secret \
  --namespace csi-s3 \
  --from-literal=accessKeyID='...' \
  --from-literal=secretAccessKey='...' \
  --from-literal=endpoint='https://s3dupauvre.6700067.xyz' \
  --from-literal=region='' \
  --dry-run=client -o yaml \
| kubeseal --controller-namespace sealed-secrets --format yaml \
> manifests/csi-s3/s3-credentials.sealed.yaml
```

**Il n'y a rien à modifier dans le fichier obtenu**, il suffit de le committer.
Le [`kustomization.yaml`](./kustomization.yaml) de ce dossier le déclare déjà et
lui applique l'annotation `SkipDryRunOnMissingResource=true` par un patch. C'est
voulu : `kubeseal` réécrit ce fichier intégralement à chaque rescellement, donc
tout ce qu'on y ajouterait à la main disparaîtrait à la rotation suivante.

## Révoquer l'ancien identifiant

Pas oublier de révoquer l'ancien identifiant une fois que le secret a été rotate.
