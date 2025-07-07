from django.db import models
from users.models import User
import uuid
from encrypted_model_fields.fields import EncryptedCharField

class EwusAccount(models.Model):
    id = models.UUIDField(default=uuid.uuid4(), editable=False, primary_key=True)
    userId = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ewuscreds')
    login = EncryptedCharField(verbose_name='zaszyfrowany login do ewuś')
    password = EncryptedCharField(verbose_name='zaszyfrowane hasło do ewuś')
    doctorId = EncryptedCharField(null=True, blank=True, verbose_name='zaszyfrowany id doktora')
    REGION_ID_CHOICES = [
    ('01', 'dolnośląskie (Wrocław)'),
    ('02', 'kujawsko-pomorskie (Bydgoszcz)'),
    ('03', 'lubelskie (Lublin)'),
    ('04', 'lubuskie (Zielona Góra)'),
    ('05', 'łódzkie (Łódź)'),
    ('06', 'małopolskie (Kraków)'),
    ('07', 'mazowieckie (Warszawa)'),
    ('08', 'opolskie (Opole)'),
    ('09', 'podkarpackie (Rzeszów)'),
    ('10', 'podlaskie (Białystok)'),
    ('11', 'pomorskie (Gdańsk)'),
    ('12', 'śląskie (Katowice)'),
    ('13', 'świętokrzyskie (Kielce)'),
    ('14', 'warmińsko-mazurskie (Olsztyn)'),
    ('15', 'wielkopolskie (Poznań)'),
    ('16', 'zachodniopomorskie (Szczecin)'),
    ]   
    regionId = models.CharField(verbose_name='id lokalizacji', choices=REGION_ID_CHOICES)



    @property
    def isDoctorIdRequired(self):
        if self.regionId in ('01', '04', '05', '06', '08,' '09', '11', '12'):
            return True
        else:
            return False
        
    def __str__(self):
        return self.userId.username