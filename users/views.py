from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.urls import reverse_lazy
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import login as otp_login
from django_otp.util import random_hex
from .forms import CustomAuthenticationForm
import qrcode
from io import BytesIO
import base64
from .models import User
import pyotp


class TwoFactorLoginView(LoginView):

    template_name = 'users/login.html'     
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        user = form.get_user()
        
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
        
        if not device:
            device = TOTPDevice.objects.create(
                user=user,
                name=f'{user.username}_totp',
                confirmed=False
            )
            self.request.session['pre_2fa_user_id'] = user.id
            return redirect('users:setup_2fa_required')
        
        self.request.session['pre_2fa_user_id'] = user.id
        return redirect('users:verify_2fa')


def setup_2fa_required(request):

    tenant_name = getattr(request, 'tenant', None)
    if tenant_name:
        tenant_label = tenant_name.name      
    else:
        tenant_label = 'Moje Zdrowie'
    
    user_id = request.session.get('pre_2fa_user_id')
    if request.user.is_authenticated:
        return redirect('users:dashboard')
    if not user_id:
        return redirect('users:login')
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(id=user_id)
    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    
    if request.method == 'POST':
        token = request.POST.get('token')
        if device and device.verify_token(token):
            device.confirmed = True
            device.save()
            
            # Zaloguj użytkownika z 2FA
            login(request, user)
            otp_login(request, device)
            
            del request.session['pre_2fa_user_id']
            messages.success(request, '2FA zostało skonfigurowane i aktywowane!')
            return redirect('users:dashboard')
        else:
            messages.error(request, 'Nieprawidłowy kod')
    
    if not device:
        return redirect('users:login')
    secret = base64.b32encode(device.bin_key).decode()
    totp = pyotp.TOTP(secret)
    # Generuj QR kod
    provisioning_uri = totp.provisioning_uri(
        name=user.username,
        issuer_name=tenant_label
    )
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_code = base64.b64encode(buffer.getvalue()).decode()
    
    return render(request, 'users/setup_2fa_required.html', {
        'qr_code': qr_code,
        'manual_entry_key': base64.b32encode(device.bin_key).decode(),
        'user': user
    })


def logout_view(request):
    logout(request)
    return redirect('users:login')

def verify_2fa(request):
    """Weryfikacja kodu 2FA przy logowaniu"""
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return redirect('users:login')
    if request.user.is_authenticated:
        return redirect('users:dashboard')
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(id=user_id)
    
    if request.method == 'POST':
        token = request.POST.get('token')
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
        
        if device and device.verify_token(token):
            # Zaloguj użytkownika z 2FA
            login(request, user)
            otp_login(request, device)
            
            del request.session['pre_2fa_user_id']
            return redirect('users:dashboard')
        else:
            messages.error(request, 'Nieprawidłowy kod 2FA')
    
    return render(request, 'users/verify_2fa.html', {'user': user})


@login_required
def setup_2fa(request):
    """Zarządzanie 2FA dla zalogowanych użytkowników"""
    user = request.user
    device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
    if request.method == 'POST':
        if 'regenerate' in request.POST and device:
            # Regeneruj urządzenie
            device.delete()
            device = TOTPDevice.objects.create(
                user=user,
                name=f'{user.username}_totp',
                confirmed=False
            )
            return redirect('users:confirm_2fa')
    
    return render(request, 'users/setup_2fa.html', {
        'has_2fa': bool(device),
        'device': device
    })


@login_required
def confirm_2fa(request):
    """Potwierdzenie nowego urządzenia 2FA"""
    user = request.user
    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    
    if not device:
        return redirect('users:setup_2fa')
    
    if request.method == 'POST':
        token = request.POST.get('token')
        if device.verify_token(token):
            device.confirmed = True
            device.save()
            messages.success(request, '2FA zostało zaktualizowane!')
            return redirect('users:setup_2fa')
        else:
            messages.error(request, 'Nieprawidłowy kod')
    
    # Generuj QR kod
    provisioning_uri = device.config_url
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_code = base64.b64encode(buffer.getvalue()).decode()
    
    return render(request, 'users/confirm_2fa.html', {
        'qr_code': qr_code,
        'manual_entry_key': base64.b32encode(device.bin_key).decode()
    })


@login_required
def dashboard(request):

    user = request.user
    context = {'user': user}
    return render(request, 'users/dashboard.html', context)

def home(request):
    return redirect('users:dashboard')
