from io import BytesIO
from functools import wraps
import re
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone
from datetime import date, datetime, timedelta
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from .models import *
from .forms import *

OPCIONES_DESCANSO = [
    'Durmió durante toda la siesta',
    'Durmió parte de la siesta',
    'No durmió',
    'Se despertó antes de terminar la siesta',
]


def ensure_default_aulas():
    aulas_default = {
        'Pollitos': '1 año',
        'Jirafitas': '2 a 3 años',
        'Abejitas': '2 a 3 años',
    }
    for nombre, descripcion in aulas_default.items():
        aula, created = Aula.objects.get_or_create(
            nombre=nombre,
            defaults={'capacidad': 12, 'descripcion': descripcion}
        )
        if not created and aula.descripcion != descripcion:
            aula.descripcion = descripcion
            aula.save()


def apoderado_con_dni_invalido(datos):
    for index in [1, 2]:
        campos = {
            campo: datos.get(f'apoderado_{index}_{campo}', '').strip()
            for campo in ['nombres', 'parentesco', 'documento', 'telefono', 'correo', 'direccion']
        }

        if index == 1 and not any(campos.values()):
            campos = {
                campo: datos.get(f'apoderado_{campo}', '').strip()
                for campo in ['nombres', 'parentesco', 'documento', 'telefono', 'correo', 'direccion']
            }

        if any(campos.values()) and not re.fullmatch(r'[0-9]{8}', campos['documento']):
            return index

    return None


def fecha_nacimiento_invalida(valor):
    try:
        fecha = date.fromisoformat(valor)
    except (TypeError, ValueError):
        return True
    return fecha > timezone.localdate()


def telefono_usuario_invalido(valor):
    return bool(valor) and not re.fullmatch(r'[0-9]{1,9}', valor)


def es_administrador(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, 'rol', '') == 'admin')


def es_cuidadora(user):
    return user.is_authenticated and getattr(user, 'rol', '') == 'cuidadora'


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not es_administrador(request.user):
            messages.error(request, 'No tienes permisos de administrador para acceder a esta sección.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


def cuidadora_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not (es_administrador(request.user) or es_cuidadora(request.user)):
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'core/login.html')


def registro_admin(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not password:
            messages.error(request, 'El usuario y la contraseña son obligatorios para registrar un administrador.')
            return redirect('login')

        if len(password) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return redirect('login')

        if Usuario.objects.filter(username=username).exists():
            messages.error(request, 'Ya existe un usuario con ese nombre.')
            return redirect('login')

        if Usuario.objects.filter(rol='admin').exists():
            messages.error(request, 'Ya existe un administrador registrado. Inicia sesión para continuar.')
            return redirect('login')

        user = Usuario.objects.create_user(
            username=username,
            email=email,
            password=password,
            rol='admin',
            is_staff=True,
            is_superuser=True,
        )
        user.estado = True
        user.save()

        messages.success(request, 'Administrador registrado correctamente. Ya puedes iniciar sesión.')
        return redirect('login')

    return render(request, 'core/registro_admin.html')

def logout_view(request):
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente')
    return redirect('login')

@login_required
def dashboard(request):
    ensure_default_aulas()
    hoy = timezone.now().date()
    
    total_ninos = Nino.objects.filter(estado_matricula=True).count()
    presentes = Asistencia.objects.filter(fecha=hoy, estado__in=['presente', 'tardanza']).count()
    ausentes = Asistencia.objects.filter(fecha=hoy, estado='ausente').count()
    incidencias_hoy = Incidencia.objects.filter(fecha=hoy).count()
    bitacoras_hoy = Bitacora.objects.filter(fecha=hoy).count()

    grupos_salones = []
    grupos_por_aula = {}
    for aula in Aula.objects.order_by('nombre'):
        grupo = {
            'id': f'aula-{aula.id}',
            'nombre': aula.nombre,
            'total_ninos': 0,
            'ninos': [],
            'presentes': [],
            'ausentes': [],
            'incidencias': [],
        }
        grupos_salones.append(grupo)
        grupos_por_aula[aula.id] = grupo

    ninos_activos = Nino.objects.filter(estado_matricula=True).select_related('aula').order_by(
        'apellidos', 'nombres'
    )
    for nino in ninos_activos:
        grupo = grupos_por_aula.get(nino.aula_id)
        if grupo is None:
            grupo = grupos_por_aula.setdefault(None, {
                'id': 'sin-aula',
                'nombre': 'Sin salón asignado',
                'total_ninos': 0,
                'ninos': [],
                'presentes': [],
                'ausentes': [],
                'incidencias': [],
            })
            if grupo not in grupos_salones:
                grupos_salones.append(grupo)
        grupo['total_ninos'] += 1
        grupo['ninos'].append(nino)

    asistencias_hoy = Asistencia.objects.filter(
        fecha=hoy
    ).select_related('nino', 'nino__aula').order_by('nino__apellidos', 'nino__nombres')
    for asistencia in asistencias_hoy:
        grupo = grupos_por_aula.get(asistencia.nino.aula_id)
        if grupo is None:
            continue
        detalle = {'nino': asistencia.nino, 'asistencia': asistencia}
        if asistencia.estado == 'ausente':
            grupo['ausentes'].append(detalle)
        elif asistencia.estado in ['presente', 'tardanza']:
            grupo['presentes'].append(detalle)

    incidencias_del_dia = Incidencia.objects.filter(fecha=hoy).select_related(
        'nino', 'nino__aula'
    ).order_by('hora')
    for incidencia in incidencias_del_dia:
        grupo = grupos_por_aula.get(incidencia.nino.aula_id)
        if grupo is None:
            grupo = grupos_por_aula.setdefault(None, {
                'id': 'sin-aula',
                'nombre': 'Sin salón asignado',
                'total_ninos': 0,
                'ninos': [],
                'presentes': [],
                'ausentes': [],
                'incidencias': [],
            })
            if grupo not in grupos_salones:
                grupos_salones.append(grupo)
        grupo['incidencias'].append(incidencia)
    
    asistencia_semanal = []
    for i in range(7):
        fecha = hoy - timedelta(days=i)
        total = Asistencia.objects.filter(fecha=fecha).count()
        presentes_dia = Asistencia.objects.filter(fecha=fecha, estado='presente').count()
        asistencia_semanal.append({
            'fecha': fecha.strftime('%d/%m'),
            'presentes': presentes_dia,
            'total': total
        })
    asistencia_semanal.reverse()

    entregas_hoy = RegistroEntrega.objects.filter(fecha=hoy).select_related(
        'nino', 'apoderado', 'persona_entrega'
    )
    ninos_para_entrega = Nino.objects.filter(
        estado_matricula=True,
        asistencia__fecha=hoy,
        asistencia__estado__in=['presente', 'tardanza'],
    ).prefetch_related('apoderados', 'autorizados').distinct().order_by('apellidos', 'nombres')
    entregas_por_nino = {entrega.nino_id: entrega for entrega in entregas_hoy}
    for nino in ninos_para_entrega:
        nino.entrega_hoy = entregas_por_nino.get(nino.id)
    
    horario_atencion = {
        'dias': 'Lunes a viernes',
        'inicio': '8:00 a. m.',
        'fin': '1:00 p. m.',
    }

    context = {
        'total_ninos': total_ninos,
        'presentes': presentes,
        'ausentes': ausentes,
        'incidencias_hoy': incidencias_hoy,
        'grupos_salones': grupos_salones,
        'bitacoras_hoy': bitacoras_hoy,
        'asistencia_semanal': asistencia_semanal,
        'hoy': hoy,
        'ninos_para_entrega': ninos_para_entrega,
        'entregas_hoy': entregas_hoy,
        'horario_atencion': horario_atencion,
    }
    return render(request, 'core/dashboard.html', context)

@login_required
@cuidadora_required
def registrar_entrega(request, nino_id):
    nino = get_object_or_404(Nino, id=nino_id, estado_matricula=True)
    hoy = timezone.now().date()

    if request.method == 'POST':
        if RegistroEntrega.objects.filter(nino=nino, fecha=hoy).exists():
            messages.error(request, f'{nino.nombre_completo} ya fue entregado hoy')
            return redirect('dashboard')

        asistencia = Asistencia.objects.filter(
            nino=nino, fecha=hoy, estado__in=['presente', 'tardanza']
        ).first()
        if not asistencia:
            messages.error(request, 'No se puede entregar un niño sin asistencia registrada hoy')
            return redirect('dashboard')

        documento = request.POST.get('documento', '').strip()
        if not documento:
            messages.error(request, 'Ingresa el DNI del padre, apoderado o persona autorizada')
            return redirect('dashboard')

        apoderado = Apoderado.objects.filter(
            nino=nino, documento=documento, estado=True
        ).first()
        autorizado = PersonaAutorizada.objects.filter(
            nino=nino, documento=documento, estado=True
        ).first()
        persona = apoderado or autorizado

        if not persona:
            messages.error(request, 'DNI no coincide con una persona autorizada. El niño no fue entregado')
            return redirect('dashboard')

        RegistroEntrega.objects.create(
            nino=nino,
            apoderado=apoderado,
            persona_entrega=autorizado,
            nombre_persona=persona.nombres,
            documento_verificado=documento,
            usuario_verifica=request.user,
            observaciones=f'Parentesco: {persona.parentesco}',
        )
        messages.success(request, f'Entrega de {nino.nombre_completo} finalizada con éxito')

    return redirect('dashboard')

@login_required
@cuidadora_required
def lista_ninos(request):
    puede_gestionar_estado = es_administrador(request.user)
    ninos = Nino.objects.all()
    if not puede_gestionar_estado:
        ninos = ninos.filter(estado_matricula=True)
    ninos = ninos.order_by('apellidos', 'nombres')
    return render(
        request,
        'core/ninos/lista.html',
        {'ninos': ninos, 'puede_gestionar_estado': puede_gestionar_estado},
    )


@login_required
@admin_required
def cambiar_estado_nino(request, nino_id):
    if request.method != 'POST':
        return redirect('lista_ninos')

    nino = get_object_or_404(Nino, id=nino_id)
    nino.estado_matricula = not nino.estado_matricula
    nino.save(update_fields=['estado_matricula'])
    estado = 'activado' if nino.estado_matricula else 'desactivado'
    messages.success(request, f'La matrícula de {nino.nombre_completo} fue {estado}.')
    return redirect('lista_ninos')

@login_required
@admin_required
def registrar_nino(request):
    ensure_default_aulas()
    if request.method == 'POST':
        # Crear un nuevo niño manualmente (sin usar forms para simplificar)
        nombres = request.POST.get('nombres')
        apellidos = request.POST.get('apellidos')
        fecha_nacimiento = request.POST.get('fecha_nacimiento')
        sexo = request.POST.get('sexo')
        aula_id = request.POST.get('aula')
        alergias = request.POST.get('alergias', '')
        restricciones = request.POST.get('restricciones', '')
        informacion_medica = request.POST.get('informacion_medica', '')
        foto = request.FILES.get('foto')

        if nombres and apellidos and fecha_nacimiento:
            if fecha_nacimiento_invalida(fecha_nacimiento):
                messages.error(request, 'La fecha de nacimiento no puede ser posterior a la fecha actual.')
                return render(
                    request,
                    'core/ninos/registrar.html',
                    {'aulas': Aula.objects.all(), 'fecha_maxima': timezone.localdate().isoformat()},
                )

            apoderado_invalido = apoderado_con_dni_invalido(request.POST)
            if apoderado_invalido:
                messages.error(
                    request,
                    f'El DNI del apoderado {apoderado_invalido} debe contener exactamente 8 dígitos numéricos.',
                )
                return render(
                    request,
                    'core/ninos/registrar.html',
                    {
                        'aulas': Aula.objects.all(),
                        'fecha_maxima': timezone.localdate().isoformat(),
                    },
                )

            nino = Nino(
                nombres=nombres,
                apellidos=apellidos,
                fecha_nacimiento=fecha_nacimiento,
                sexo=sexo,
                alergias=alergias,
                restricciones=restricciones,
                informacion_medica=informacion_medica,
                foto=foto
            )
            
            if aula_id:
                try:
                    nino.aula = Aula.objects.get(id=aula_id)
                except Aula.DoesNotExist:
                    pass
            
            nino.save()

            apoderado_entries = []
            for index in [1, 2]:
                nombres_apoderado = request.POST.get(f'apoderado_{index}_nombres', '').strip()
                parentesco_apoderado = request.POST.get(f'apoderado_{index}_parentesco', '').strip()
                documento_apoderado = request.POST.get(f'apoderado_{index}_documento', '').strip()
                telefono_apoderado = request.POST.get(f'apoderado_{index}_telefono', '').strip()
                correo_apoderado = request.POST.get(f'apoderado_{index}_correo', '').strip()
                direccion_apoderado = request.POST.get(f'apoderado_{index}_direccion', '').strip()

                if not any([nombres_apoderado, parentesco_apoderado, documento_apoderado, telefono_apoderado, correo_apoderado, direccion_apoderado]):
                    if index == 1:
                        nombres_apoderado = request.POST.get('apoderado_nombres', '').strip()
                        parentesco_apoderado = request.POST.get('apoderado_parentesco', '').strip()
                        documento_apoderado = request.POST.get('apoderado_documento', '').strip()
                        telefono_apoderado = request.POST.get('apoderado_telefono', '').strip()
                        correo_apoderado = request.POST.get('apoderado_correo', '').strip()
                        direccion_apoderado = request.POST.get('apoderado_direccion', '').strip()
                    else:
                        continue

                if not any([nombres_apoderado, parentesco_apoderado, documento_apoderado, telefono_apoderado, correo_apoderado, direccion_apoderado]):
                    continue

                if not (nombres_apoderado and parentesco_apoderado and documento_apoderado and telefono_apoderado):
                    messages.warning(request, f'Faltan datos del apoderado {index}: nombres, parentesco, documento y teléfono son obligatorios para el retiro seguro.')
                    continue

                apoderado_entries.append({
                    'nombres': nombres_apoderado,
                    'parentesco': parentesco_apoderado,
                    'documento': documento_apoderado,
                    'telefono': telefono_apoderado,
                    'correo': correo_apoderado,
                    'direccion': direccion_apoderado,
                })

            for apoderado_data in apoderado_entries:
                Apoderado.objects.create(
                    nino=nino,
                    nombres=apoderado_data['nombres'],
                    parentesco=apoderado_data['parentesco'],
                    documento=apoderado_data['documento'],
                    telefono=apoderado_data['telefono'],
                    correo=apoderado_data['correo'],
                    direccion=apoderado_data['direccion'],
                )

            messages.success(request, f'¡Niño {nino.nombre_completo} registrado exitosamente!')
            return redirect('lista_ninos')
        else:
            messages.error(request, 'Por favor completa todos los campos obligatorios')
    
    aulas = Aula.objects.all()
    return render(
        request,
        'core/ninos/registrar.html',
        {'aulas': aulas, 'fecha_maxima': timezone.localdate().isoformat()},
    )

@login_required
@cuidadora_required
def detalle_nino(request, nino_id):
    nino = get_object_or_404(Nino, id=nino_id)
    return render(request, 'core/ninos/detalle.html', {'nino': nino, 'nino_id': nino.id})

@login_required
@admin_required
def editar_nino(request, nino_id):
    ensure_default_aulas()
    nino = get_object_or_404(Nino, id=nino_id)
    apoderados = list(nino.apoderados.order_by('id')[:2])
    
    if request.method == 'POST':
        fecha_nacimiento = request.POST.get('fecha_nacimiento', '')
        if fecha_nacimiento_invalida(fecha_nacimiento):
            messages.error(request, 'La fecha de nacimiento no puede ser posterior a la fecha actual.')
            aulas = Aula.objects.all()
            return render(
                request,
                'core/ninos/editar.html',
                {
                    'nino': nino,
                    'aulas': aulas,
                    'apoderados': apoderados,
                    'fecha_maxima': timezone.localdate().isoformat(),
                },
            )

        apoderado_invalido = apoderado_con_dni_invalido(request.POST)
        if apoderado_invalido:
            messages.error(
                request,
                f'El DNI del apoderado {apoderado_invalido} debe contener exactamente 8 dígitos numéricos.',
            )
            aulas = Aula.objects.all()
            return render(
                request,
                'core/ninos/editar.html',
                {
                    'nino': nino,
                    'aulas': aulas,
                    'apoderados': apoderados,
                    'fecha_maxima': timezone.localdate().isoformat(),
                },
            )

        nino.nombres = request.POST.get('nombres', nino.nombres)
        nino.apellidos = request.POST.get('apellidos', nino.apellidos)
        nino.fecha_nacimiento = fecha_nacimiento
        nino.sexo = request.POST.get('sexo', nino.sexo)
        nino.alergias = request.POST.get('alergias', nino.alergias)
        nino.restricciones = request.POST.get('restricciones', nino.restricciones)
        nino.informacion_medica = request.POST.get('informacion_medica', nino.informacion_medica)
        
        if 'foto' in request.FILES:
            nino.foto = request.FILES['foto']
        
        aula_id = request.POST.get('aula')
        if aula_id:
            try:
                nino.aula = Aula.objects.get(id=aula_id)
            except Aula.DoesNotExist:
                pass

        for index in [1, 2]:
            nombres = request.POST.get(f'apoderado_{index}_nombres', '').strip()
            parentesco = request.POST.get(f'apoderado_{index}_parentesco', '').strip()
            documento = request.POST.get(f'apoderado_{index}_documento', '').strip()
            telefono = request.POST.get(f'apoderado_{index}_telefono', '').strip()
            correo = request.POST.get(f'apoderado_{index}_correo', '').strip()
            direccion = request.POST.get(f'apoderado_{index}_direccion', '').strip()

            if not any([nombres, parentesco, documento, telefono, correo, direccion]):
                continue

            if not (nombres and parentesco and documento and telefono):
                messages.warning(request, f'Faltan datos obligatorios para el apoderado {index}.')
                continue

            apoderado = apoderados[index - 1] if index - 1 < len(apoderados) else None
            if apoderado is None:
                apoderado = Apoderado(nino=nino)

            apoderado.nombres = nombres
            apoderado.parentesco = parentesco
            apoderado.documento = documento
            apoderado.telefono = telefono
            apoderado.correo = correo
            apoderado.direccion = direccion
            apoderado.estado = True
            apoderado.save()

        nino.save()
        messages.success(request, f'Niño {nino.nombre_completo} actualizado correctamente')
        return redirect('detalle_nino', nino_id=nino.id)
    
    aulas = Aula.objects.all()
    return render(
        request,
        'core/ninos/editar.html',
        {
            'nino': nino,
            'aulas': aulas,
            'apoderados': apoderados,
            'fecha_maxima': timezone.localdate().isoformat(),
        },
    )

@login_required
@cuidadora_required
def asistencia_hoy(request):
    hoy = timezone.localdate()
    ninos = Nino.objects.filter(estado_matricula=True)
    
    for nino in ninos:
        if not Asistencia.objects.filter(nino=nino, fecha=hoy).exists():
            Asistencia.objects.create(nino=nino, fecha=hoy, estado='ausente')
    
    asistencias = Asistencia.objects.filter(fecha=hoy).select_related('nino')
    
    context = {
        'asistencias': asistencias,
        'hoy': hoy,
        'total': ninos.count(),
        'presentes': asistencias.filter(estado='presente').count(),
        'ausentes': asistencias.filter(estado='ausente').count(),
        'tardanzas': asistencias.filter(estado='tardanza').count(),
    }
    return render(request, 'core/asistencia/hoy.html', context)

@login_required
@cuidadora_required
def registrar_asistencia(request, asistencia_id):
    asistencia = get_object_or_404(Asistencia, id=asistencia_id)
    
    if request.method == 'POST':
        estado = request.POST.get('estado')
        motivo = request.POST.get('motivo_ausencia', '')
        
        asistencia.estado = estado
        asistencia.motivo_ausencia = motivo
        asistencia.usuario_registro = request.user
        
        if estado != 'ausente' and not asistencia.fecha_hora_ingreso and not asistencia.hora_ingreso:
            marca_ingreso = timezone.localtime()
            asistencia.fecha = marca_ingreso.date()
            asistencia.hora_ingreso = marca_ingreso.time()
            asistencia.fecha_hora_ingreso = marca_ingreso
        
        asistencia.save()
        messages.success(request, f'Asistencia de {asistencia.nino.nombre_completo} actualizada')
    
    return redirect('asistencia_hoy')

@login_required
@cuidadora_required
def registrar_salida(request, asistencia_id):
    asistencia = get_object_or_404(Asistencia, id=asistencia_id)
    
    if request.method == 'POST':
        if not asistencia.fecha_hora_ingreso and not asistencia.hora_ingreso:
            messages.error(request, 'Registre el ingreso antes de marcar la salida')
        elif asistencia.fecha_hora_salida or asistencia.hora_salida:
            messages.warning(request, f'La salida de {asistencia.nino.nombre_completo} ya fue registrada')
        else:
            marca_salida = timezone.localtime()
            asistencia.hora_salida = marca_salida.time()
            asistencia.fecha_hora_salida = marca_salida
            asistencia.save()
            messages.success(request, f'Salida de {asistencia.nino.nombre_completo} registrada correctamente')
    
    return redirect('asistencia_hoy')

@login_required
@admin_required
def bitacora_hoy(request):
    hoy = timezone.localdate()
    if 'fecha_desde' not in request.GET and 'fecha_hasta' not in request.GET:
        fecha_desde_parametro = hoy.isoformat()
        fecha_hasta_parametro = hoy.isoformat()
    else:
        fecha_desde_parametro = request.GET.get('fecha_desde', '').strip()
        fecha_hasta_parametro = request.GET.get('fecha_hasta', '').strip()

    try:
        fecha_desde = date.fromisoformat(fecha_desde_parametro) if fecha_desde_parametro else None
        fecha_hasta = date.fromisoformat(fecha_hasta_parametro) if fecha_hasta_parametro else None
    except ValueError:
        messages.error(request, 'El período seleccionado contiene una fecha no válida.')
        fecha_desde = hoy
        fecha_hasta = hoy
        fecha_desde_parametro = hoy.isoformat()
        fecha_hasta_parametro = hoy.isoformat()

    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        messages.error(request, 'La fecha inicial no puede ser posterior a la fecha final.')
        fecha_desde = hoy
        fecha_hasta = hoy
        fecha_desde_parametro = hoy.isoformat()
        fecha_hasta_parametro = hoy.isoformat()

    incluye_hoy = (
        (fecha_desde is None or fecha_desde <= hoy)
        and (fecha_hasta is None or hoy <= fecha_hasta)
    )
    if incluye_hoy:
        ninos_activos = Nino.objects.filter(estado_matricula=True)
        for nino in ninos_activos:
            if not Bitacora.objects.filter(nino=nino, fecha=hoy).exists():
                Bitacora.objects.create(nino=nino, fecha=hoy)

    bitacoras = Bitacora.objects.select_related('nino', 'nino__aula')
    if fecha_desde:
        bitacoras = bitacoras.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        bitacoras = bitacoras.filter(fecha__lte=fecha_hasta)

    nino_parametro = request.GET.get('nino', '').strip()
    if nino_parametro:
        if nino_parametro.isdigit():
            bitacoras = bitacoras.filter(nino_id=int(nino_parametro))
        else:
            messages.error(request, 'El filtro de niño no es válido.')
            nino_parametro = ''

    aula_parametro = request.GET.get('aula', '').strip()
    if aula_parametro:
        if aula_parametro.isdigit():
            bitacoras = bitacoras.filter(nino__aula_id=int(aula_parametro))
        else:
            messages.error(request, 'El filtro de aula no es válido.')
            aula_parametro = ''

    estado_animo_parametro = request.GET.get('estado_animo', '').strip()
    if estado_animo_parametro:
        estados_validos = dict(Bitacora.ESTADOS_ANIMO)
        if estado_animo_parametro in estados_validos:
            bitacoras = bitacoras.filter(estado_animo=estado_animo_parametro)
        else:
            messages.error(request, 'El filtro de estado de ánimo no es válido.')
            estado_animo_parametro = ''

    bitacoras = bitacoras.order_by('-fecha', 'nino__apellidos', 'nino__nombres')
    fechas_bitacoras = {bitacora.fecha for bitacora in bitacoras}
    menus_por_fecha = {}
    if fechas_bitacoras:
        menus_desayuno = MenuDiario.objects.filter(
            fecha__in=fechas_bitacoras,
            tipo_comida='desayuno',
        )
        for menu in menus_desayuno:
            menus_por_fecha.setdefault(menu.fecha, []).append(menu)
        for bitacora in bitacoras:
            bitacora.menus_desayuno = menus_por_fecha.get(bitacora.fecha, [])
            descansos_actuales = bitacora.descanso.splitlines()
            opciones_descanso = [
                {'valor': opcion, 'seleccionado': opcion in descansos_actuales}
                for opcion in OPCIONES_DESCANSO
            ]
            opciones_descanso.extend(
                {'valor': descanso, 'seleccionado': True}
                for descanso in descansos_actuales
                if descanso and descanso not in OPCIONES_DESCANSO
            )
            bitacora.opciones_descanso = opciones_descanso

    aulas = Aula.objects.all().order_by('nombre')
    ninos = Nino.objects.all().order_by('apellidos', 'nombres')

    context = {
        'bitacoras': bitacoras,
        'hoy': hoy,
        'aulas': aulas,
        'ninos': ninos,
        'estados_animo': Bitacora.ESTADOS_ANIMO,
        'filtros': {
            'fecha_desde': fecha_desde_parametro,
            'fecha_hasta': fecha_hasta_parametro,
            'nino': nino_parametro,
            'aula': aula_parametro,
            'estado_animo': estado_animo_parametro,
        },
    }
    return render(request, 'core/bitacora/hoy.html', context)

@login_required
@admin_required
def registrar_bitacora(request, bitacora_id):
    bitacora = get_object_or_404(Bitacora, id=bitacora_id)
    
    if request.method == 'POST':
        menu_desayuno_id = request.POST.get('menu_desayuno', '').strip()
        if menu_desayuno_id:
            menu_desayuno = MenuDiario.objects.filter(
                id=menu_desayuno_id,
                fecha=bitacora.fecha,
                tipo_comida='desayuno',
            ).first()
            if menu_desayuno is None:
                messages.error(request, 'Selecciona un menú de desayuno válido para la fecha de esta bitácora.')
                return redirect('bitacora_hoy')
            bitacora.alimentacion = menu_desayuno.descripcion
        else:
            bitacora.alimentacion = ''
        descansos_seleccionados = request.POST.getlist('descanso')
        descansos_actuales = bitacora.descanso.splitlines()
        opciones_validas = set(OPCIONES_DESCANSO + descansos_actuales)
        if any(descanso not in opciones_validas for descanso in descansos_seleccionados):
            messages.error(request, 'Selecciona únicamente las opciones disponibles para el descanso.')
            return redirect('bitacora_hoy')
        bitacora.descanso = '\n'.join(dict.fromkeys(descansos_seleccionados))
        bitacora.actividades = request.POST.get('actividades', '')
        bitacora.higiene = request.POST.get('higiene', '')
        bitacora.estado_animo = request.POST.get('estado_animo', '')
        bitacora.observaciones = request.POST.get('observaciones', '')
        bitacora.usuario_registro = request.user
        bitacora.save()
        messages.success(request, f'Bitácora de {bitacora.nino.nombre_completo} actualizada')
    
    return redirect('bitacora_hoy')


@login_required
@cuidadora_required
def menu_diario(request):
    fecha_parametro = request.GET.get('fecha', '')
    try:
        fecha = date.fromisoformat(fecha_parametro) if fecha_parametro else timezone.localdate()
    except ValueError:
        messages.error(request, 'La fecha seleccionada no es válida.')
        fecha = timezone.localdate()

    menus = MenuDiario.objects.filter(fecha=fecha)
    return render(
        request,
        'core/menu/diario.html',
        {
            'menus': menus,
            'fecha': fecha,
            'puede_gestionar_menu': es_administrador(request.user),
            'tipos_comida': MenuDiario.TIPOS_COMIDA,
        },
    )


@login_required
@admin_required
def crear_menu_diario(request):
    if request.method != 'POST':
        return redirect('menu_diario')

    fecha_texto = request.POST.get('fecha', '')
    tipo_comida = request.POST.get('tipo_comida', '')
    descripcion = request.POST.get('descripcion', '').strip()
    try:
        fecha = date.fromisoformat(fecha_texto)
    except ValueError:
        messages.error(request, 'Selecciona una fecha válida para el menú.')
        return redirect('menu_diario')

    if tipo_comida not in dict(MenuDiario.TIPOS_COMIDA) or not descripcion:
        messages.error(request, 'Selecciona el tipo de comida e ingresa su descripción.')
        return redirect(f'{reverse("menu_diario")}?fecha={fecha.isoformat()}')

    if MenuDiario.objects.filter(fecha=fecha, tipo_comida=tipo_comida).exists():
        messages.error(request, 'Ya existe un menú para ese tipo de comida y fecha. Puedes editarlo.')
        return redirect(f'{reverse("menu_diario")}?fecha={fecha.isoformat()}')

    MenuDiario.objects.create(
        fecha=fecha,
        tipo_comida=tipo_comida,
        descripcion=descripcion,
        usuario_registro=request.user,
    )
    messages.success(request, 'Menú guardado correctamente.')
    return redirect(f'{reverse("menu_diario")}?fecha={fecha.isoformat()}')


@login_required
@admin_required
def editar_menu_diario(request, menu_id):
    menu = get_object_or_404(MenuDiario, id=menu_id)
    if request.method == 'POST':
        fecha_texto = request.POST.get('fecha', '')
        tipo_comida = request.POST.get('tipo_comida', '')
        descripcion = request.POST.get('descripcion', '').strip()
        try:
            fecha = date.fromisoformat(fecha_texto)
        except ValueError:
            messages.error(request, 'Selecciona una fecha válida para el menú.')
            return redirect('editar_menu_diario', menu_id=menu.id)

        if tipo_comida not in dict(MenuDiario.TIPOS_COMIDA) or not descripcion:
            messages.error(request, 'Selecciona el tipo de comida e ingresa su descripción.')
        elif MenuDiario.objects.filter(
            fecha=fecha,
            tipo_comida=tipo_comida,
        ).exclude(id=menu.id).exists():
            messages.error(request, 'Ya existe un menú para ese tipo de comida y fecha.')
        else:
            menu.fecha = fecha
            menu.tipo_comida = tipo_comida
            menu.descripcion = descripcion
            menu.save(update_fields=['fecha', 'tipo_comida', 'descripcion'])
            messages.success(request, 'Menú actualizado correctamente.')
            return redirect(f'{reverse("menu_diario")}?fecha={fecha.isoformat()}')

    return render(
        request,
        'core/menu/editar.html',
        {'menu': menu, 'tipos_comida': MenuDiario.TIPOS_COMIDA},
    )


@login_required
@admin_required
def eliminar_menu_diario(request, menu_id):
    if request.method != 'POST':
        return redirect('menu_diario')

    menu = get_object_or_404(MenuDiario, id=menu_id)
    fecha = menu.fecha
    menu.delete()
    messages.success(request, 'Menú eliminado correctamente.')
    return redirect(f'{reverse("menu_diario")}?fecha={fecha.isoformat()}')


@login_required
@admin_required
def lista_incidencias(request):
    incidencias = Incidencia.objects.all().order_by('-fecha', '-hora')
    return render(request, 'core/incidencias/lista.html', {'incidencias': incidencias})

@login_required
@admin_required
def registrar_incidencia(request):
    if request.method == 'POST':
        nino_id = request.POST.get('nino')
        tipo = request.POST.get('tipo')
        descripcion = request.POST.get('descripcion')
        accion_realizada = request.POST.get('accion_realizada', '')
        comunicacion_apoderado = request.POST.get('comunicacion_apoderado') == 'on'
        
        if nino_id and tipo and descripcion:
            nino = get_object_or_404(Nino, id=nino_id)
            incidencia = Incidencia(
                nino=nino,
                tipo=tipo,
                descripcion=descripcion,
                accion_realizada=accion_realizada,
                comunicacion_apoderado=comunicacion_apoderado,
                usuario_registro=request.user
            )
            incidencia.save()
            messages.success(request, 'Incidencia registrada exitosamente')
            return redirect('lista_incidencias')
        else:
            messages.error(request, 'Por favor completa todos los campos obligatorios')
    
    ninos = Nino.objects.filter(estado_matricula=True)
    return render(request, 'core/incidencias/registrar.html', {'ninos': ninos})

@login_required
@admin_required
def detalle_incidencia(request, incidencia_id):
    incidencia = get_object_or_404(Incidencia, id=incidencia_id)
    return render(request, 'core/incidencias/detalle.html', {'incidencia': incidencia})

@login_required
@admin_required
def finalizar_incidencia(request, incidencia_id):
    incidencia = get_object_or_404(Incidencia, id=incidencia_id)

    if request.method == 'POST':
        incidencia.estado = 'cerrado'
        if not incidencia.accion_realizada:
            incidencia.accion_realizada = 'Acción finalizada' 
        incidencia.save()
        messages.success(request, f'Incidencia de {incidencia.nino.nombre_completo} finalizada correctamente')

    return redirect('lista_incidencias')

@login_required
@admin_required
def generar_reportes(request):
    return render(request, 'core/reportes/index.html', {
        'ninos_reporte': Nino.objects.filter(estado_matricula=True).order_by('apellidos', 'nombres'),
        'semana_actual': timezone.localdate().strftime('%G-W%V'),
    })


class BabyIllustration(Flowable):
    def __init__(self):
        super().__init__()
        self.width = 48
        self.height = 48

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(colors.HexColor('#F8B4C5'))
        canvas.circle(8, 39, 2, fill=1, stroke=0)
        canvas.circle(39, 34, 2, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#8ED6C2'))
        canvas.ellipse(8, 0, 40, 23, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#F6C9A8'))
        canvas.circle(24, 27, 15, fill=1, stroke=0)
        canvas.circle(9, 26, 4, fill=1, stroke=0)
        canvas.circle(39, 26, 4, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#8C6CCB'))
        canvas.wedge(9, 25, 39, 48, 0, 180, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#FFD166'))
        canvas.circle(24, 47, 3, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#374151'))
        canvas.circle(19, 28, 1.2, fill=1, stroke=0)
        canvas.circle(29, 28, 1.2, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor('#C66B72'))
        canvas.setLineWidth(1)
        canvas.arc(19, 18, 29, 26, 200, 140)


@login_required
@admin_required
def reporte_estudiantes(request):
    semana = request.GET.get('semana', '').strip()
    if not semana:
        semana = timezone.localdate().strftime('%G-W%V')
    if not re.fullmatch(r'\d{4}-W\d{2}', semana):
        messages.error(request, 'Selecciona una semana válida para generar el reporte.')
        return redirect('generar_reportes')

    try:
        fecha_inicio = datetime.strptime(f'{semana}-1', '%G-W%V-%u').date()
    except ValueError:
        messages.error(request, 'Selecciona una semana válida para generar el reporte.')
        return redirect('generar_reportes')
    fecha_fin = fecha_inicio + timedelta(days=6)

    nino_id = request.GET.get('nino', '').strip()
    if not nino_id or not nino_id.isdecimal():
        messages.error(request, 'Selecciona un estudiante para generar el reporte.')
        return redirect('generar_reportes')
    ninos = Nino.objects.filter(pk=nino_id, estado_matricula=True)
    if not ninos.exists():
        messages.error(request, 'El estudiante seleccionado no existe o no está matriculado.')
        return redirect('generar_reportes')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=32, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'StudentReportTitle',
        parent=styles['Title'],
        fontSize=17,
        leading=21,
        textColor=colors.HexColor('#24476B'),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'StudentReportSubtitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#60758A'),
    )
    section_style = ParagraphStyle(
        'StudentReportSection',
        parent=styles['Heading3'],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#315F83'),
        spaceBefore=2,
        spaceAfter=6,
    )
    cell_style = ParagraphStyle('StudentReportCell', parent=styles['BodyText'], fontSize=8, leading=10)
    header_cell_style = ParagraphStyle(
        'StudentReportHeaderCell',
        parent=cell_style,
        textColor=colors.white,
        fontName='Helvetica-Bold',
    )

    def paragraph(value):
        return Paragraph(escape(str(value or '--')), cell_style)

    def add_table(headers, rows, widths):
        data = [[Paragraph(escape(header), header_cell_style) for header in headers]]
        data.extend([[paragraph(value) for value in row] for row in rows])
        table = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#568FC2')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F8FC')]),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#D5E1EB')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)

    ninos = ninos.select_related('aula')
    for nino in ninos:
        asistencias = list(Asistencia.objects.filter(
            nino=nino, fecha__range=(fecha_inicio, fecha_fin)
        ).order_by('fecha'))
        bitacoras = list(Bitacora.objects.filter(
            nino=nino, fecha__range=(fecha_inicio, fecha_fin)
        ).order_by('fecha'))
        incidencias = list(Incidencia.objects.filter(
            nino=nino, fecha__range=(fecha_inicio, fecha_fin)
        ).order_by('fecha', 'hora'))
        total_presentes = sum(asistencia.estado in ('presente', 'tardanza') for asistencia in asistencias)
        total_ausentes = sum(asistencia.estado == 'ausente' for asistencia in asistencias)

        header = Table(
            [[
                BabyIllustration(),
                [
                    Paragraph('Mi semana en NidoControl', title_style),
                    Paragraph(
                        f'Ficha semanal · {fecha_inicio.strftime("%d/%m/%Y")} al {fecha_fin.strftime("%d/%m/%Y")}',
                        subtitle_style,
                    ),
                ],
            ]],
            colWidths=[60, 463],
        )
        header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EAF5FC')),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#D0E5F2')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(header)
        elements.append(Spacer(1, 12))

        estudiante = Table(
            [[
                Paragraph(
                    f'<b>{escape(nino.nombre_completo)}</b><br/>'
                    f'Aula: {escape(nino.aula.nombre if nino.aula else "Sin aula")} '
                    f' · Edad: {nino.edad} años · Nacimiento: {nino.fecha_nacimiento.strftime("%d/%m/%Y")}',
                    styles['BodyText'],
                ),
                Paragraph(
                    f'<b>{total_presentes}</b> presentes<br/><b>{total_ausentes}</b> ausencias',
                    styles['BodyText'],
                ),
            ]],
            colWidths=[390, 133],
        )
        estudiante.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF7E8')),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#F1D9A8')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ]))
        elements.append(estudiante)

        elements.append(Spacer(1, 14))
        elements.append(Paragraph('Asistencia', section_style))
        add_table(
            ['Fecha', 'Estado', 'Ingreso', 'Salida', 'Motivo de ausencia'],
            [[
                asistencia.fecha.strftime('%d/%m/%Y'),
                asistencia.get_estado_display(),
                asistencia.hora_ingreso.strftime('%H:%M') if asistencia.hora_ingreso else '--:--',
                asistencia.hora_salida.strftime('%H:%M') if asistencia.hora_salida else '--:--',
                asistencia.motivo_ausencia,
            ] for asistencia in asistencias] or [['Sin registros', '', '', '', '']],
            [65, 75, 55, 55, 283],
        )

        elements.append(Spacer(1, 14))
        elements.append(Paragraph('Bitácora diaria', section_style))
        add_table(
            ['Fecha', 'Alimentación', 'Descanso', 'Actividades', 'Higiene', 'Estado de ánimo', 'Observaciones'],
            [[
                bitacora.fecha.strftime('%d/%m/%Y'),
                bitacora.alimentacion,
                bitacora.descanso,
                bitacora.actividades,
                bitacora.higiene,
                bitacora.get_estado_animo_display() if bitacora.estado_animo else '--',
                bitacora.observaciones,
            ] for bitacora in bitacoras] or [['Sin registros', '', '', '', '', '', '']],
            [48, 68, 62, 75, 50, 70, 150],
        )

        elements.append(Spacer(1, 14))
        elements.append(Paragraph('Incidencias', section_style))
        add_table(
            ['Fecha', 'Tipo', 'Descripción', 'Acción realizada', 'Estado', 'Apoderado informado'],
            [[
                incidencia.fecha.strftime('%d/%m/%Y'),
                incidencia.get_tipo_display(),
                incidencia.descripcion,
                incidencia.accion_realizada,
                incidencia.get_estado_display(),
                'Sí' if incidencia.comunicacion_apoderado else 'No',
            ] for incidencia in incidencias] or [['Sin registros', '', '', '', '', '']],
            [48, 65, 130, 120, 70, 90],
        )

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="reporte_estudiante_{nino_id}_{fecha_inicio}_{fecha_fin}.pdf"'
    )
    return response


@login_required
@admin_required
def reporte_asistencia(request):
    """Genera reporte de asistencia en PDF"""
    hoy = timezone.now().date()
    asistencias = Asistencia.objects.filter(fecha=hoy).select_related('nino')
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#4A90D9'),
        spaceAfter=30,
        alignment=1
    )
    
    elements.append(Paragraph("NidoControl - Reporte de Asistencia", title_style))
    elements.append(Paragraph(f"Fecha: {hoy.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    data = [['Niño', 'Aula', 'Estado', 'Ingreso', 'Salida']]
    for a in asistencias:
        data.append([
            a.nino.nombre_completo,
            a.nino.aula.nombre if a.nino.aula else 'Sin aula',
            a.get_estado_display(),
            str(a.hora_ingreso) if a.hora_ingreso else '--:--',
            str(a.hora_salida) if a.hora_salida else '--:--',
        ])
    
    if len(data) > 1:
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90D9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No hay registros de asistencia para hoy.", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="asistencia_{hoy}.pdf"'
    return response


@login_required
@admin_required
def reporte_incidencias(request):
    """Genera reporte de incidencias en PDF"""
    incidencias = Incidencia.objects.all().order_by('-fecha')[:50]
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#4A90D9'),
        spaceAfter=30,
        alignment=1
    )
    
    elements.append(Paragraph("NidoControl - Reporte de Incidencias", title_style))
    elements.append(Spacer(1, 20))
    
    data = [['Niño', 'Tipo', 'Fecha', 'Descripción', 'Estado']]
    for i in incidencias:
        data.append([
            i.nino.nombre_completo,
            i.get_tipo_display(),
            i.fecha.strftime('%d/%m/%Y'),
            i.descripcion[:40] + '...' if len(i.descripcion) > 40 else i.descripcion,
            i.get_estado_display(),
        ])
    
    if len(data) > 1:
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF6B6B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No hay incidencias registradas.", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="incidencias.pdf"'
    return response


@login_required
@admin_required
def reporte_bitacora(request):
    """Genera reporte de bitácora en PDF"""
    hoy = timezone.now().date()
    bitacoras = Bitacora.objects.filter(fecha=hoy).select_related('nino')
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#4A90D9'),
        spaceAfter=30,
        alignment=1
    )
    
    elements.append(Paragraph("NidoControl - Reporte de Bitácora", title_style))
    elements.append(Paragraph(f"Fecha: {hoy.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    data = [['Niño', 'Alimentación', 'Descanso', 'Estado Ánimo']]
    for b in bitacoras:
        data.append([
            b.nino.nombre_completo,
            b.alimentacion[:30] if b.alimentacion else '--',
            b.descanso[:30] if b.descanso else '--',
            b.get_estado_animo_display() if b.estado_animo else '--',
        ])
    
    if len(data) > 1:
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4facfe')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No hay registros de bitácora para hoy.", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="bitacora_{hoy}.pdf"'
    return response


# ============================================
# ESTADÍSTICAS
# ============================================

@login_required
@admin_required
def estadisticas(request):
    """Vista principal de estadísticas con gráficos"""
    hoy = timezone.localdate()
    periodo = request.GET.get('periodo', 'mes')
    fecha_desde = request.GET.get('desde', '').strip()
    fecha_hasta = request.GET.get('hasta', '').strip()
    rango_personalizado = bool(fecha_desde or fecha_hasta)

    if rango_personalizado:
        try:
            if not fecha_desde or not fecha_hasta:
                raise ValueError
            fecha_inicio = date.fromisoformat(fecha_desde)
            fecha_fin = date.fromisoformat(fecha_hasta)
            if fecha_inicio > fecha_fin:
                raise ValueError
        except ValueError:
            messages.error(request, 'Selecciona un rango válido: indica ambas fechas y asegúrate de que "Desde" no sea posterior a "Hasta".')
            rango_personalizado = False
            periodo = 'mes'
            fecha_inicio = hoy.replace(day=1)
            fecha_fin = hoy
    else:
        if periodo == 'dia':
            fecha_inicio = hoy
            fecha_fin = hoy
        elif periodo == 'semana':
            fecha_inicio = hoy - timedelta(days=hoy.weekday())
            fecha_fin = hoy
        elif periodo == 'año':
            fecha_inicio = hoy.replace(month=1, day=1)
            fecha_fin = hoy
        else:
            periodo = 'mes'
            fecha_inicio = hoy.replace(day=1)
            fecha_fin = hoy
    
    total_ninos = Nino.objects.filter(estado_matricula=True).count()
    total_aulas = Aula.objects.count()
    
    asistencias = Asistencia.objects.filter(fecha__range=[fecha_inicio, fecha_fin])
    total_asistencias = asistencias.count()
    total_presentes = asistencias.filter(estado='presente').count()
    total_ausentes = asistencias.filter(estado='ausente').count()
    total_tardanzas = asistencias.filter(estado='tardanza').count()
    
    porcentaje_presentes = round((total_presentes / total_asistencias * 100) if total_asistencias > 0 else 0, 1)
    porcentaje_ausentes = round((total_ausentes / total_asistencias * 100) if total_asistencias > 0 else 0, 1)
    porcentaje_tardanzas = round((total_tardanzas / total_asistencias * 100) if total_asistencias > 0 else 0, 1)
    
    datos_por_aula = []
    for aula in Aula.objects.all():
        ninos_aula = Nino.objects.filter(aula=aula, estado_matricula=True)
        total_ninos_aula = ninos_aula.count()
        
        asist_aula = asistencias.filter(nino__aula=aula)
        presentes_aula = asist_aula.filter(estado='presente').count()
        ausentes_aula = asist_aula.filter(estado='ausente').count()
        tardanzas_aula = asist_aula.filter(estado='tardanza').count()
        
        datos_por_aula.append({
            'aula': aula.nombre,
            'total_ninos': total_ninos_aula,
            'presentes': presentes_aula,
            'ausentes': ausentes_aula,
            'tardanzas': tardanzas_aula,
            'total_registros': asist_aula.count(),
        })
    
    dias_labels = []
    dias_presentes = []
    dias_ausentes = []
    
    for i in range(29, -1, -1):
        fecha = hoy - timedelta(days=i)
        dias_labels.append(fecha.strftime('%d/%m'))
        dias_presentes.append(Asistencia.objects.filter(fecha=fecha, estado='presente').count())
        dias_ausentes.append(Asistencia.objects.filter(fecha=fecha, estado='ausente').count())
    
    incidencias_periodo = Incidencia.objects.filter(fecha__range=[fecha_inicio, fecha_fin])
    total_incidencias = incidencias_periodo.count()
    
    incidencias_por_tipo = {
        'accidente': incidencias_periodo.filter(tipo='accidente').count(),
        'enfermedad': incidencias_periodo.filter(tipo='enfermedad').count(),
        'comportamiento': incidencias_periodo.filter(tipo='comportamiento').count(),
        'otro': incidencias_periodo.filter(tipo='otro').count(),
    }
    
    bitacoras_periodo = Bitacora.objects.filter(fecha__range=[fecha_inicio, fecha_fin])
    total_bitacoras = bitacoras_periodo.count()
    
    estados_animo = {
        'tranquilo': bitacoras_periodo.filter(estado_animo='tranquilo').count(),
        'alegre': bitacoras_periodo.filter(estado_animo='alegre').count(),
        'cansado': bitacoras_periodo.filter(estado_animo='cansado').count(),
        'irritable': bitacoras_periodo.filter(estado_animo='irritable').count(),
        'otro': bitacoras_periodo.filter(estado_animo='otro').count(),
    }
    
    pagos_pagados = Pago.objects.filter(estado='pagado').count()
    pagos_pendientes = Pago.objects.filter(estado='pendiente').count()
    pagos_vencidos = Pago.objects.filter(estado='vencido').count()
    
    context = {
        'total_ninos': total_ninos,
        'total_aulas': total_aulas,
        'periodo': periodo,
        'rango_personalizado': rango_personalizado,
        'fecha_desde': fecha_inicio.isoformat(),
        'fecha_hasta': fecha_fin.isoformat(),
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'total_asistencias': total_asistencias,
        'total_presentes': total_presentes,
        'total_ausentes': total_ausentes,
        'total_tardanzas': total_tardanzas,
        'porcentaje_presentes': porcentaje_presentes,
        'porcentaje_ausentes': porcentaje_ausentes,
        'porcentaje_tardanzas': porcentaje_tardanzas,
        'datos_por_aula': datos_por_aula,
        'dias_labels': dias_labels,
        'dias_presentes': dias_presentes,
        'dias_ausentes': dias_ausentes,
        'total_incidencias': total_incidencias,
        'incidencias_por_tipo': incidencias_por_tipo,
        'total_bitacoras': total_bitacoras,
        'estados_animo': estados_animo,
        'pagos_pagados': pagos_pagados,
        'pagos_pendientes': pagos_pendientes,
        'pagos_vencidos': pagos_vencidos,
    }
    return render(request, 'core/estadisticas/index.html', context)


# ============================================
# CONFIGURACIÓN
# ============================================

@login_required
@admin_required
def configuracion(request):
    """Panel de configuración principal"""
    # Estadísticas generales
    total_ninos = Nino.objects.filter(estado_matricula=True).count()
    total_aulas = Aula.objects.count()
    total_usuarios = Usuario.objects.filter(estado=True).count()
    
    context = {
        'total_ninos': total_ninos,
        'total_aulas': total_aulas,
        'total_usuarios': total_usuarios,
    }
    return render(request, 'core/configuracion/index.html', context)


@login_required
@admin_required
def lista_aulas(request):
    """Lista de aulas"""
    ensure_default_aulas()
    aulas = Aula.objects.all()
    return render(request, 'core/configuracion/aulas.html', {'aulas': aulas})


@login_required
@admin_required
def crear_aula(request):
    """Crear nueva aula"""
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        capacidad = request.POST.get('capacidad')
        descripcion = request.POST.get('descripcion', '')
        
        if nombre and capacidad:
            Aula.objects.create(
                nombre=nombre,
                capacidad=int(capacidad),
                descripcion=descripcion
            )
            messages.success(request, f'Aula "{nombre}" creada correctamente')
            return redirect('lista_aulas')
        else:
            messages.error(request, 'Por favor completa los campos obligatorios')
    
    return redirect('lista_aulas')


@login_required
@admin_required
def editar_aula(request, aula_id):
    """Editar aula existente"""
    aula = get_object_or_404(Aula, id=aula_id)
    
    if request.method == 'POST':
        aula.nombre = request.POST.get('nombre', aula.nombre)
        aula.capacidad = request.POST.get('capacidad', aula.capacidad)
        aula.descripcion = request.POST.get('descripcion', aula.descripcion)
        aula.save()
        messages.success(request, f'Aula "{aula.nombre}" actualizada')
        return redirect('lista_aulas')
    
    return render(request, 'core/configuracion/editar_aula.html', {'aula': aula})


@login_required
@admin_required
def eliminar_aula(request, aula_id):
    """Eliminar aula"""
    aula = get_object_or_404(Aula, id=aula_id)
    nombre = aula.nombre
    aula.delete()
    messages.success(request, f'Aula "{nombre}" eliminada')
    return redirect('lista_aulas')


@login_required
@admin_required
def lista_usuarios(request):
    """Lista de usuarios"""
    usuarios = Usuario.objects.all().order_by('-date_joined')
    return render(request, 'core/configuracion/usuarios.html', {'usuarios': usuarios})


@login_required
@admin_required
def crear_usuario(request):
    """Crear nuevo usuario"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        rol = request.POST.get('rol', 'cuidadora')
        telefono = request.POST.get('telefono', '')

        if telefono_usuario_invalido(telefono):
            messages.error(request, 'El teléfono debe contener solo números y un máximo de 9 dígitos.')
            return redirect('lista_usuarios')

        if not username or not password:
            messages.error(request, 'Por favor completa los campos obligatorios')
            return redirect('lista_usuarios')

        if len(password) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return redirect('lista_usuarios')

        if Usuario.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya existe')
            return redirect('lista_usuarios')

        user = Usuario.objects.create_user(
            username=username,
            email=email,
            password=password,
            rol=rol,
            telefono=telefono
        )
        if rol == 'admin':
            user.is_staff = True
            user.is_superuser = True
        else:
            user.is_staff = False
            user.is_superuser = False
        user.save()
        messages.success(request, f'Usuario "{username}" creado correctamente')
        return redirect('lista_usuarios')

    return redirect('lista_usuarios')


@login_required
@admin_required
def editar_usuario(request, usuario_id):
    """Editar datos de un usuario"""
    usuario = get_object_or_404(Usuario, id=usuario_id)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        rol = request.POST.get('rol', usuario.rol)
        telefono = request.POST.get('telefono', '').strip()
        password = request.POST.get('password', '').strip()

        if telefono_usuario_invalido(telefono):
            messages.error(request, 'El teléfono debe contener solo números y un máximo de 9 dígitos.')
            return redirect('editar_usuario', usuario_id=usuario.id)

        if not username:
            messages.error(request, 'El nombre de usuario es obligatorio.')
            return redirect('editar_usuario', usuario_id=usuario.id)

        if Usuario.objects.filter(username=username).exclude(id=usuario.id).exists():
            messages.error(request, 'Ya existe otro usuario con ese nombre.')
            return redirect('editar_usuario', usuario_id=usuario.id)

        if password and len(password) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return redirect('editar_usuario', usuario_id=usuario.id)

        usuario.username = username
        usuario.email = email
        usuario.rol = rol
        usuario.telefono = telefono
        if rol == 'admin':
            usuario.is_staff = True
            usuario.is_superuser = True
        else:
            usuario.is_staff = False
            usuario.is_superuser = False
        if password:
            usuario.set_password(password)
        usuario.save()

        messages.success(request, f'Usuario "{usuario.username}" actualizado correctamente')
        return redirect('lista_usuarios')

    return render(request, 'core/configuracion/editar_usuario.html', {'usuario': usuario})


@login_required
@admin_required
def eliminar_usuario(request, usuario_id):
    """Eliminar un usuario"""
    usuario = get_object_or_404(Usuario, id=usuario_id)

    if usuario == request.user:
        messages.error(request, 'No puedes eliminar tu propio usuario.')
        return redirect('lista_usuarios')

    nombre = usuario.username
    usuario.delete()
    messages.success(request, f'Usuario "{nombre}" eliminado correctamente')
    return redirect('lista_usuarios')


@login_required
@admin_required
def cambiar_estado_usuario(request, usuario_id):
    """Activar/Desactivar usuario"""
    if request.method != 'POST':
        return redirect('lista_usuarios')

    usuario = get_object_or_404(Usuario, id=usuario_id)
    
    if usuario == request.user:
        messages.error(request, 'No puedes cambiar tu propio estado')
    else:
        usuario.estado = not usuario.estado
        usuario.is_active = usuario.estado
        usuario.save()
        estado = "activado" if usuario.estado else "desactivado"
        messages.success(request, f'Usuario "{usuario.username}" {estado}')
    
    return redirect('lista_usuarios')


@login_required
@cuidadora_required
def mi_perfil(request):
    """Ver y editar perfil del usuario actual"""
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.telefono = request.POST.get('telefono', '')
        request.user.direccion = request.POST.get('direccion', '')
        request.user.save()
        messages.success(request, 'Perfil actualizado correctamente')
        return redirect('mi_perfil')
    
    return render(request, 'core/configuracion/mi_perfil.html')


@login_required
@cuidadora_required
def cambiar_password(request):
    """Cambiar contraseña del usuario actual"""
    if request.method == 'POST':
        password_actual = request.POST.get('password_actual')
        password_nuevo = request.POST.get('password_nuevo')
        password_confirmar = request.POST.get('password_confirmar')
        
        if not request.user.check_password(password_actual):
            messages.error(request, 'La contraseña actual es incorrecta')
        elif password_nuevo != password_confirmar:
            messages.error(request, 'Las contraseñas nuevas no coinciden')
        elif len(password_nuevo) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres')
        else:
            request.user.set_password(password_nuevo)
            request.user.save()
            messages.success(request, 'Contraseña cambiada. Por favor inicia sesión nuevamente.')
            return redirect('login')
    
    return render(request, 'core/configuracion/cambiar_password.html')
