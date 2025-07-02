# users/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django_otp import user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.contrib import messages


class Require2FAMiddleware:
    """Middleware wymuszający 2FA dla wszystkich użytkowników"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs które nie wymagają 2FA
        self.exempt_urls = [
            '/login/',
            '/verify-2fa/',
            '/setup-2fa-required/',
            '/logout/',

            '/static/',  
            '/media/',  
        ]
    
    def __call__(self, request):
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            
            if not any(request.path.startswith(url) for url in self.exempt_urls):
                
                has_confirmed_device = TOTPDevice.objects.filter(
                    user=request.user, 
                    confirmed=True
                ).exists()
                
                if not has_confirmed_device:
                    # Dla dostępu do admin, wymagaj natychmiastowej konfiguracji 2FA
                    if request.path.startswith('/admin/'):
                        messages.warning(request, 'Panel administratora wymaga aktywacji 2FA')
                    
                    if not request.session.get('pre_2fa_user_id'):
                        request.session['pre_2fa_user_id'] = request.user.id
                    return redirect('users:setup_2fa_required')  # ← POPRAWIONE z 'accounts:'
                
                # Sprawdź czy użytkownik jest zweryfikowany z 2FA w tej sesji
                if not request.user.is_verified():
                    if request.path.startswith('/admin/'):
                        messages.info(request, 'Potwierdź kod 2FA aby uzyskać dostęp do panelu administratora')
                    
                    if not request.session.get('pre_2fa_user_id'):
                        request.session['pre_2fa_user_id'] = request.user.id
                    return redirect('users:verify_2fa')  # ← POPRAWIONE z 'accounts:'
        
        response = self.get_response(request)
        return response