from django.urls import path
from . import views

urlpatterns = [
    path('patient/', views.find_patient, name='find-patient' )
]