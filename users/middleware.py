# users/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django_otp import user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice


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
            '/admin/login/',
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
                   
                    if not request.session.get('pre_2fa_user_id'):
                        request.session['pre_2fa_user_id'] = request.user.id
                    return redirect('accounts:setup_2fa_required')
                
                
                if not request.user.is_verified():
                   
                    if not request.session.get('pre_2fa_user_id'):
                        request.session['pre_2fa_user_id'] = request.user.id
                    return redirect('accounts:verify_2fa')
        
        response = self.get_response(request)
        return response