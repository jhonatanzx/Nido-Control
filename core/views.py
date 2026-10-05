from io import BytesIO
from functools import wraps
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from .models import *
from .forms import *

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
    presentes = Asistencia.objects.filter(fecha=hoy, estado='presente').count()
    ausentes = Asistencia.objects.filter(fecha=hoy, estado='ausente').count()
    incidencias_hoy = Incidencia.objects.filter(fecha=hoy).count()
    bitacoras_hoy = Bitacora.objects.filter(fecha=hoy).count()
    
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
    ninos = Nino.objects.filter(estado_matricula=True).order_by('apellidos', 'nombres')
    return render(request, 'core/ninos/lista.html', {'ninos': ninos})

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
    return render(request, 'core/ninos/registrar.html', {'aulas': aulas})

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
        nino.nombres = request.POST.get('nombres', nino.nombres)
        nino.apellidos = request.POST.get('apellidos', nino.apellidos)
        nino.fecha_nacimiento = request.POST.get('fecha_nacimiento', nino.fecha_nacimiento)
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
    return render(request, 'core/ninos/editar.html', {'nino': nino, 'aulas': aulas, 'apoderados': apoderados})

@login_required
@cuidadora_required
def asistencia_hoy(request):
    hoy = timezone.now().date()
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
        hora_ingreso = request.POST.get('hora_ingreso')
        motivo = request.POST.get('motivo_ausencia', '')
        
        asistencia.estado = estado
        asistencia.motivo_ausencia = motivo
        asistencia.usuario_registro = request.user
        
        if estado == 'ausente':
            asistencia.hora_ingreso = None
            asistencia.hora_salida = None
        else:
            asistencia.hora_ingreso = hora_ingreso or asistencia.hora_ingreso
            if estado == 'tardanza' and not asistencia.hora_ingreso:
                asistencia.hora_ingreso = timezone.now().time()
        
        asistencia.save()
        messages.success(request, f'Asistencia de {asistencia.nino.nombre_completo} actualizada')
    
    return redirect('asistencia_hoy')

@login_required
@cuidadora_required
def registrar_salida(request, asistencia_id):
    asistencia = get_object_or_404(Asistencia, id=asistencia_id)
    
    if request.method == 'POST':
        hora_salida = request.POST.get('hora_salida')
        if hora_salida:
            asistencia.hora_salida = hora_salida
            asistencia.save()
            messages.success(request, f'Salida de {asistencia.nino.nombre_completo} registrada correctamente')
    
    return redirect('asistencia_hoy')

@login_required
@admin_required
def bitacora_hoy(request):
    hoy = timezone.now().date()
    ninos = Nino.objects.filter(estado_matricula=True)
    
    for nino in ninos:
        if not Bitacora.objects.filter(nino=nino, fecha=hoy).exists():
            Bitacora.objects.create(nino=nino, fecha=hoy)
    
    bitacoras = Bitacora.objects.filter(fecha=hoy).select_related('nino')
    
    context = {
        'bitacoras': bitacoras,
        'hoy': hoy,
    }
    return render(request, 'core/bitacora/hoy.html', context)

@login_required
@admin_required
def registrar_bitacora(request, bitacora_id):
    bitacora = get_object_or_404(Bitacora, id=bitacora_id)
    
    if request.method == 'POST':
        bitacora.alimentacion = request.POST.get('alimentacion', '')
        bitacora.descanso = request.POST.get('descanso', '')
        bitacora.actividades = request.POST.get('actividades', '')
        bitacora.higiene = request.POST.get('higiene', '')
        bitacora.estado_animo = request.POST.get('estado_animo', '')
        bitacora.observaciones = request.POST.get('observaciones', '')
        bitacora.usuario_registro = request.user
        bitacora.save()
        messages.success(request, f'Bitácora de {bitacora.nino.nombre_completo} actualizada')
    
    return redirect('bitacora_hoy')

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
    return render(request, 'core/reportes/index.html')

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
    hoy = timezone.now().date()
    
    periodo = request.GET.get('periodo', 'mes')
    
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
