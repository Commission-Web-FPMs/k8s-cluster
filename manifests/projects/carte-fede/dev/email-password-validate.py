# Native Authentik policy; password never leaves this process.
from django.db import transaction
from django.utils.timezone import now
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from authentik.core.models import User
from authentik.flows.models import Flow,FlowToken
import secrets,hashlib
plan=request.context.get('flow_plan') or request.http_request.session.get('authentik/flows/plan')
prompt=request.context.get('prompt_data',{})
if not plan or not Flow.objects.filter(pk=plan.flow_pk,slug='carte-fede-dev-enrollment').exists():return False
token=plan.context.get('is_restored');pending=plan.context.get('pending_user')
password=prompt.get('password','')
if not token or token.pk is not None or str(token.flow_id).replace('-','')!=str(plan.flow_pk).replace('-','') or not pending or not pending.pk or token.user_id!=pending.pk or not set(prompt)<={'component','password','password_repeat'} or not isinstance(password,str) or not 12<=len(password)<=128 or password!=prompt.get('password_repeat'):
    ak_message('Lien invalide ou mot de passe invalide.');return False
try:
    with transaction.atomic():
        # Lock user first: all valid links for this user share one barrier.
        user=User.objects.select_for_update().get(pk=pending.pk)
        consumed=hashlib.sha256(token.key.encode()).hexdigest()
        if token.expires<=now() or user.attributes.get('carte_fede_dev_consumed_link')==consumed or user.is_active or user.email!=pending.email or user.path!='users/carte-fede-dev-enrollment' or user.type!='internal' or user.attributes.get('carte_fede_dev_owned') is not True or user.is_superuser or user.roles.exists() or set(user.groups.values_list('name',flat=True))!={'default'}:
            ak_message('Lien expiré ou déjà utilisé.');return False
        validate_password(password,user)
        proof=secrets.token_urlsafe(32)
        user.set_password(password,request=request.http_request)
        user.attributes=dict(user.attributes,carte_fede_dev_verified_email=user.email,carte_fede_dev_email_proof=proof,carte_fede_dev_password_initialized=True,carte_fede_dev_consumed_link=consumed)
        user.save()
        # Revoke every outstanding enrollment link atomically with the password.
        FlowToken.objects.filter(flow_id=plan.flow_pk,user_id=user.pk).delete()
    plan.context['pending_user']=user
    plan.context['carte_fede_dev_email_proof']=proof
    prompt.clear();plan.context['prompt_data']={}
    return True
except (ValidationError,User.DoesNotExist):
    ak_message('Lien invalide ou mot de passe insuffisamment robuste.');return False
