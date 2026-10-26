from datetime import time

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Subquery
from django.utils import timezone

from core.models import Asistencia, Nino


HORA_CIERRE = time(17, 0)


class Command(BaseCommand):
    help = 'Registra como ausentes a los niños activos sin asistencia al cierre del horario.'

    def handle(self, *args, **options):
        ahora = timezone.localtime()
        if ahora.weekday() >= 5:
            self.stdout.write('No se registran ausencias durante el fin de semana.')
            return
        if ahora.time() < HORA_CIERRE:
            raise CommandError('Este comando solo se puede ejecutar a partir de las 17:00, hora de Lima.')

        ids_con_asistencia = Asistencia.objects.filter(fecha=ahora.date()).values('nino_id')
        ninos_pendientes = Nino.objects.filter(estado_matricula=True).exclude(
            pk__in=Subquery(ids_con_asistencia)
        )
        nuevos_registros = [
            Asistencia(nino_id=nino_id, fecha=ahora.date(), estado='ausente')
            for nino_id in ninos_pendientes.values_list('id', flat=True)
        ]

        existentes_antes = Asistencia.objects.filter(
            fecha=ahora.date(),
            nino__estado_matricula=True,
        ).count()
        Asistencia.objects.bulk_create(nuevos_registros, ignore_conflicts=True)
        existentes_despues = Asistencia.objects.filter(
            fecha=ahora.date(),
            nino__estado_matricula=True,
        ).count()
        registrados = existentes_despues - existentes_antes

        self.stdout.write(
            self.style.SUCCESS(
                f'Se registraron {registrados} ausencias para {ahora.date()}.'
            )
        )
