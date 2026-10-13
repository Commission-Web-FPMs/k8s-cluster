plan=request.context['flow_plan'];user=request.http_request.user
plan.context['redirect_stage_target']='ak-flow://carte-fede-dev-existing-registration' if user.is_authenticated and user.is_active else 'ak-flow://carte-fede-dev-enrollment'
return True
