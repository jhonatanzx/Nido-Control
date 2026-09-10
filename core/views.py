from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from .models import *
from .forms import *

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

def logout_view(request):
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente')
    return redirect('login')

@login_required
def dashboard(request):
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
    
    context = {
        'total_ninos': total_ninos,
        'presentes': presentes,
        'ausentes': ausentes,
        'incidencias_hoy': incidencias_hoy,
        'bitacoras_hoy': bitacoras_hoy,
        'asistencia_semanal': asistencia_semanal,
        'hoy': hoy,
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def lista_ninos(request):
    ninos = Nino.objects.filter(estado_matricula=True).order_by('apellidos', 'nombres')
    return render(request, 'core/ninos/lista.html', {'ninos': ninos})

@login_required
def registrar_nino(request):
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
            messages.success(request, f'¡Niño {nino.nombre_completo} registrado exitosamente!')
            return redirect('lista_ninos')
        else:
            messages.error(request, 'Por favor completa todos los campos obligatorios')
    
    aulas = Aula.objects.all()
    return render(request, 'core/ninos/registrar.html', {'aulas': aulas})

@login_required
def detalle_nino(request, nino_id):
    nino = get_object_or_404(Nino, id=nino_id)
    return render(request, 'core/ninos/detalle.html', {'nino': nino})

@login_required
def editar_nino(request, nino_id):
    nino = get_object_or_404(Nino, id=nino_id)
    
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
        
        nino.save()
        messages.success(request, f'Niño {nino.nombre_completo} actualizado correctamente')
        return redirect('detalle_nino', nino_id=nino.id)
    
    aulas = Aula.objects.all()
    return render(request, 'core/ninos/editar.html', {'nino': nino, 'aulas': aulas})

@login_required
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
def registrar_asistencia(request, asistencia_id):
    asistencia = get_object_or_404(Asistencia, id=asistencia_id)
    
    if request.method == 'POST':
        estado = request.POST.get('estado')
        hora_ingreso = request.POST.get('hora_ingreso')
        motivo = request.POST.get('motivo_ausencia', '')
        
        asistencia.estado = estado
        asistencia.motivo_ausencia = motivo
        asistencia.usuario_registro = request.user
        
        if estado == 'presente' and hora_ingreso:
            asistencia.hora_ingreso = hora_ingreso
        elif estado == 'ausente':
            asistencia.hora_ingreso = None
        
        asistencia.save()
        messages.success(request, f'Asistencia de {asistencia.nino.nombre_completo} actualizada')
    
    return redirect('asistencia_hoy')

@login_required
@login_required
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
def lista_incidencias(request):
    incidencias = Incidencia.objects.all().order_by('-fecha', '-hora')
    return render(request, 'core/incidencias/lista.html', {'incidencias': incidencias})

@login_required
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
def detalle_incidencia(request, incidencia_id):
    incidencia = get_object_or_404(Incidencia, id=incidencia_id)
    return render(request, 'core/incidencias/detalle.html', {'incidencia': incidencia})

@login_required
def generar_reportes(request):
    return render(request, 'core/reportes/index.html')

@login_required
@login_required
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
def lista_aulas(request):
    """Lista de aulas"""
    aulas = Aula.objects.all()
    return render(request, 'core/configuracion/aulas.html', {'aulas': aulas})


@login_required
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
def eliminar_aula(request, aula_id):
    """Eliminar aula"""
    aula = get_object_or_404(Aula, id=aula_id)
    nombre = aula.nombre
    aula.delete()
    messages.success(request, f'Aula "{nombre}" eliminada')
    return redirect('lista_aulas')


@login_required
def lista_usuarios(request):
    """Lista de usuarios"""
    usuarios = Usuario.objects.all().order_by('-date_joined')
    return render(request, 'core/configuracion/usuarios.html', {'usuarios': usuarios})


@login_required
def crear_usuario(request):
    """Crear nuevo usuario"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        rol = request.POST.get('rol', 'cuidadora')
        telefono = request.POST.get('telefono', '')
        
        if username and password:
            if Usuario.objects.filter(username=username).exists():
                messages.error(request, 'El nombre de usuario ya existe')
            else:
                user = Usuario.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    rol=rol,
                    telefono=telefono
                )
                messages.success(request, f'Usuario "{username}" creado correctamente')
                return redirect('lista_usuarios')
        else:
            messages.error(request, 'Por favor completa los campos obligatorios')
    
    return redirect('lista_usuarios')


@login_required
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
