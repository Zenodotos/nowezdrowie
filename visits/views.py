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
    
from django.views.generic import ListView

class VisitCardListView(LoginRequiredMixin, ListView):
    model = VisitCard
    template_name = 'visits/visit_card_list.html'
    context_object_name = 'visit_cards'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related('patient', 'visit_type')
        q = self.request.GET.get('q', '').strip()
        sort = self.request.GET.get('sort', '-created_at')
        
        if q:
            matching_ids = []
            for visit_card in qs:
                try:
                    full_name = visit_card.patient.get_decrypted_full_name().lower()
                    pesel = visit_card.patient.get_decrypted_pesel()
                    
                    if (q.lower() in full_name or q in pesel):
                        matching_ids.append(visit_card.id)
                except:
                    continue
            qs = qs.filter(id__in=matching_ids)

        sort_mapping = {
            'patient_name': 'patient__first_name_encrypted',
            '-patient_name': '-patient__first_name_encrypted',
            'questionnaire_date': 'questionnaire_date',
            '-questionnaire_date': '-questionnaire_date',
            'visit_status': 'visit_status',
            '-visit_status': '-visit_status',
        }
        
        if sort in sort_mapping:
            return qs.order_by(sort_mapping[sort])
        
        return qs.order_by(sort)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'q': self.request.GET.get('q', ''),
            'sort': self.request.GET.get('sort', '-created_at'),
            'page_title': 'Karty wizyt',
            'breadcrumbs': [
                {'name': 'Karty wizyt', 'url': None}
            ]
        })
        return context