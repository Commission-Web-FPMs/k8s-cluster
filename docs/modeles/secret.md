---
service:      Nom lisible du service auquel ce secret donne accès
secret:       nom-du-secret-kubernetes
namespace:    namespace-de-destination
portee:       ce que cet identifiant permet, et ce qu'il ne permet pas
reemission:   le rôle qui peut en émettre un nouveau, jamais un prénom
consomme_par: manifests/.../application.yaml
---

<!--
Modèle de fiche de secret. À copier à côté du fichier scellé qu'il décrit :

  manifests/mon-composant/mon-secret.sealed.yaml   <- généré par kubeseal
  manifests/mon-composant/mon-secret.md            <- cette fiche

Le fichier scellé est un artefact : kubeseal le réécrit intégralement à chaque
scellement et n'y conserve aucun commentaire. Tout ce qui est destiné à un
humain vit donc ici.

Deux consignes pour l'en-tête ci-dessus. `reemission` désigne un rôle et non
une personne : dans un cercle où les membres tournent chaque année, « le
responsable infra » reste vrai, un prénom non. Et `portee` doit dire ce que
l'identifiant ne permet pas, parce que c'est ce qui détermine l'ampleur des
dégâts en cas de fuite.

Pensez à ajouter la ligne correspondante dans docs/secrets-inventaire.md.
-->

# Titre

## À quoi ça sert

Une ou deux phrases : ce que ce secret permet, et ce qui casse sans lui. De
quoi permettre à quelqu'un qui découvre le dépôt de décider si le problème
qu'il a sous les yeux vient de là.

## Obtenir de nouveaux identifiants

La partie qui compte, et la seule que personne ne peut deviner. Décrire le
chemin réel, écran par écran : l'adresse à ouvrir, le compte à utiliser, le
menu, le bouton.

1. Ouvrir <https://...> et se connecter avec ...
2. Menu **...** → **...**
3. Cliquer sur **...**
4. Renseigner ... et cocher ... uniquement.
5. Copier la valeur affichée. Préciser ici si elle n'est montrée qu'une fois.

Signaler aussi ce qu'il ne faut **pas** faire : les permissions trop larges, la
clé maîtresse au lieu d'une clé restreinte, le compte personnel au lieu du
compte de service.

## Sceller et committer

La procédure générale est dans [secrets.md](../../docs/secrets.md). Reproduire
ici la commande exacte pour ce secret, avec le bon namespace, le bon nom et les
bons noms de clés, pour qu'elle soit copiable telle quelle :

```sh
kubectl create secret generic mon-secret \
  --namespace mon-namespace \
  --from-literal=cle='...' \
  --dry-run=client -o yaml \
| kubeseal --controller-namespace sealed-secrets --format yaml \
> manifests/mon-composant/mon-secret.sealed.yaml
```

Ne rien ajouter à la main dans le fichier obtenu : `kubeseal` le réécrit
intégralement à chaque rescellement. C'est le `kustomization.yaml` du composant
qui doit le déclarer et lui appliquer l'annotation
`SkipDryRunOnMissingResource=true` par un patch — voir
[secrets.md](../../docs/secrets.md), « Committer le résultat », et
`manifests/csi-s3/kustomization.yaml` pour un exemple en place.

## Révoquer l'ancien identifiant

Une rotation n'est pas finie quand le nouveau secret fonctionne, elle est finie
quand l'ancien est mort. C'est l'étape qu'on oublie, et celle qui fait qu'un
identifiant compromis reste valable des mois.

Décrire ici où révoquer, avec le même niveau de détail que pour l'émission.

**L'ordre dépend de la situation :**

- *Rotation de routine* — créer le nouveau, déployer, vérifier, **puis**
  révoquer l'ancien. Aucune coupure de service.
- *Fuite avérée* — révoquer **d'abord**, tout de suite, et accepter la coupure.
  On ne laisse pas vivre un identifiant compromis le temps de faire les choses
  proprement.
