from functools import wraps
from django.http import HttpResponseForbidden

def feature_required(feature_key):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            tenant = getattr(request, 'tenant', None)
            try:
                subscription = tenant.subscriptions.filter(is_active=True).latest('start_date')
                if subscription.package.features.get(feature_key, False):
                    return view_func(request, *args, **kwargs)
            except Exception:
                pass
            return HttpResponseForbidden("Funkcja niedostępna w Twoim pakiecie.")
        return _wrapped_view
    return decorator
