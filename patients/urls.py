from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    path('', views.PatientListView.as_view(), name='list'),
    path('create/', views.PatientCreateView.as_view(), name='create'),
]
