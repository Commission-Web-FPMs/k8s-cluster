import hashlib,hmac,json,time,uuid,re
import requests
from authentik.flows.models import Flow
from authentik.core.models import Token,User
# Prompt validation policies receive prompt_data, but no flow_plan in 2026.8.
# Read the server-side executor session; never accept a client flow identifier.
plan=request.context.get('flow_plan') or request.http_request.session.get('authentik/flows/plan')
if not plan:
    return False
if not Flow.objects.filter(pk=plan.flow_pk,slug='carte-fede-dev-enrollment').exists() or (request.http_request and request.http_request.user.is_authenticated):
    ak_message('Utilisez la connexion existante pour une identité déjà active.');return False
prompt=request.context.get('prompt_data',{})
allowed={'username','password','password_repeat','nom','prenom','member_id','business_email','free_card_requested','component'}
if not set(prompt)<=allowed or not 12<=len(prompt.get('password',''))<=128:
    ak_message('Champs invalides ou mot de passe trop court (12 caractères).');return False
business={k:prompt.get(k,'') for k in ['nom','prenom','member_id']}
business['email']=prompt.get('business_email','');business['free_card_requested']=bool(prompt.get('free_card_requested',False))
key=Token.objects.get(identifier='carte-fede-dev-enrollment-hook').key
stamp=str(int(time.time()));body=json.dumps({'operation':'check','business':business},sort_keys=True).encode()
sign=hmac.new(key.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
try:
    response=requests.post('http://carte-fede-dev.carte-fede-dev.svc.cluster.local:8000/api/dev/enrollment-hook',data=body,headers={'Content-Type':'application/json','X-Enrollment-Time':stamp,'X-Enrollment-Signature':sign},timeout=8,allow_redirects=False)
    if response.status_code!=200:
        ak_message('Informations invalides ou inscription déjà en attente.');return False
except requests.RequestException:
    ak_message('Inscription temporairement indisponible.');return False
# Keep only fixed built-in user fields and a server-owned marker for User Write.
plan.context['carte_fede_dev_business']=business
username,password=prompt['username'],prompt['password']
prompt.clear();prompt.update(username=username,password=password,name='Carte Fede DEV enrollment',attributes={'carte_fede_dev_owned':True})
plan.context['prompt_data']=prompt
return True
