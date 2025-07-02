from django.core.management.base import BaseCommand
from django.db import transaction, connection
from patients.models import Patient
from tenants.models import Tenant
import random
from datetime import date


class Command(BaseCommand):
    help = 'Tworzy przykładowych pacjentów z prawidłowymi numerami PESEL dla wybranego tenanta'

    def add_arguments(self, parser):
        parser.add_argument(
            'tenant_schema',
            type=str,
            help='Schema name tenanta (np. "tenant1", "przychodnia_a")'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Liczba pacjentów do utworzenia (domyślnie: 20)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Usuń wszystkich istniejących pacjentów przed dodaniem nowych'
        )

    def handle(self, *args, **options):
        tenant_schema = options['tenant_schema']
        count = options['count']
        
        # Sprawdź czy tenant istnieje
        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Tenant "{tenant_schema}" nie istnieje!')
            )
            # Pokaż dostępne tenantów
            available_tenants = Tenant.objects.all()
            if available_tenants:
                self.stdout.write('Dostępne tenantów:')
                for t in available_tenants:
                    self.stdout.write(f'  - {t.schema_name} ({t.name})')
            return
        
        # Przełącz na schemat tenanta
        connection.set_schema_to_tenant(tenant)
        
        self.stdout.write(
            self.style.SUCCESS(f'🏥 Pracuję z tenant: {tenant.name} (schema: {tenant_schema})')
        )
        
        if options['clear']:
            deleted_count = Patient.objects.count()
            Patient.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'Usunięto {deleted_count} istniejących pacjentów z {tenant.name}.')
            )

        # Przykładowe imiona i nazwiska
        imiona_m = [
            'Adam', 'Andrzej', 'Antoni', 'Bartosz', 'Damian', 'Daniel', 'Dawid',
            'Filip', 'Grzegorz', 'Jakub', 'Jan', 'Kamil', 'Krzysztof', 'Łukasz',
            'Maciej', 'Marcin', 'Marek', 'Mateusz', 'Michał', 'Paweł', 'Piotr',
            'Przemysław', 'Rafał', 'Robert', 'Sebastian', 'Szymon', 'Tomasz', 'Wojciech'
        ]
        
        imiona_k = [
            'Agnieszka', 'Aleksandra', 'Anna', 'Barbara', 'Beata', 'Dorota', 
            'Ewa', 'Gabriela', 'Grażyna', 'Halina', 'Iwona', 'Joanna', 'Justyna',
            'Katarzyna', 'Krystyna', 'Magdalena', 'Małgorzata', 'Maria', 'Monika',
            'Natalia', 'Paulina', 'Renata', 'Sylwia', 'Teresa', 'Urszula', 'Wioletta'
        ]
        
        nazwiska = [
            'Nowak', 'Kowalski', 'Wiśniewski', 'Dąbrowski', 'Lewandowski', 'Wójcik',
            'Kamiński', 'Kowalczyk', 'Zieliński', 'Szymański', 'Woźniak', 'Kozłowski',
            'Jankowski', 'Wojciechowski', 'Kwiatkowski', 'Kaczmarek', 'Mazur', 'Krawczyk',
            'Piotrowski', 'Grabowski', 'Nowakowski', 'Pawłowski', 'Michalski', 'Nowicki',
            'Adamczyk', 'Dudek', 'Zając', 'Wieczorek', 'Jabłoński', 'Król', 'Majewski',
            'Olszewski', 'Jaworski', 'Wróbel', 'Malinowski', 'Pawlak', 'Witkowski'
        ]

        # Przykładowe domeny email
        domeny_email = [
            'gmail.com', 'wp.pl', 'onet.pl', 'o2.pl', 'interia.pl', 
            'gazeta.pl', 'poczta.onet.pl', 'tlen.pl', 'yahoo.com'
        ]

        created_count = 0
        
        with transaction.atomic():
            for i in range(count):
                try:
                    # Losuj płeć
                    plec = random.choice(['M', 'K'])
                    
                    # Losuj imię na podstawie płci
                    if plec == 'M':
                        imie = random.choice(imiona_m)
                    else:
                        imie = random.choice(imiona_k)
                    
                    nazwisko = random.choice(nazwiska)
                    
                    # Generuj prawidłowy PESEL
                    pesel = self.generate_valid_pesel(plec)
                    if not pesel:
                        continue
                    
                    # Sprawdź czy PESEL już istnieje w tym tenant
                    existing_patient = Patient.objects.search_by_pesel(pesel).first()
                    if existing_patient:
                        self.stdout.write(
                            self.style.WARNING(f'PESEL {pesel} już istnieje, pomijam...')
                        )
                        continue
                    
                    # Generuj email (z małą szansą na brak)
                    if random.random() > 0.1:  # 90% ma email
                        email = f"{imie.lower()}.{nazwisko.lower()}@{random.choice(domeny_email)}"
                        # Upewnij się że email jest unikalny
                        counter = 1
                        original_email = email
                        while Patient.objects.filter(email=email).exists():
                            email = f"{original_email.split('@')[0]}{counter}@{original_email.split('@')[1]}"
                            counter += 1
                    else:
                        email = None
                    
                    # Generuj telefon (z małą szansą na brak)
                    if random.random() > 0.15:  # 85% ma telefon
                        # Polskie numery telefonów
                        prefix = random.choice(['500', '501', '502', '503', '504', '505', '506', '507', '508', '509',
                                              '510', '511', '512', '513', '514', '515', '516', '517', '518', '519',
                                              '530', '531', '532', '533', '534', '535', '536', '537', '538', '539',
                                              '570', '571', '572', '573', '574', '575', '576', '577', '578', '579',
                                              '600', '601', '602', '603', '604', '605', '606', '607', '608', '609'])
                        phone = f"+48{prefix}{random.randint(100000, 999999)}"
                    else:
                        phone = None
                    
                    # Utwórz pacjenta
                    patient = Patient.objects.create(
                        first_name_encrypted=imie,
                        last_name_encrypted=nazwisko,
                        pesel_encrypted=pesel,
                        email=email,
                        phone=phone
                    )
                    
                    created_count += 1
                    
                    # Pokaż postęp co 5 pacjentów
                    if created_count % 5 == 0:
                        self.stdout.write(f'✅ Utworzono {created_count}/{count} pacjentów w {tenant.name}...')
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Błąd podczas tworzenia pacjenta {i+1}: {str(e)}')
                    )
                    continue

        self.stdout.write(
            self.style.SUCCESS(f'🎉 Pomyślnie utworzono {created_count} pacjentów w tenant "{tenant.name}"!')
        )
        
        # Pokaż statystyki
        total_patients = Patient.objects.count()
        self.stdout.write(f'📊 Łączna liczba pacjentów w {tenant.name}: {total_patients}')
        
        # Pokaż przykładowe dane
        if created_count > 0:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(f'PRZYKŁADOWI PACJENCI W TENANT "{tenant.name.upper()}":')
            self.stdout.write('='*60)
            
            for patient in Patient.objects.all()[:5]:
                self.stdout.write(
                    f"• {patient.get_decrypted_full_name()} "
                    f"(PESEL: {patient.get_masked_pesel()}, "
                    f"ur. {patient.date_of_birth}, "
                    f"płeć: {patient.gender})"
                )
        
        # Informacja o dostępie
        self.stdout.write('\n' + '='*60)
        self.stdout.write(f'🌐 Aby zobaczyć pacjentów w przeglądarce:')
        self.stdout.write(f'   http://{tenant_schema}.localhost:8000/pacjenci/')
        self.stdout.write('='*60)

        # Przykładowe imiona i nazwiska
        imiona_m = [
            'Adam', 'Andrzej', 'Antoni', 'Bartosz', 'Damian', 'Daniel', 'Dawid',
            'Filip', 'Grzegorz', 'Jakub', 'Jan', 'Kamil', 'Krzysztof', 'Łukasz',
            'Maciej', 'Marcin', 'Marek', 'Mateusz', 'Michał', 'Paweł', 'Piotr',
            'Przemysław', 'Rafał', 'Robert', 'Sebastian', 'Szymon', 'Tomasz', 'Wojciech'
        ]
        
        imiona_k = [
            'Agnieszka', 'Aleksandra', 'Anna', 'Barbara', 'Beata', 'Dorota', 
            'Ewa', 'Gabriela', 'Grażyna', 'Halina', 'Iwona', 'Joanna', 'Justyna',
            'Katarzyna', 'Krystyna', 'Magdalena', 'Małgorzata', 'Maria', 'Monika',
            'Natalia', 'Paulina', 'Renata', 'Sylwia', 'Teresa', 'Urszula', 'Wioletta'
        ]
        
        nazwiska = [
            'Nowak', 'Kowalski', 'Wiśniewski', 'Dąbrowski', 'Lewandowski', 'Wójcik',
            'Kamiński', 'Kowalczyk', 'Zieliński', 'Szymański', 'Woźniak', 'Kozłowski',
            'Jankowski', 'Wojciechowski', 'Kwiatkowski', 'Kaczmarek', 'Mazur', 'Krawczyk',
            'Piotrowski', 'Grabowski', 'Nowakowski', 'Pawłowski', 'Michalski', 'Nowicki',
            'Adamczyk', 'Dudek', 'Zając', 'Wieczorek', 'Jabłoński', 'Król', 'Majewski',
            'Olszewski', 'Jaworski', 'Wróbel', 'Malinowski', 'Pawlak', 'Witkowski'
        ]

        # Przykładowe domeny email
        domeny_email = [
            'gmail.com', 'wp.pl', 'onet.pl', 'o2.pl', 'interia.pl', 
            'gazeta.pl', 'poczta.onet.pl', 'tlen.pl', 'yahoo.com'
        ]

        created_count = 0
        
        with transaction.atomic():
            for i in range(count):
                try:
                    # Losuj płeć
                    plec = random.choice(['M', 'K'])
                    
                    # Losuj imię na podstawie płci
                    if plec == 'M':
                        imie = random.choice(imiona_m)
                    else:
                        imie = random.choice(imiona_k)
                    
                    nazwisko = random.choice(nazwiska)
                    
                    # Generuj prawidłowy PESEL
                    pesel = self.generate_valid_pesel(plec)
                    
                    # Generuj email (z małą szansą na brak)
                    if random.random() > 0.1:  # 90% ma email
                        email = f"{imie.lower()}.{nazwisko.lower()}@{random.choice(domeny_email)}"
                        # Upewnij się że email jest unikalny
                        counter = 1
                        original_email = email
                        while Patient.objects.filter(email=email).exists():
                            email = f"{original_email.split('@')[0]}{counter}@{original_email.split('@')[1]}"
                            counter += 1
                    else:
                        email = None
                    
                    # Generuj telefon (z małą szansą na brak)
                    if random.random() > 0.15:  # 85% ma telefon
                        # Polskie numery telefonów
                        prefix = random.choice(['500', '501', '502', '503', '504', '505', '506', '507', '508', '509',
                                              '510', '511', '512', '513', '514', '515', '516', '517', '518', '519',
                                              '530', '531', '532', '533', '534', '535', '536', '537', '538', '539',
                                              '570', '571', '572', '573', '574', '575', '576', '577', '578', '579',
                                              '600', '601', '602', '603', '604', '605', '606', '607', '608', '609'])
                        phone = f"+48{prefix}{random.randint(100000, 999999)}"
                    else:
                        phone = None
                    
                    # Utwórz pacjenta
                    patient = Patient.objects.create(
                        first_name_encrypted=imie,
                        last_name_encrypted=nazwisko,
                        pesel_encrypted=pesel,
                        email=email,
                        phone=phone
                    )
                    
                    created_count += 1
                    
                    # Pokaż postęp co 5 pacjentów
                    if created_count % 5 == 0:
                        self.stdout.write(f'Utworzono {created_count}/{count} pacjentów...')
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Błąd podczas tworzenia pacjenta {i+1}: {str(e)}')
                    )
                    continue

        self.stdout.write(
            self.style.SUCCESS(f'Pomyślnie utworzono {created_count} pacjentów!')
        )
        
        # Pokaż przykładowe dane
        if created_count > 0:
            self.stdout.write('\n' + '='*50)
            self.stdout.write('PRZYKŁADOWI PACJENCI:')
            self.stdout.write('='*50)
            
            for patient in Patient.objects.all()[:5]:
                self.stdout.write(
                    f"• {patient.get_decrypted_full_name()} "
                    f"(PESEL: {patient.get_masked_pesel()}, "
                    f"ur. {patient.date_of_birth}, "
                    f"płeć: {patient.gender})"
                )

    def generate_valid_pesel(self, plec='M'):
        """
        Generuje prawidłowy numer PESEL z sumą kontrolną
        plec: 'M' dla mężczyzny, 'K' dla kobiety
        
        Struktura PESEL: RRMMDDSSSP(K)
        RR - rok urodzenia
        MM - miesiąc z kodowaniem stulecia  
        DD - dzień
        SSS - numer porządkowy (3 cyfry)
        P - płeć (1 cyfra: parzysta=K, nieparzysta=M)
        K - cyfra kontrolna
        """
        # Losuj datę urodzenia (od 1950 do 2005)
        year = random.randint(1950, 2005)
        month = random.randint(1, 12)
        
        # Dni w miesiącu
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        # Sprawdź rok przestępny
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            days_in_month[1] = 29
            
        day = random.randint(1, days_in_month[month - 1])
        
        # Konwertuj na format PESEL
        year_short = year % 100
        
        # Kodowanie miesiąca według stulecia
        if 1900 <= year <= 1999:
            month_coded = month
        elif 2000 <= year <= 2099:
            month_coded = month + 20
        elif 1800 <= year <= 1899:
            month_coded = month + 80
        elif 2100 <= year <= 2199:
            month_coded = month + 40
        else:
            month_coded = month
        
        # Numer porządkowy (3 cyfry) - losowy
        serial_number = random.randint(0, 999)
        
        # Cyfra płci (1 cyfra)
        if plec == 'M':
            # Mężczyźni - cyfra nieparzysta (1, 3, 5, 7, 9)
            gender_digit = random.choice([1, 3, 5, 7, 9])
        else:
            # Kobiety - cyfra parzysta (0, 2, 4, 6, 8)
            gender_digit = random.choice([0, 2, 4, 6, 8])
        
        # Składaj PESEL (bez cyfry kontrolnej) - 10 cyfr
        pesel_parts = [
            f"{year_short:02d}",        # 2 cyfry
            f"{month_coded:02d}",       # 2 cyfry
            f"{day:02d}",               # 2 cyfry
            f"{serial_number:03d}",     # 3 cyfry
            f"{gender_digit:01d}"       # 1 cyfra
        ]
        
        pesel_without_control = ''.join(pesel_parts)
        
        # Sprawdź czy mamy 10 cyfr
        if len(pesel_without_control) != 10:
            self.stdout.write(
                self.style.ERROR(f'Błąd: PESEL bez kontrolnej ma {len(pesel_without_control)} cyfr: {pesel_without_control}')
            )
            return None
        
        # Oblicz cyfrę kontrolną
        weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
        checksum = 0
        
        for i, digit in enumerate(pesel_without_control):
            checksum += int(digit) * weights[i]
        
        control_digit = (10 - (checksum % 10)) % 10
        
        # Finalny PESEL - 11 cyfr
        pesel = pesel_without_control + str(control_digit)
        
        # Sprawdź czy mamy 11 cyfr
        if len(pesel) != 11:
            self.stdout.write(
                self.style.ERROR(f'Błąd: Finalny PESEL ma {len(pesel)} cyfr: {pesel}')
            )
            return None
        
        return pesel