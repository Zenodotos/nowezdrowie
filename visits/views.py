from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import VisitCard

class VisitCardDetailView(LoginRequiredMixin, DetailView):
    model = VisitCard
    template_name = 'visits/visit_card_detail.html'
    context_object_name = 'visit_card'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visit_card = self.get_object()
        
        context.update({
            'page_title': f'Wizyta {visit_card.visit_type} - {visit_card.patient.get_decrypted_full_name()}',
            'examinations': visit_card.examinations.all().order_by('-created_at'),
            'measurements': visit_card.measurements.all().order_by('-measurement_date'),
            'status_badge_class': {
                'oczekiwanie': 'badge-warning',
                'przyjęte_do_realizacji': 'badge-info', 
                'badania_w_toku': 'badge-primary',
                'wizyta_odbyta': 'badge-success',
                'zakończone': 'badge-success',
                'odwołane': 'badge-error'
            }.get(visit_card.visit_status, 'badge-neutral')
        })
        return context