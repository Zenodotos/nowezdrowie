from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.start_ewus_session, name='login'),
    path('check/', views.check_patient, name='check'),
    path('logout/', views.end_ewus_session, name='logout')
]