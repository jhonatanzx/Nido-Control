from django.urls import path
from . import views

urlpatterns = [
    # Autenticación
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard, name='dashboard'),
    
    # Niños
    path('ninos/', views.lista_ninos, name='lista_ninos'),
    path('ninos/registrar/', views.registrar_nino, name='registrar_nino'),
    path('ninos/<int:nino_id>/', views.detalle_nino, name='detalle_nino'),
    path('ninos/<int:nino_id>/editar/', views.editar_nino, name='editar_nino'),
    
    # Asistencia
    path('asistencia/', views.asistencia_hoy, name='asistencia_hoy'),
    path('asistencia/<int:asistencia_id>/registrar/', views.registrar_asistencia, name='registrar_asistencia'),
    path('asistencia/<int:asistencia_id>/salida/', views.registrar_salida, name='registrar_salida'),
    
    # Bitácora
    path('bitacora/', views.bitacora_hoy, name='bitacora_hoy'),
    path('bitacora/<int:bitacora_id>/registrar/', views.registrar_bitacora, name='registrar_bitacora'),
    
    # Incidencias
    path('incidencias/', views.lista_incidencias, name='lista_incidencias'),
    path('incidencias/registrar/', views.registrar_incidencia, name='registrar_incidencia'),
    path('incidencias/<int:incidencia_id>/', views.detalle_incidencia, name='detalle_incidencia'),
    path('incidencias/<int:incidencia_id>/finalizar/', views.finalizar_incidencia, name='finalizar_incidencia'),
    
    # Reportes
    path('reportes/', views.generar_reportes, name='generar_reportes'),
    path('reportes/asistencia/', views.reporte_asistencia, name='reporte_asistencia'),
    path('reportes/incidencias/', views.reporte_incidencias, name='reporte_incidencias'),
    path('reportes/bitacora/', views.reporte_bitacora, name='reporte_bitacora'),
    
    # Estadísticas
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    
    # Configuración
    path('configuracion/', views.configuracion, name='configuracion'),
    path('configuracion/aulas/', views.lista_aulas, name='lista_aulas'),
    path('configuracion/aulas/crear/', views.crear_aula, name='crear_aula'),
    path('configuracion/aulas/<int:aula_id>/editar/', views.editar_aula, name='editar_aula'),
    path('configuracion/aulas/<int:aula_id>/eliminar/', views.eliminar_aula, name='eliminar_aula'),
    path('configuracion/usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('configuracion/usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    path('configuracion/usuarios/<int:usuario_id>/estado/', views.cambiar_estado_usuario, name='cambiar_estado_usuario'),
    path('configuracion/perfil/', views.mi_perfil, name='mi_perfil'),
    path('configuracion/password/', views.cambiar_password, name='cambiar_password'),
]
