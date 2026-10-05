from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Apoderado, Asistencia, Aula, Nino, RegistroEntrega


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

    def test_registro_admin_desde_login_crea_usuario_admin(self):
        response = self.client.post(
            reverse('registro_admin'),
            {
                'username': 'admin_nuevo',
                'email': 'nuevo@admin.com',
                'password': '12345678',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(get_user_model().objects.filter(username='admin_nuevo', rol='admin').exists())
        self.assertTrue(get_user_model().objects.get(username='admin_nuevo').is_superuser)

    def test_login_muestra_solo_boton_para_registrar_admin(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registrar administrador')
        self.assertNotContains(response, 'Crea tu usuario')

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

    def test_editar_nino_puede_guardar_apoderados(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('editar_nino', args=[self.nino.id]),
            {
                'nombres': 'Ana',
                'apellidos': 'García',
                'fecha_nacimiento': '2018-05-10',
                'sexo': 'F',
                'apoderado_1_nombres': 'Carlos García',
                'apoderado_1_parentesco': 'padre',
                'apoderado_1_documento': '12345678',
                'apoderado_1_telefono': '987654321',
                'apoderado_1_correo': 'carlos@example.com',
                'apoderado_1_direccion': 'Calle 1',
                'apoderado_2_nombres': 'María García',
                'apoderado_2_parentesco': 'otro',
                'apoderado_2_documento': '87654321',
                'apoderado_2_telefono': '912345678',
                'apoderado_2_correo': 'maria@example.com',
                'apoderado_2_direccion': 'Calle 2',
            },
        )

        self.assertRedirects(response, reverse('detalle_nino', args=[self.nino.id]))
        self.assertEqual(self.nino.apoderados.count(), 2)
        self.assertTrue(self.nino.apoderados.filter(documento='12345678').exists())
        self.assertTrue(self.nino.apoderados.filter(documento='87654321').exists())

    def test_registrar_nino_puede_guardar_dos_apoderados(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('registrar_nino'),
            {
                'nombres': 'Luis',
                'apellidos': 'Pérez',
                'fecha_nacimiento': '2020-01-15',
                'sexo': 'M',
                'apoderado_1_nombres': 'Carlos Pérez',
                'apoderado_1_parentesco': 'padre',
                'apoderado_1_documento': '11111111',
                'apoderado_1_telefono': '987654321',
                'apoderado_1_correo': 'carlos@example.com',
                'apoderado_1_direccion': 'Calle 1',
                'apoderado_2_nombres': 'María Pérez',
                'apoderado_2_parentesco': 'otro',
                'apoderado_2_documento': '22222222',
                'apoderado_2_telefono': '912345678',
                'apoderado_2_correo': 'maria@example.com',
                'apoderado_2_direccion': 'Calle 2',
            },
        )

        nino = Nino.objects.get(nombres='Luis', apellidos='Pérez')
        self.assertRedirects(response, reverse('lista_ninos'))
        self.assertEqual(nino.apoderados.count(), 2)
        self.assertTrue(nino.apoderados.filter(documento='11111111').exists())
        self.assertTrue(nino.apoderados.filter(documento='22222222').exists())

    def test_cuidadora_puede_usar_asistencia_pero_no_registrar_ninos(self):
        cuidadora = get_user_model().objects.create_user(
            username='cuidadora',
            password='123456',
            rol='cuidadora',
            is_staff=False,
            is_superuser=False,
        )
        self.client.force_login(cuidadora)

        asistencia_response = self.client.get(reverse('asistencia_hoy'))
        self.assertEqual(asistencia_response.status_code, 200)

        registro_response = self.client.get(reverse('registrar_nino'))
        self.assertEqual(registro_response.status_code, 302)
        self.assertRedirects(registro_response, reverse('dashboard'))

    def test_crear_usuario_requiere_contraseña_de_minimo_8_caracteres(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('crear_usuario'),
            {
                'username': 'nuevo_usuario',
                'email': 'nuevo@example.com',
                'password': '12345',
                'rol': 'cuidadora',
                'telefono': '987654321',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(username='nuevo_usuario').exists())

    def test_gestion_usuarios_muestra_botones_de_editar_y_eliminar_solo_para_admin(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('lista_usuarios'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Editar')
        self.assertContains(response, 'Eliminar')

    def test_dashboard_muestra_aulas_predeterminadas_y_horario(self):
        from .views import ensure_default_aulas
        ensure_default_aulas()
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Aula.objects.filter(nombre='Pollitos').exists())
        self.assertTrue(Aula.objects.filter(nombre='Jirafitas').exists())
        self.assertTrue(Aula.objects.filter(nombre='Abejitas').exists())
        self.assertContains(response, 'Lunes a viernes')
        self.assertContains(response, '8:00 a. m.')
        self.assertContains(response, '1:00 p. m.')

    def test_aulas_predeterminadas_tienen_rango_de_edad(self):
        from .views import ensure_default_aulas

        ensure_default_aulas()

        self.assertEqual(Aula.objects.get(nombre='Pollitos').descripcion, '1 año')
        self.assertEqual(Aula.objects.get(nombre='Jirafitas').descripcion, '2 a 3 años')
        self.assertEqual(Aula.objects.get(nombre='Abejitas').descripcion, '2 a 3 años')

    def test_registro_nino_muestra_rango_de_edad_en_el_select(self):
        from .views import ensure_default_aulas

        ensure_default_aulas()
        self.client.force_login(self.user)
        response = self.client.get(reverse('registrar_nino'))

        self.assertContains(response, 'Pollitos - 1 año')
        self.assertContains(response, 'Jirafitas - 2 a 3 años')
        self.assertContains(response, 'Abejitas - 2 a 3 años')

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

    def test_entrega_exitosa_cuando_dni_coincide(self):
        apoderado = Apoderado.objects.create(
            nino=self.nino,
            nombres='Carlos García',
            parentesco='padre',
            documento='12345678',
            telefono='999999999',
        )
        Asistencia.objects.create(nino=self.nino, fecha=timezone.now().date(), estado='presente')
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('registrar_entrega', args=[self.nino.id]),
            {'documento': apoderado.documento},
        )

        self.assertRedirects(response, reverse('dashboard'))
        entrega = RegistroEntrega.objects.get(nino=self.nino)
        self.assertEqual(entrega.apoderado, apoderado)
        self.assertEqual(entrega.documento_verificado, '12345678')

    def test_entrega_rechazada_cuando_dni_no_coincide(self):
        Apoderado.objects.create(
            nino=self.nino,
            nombres='Carlos García',
            parentesco='padre',
            documento='12345678',
            telefono='999999999',
        )
        Asistencia.objects.create(nino=self.nino, fecha=timezone.now().date(), estado='presente')
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('registrar_entrega', args=[self.nino.id]),
            {'documento': '00000000'},
            follow=True,
        )

        self.assertFalse(RegistroEntrega.objects.filter(nino=self.nino).exists())
        self.assertContains(response, 'DNI no coincide')

    def test_no_permite_dos_entregas_el_mismo_dia(self):
        Asistencia.objects.create(nino=self.nino, fecha=timezone.now().date(), estado='presente')
        RegistroEntrega.objects.create(
            nino=self.nino,
            nombre_persona='Carlos García',
            documento_verificado='12345678',
            usuario_verifica=self.user,
        )
        self.client.force_login(self.user)

        self.client.post(
            reverse('registrar_entrega', args=[self.nino.id]),
            {'documento': '12345678'},
        )

        self.assertEqual(RegistroEntrega.objects.filter(nino=self.nino).count(), 1)
