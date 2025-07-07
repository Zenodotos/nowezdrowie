from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    path('', views.PatientListView.as_view(), name='list'),
    path('create/', views.PatientCreateView.as_view(), name='create'),
    path('<int:pk>/', views.PatientDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.PatientUpdateView.as_view(), name='edit'),
    path('<int:pk>/start-40plus/', views.start_40plus_visit, name='start_40plus'),
    path('<int:pk>/check-insurance/', views.check_patient_insurance, name='check_insurance'),
]