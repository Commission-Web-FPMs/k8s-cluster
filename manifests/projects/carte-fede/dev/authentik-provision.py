import json
from pathlib import Path
from uuid import UUID
from django.db import transaction
from authentik.blueprints.v1.importer import Importer
from authentik.core.models import User, Group
fixtures = json.loads(Path('/secrets/dev/FIXTURES_JSON').read_text())
with transaction.atomic():
    for label, fixture in fixtures.items():
        u = User.objects.filter(username=fixture['username']).first()
        if u is None:
            u = User.objects.create(username=fixture['username'], uuid=UUID(fixture['auth_uuid']),name='Synthetic DEV '+label,path='users/carte-fede-dev',is_active=label!='attente',attributes={'carte_fede_dev_uuid':fixture['business_uuid']})
            u.set_password(fixture['password']); u.save()
        assert str(u.uuid)==fixture['auth_uuid'] and u.path=='users/carte-fede-dev' and u.attributes.get('carte_fede_dev_uuid')==fixture['business_uuid'], 'Synthetic identity drift; no adoption'
    importer = Importer.from_string(Path('/blueprints/dev/blueprint.yaml').read_text())
    valid, logs = importer.validate()
    assert valid, 'DEV blueprint validation failed; diagnostics withheld'
    assert importer.apply(), 'DEV blueprint apply failed; diagnostics withheld'
    group = Group.objects.get(name='carte-fede-dev-testers')
    assert not group.is_superuser and not group.roles.exists() and not group.parents.exists()
    for label, fixture in fixtures.items():
        u = User.objects.get(username=fixture['username'])
        assert not u.roles.exists(), 'DEV users must not have Authentik roles'
        assert not u.groups.exclude(pk=group.pk).exists(), 'Unexpected synthetic membership'
        u.groups.add(group)
        assert u.is_active==(label!='attente'), 'Synthetic activation drift'
print('DEV OIDC provisioned; four synthetic identities only; no production changes')
