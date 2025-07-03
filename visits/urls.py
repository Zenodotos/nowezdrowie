from django.urls import path
from . import views

app_name = 'visits'

urlpatterns = [
    path('<int:pk>/', views.VisitCardDetailView.as_view(), name='detail'),
    path('', views.VisitCardListView.as_view(), name='list'),
]