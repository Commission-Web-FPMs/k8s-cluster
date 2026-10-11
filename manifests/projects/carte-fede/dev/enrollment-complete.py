import hashlib,hmac,json,time
import requests
from authentik.flows.models import Flow
from authentik.core.models import Token,Group
from authentik.rbac.models import Role
plan=request.context['flow_plan'];user=plan.context.get('pending_user')
if not Flow.objects.filter(pk=plan.flow_pk,slug='carte-fede-dev-enrollment').exists() or not user or user.path!='users/carte-fede-dev-enrollment' or user.attributes.get('carte_fede_dev_owned') is not True or user.is_active or user.is_superuser or user.roles.exists():
    return False
if set(user.groups.values_list('name',flat=True))!={'default'}:
    return False
role=Role.objects.get(name='carte-fede-dev-owned-identities')
role.assign_perms(['authentik_core.view_user','authentik_core.change_user'],user)
key=Token.objects.get(identifier='carte-fede-dev-enrollment-hook').key
stamp=str(int(time.time()));body=json.dumps({'operation':'created','subject':str(user.uuid),'auth_user_pk':user.pk,'business':plan.context['carte_fede_dev_business']},sort_keys=True).encode()
sign=hmac.new(key.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
try:
    response=requests.post('http://carte-fede-dev.carte-fede-dev.svc.cluster.local:8000/api/dev/enrollment-hook',data=body,headers={'Content-Type':'application/json','X-Enrollment-Time':stamp,'X-Enrollment-Signature':sign},timeout=8,allow_redirects=False)
    if response.status_code not in [200,202]:
        ak_message('Identité créée inactive ; transmission à reprendre, aucun accès accordé.');return False
except requests.RequestException:
    ak_message('Identité inactive conservée ; transmission à reprendre.');return False
from urllib.parse import urlsplit,parse_qs
target=response.json().get('confirmation_url','')
parsed=urlsplit(target)
if parsed.scheme!='https' or parsed.netloc!='carte-dev.fede.fpms.ac.be' or parsed.path!='/api/dev/enrollment-confirm' or set(parse_qs(parsed.query))!={'state'}:
    return False
plan.context['redirect_stage_target']=target
return True
