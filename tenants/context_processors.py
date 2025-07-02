def tenant_features(request):
    features = {}
    tenant = getattr(request, 'tenant', None)

    if tenant:
        try:
            subscription = tenant.subscriptions.filter(is_active=True).latest('start_date')
            package = subscription.package
            features = package.features or {}
        except Exception:
            pass

    return {
        'package_features': features
    }
