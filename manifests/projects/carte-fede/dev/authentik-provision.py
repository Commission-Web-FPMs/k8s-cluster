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

registration=Path('/blueprints/dev/enrollment-blueprint.yaml')
if registration.exists():
    importer=Importer.from_string(registration.read_text())
    valid,logs=importer.validate()
    assert valid, 'DEV enrollment invalid; details withheld'
    assert importer.apply(), 'DEV enrollment import failed; details withheld'
    from authentik.stages.email.models import EmailStage
    from authentik.stages.prompt.models import PromptStage
    stage=EmailStage.objects.get(name='carte-fede-dev-email-verification')
    assert not stage.use_global_settings and not stage.activate_user_on_success
    assert stage.host=='smtp.gmail.com' and stage.port==587 and stage.use_tls and not stage.use_ssl
    assert stage.username and stage.password and stage.from_address==stage.username
    prompt=PromptStage.objects.get(name='carte-fede-dev-email-enrollment-prompt')
    assert set(prompt.fields.exclude(type='static').values_list('field_key',flat=True))=={'nom','prenom','identifier'}
    for group_name in ['default','membres']:
        group=Group.objects.get(name=group_name)
        assert not group.is_superuser and not group.roles.exists() and not group.parents.exists(), 'Unexpected access inheritance; stop'
    from authentik.rbac.models import Role
    service=User.objects.get(username='carte-fede-dev-identity-service')
    assert not service.is_superuser and not service.groups.exists()
    role=Role.objects.get(name='carte-fede-dev-owned-identities')
    assert not service.has_perm('authentik_core.change_user') and not service.has_perm('authentik_core.add_user') and not service.has_perm('authentik_rbac.change_role'), 'No global permissions allowed'
    print('SAFE_DEV_ENROLLMENT_PROVISIONED dedicated_flow_object_scoped_API_no_global_permission')
