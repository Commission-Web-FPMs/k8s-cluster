import hashlib,hmac,json,time
import requests
from authentik.flows.models import Flow
from authentik.core.models import Token,User
plan=request.context['flow_plan'];pending=plan.context.get('pending_user')
if not plan or not Flow.objects.filter(pk=plan.flow_pk,slug='carte-fede-dev-enrollment').exists() or not pending or not pending.pk:return False
user=User.objects.get(pk=pending.pk)
proof=plan.context.get('carte_fede_dev_email_proof')
if not proof or user.attributes.get('carte_fede_dev_email_proof')!=proof or user.attributes.get('carte_fede_dev_verified_email')!=user.email or not user.has_usable_password() or user.attributes.get('carte_fede_dev_password_initialized') is not True:return False
key=Token.objects.get(identifier='carte-fede-dev-enrollment-hook').key
data={'operation':'email-verified','subject':str(user.uuid),'auth_user_pk':user.pk,'proof_id':proof,'business':user.attributes['carte_fede_dev_intake']}
stamp=str(int(time.time()));body=json.dumps(data,sort_keys=True).encode();sign=hmac.new(key.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
try:
    result=requests.post('http://carte-fede-dev.carte-fede-dev.svc.cluster.local:8000/api/dev/enrollment-hook',data=body,headers={'Content-Type':'application/json','X-Enrollment-Time':stamp,'X-Enrollment-Signature':sign},timeout=8,allow_redirects=False)
    if result.status_code!=202 or result.json().get('state')!='approved':
        ak_message('Compte conservé sans accès complet ; finalisation à reprendre.');return False
except requests.RequestException:
    ak_message('Finalisation indisponible ; dossier conservé.');return False
plan.context['redirect_stage_target']='https://carte-dev.fede.fpms.ac.be/login/'
return True
