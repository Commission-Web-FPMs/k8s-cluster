# Inventaire des secrets

Un secret par ligne, avec un lien vers sa fiche. **Rien d'autre.**

Cette pauvreté est délibérée. Un inventaire qui recopierait la portée de chaque
identifiant ou le nom de son responsable finirait par les recopier faux, et un
inventaire qui ment est pire que pas d'inventaire, parce qu'on le lit le jour
d'une fuite en lui faisant confiance. Toute la vérité vit dans les fiches. Ici,
le seul défaut possible est une ligne manquante.

Aucune valeur ne figure dans cette page ni dans les fiches qu'elle référence.
Elles décrivent où obtenir un identifiant, jamais lequel.

| Service | Fiche |
| --- | --- |
| Stockage objet S3 (fournisseur externe) | [s3-credentials](../manifests/csi-s3/s3-credentials.md) |

## Comment ajouter une ligne

Un secret scellé se compose toujours de deux fichiers voisins :

```text
manifests/mon-composant/mon-secret.sealed.yaml   <- généré par kubeseal
manifests/mon-composant/mon-secret.md            <- la fiche
```

Partez de [modeles/secret.md](./modeles/secret.md), remplissez-le, ajoutez la
ligne ici. La procédure de scellement elle-même est dans
[secrets.md](./secrets.md).

La section qui compte dans une fiche est **« Obtenir de nouveaux
identifiants »** : le chemin réel dans l'interface du fournisseur, écran par
écran. C'est la seule chose que personne ne peut reconstituer seul, et c'est
celle qu'un cercle perd d'une année sur l'autre. Une fiche dont cette section
est vide vaut mieux qu'une fiche dont cette section est inventée : la première
se voit, la seconde se découvre au mauvais moment.
