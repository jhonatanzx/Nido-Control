import os
import tempfile
from datetime import datetime, time, timedelta
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from .models import Apoderado, Asistencia, Aula, Bitacora, Incidencia, MenuDiario, Nino, RegistroEntrega


def imagen_subida(nombre, formato, color):
    contenido = BytesIO()
    Image.new('RGB', (2, 2), color).save(contenido, format=formato)
    return SimpleUploadedFile(nombre, contenido.getvalue(), content_type=f'image/{formato.lower()}')


class NinoEditTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_root.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media_root.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

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

    def test_editar_nino_rechaza_dni_con_letras_o_longitud_incorrecta(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('editar_nino', args=[self.nino.id]),
            {
                'nombres': 'Nombre que no debe guardarse',
                'apellidos': 'García',
                'fecha_nacimiento': '2018-05-10',
                'sexo': 'F',
                'apoderado_1_nombres': 'Carlos García',
                'apoderado_1_parentesco': 'padre',
                'apoderado_1_documento': '1234AB78',
                'apoderado_1_telefono': '987654321',
            },
        )

        self.nino.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'debe contener exactamente 8 dígitos numéricos')
        self.assertEqual(self.nino.nombres, 'Ana')
        self.assertFalse(self.nino.apoderados.exists())

    def test_registrar_nino_rechaza_dni_con_caracteres_no_numericos(self):
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
                'apoderado_1_documento': '1234567-',
                'apoderado_1_telefono': '987654321',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'debe contener exactamente 8 dígitos numéricos')
        self.assertFalse(Nino.objects.filter(nombres='Luis', apellidos='Pérez').exists())

    def test_registrar_nino_rechaza_fecha_nacimiento_futura(self):
        self.client.force_login(self.user)
        formulario = self.client.get(reverse('registrar_nino'))
        self.assertContains(formulario, f'max="{timezone.localdate().isoformat()}"')
        fecha_futura = (timezone.localdate() + timedelta(days=1)).isoformat()

        response = self.client.post(
            reverse('registrar_nino'),
            {
                'nombres': 'Luis',
                'apellidos': 'Pérez',
                'fecha_nacimiento': fecha_futura,
                'sexo': 'M',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La fecha de nacimiento no puede ser posterior a la fecha actual.')
        self.assertFalse(Nino.objects.filter(nombres='Luis', apellidos='Pérez').exists())

    def test_editar_nino_rechaza_fecha_nacimiento_futura(self):
        self.client.force_login(self.user)
        fecha_futura = (timezone.localdate() + timedelta(days=1)).isoformat()

        response = self.client.post(
            reverse('editar_nino', args=[self.nino.id]),
            {
                'nombres': 'Nombre que no debe guardarse',
                'apellidos': 'García',
                'fecha_nacimiento': fecha_futura,
                'sexo': 'F',
            },
        )

        self.nino.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La fecha de nacimiento no puede ser posterior a la fecha actual.')
        self.assertEqual(self.nino.fecha_nacimiento.isoformat(), '2018-05-10')
        self.assertEqual(self.nino.nombres, 'Ana')

    def test_editar_nino_reemplaza_foto_y_elimina_archivo_anterior(self):
        self.nino.foto = imagen_subida('foto_anterior.jpg', 'JPEG', 'red')
        self.nino.save()
        ruta_anterior = self.nino.foto.path
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('editar_nino', args=[self.nino.id]),
            {
                'nombres': 'Ana',
                'apellidos': 'García',
                'fecha_nacimiento': '2018-05-10',
                'sexo': 'F',
                'foto': imagen_subida('foto_nueva.gif', 'GIF', 'blue'),
            },
        )

        self.nino.refresh_from_db()
        self.assertRedirects(response, reverse('detalle_nino', args=[self.nino.id]))
        self.assertEqual(self.nino.foto.name, 'fotos_ninos/foto_nueva.jpg')
        with Image.open(self.nino.foto.path) as foto_guardada:
            self.assertEqual(foto_guardada.format, 'JPEG')
        self.assertFalse(os.path.exists(ruta_anterior))
        self.assertTrue(os.path.exists(self.nino.foto.path))

    def test_editar_nino_conserva_foto_actual_si_no_se_reemplaza(self):
        self.nino.foto = imagen_subida('foto_actual.jpg', 'JPEG', 'green')
        self.nino.save()
        ruta_foto = self.nino.foto.path
        self.client.force_login(self.user)

        response = self.client.get(reverse('editar_nino', args=[self.nino.id]))

        self.nino.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Foto actual')
        self.assertNotContains(response, 'Eliminar foto actual')
        self.assertNotContains(response, 'name="eliminar_foto"')
        self.assertTrue(self.nino.foto)
        self.assertTrue(os.path.exists(ruta_foto))

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

    def test_admin_puede_desactivar_y_reactivar_matricula_desde_lista_de_ninos(self):
        nino = Nino.objects.create(
            nombres='Luis',
            apellidos='Pérez',
            fecha_nacimiento='2020-01-15',
            sexo='M',
        )
        self.client.force_login(self.user)

        lista = self.client.get(reverse('lista_ninos'))
        self.assertContains(lista, 'Desactivar matrícula')

        response = self.client.post(reverse('cambiar_estado_nino', args=[nino.id]))
        nino.refresh_from_db()
        self.assertRedirects(response, reverse('lista_ninos'))
        self.assertFalse(nino.estado_matricula)

        lista = self.client.get(reverse('lista_ninos'))
        self.assertContains(lista, 'Luis Pérez')
        self.assertContains(lista, 'Reactivar matrícula')

        response = self.client.post(reverse('cambiar_estado_nino', args=[nino.id]))
        nino.refresh_from_db()
        self.assertRedirects(response, reverse('lista_ninos'))
        self.assertTrue(nino.estado_matricula)

    def test_lista_ninos_oculta_inactivos_a_cuidadoras_y_no_permite_cambiar_estado(self):
        nino = Nino.objects.create(
            nombres='Luis',
            apellidos='Pérez',
            fecha_nacimiento='2020-01-15',
            sexo='M',
            estado_matricula=False,
        )
        cuidadora = get_user_model().objects.create_user(
            username='cuidadora',
            password='123456',
            rol='cuidadora',
            is_staff=False,
            is_superuser=False,
        )
        self.client.force_login(cuidadora)

        lista = self.client.get(reverse('lista_ninos'))
        self.assertNotContains(lista, 'Luis Pérez')

        response = self.client.post(reverse('cambiar_estado_nino', args=[nino.id]))
        nino.refresh_from_db()
        self.assertRedirects(response, reverse('dashboard'))
        self.assertFalse(nino.estado_matricula)

    def test_estado_usuario_se_cambia_solo_por_post_y_permite_reactivar(self):
        usuario = get_user_model().objects.create_user(
            username='cuidadora_inactiva',
            password='123456',
            rol='cuidadora',
            is_active=False,
            estado=False,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('cambiar_estado_usuario', args=[usuario.id]))
        usuario.refresh_from_db()
        self.assertRedirects(response, reverse('lista_usuarios'))
        self.assertFalse(usuario.estado)

        lista = self.client.get(reverse('lista_usuarios'))
        self.assertContains(lista, 'Reactivar')

        response = self.client.post(reverse('cambiar_estado_usuario', args=[usuario.id]))
        usuario.refresh_from_db()
        self.assertRedirects(response, reverse('lista_usuarios'))
        self.assertTrue(usuario.estado)
        self.assertTrue(usuario.is_active)

    def test_admin_puede_guardar_consultar_editar_y_eliminar_menu(self):
        self.client.force_login(self.user)
        fecha_menu = timezone.localdate().isoformat()

        response = self.client.post(
            reverse('crear_menu_diario'),
            {
                'fecha': fecha_menu,
                'tipo_comida': 'almuerzo',
                'descripcion': 'Arroz con pollo y ensalada',
            },
        )
        self.assertRedirects(response, f"{reverse('menu_diario')}?fecha={fecha_menu}")
        menu = MenuDiario.objects.get(fecha=fecha_menu, tipo_comida='almuerzo')
        self.assertEqual(menu.usuario_registro, self.user)

        consulta = self.client.get(reverse('menu_diario'), {'fecha': fecha_menu})
        self.assertContains(consulta, 'Arroz con pollo y ensalada')
        self.assertContains(consulta, 'Almuerzo')
        self.assertContains(consulta, 'Editar')

        response = self.client.post(
            reverse('editar_menu_diario', args=[menu.id]),
            {
                'fecha': fecha_menu,
                'tipo_comida': 'almuerzo',
                'descripcion': 'Arroz con pollo, ensalada y fruta',
            },
        )
        self.assertRedirects(response, f"{reverse('menu_diario')}?fecha={fecha_menu}")
        menu.refresh_from_db()
        self.assertEqual(menu.descripcion, 'Arroz con pollo, ensalada y fruta')

        response = self.client.post(reverse('eliminar_menu_diario', args=[menu.id]))
        self.assertRedirects(response, f"{reverse('menu_diario')}?fecha={fecha_menu}")
        self.assertFalse(MenuDiario.objects.filter(id=menu.id).exists())

    def test_cuidadora_puede_consultar_menu_pero_no_modificarlo(self):
        fecha_menu = timezone.localdate()
        MenuDiario.objects.create(
            fecha=fecha_menu,
            tipo_comida='desayuno',
            descripcion='Avena y fruta',
        )
        cuidadora = get_user_model().objects.create_user(
            username='cuidadora_menu',
            password='123456',
            rol='cuidadora',
            is_staff=False,
            is_superuser=False,
        )
        self.client.force_login(cuidadora)

        consulta = self.client.get(reverse('menu_diario'), {'fecha': fecha_menu.isoformat()})
        self.assertEqual(consulta.status_code, 200)
        self.assertContains(consulta, 'Avena y fruta')
        self.assertNotContains(consulta, 'Agregar menú')

        response = self.client.post(
            reverse('crear_menu_diario'),
            {
                'fecha': fecha_menu.isoformat(),
                'tipo_comida': 'merienda',
                'descripcion': 'Yogur',
            },
        )
        self.assertRedirects(response, reverse('dashboard'))
        self.assertFalse(MenuDiario.objects.filter(tipo_comida='merienda').exists())

    def test_menu_rechaza_tipo_invalido_y_duplicado(self):
        self.client.force_login(self.user)
        fecha_menu = timezone.localdate().isoformat()

        response = self.client.post(
            reverse('crear_menu_diario'),
            {'fecha': fecha_menu, 'tipo_comida': 'cena', 'descripcion': 'Cena'},
        )
        self.assertRedirects(response, f"{reverse('menu_diario')}?fecha={fecha_menu}")
        self.assertFalse(MenuDiario.objects.exists())

        MenuDiario.objects.create(
            fecha=fecha_menu,
            tipo_comida='desayuno',
            descripcion='Pan y leche',
        )
        response = self.client.post(
            reverse('crear_menu_diario'),
            {
                'fecha': fecha_menu,
                'tipo_comida': 'desayuno',
                'descripcion': 'Otro desayuno',
            },
        )
        self.assertRedirects(response, f"{reverse('menu_diario')}?fecha={fecha_menu}")
        self.assertEqual(MenuDiario.objects.filter(fecha=fecha_menu).count(), 1)

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

    def test_crear_usuario_rechaza_telefono_con_letras_o_mas_de_nueve_digitos(self):
        self.client.force_login(self.user)

        for username, telefono in [('usuario_letras', '12345abc'), ('usuario_largo', '1234567890')]:
            with self.subTest(telefono=telefono):
                self.client.post(
                    reverse('crear_usuario'),
                    {
                        'username': username,
                        'email': f'{username}@example.com',
                        'password': '12345678',
                        'rol': 'cuidadora',
                        'telefono': telefono,
                    },
                )
                self.assertFalse(get_user_model().objects.filter(username=username).exists())

    def test_editar_usuario_rechaza_telefono_con_letras_o_mas_de_nueve_digitos(self):
        self.client.force_login(self.user)

        for telefono in ['12345abc', '1234567890']:
            with self.subTest(telefono=telefono):
                response = self.client.post(
                    reverse('editar_usuario', args=[self.user.id]),
                    {
                        'username': self.user.username,
                        'email': self.user.email,
                        'rol': self.user.rol,
                        'telefono': telefono,
                    },
                )
                self.assertRedirects(response, reverse('editar_usuario', args=[self.user.id]))

        self.user.refresh_from_db()
        self.assertEqual(self.user.telefono, '')

    def test_formulario_gestion_usuarios_limita_telefono_a_nueve_digitos(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('lista_usuarios'))

        self.assertContains(response, 'maxlength="9"')
        self.assertContains(response, 'pattern="[0-9]{0,9}"')

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

    def test_dashboard_muestra_asistencia_e_incidencias_agrupadas_por_salon(self):
        hoy = timezone.localdate()
        nino_ausente = Nino.objects.create(
            nombres='Luis',
            apellidos='Pérez',
            fecha_nacimiento='2020-01-15',
            sexo='M',
            aula=self.aula,
        )
        Asistencia.objects.create(nino=self.nino, fecha=hoy, estado='tardanza')
        Asistencia.objects.create(
            nino=nino_ausente,
            fecha=hoy,
            estado='ausente',
            motivo_ausencia='Resfrío',
        )
        incidencia = Incidencia.objects.create(
            nino=nino_ausente,
            tipo='enfermedad',
            fecha=hoy,
            descripcion='Presentó tos durante la mañana.',
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['presentes'], 1)
        grupo = next(
            salon for salon in response.context['grupos_salones']
            if salon['id'] == f'aula-{self.aula.id}'
        )
        self.assertEqual(grupo['ninos'], [self.nino, nino_ausente])
        self.assertEqual([detalle['nino'] for detalle in grupo['presentes']], [self.nino])
        self.assertEqual([detalle['nino'] for detalle in grupo['ausentes']], [nino_ausente])
        self.assertEqual(grupo['incidencias'], [incidencia])
        self.assertContains(response, 'dashboard-stat-group-title')
        self.assertContains(response, 'data-bs-target="#dashboard-details-matriculados"')
        self.assertContains(response, 'data-bs-target="#dashboard-details-presentes"')
        self.assertContains(response, 'data-bs-target="#dashboard-details-ausentes"')
        self.assertContains(response, 'data-bs-target="#dashboard-details-incidencias"')
        self.assertContains(response, 'id="dashboard-details-matriculados"')
        self.assertContains(response, 'id="dashboard-details-presentes"')
        self.assertContains(response, 'id="dashboard-details-ausentes"')
        self.assertContains(response, 'id="dashboard-details-incidencias"')
        self.assertNotContains(response, 'id="dashboard-details"')
        self.assertContains(response, 'Presentes hoy')
        self.assertContains(response, 'Ausentes hoy')
        self.assertContains(response, 'Incidencias hoy')
        self.assertContains(response, 'dashboard-stat-list')
        self.assertContains(response, 'Luis Pérez')
        self.assertNotContains(response, 'dashboard-stat-item')
        self.assertNotContains(response, 'Presentó tos durante la mañana.')

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

    def test_reporte_estudiantes_generates_weekly_detail_pdf(self):
        self.client.force_login(self.user)
        hoy = timezone.localdate()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        semana = hoy.strftime('%G-W%V')
        Asistencia.objects.create(
            nino=self.nino,
            fecha=inicio_semana,
            estado='presente',
            hora_ingreso=time(8, 0),
            usuario_registro=self.user,
        )
        Bitacora.objects.create(
            nino=self.nino,
            fecha=inicio_semana,
            alimentacion='Desayunó bien',
            descanso='Descansó',
            actividades='Pintura',
            higiene='Correcta',
            estado_animo='alegre',
        )
        Incidencia.objects.create(
            nino=self.nino,
            tipo='enfermedad',
            fecha=inicio_semana,
            descripcion='Se sintió indispuesto',
        )

        response = self.client.get(
            reverse('reporte_estudiantes'),
            {'nino': self.nino.id, 'semana': semana},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn(f'reporte_estudiante_{self.nino.id}_{inicio_semana}_', response['Content-Disposition'])

    def test_reporte_estudiantes_rechaza_semana_invalida(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('reporte_estudiantes'), {'semana': '2026-W99'})

        self.assertRedirects(response, reverse('generar_reportes'))

    def test_reporte_estudiantes_requiere_seleccionar_un_nino(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('reporte_estudiantes'),
            {'semana': timezone.localdate().strftime('%G-W%V')},
        )

        self.assertRedirects(response, reverse('generar_reportes'))

    def test_formulario_reporte_estudiantes_exige_un_nino_especifico(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('generar_reportes'))

        self.assertContains(response, 'name="nino"')
        self.assertContains(response, 'required')
        self.assertContains(response, 'Selecciona un estudiante')
        self.assertNotContains(response, 'Todos los estudiantes')

    def test_estadisticas_filtra_los_tres_graficos_por_rango_de_fechas(self):
        self.client.force_login(self.user)
        hoy = timezone.localdate()
        fecha_dentro = hoy - timedelta(days=5)
        fecha_fuera = hoy - timedelta(days=15)
        Asistencia.objects.create(nino=self.nino, fecha=fecha_dentro, estado='presente')
        Asistencia.objects.create(nino=self.nino, fecha=fecha_fuera, estado='ausente')
        Incidencia.objects.create(
            nino=self.nino,
            tipo='accidente',
            fecha=fecha_dentro,
            descripcion='Dentro del rango',
        )
        Incidencia.objects.create(
            nino=self.nino,
            tipo='enfermedad',
            fecha=fecha_fuera,
            descripcion='Fuera del rango',
        )
        Bitacora.objects.create(nino=self.nino, fecha=fecha_dentro, estado_animo='alegre')
        Bitacora.objects.create(nino=self.nino, fecha=fecha_fuera, estado_animo='cansado')

        response = self.client.get(
            reverse('estadisticas'),
            {'desde': fecha_dentro.isoformat(), 'hasta': hoy.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_asistencias'], 1)
        self.assertEqual(response.context['total_presentes'], 1)
        self.assertEqual(response.context['total_ausentes'], 0)
        self.assertEqual(response.context['total_incidencias'], 1)
        self.assertEqual(response.context['incidencias_por_tipo']['accidente'], 1)
        self.assertEqual(response.context['incidencias_por_tipo']['enfermedad'], 0)
        self.assertEqual(response.context['estados_animo']['alegre'], 1)
        self.assertEqual(response.context['estados_animo']['cansado'], 0)
        self.assertTrue(response.context['rango_personalizado'])
        self.assertContains(response, f'value="{fecha_dentro.isoformat()}"')
        self.assertContains(response, f'value="{hoy.isoformat()}"')

    def test_estadisticas_muestra_error_para_rango_invalido(self):
        self.client.force_login(self.user)
        hoy = timezone.localdate()
        desde = hoy.isoformat()
        hasta = (hoy - timedelta(days=1)).isoformat()

        response = self.client.get(reverse('estadisticas'), {'desde': desde, 'hasta': hasta})

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Selecciona un rango válido: indica ambas fechas y asegúrate de que &quot;Desde&quot; no sea posterior a &quot;Hasta&quot;.',
        )
        self.assertFalse(response.context['rango_personalizado'])

    def test_pagina_reportes_muestra_estado_de_descarga_sin_abrir_pestanas(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('generar_reportes'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="reporte-descarga-estado"')
        self.assertContains(response, 'data-pdf-download')
        self.assertNotContains(response, 'target="_blank"')
        self.assertContains(response, 'la descarga comenzó')

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

    def test_asistencia_registra_fecha_y_horas_automaticamente(self):
        asistencia = self.nino.asistencia_set.create(fecha='2026-09-10', estado='tardanza')
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('registrar_salida', args=[asistencia.id]),
            {'hora_salida': '12:15'},
        )
        asistencia.refresh_from_db()
        self.assertRedirects(response, reverse('asistencia_hoy'))
        self.assertIsNone(asistencia.hora_salida)

        hora_ingreso_servidor = timezone.make_aware(
            datetime(2026, 9, 10, 9, 30, 15),
            timezone.get_current_timezone(),
        )

        with patch('core.views.timezone.localtime', return_value=hora_ingreso_servidor):
            response = self.client.post(
                reverse('registrar_asistencia', args=[asistencia.id]),
                {
                    'estado': 'tardanza',
                    'hora_ingreso': '00:00',
                    'motivo_ausencia': '',
                },
            )

        asistencia.refresh_from_db()
        self.assertRedirects(response, reverse('asistencia_hoy'))
        self.assertEqual(str(asistencia.fecha), '2026-09-10')
        self.assertEqual(str(asistencia.hora_ingreso), '09:30:15')
        self.assertEqual(asistencia.fecha_hora_ingreso, hora_ingreso_servidor)
        self.assertEqual(asistencia.estado, 'tardanza')

        hora_salida_servidor = timezone.make_aware(
            datetime(2026, 9, 11, 0, 15, 45),
            timezone.get_current_timezone(),
        )
        with patch('core.views.timezone.localtime', return_value=hora_salida_servidor):
            response = self.client.post(
                reverse('registrar_salida', args=[asistencia.id]),
                {'hora_salida': '23:59'},
            )

        asistencia.refresh_from_db()
        self.assertRedirects(response, reverse('asistencia_hoy'))
        self.assertEqual(str(asistencia.hora_salida), '00:15:45')
        self.assertEqual(asistencia.fecha_hora_salida, hora_salida_servidor)

        with patch('core.views.timezone.localtime', return_value=hora_ingreso_servidor):
            self.client.post(
                reverse('registrar_asistencia', args=[asistencia.id]),
                {'estado': 'tardanza', 'hora_ingreso': '15:00'},
            )
        with patch('core.views.timezone.localtime', return_value=hora_salida_servidor):
            self.client.post(
                reverse('registrar_salida', args=[asistencia.id]),
                {'hora_salida': '16:00'},
            )

        asistencia.refresh_from_db()
        self.assertEqual(str(asistencia.hora_ingreso), '09:30:15')
        self.assertEqual(str(asistencia.hora_salida), '00:15:45')
        self.assertEqual(asistencia.fecha_hora_ingreso, hora_ingreso_servidor)
        self.assertEqual(asistencia.fecha_hora_salida, hora_salida_servidor)

    def test_formulario_asistencia_no_permite_ingresar_horas_manualmente(self):
        self.client.force_login(self.user)
        Asistencia.objects.create(
            nino=self.nino,
            fecha=timezone.localdate(),
            estado='presente',
            hora_ingreso=time(9, 30, 15),
            hora_salida=time(15, 45, 30),
        )

        response = self.client.get(reverse('asistencia_hoy'))

        self.assertContains(response, 'La fecha y hora de ingreso se registran automáticamente')
        self.assertContains(response, '09:30:15')
        self.assertContains(response, '15:45:30')
        self.assertContains(response, timezone.localdate().strftime('%d/%m/%Y'))
        self.assertNotContains(response, 'name="hora_ingreso"')
        self.assertNotContains(response, 'name="hora_salida"')
        self.assertNotContains(response, 'type="time"')

    def test_lista_asistencia_muestra_comentario_de_tardanza(self):
        self.client.force_login(self.user)
        Asistencia.objects.create(
            nino=self.nino,
            fecha=timezone.localdate(),
            estado='tardanza',
            motivo_ausencia='Llegó tarde por tráfico',
        )

        response = self.client.get(reverse('asistencia_hoy'))

        self.assertContains(response, 'Comentario de tardanza')
        self.assertContains(response, 'Llegó tarde por tráfico')

    def test_lista_asistencia_indica_cuando_tardanza_no_tiene_comentario(self):
        self.client.force_login(self.user)
        Asistencia.objects.create(
            nino=self.nino,
            fecha=timezone.localdate(),
            estado='tardanza',
        )

        response = self.client.get(reverse('asistencia_hoy'))

        self.assertContains(response, 'Sin comentario')

    def test_bitacora_desayuno_muestra_y_guarda_menu_del_dia_seleccionado(self):
        hoy = timezone.localdate()
        menu = MenuDiario.objects.create(
            fecha=hoy,
            tipo_comida='desayuno',
            descripcion='Avena con fruta y leche',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('bitacora_hoy'))

        self.assertContains(response, 'Desayuno')
        self.assertContains(response, f'value="{menu.id}"')
        self.assertContains(response, 'Avena con fruta y leche')

        bitacora = self.nino.bitacora_set.get(fecha=hoy)
        response = self.client.post(
            reverse('registrar_bitacora', args=[bitacora.id]),
            {
                'menu_desayuno': str(menu.id),
                'descanso': [
                    'Durmió durante toda la siesta',
                    'Se despertó antes de terminar la siesta',
                ],
                'actividades': 'Pintura',
                'higiene': 'Manos limpias',
                'estado_animo': 'alegre',
                'observaciones': '',
            },
        )

        bitacora.refresh_from_db()
        self.assertRedirects(response, reverse('bitacora_hoy'))
        self.assertEqual(bitacora.alimentacion, menu.descripcion)
        self.assertEqual(
            bitacora.descanso,
            'Durmió durante toda la siesta\nSe despertó antes de terminar la siesta',
        )

    def test_bitacora_descanso_muestra_cuatro_opciones_y_permite_seleccionar_varias(self):
        hoy = timezone.localdate()
        bitacora = Bitacora.objects.create(
            nino=self.nino,
            fecha=hoy,
            descanso='No durmió',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('bitacora_hoy'))

        self.assertContains(response, 'Selecciona una o varias opciones:')
        for opcion in [
            'Durmió durante toda la siesta',
            'Durmió parte de la siesta',
            'No durmió',
            'Se despertó antes de terminar la siesta',
        ]:
            self.assertContains(response, opcion)
        self.assertContains(response, 'value="No durmió" checked')

        response = self.client.post(
            reverse('registrar_bitacora', args=[bitacora.id]),
            {
                'descanso': ['Durmió parte de la siesta', 'No durmió'],
                'actividades': '',
                'higiene': '',
                'estado_animo': '',
                'observaciones': '',
            },
        )

        bitacora.refresh_from_db()
        self.assertRedirects(response, reverse('bitacora_hoy'))
        self.assertEqual(bitacora.descanso, 'Durmió parte de la siesta\nNo durmió')

    def test_bitacora_descanso_rechaza_opcion_no_disponible(self):
        self.client.force_login(self.user)
        bitacora = Bitacora.objects.create(nino=self.nino, fecha=timezone.localdate())

        response = self.client.post(
            reverse('registrar_bitacora', args=[bitacora.id]),
            {'descanso': 'Opción inventada'},
        )

        bitacora.refresh_from_db()
        self.assertRedirects(response, reverse('bitacora_hoy'))
        self.assertEqual(bitacora.descanso, '')

    def test_bitacora_rechaza_menu_de_otra_fecha_o_tipo(self):
        hoy = timezone.localdate()
        menu_almuerzo = MenuDiario.objects.create(
            fecha=hoy,
            tipo_comida='almuerzo',
            descripcion='Sopa y arroz',
        )
        self.client.force_login(self.user)
        bitacora = self.nino.bitacora_set.create(fecha=hoy, alimentacion='Desayuno previo')

        response = self.client.post(
            reverse('registrar_bitacora', args=[bitacora.id]),
            {
                'menu_desayuno': str(menu_almuerzo.id),
                'descanso': 'No debe actualizar',
            },
        )

        bitacora.refresh_from_db()
        self.assertRedirects(response, reverse('bitacora_hoy'))
        self.assertEqual(bitacora.alimentacion, 'Desayuno previo')
        self.assertEqual(bitacora.descanso, '')

    def test_bitacora_filtra_por_periodo_nino_aula_y_estado_de_animo(self):
        hoy = timezone.localdate()
        ayer = hoy - timedelta(days=1)
        otra_aula = Aula.objects.create(nombre='Aula 2', capacidad=10)
        otro_nino = Nino.objects.create(
            nombres='Luis',
            apellidos='Pérez',
            fecha_nacimiento='2020-01-15',
            sexo='M',
            aula=otra_aula,
        )
        Bitacora.objects.create(
            nino=self.nino,
            fecha=ayer,
            estado_animo='alegre',
            observaciones='Registro que coincide',
        )
        Bitacora.objects.create(
            nino=self.nino,
            fecha=hoy,
            estado_animo='cansado',
            observaciones='Otro ánimo',
        )
        Bitacora.objects.create(
            nino=otro_nino,
            fecha=ayer,
            estado_animo='alegre',
            observaciones='Otro niño y aula',
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('bitacora_hoy'),
            {
                'fecha_desde': ayer.isoformat(),
                'fecha_hasta': hoy.isoformat(),
                'nino': self.nino.id,
                'aula': self.aula.id,
                'estado_animo': 'alegre',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registro que coincide')
        self.assertNotContains(response, 'Otro ánimo')
        self.assertNotContains(response, 'Otro niño y aula')
        self.assertEqual(response.context['bitacoras'].count(), 1)

    def test_bitacora_periodo_invalido_muestra_error_y_vuelve_a_hoy(self):
        hoy = timezone.localdate()
        manana = hoy + timedelta(days=1)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('bitacora_hoy'),
            {'fecha_desde': manana.isoformat(), 'fecha_hasta': hoy.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La fecha inicial no puede ser posterior a la fecha final.')
        self.assertEqual(response.context['filtros']['fecha_desde'], hoy.isoformat())
        self.assertEqual(response.context['filtros']['fecha_hasta'], hoy.isoformat())

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
