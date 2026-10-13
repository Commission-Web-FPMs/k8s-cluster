import hashlib,hmac,json,time
import requests
from authentik.flows.models import Flow
from authentik.core.models import Token
plan=request.context['flow_plan'];user=request.http_request.user
if not Flow.objects.filter(pk=plan.flow_pk,slug='carte-fede-dev-existing-registration').exists() or not user.is_authenticated or not user.is_active or user.type not in ('internal','external'):return False
key=Token.objects.get(identifier='carte-fede-dev-enrollment-hook').key
data={'operation':'existing-verified','active_attestation':True,'subject':str(user.uuid),'business':plan.context['carte_fede_dev_business']}
if user.path=='users/carte-fede-dev-enrollment' and user.attributes.get('carte_fede_dev_owned') is True and user.attributes.get('carte_fede_dev_email_proof'):
    # Resume our own verified identity after a remote/local partial completion;
    # never convert an old pending identity solely because it has a pending row.
    data={'operation':'email-verified','subject':str(user.uuid),'auth_user_pk':user.pk,
          'proof_id':user.attributes['carte_fede_dev_email_proof'],
          'business':user.attributes['carte_fede_dev_intake']}
stamp=str(int(time.time()));body=json.dumps(data,sort_keys=True).encode();sign=hmac.new(key.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
try:
    response=requests.post('http://carte-fede-dev.carte-fede-dev.svc.cluster.local:8000/api/dev/enrollment-hook',data=body,headers={'Content-Type':'application/json','X-Enrollment-Time':stamp,'X-Enrollment-Signature':sign},timeout=8,allow_redirects=False)
    if response.status_code!=202 or response.json().get('state')!='approved':
        ak_message('Profil indisponible ; identité existante inchangée.');return False
except requests.RequestException:
    ak_message('Profil indisponible ; identité existante inchangée.');return False
plan.context['redirect_stage_target']='https://carte-dev.fede.fpms.ac.be/login/'
return True
