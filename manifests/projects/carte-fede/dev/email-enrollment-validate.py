"""Native DEV intake. Existing identities are never altered by anonymous intake."""
import hashlib,hmac,json,time,uuid,re
import requests
from django.db import transaction,connection
from django.core.cache import cache
from authentik.flows.models import Flow
from authentik.core.models import User,Group,Token
from authentik.rbac.models import Role
plan=request.context.get('flow_plan') or request.http_request.session.get('authentik/flows/plan')
prompt=request.context.get('prompt_data',{})
if not plan or not Flow.objects.filter(pk=plan.flow_pk,slug='carte-fede-dev-enrollment').exists() or request.http_request.user.is_authenticated:return False
if not set(prompt)<={'component','nom','prenom','identifier','existing_account'}:return False
business={k:prompt.get(k,'').strip() if isinstance(prompt.get(k,''),str) else '' for k in ['nom','prenom','identifier']}
if any(not 1<=len(business[k])<=100 for k in ['nom','prenom']) or any(re.search(r'[\x00-\x1f\x7f]',str(v)) for v in prompt.values()):
    ak_message('Informations invalides.');return False
identifier=business['identifier'].lower()
if re.fullmatch(r'[0-9]{6}',identifier):email=identifier+'@umons.ac.be'
elif len(identifier)<=254 and re.fullmatch(r'[^@\s<>(),;:\\\[\]\"]+@[^@\s<>(),;:\\\[\]\"]+\.[^@\s<>(),;:\\\[\]\"]+',identifier):email=identifier
else:
    ak_message('Matricule de six chiffres ou adresse e-mail requis.');return False
business['identifier']=identifier
canonical_matricule=re.fullmatch(r'([0-9]{6})@umons\.ac\.be',email)
if canonical_matricule:business['identifier']=canonical_matricule.group(1)
# The operator authorized real common SMTP for DEV. Native email proof is
# mandatory; clone tests replace this guard and SMTP with synthetic capture.
eligible=True
digest=hashlib.sha256(email.encode()).hexdigest()
pending=User(email=digest+'@example.invalid',name='Carte Fede DEV verification')
with transaction.atomic():
    for scope in sorted([digest,'origin:'+str(request.http_request.META.get('REMOTE_ADDR','unknown'))]):
        lock=int.from_bytes(hashlib.sha256(('carte-fede-dev-email:'+scope).encode()).digest()[:8],'big',signed=True)
        with connection.cursor() as cursor:cursor.execute('SELECT pg_advisory_xact_lock(%s)',[lock])
    rate_key='carte-fede-dev-email-intake:'+digest
    origin_key='carte-fede-dev-email-origin:'+hashlib.sha256(str(request.http_request.META.get('REMOTE_ADDR','unknown')).encode()).hexdigest()
    attempts=cache.get(rate_key,0);origins=cache.get(origin_key,0)
    cache.set(rate_key,attempts+1,3600);cache.set(origin_key,origins+1,3600)
    eligible=eligible and attempts<3 and origins<20
    matches=list(User.objects.filter(email__iexact=email).select_for_update()[:2])
    if eligible:
        # Prevent a duplicate identity when an existing Authentik account has no
        # email field but its authoritative business contact is already reserved.
        check={'operation':'email-check','business':business}
        if len(matches)==1:check['subject']=str(matches[0].uuid)
        key=Token.objects.get(identifier='carte-fede-dev-enrollment-hook').key
        stamp=str(int(time.time()));body=json.dumps(check,sort_keys=True).encode();sign=hmac.new(key.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        try:
            answer=requests.post('http://carte-fede-dev.carte-fede-dev.svc.cluster.local:8000/api/dev/enrollment-hook',data=body,headers={'Content-Type':'application/json','X-Enrollment-Time':stamp,'X-Enrollment-Signature':sign},timeout=8,allow_redirects=False)
            eligible=answer.status_code==200
        except requests.RequestException:eligible=False
    if eligible and not matches:
        owned=User(username='carte-fede-dev-email-'+uuid.uuid4().hex,name='Carte Fede DEV enrollment',email=email,is_active=False,type='internal',path='users/carte-fede-dev-enrollment',attributes={'carte_fede_dev_owned':True,'carte_fede_dev_intake':business})
        owned.set_unusable_password();owned.save();owned.groups.add(Group.objects.get(name='default'))
        Role.objects.get(name='carte-fede-dev-owned-identities').assign_perms(['authentik_core.view_user','authentik_core.change_user'],owned)
        matches=[owned]
    if eligible and len(matches)==1:
        owned=matches[0]
        if not owned.is_active and owned.path=='users/carte-fede-dev-enrollment' and owned.attributes.get('carte_fede_dev_owned') is True and owned.attributes.get('carte_fede_dev_intake')==business and not owned.is_superuser and not owned.roles.exists() and set(owned.groups.values_list('name',flat=True))=={'default'}:
            pending=owned
if pending.pk:
    data={'operation':'email-created','subject':str(pending.uuid),'auth_user_pk':pending.pk,'business':business}
    key=Token.objects.get(identifier='carte-fede-dev-enrollment-hook').key;stamp=str(int(time.time()));body=json.dumps(data,sort_keys=True).encode();sign=hmac.new(key.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
    try:
        response=requests.post('http://carte-fede-dev.carte-fede-dev.svc.cluster.local:8000/api/dev/enrollment-hook',data=body,headers={'Content-Type':'application/json','X-Enrollment-Time':stamp,'X-Enrollment-Signature':sign},timeout=8,allow_redirects=False)
        if response.status_code!=202:
            # Same generic challenge for collision / unavailable business profile.
            pending=User(email=digest+'@example.invalid',name='Carte Fede DEV verification')
    except requests.RequestException:
        pending=User(email=digest+'@example.invalid',name='Carte Fede DEV verification')
plan.context['pending_user']=pending
prompt.clear();plan.context['prompt_data']={}
return True
