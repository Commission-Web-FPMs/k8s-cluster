"""Validation transactionnelle via ak shell, avec un payload JSON sur stdin."""

import json
import secrets
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yaml
from django.db import transaction

from authentik.blueprints.v1.importer import Importer
from authentik.core.models import Application, Group, Token, User
from authentik.policies.models import PolicyBinding
from authentik.providers.oauth2.models import OAuth2Provider


def check(condition, message):
    if not condition:
        raise AssertionError(message)


payload = json.load(sys.stdin)
configuration = payload["configuration"]
if "render" in payload:
    resources = list(yaml.safe_load_all(payload["render"]))
    configurations = [
        resource for resource in resources
        if resource and resource["kind"] == "ConfigMap"
        and resource["metadata"]["name"] == "authentik-config"
    ]
    check(len(configurations) == 2, "Les deux ConfigMaps de configuration sont absentes")
    check(
        {resource["metadata"]["namespace"] for resource in configurations}
        == {"authentik", "carte-fede-main"},
        "Namespaces des ConfigMaps incorrects",
    )
    check(all(resource["data"] == configuration for resource in configurations), "Configurations divergentes")
    sealed = [
        resource for resource in resources
        if resource and resource["kind"] == "SealedSecret"
        and (resource["metadata"].get("namespace"), resource["metadata"]["name"])
        in {("authentik", "carte-fede-credentials"), ("carte-fede-main", "authentik-credentials")}
    ]
    check(len(sealed) == 2, "Les deux SealedSecrets sont absents")
    check(
        all(set(resource["spec"]["encryptedData"]) == {"AUTHENTIK_API_TOKEN", "OIDC_CLIENT_SECRET"} for resource in sealed),
        "Clés des SealedSecrets incorrectes",
    )
    blueprint_maps = [
        resource for resource in resources
        if resource and resource["kind"] == "ConfigMap"
        and resource["metadata"]["name"] == "authentik-blueprints"
    ]
    check(len(blueprint_maps) == 1 and blueprint_maps[0]["data"]["fede.yaml"] == payload["blueprint"], "Blueprint absent du rendu")
    print("PASS : rendu Kustomize, configurations partagées et SealedSecrets")
check(
    configuration["OIDC_ISSUER_URL"]
    == "https://auth.fede.fpms.ac.be/application/o/"
    + configuration["OIDC_APP_SLUG"]
    + "/",
    "Issuer et slug incohérents",
)
check(
    urlparse(configuration["OIDC_REDIRECT_URI"]).scheme == "https"
    and urlparse(configuration["OIDC_REDIRECT_URI"]).netloc
    == urlparse(configuration["OIDC_APP_BASE_URL"]).netloc,
    "Callback hors du domaine applicatif HTTPS",
)
baseline = [model.objects.count() for model in (User, Group, Token, OAuth2Provider, Application)]
service_account_exists = User.objects.filter(username="svc-carte-fede-main").exists()

with tempfile.TemporaryDirectory(prefix="authentik-blueprint-test-") as directory:
    root = Path(directory)
    credentials = {
        key: secrets.token_urlsafe(64)
        for key in ("AUTHENTIK_API_TOKEN", "OIDC_CLIENT_SECRET")
    }
    for key, value in {**configuration, **credentials}.items():
        (root / key).write_text(value, encoding="utf-8")
    source = payload["blueprint"].replace("/secrets/carte-fede/", directory + "/")
    source = source.replace("/config/carte-fede/", directory + "/")

    with transaction.atomic():
        importer = Importer.from_string(source)
        valid, logs = importer.validate()
        check(valid, "Le blueprint est invalide")
        check(importer.apply(), "La première application a échoué")

        person = User.objects.create(
            username="gitops-test-" + secrets.token_hex(8), type="internal"
        )
        person.groups.add(Group.objects.get(name="membres"))
        check(importer.apply(), "La seconde application a échoué")
        check(person.groups.filter(name="membres").exists(), "Une appartenance humaine a été perdue")
        check(
            User.objects.count() == baseline[0] + 1 + int(not service_account_exists),
            "Création inattendue d'utilisateurs",
        )

        user = User.objects.get(username="svc-carte-fede-main")
        check(user.type == "service_account", "Type de compte incorrect")
        check(user.groups.count() == 0 and not user.is_superuser, "Le compte technique est privilégié")
        check(user.has_perm("authentik_core.view_user"), "Permission de lecture absente")
        check(not user.has_perm("authentik_core.change_user"), "Permission d'écriture inattendue")
        check(not user.has_perm("authentik_core.add_user"), "Permission de création inattendue")
        token = Token.objects.get(identifier="carte-fede-main-api")
        check(token.user_id == user.pk and token.intent == "api", "Token lié au mauvais compte")
        check(token.key == credentials["AUTHENTIK_API_TOKEN"], "Clé du token différente")

        application = Application.objects.get(slug=configuration["OIDC_APP_SLUG"])
        provider = OAuth2Provider.objects.get(pk=application.provider_id)
        check(provider.client_id == configuration["OIDC_CLIENT_ID"], "Client ID différent")
        check(provider.client_secret == credentials["OIDC_CLIENT_SECRET"], "Secret OIDC différent")
        check(provider.client_type == "confidential", "Type de client incorrect")
        check(provider.issuer_mode == "per_provider", "Mode issuer incorrect")
        check(provider.grant_types == ["authorization_code"], "Grants inattendus")
        check(
            len(provider.redirect_uris) == 1
            and provider.redirect_uris[0].url == configuration["OIDC_REDIRECT_URI"]
            and provider.redirect_uris[0].matching_mode == "strict",
            "Callback incorrect",
        )
        check(provider.signing_key is not None, "Clé de signature absente")
        check(
            "goauthentik.io/providers/oauth2/scope-profile"
            in provider.property_mappings.values_list("managed", flat=True),
            "Mapping profile absent",
        )
        bindings = PolicyBinding.objects.filter(target=application)
        check(application.policy_engine_mode == "any", "Accès aux groupes non alternatif")
        check(
            set(bindings.values_list("group__name", flat=True)) == {"membres", "comite", "admin"},
            "Bindings de groupes incorrects",
        )
        check(not Group.objects.filter(name__in=["membres", "comite", "admin"], is_superuser=True).exists(), "Groupe applicatif superuser")
        transaction.set_rollback(True)

check(
    [model.objects.count() for model in (User, Group, Token, OAuth2Provider, Application)] == baseline,
    "La validation a laissé des objets en base",
)
print("PASS : création, réapplication, permissions, credentials, OIDC et rollback")
