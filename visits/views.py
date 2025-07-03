from django.views.generic import DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import VisitCard
from django.urls import reverse



class VisitCardDetailView(LoginRequiredMixin, DetailView):
    model = VisitCard
    template_name = 'visits/visit_card_detail.html'
    context_object_name = 'visit_card'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visit_card = self.get_object()
        
        # Ustal URL powrotu na podstawie parametru 'from'
        from_page = self.request.GET.get('from', 'patient_detail')
        
        if from_page == 'visits_list':
            back_url = reverse('visits:list')
            back_text = 'Powrót do listy wizyt'
        else:
            back_url = reverse('patients:detail', kwargs={'pk': visit_card.patient.pk})
            back_text = 'Powrót do pacjenta'
        
        context.update({
            'page_title': f'Wizyta {visit_card.visit_type} - {visit_card.patient.get_decrypted_full_name()}',
            'examinations': visit_card.examinations.all().order_by('-created_at'),
            'measurements': visit_card.measurements.all().order_by('-measurement_date'),
            'back_url': back_url,
            'back_text': back_text,
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
    



class VisitCardListView(LoginRequiredMixin, ListView):
    model = VisitCard
    template_name = 'visits/visit_card_list.html'
    context_object_name = 'visit_cards'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related('patient')
        q = self.request.GET.get('q', '').strip()
        sort = self.request.GET.get('sort', '-created_at')
        status_filters = self.request.GET.getlist('status')
        
        # Filtrowanie po statusach
        if status_filters:
            qs = qs.filter(visit_status__in=status_filters)
        
        if q:
            matching_ids = []
            for visit_card in qs:
                try:
                    full_name = visit_card.patient.get_decrypted_full_name().lower()
                    pesel = visit_card.patient.get_decrypted_pesel()
                    
                    if (q.lower() in full_name or q in pesel):
                        matching_ids.append(visit_card.pk)
                except:
                    continue
            
            qs = qs.filter(pk__in=matching_ids)
        
        # Sortowanie
        if sort:
            direction = '' if sort.startswith('-') else ''
            sort_field = sort.lstrip('-')
            
            sort_mapping = {
                'patient_name': 'patient__last_name_encrypted',
                'questionnaire_date': 'questionnaire_date',
                'visit_status': 'visit_status',
                'visit_type': 'visit_type',
                'created_at': 'created_at',
            }
            
            if sort_field in sort_mapping:
                db_field = sort_mapping[sort_field]
                qs = qs.order_by(f"{direction}{db_field}")
            else:
                qs = qs.order_by('-created_at')
        else:
            qs = qs.order_by('-created_at')
            
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['sort'] = self.request.GET.get('sort', '')
        ctx['status_filters'] = self.request.GET.getlist('status')
        ctx['page_title'] = 'Karty wizyt'
        return ctx

    def get_template_names(self):
        if self.request.htmx:
            return ['visits/visit_card_table.html']
        return ['visits/visit_card_list.html']