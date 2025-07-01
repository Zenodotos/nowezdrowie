from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.TwoFactorLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verify-2fa/', views.verify_2fa, name='verify_2fa'),
    path('setup-2fa-required/', views.setup_2fa_required, name='setup_2fa_required'),
    path('setup-2fa/', views.setup_2fa, name='setup_2fa'),
    path('confirm-2fa/', views.confirm_2fa, name='confirm_2fa'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('', views.home, name='home')
]