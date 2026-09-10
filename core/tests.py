from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import Aula, Nino


class NinoEditTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin',
            password='123456',
            is_staff=True,
            is_superuser=True,
        )
        self.aula = Aula.objects.create(nombre='Aula 1', capacidad=12, descripcion='Primera aula')
        self.nino = Nino.objects.create(
            nombres='Ana',
            apellidos='García',
            fecha_nacimiento='2018-05-10',
            sexo='F',
            aula=self.aula,
            alergias='Ninguna',
            restricciones='Sin restricciones',
            informacion_medica='Sin observaciones',
        )

    def test_get_editar_nino_renders_form(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('editar_nino', args=[self.nino.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Editar Niño')
        self.assertContains(response, 'Ana')
        self.assertContains(response, 'García')

    def test_post_editar_nino_updates_data(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('editar_nino', args=[self.nino.id]),
            {
                'nombres': 'Ana María',
                'apellidos': 'Pérez García',
                'fecha_nacimiento': '2018-05-10',
                'sexo': 'F',
                'aula': str(self.aula.id),
                'alergias': 'Polen',
                'restricciones': 'No tomar leche',
                'informacion_medica': 'Revisar cada 6 meses',
            },
        )

        self.nino.refresh_from_db()
        self.assertRedirects(response, reverse('detalle_nino', args=[self.nino.id]))
        self.assertEqual(self.nino.nombres, 'Ana María')
        self.assertEqual(self.nino.apellidos, 'Pérez García')
        self.assertEqual(self.nino.alergias, 'Polen')
        self.assertEqual(self.nino.restricciones, 'No tomar leche')
        self.assertEqual(self.nino.informacion_medica, 'Revisar cada 6 meses')

    def test_reporte_asistencia_generates_pdf(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reporte_asistencia'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="asistencia_', response['Content-Disposition'])

    def test_reporte_incidencias_generates_pdf(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reporte_incidencias'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="incidencias.pdf"', response['Content-Disposition'])

    def test_reporte_bitacora_generates_pdf(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reporte_bitacora'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="bitacora_', response['Content-Disposition'])

    def test_finalizar_incidencia_updates_state(self):
        incidencia = self.nino.__class__
        self.client.force_login(self.user)
        self.client.post('/incidencias/registrar/', {
            'nino': self.nino.id,
            'tipo': 'comportamiento',
            'descripcion': 'Se peleó con un compañero',
            'accion_realizada': 'Se habló con él',
            'comunicacion_apoderado': 'on',
            'estado': 'pendiente',
        })
        inc = self.nino.incidencia_set.first()
        response = self.client.post(reverse('finalizar_incidencia', args=[inc.id]))

        inc.refresh_from_db()
        self.assertRedirects(response, reverse('lista_incidencias'))
        self.assertEqual(inc.estado, 'cerrado')

    def test_tardanza_guardada_con_hora_y_salida(self):
        asistencia = self.nino.asistencia_set.create(fecha='2026-09-10', estado='tardanza')
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('registrar_asistencia', args=[asistencia.id]),
            {
                'estado': 'tardanza',
                'hora_ingreso': '09:30',
                'motivo_ausencia': '',
            },
        )

        asistencia.refresh_from_db()
        self.assertRedirects(response, reverse('asistencia_hoy'))
        self.assertEqual(str(asistencia.hora_ingreso), '09:30:00')
        self.assertEqual(asistencia.estado, 'tardanza')

        response = self.client.post(
            reverse('registrar_salida', args=[asistencia.id]),
            {'hora_salida': '12:15'},
        )

        asistencia.refresh_from_db()
        self.assertRedirects(response, reverse('asistencia_hoy'))
        self.assertEqual(str(asistencia.hora_salida), '12:15:00')
