from authentik.flows.models import Flow
import re
plan=request.context.get('flow_plan') or request.http_request.session.get('authentik/flows/plan')
user=request.http_request.user;prompt=request.context.get('prompt_data',{})
if not plan or not Flow.objects.filter(pk=plan.flow_pk,slug='carte-fede-dev-existing-registration').exists() or not user.is_authenticated or not user.is_active or user.type not in ('internal','external'):return False
if not set(prompt)<={'component','nom','prenom','identifier'}:return False
business={k:prompt.get(k,'').strip() if isinstance(prompt.get(k,''),str) else '' for k in ['nom','prenom','identifier']}
if any(not 1<=len(business[k])<=100 for k in ['nom','prenom']) or any(re.search(r'[\x00-\x1f\x7f]',str(v)) for v in prompt.values()):return False
value=business['identifier'].lower()
if not re.fullmatch(r'[0-9]{6}',value) and not (len(value)<=254 and re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',value)):return False
business['identifier']=value
plan.context['carte_fede_dev_business']=business
return True
