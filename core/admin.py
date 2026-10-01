from django.contrib import admin
from .models import *

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'rol', 'estado']
    list_filter = ['rol', 'estado']
    search_fields = ['username', 'email']

@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'capacidad']
    search_fields = ['nombre']

@admin.register(Nino)
class NinoAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'fecha_nacimiento', 'edad', 'aula', 'estado_matricula']
    list_filter = ['aula', 'estado_matricula', 'sexo']
    search_fields = ['nombres', 'apellidos']
    readonly_fields = ['fecha_registro']

@admin.register(Apoderado)
class ApoderadoAdmin(admin.ModelAdmin):
    list_display = ['nombres', 'nino', 'parentesco', 'telefono']
    list_filter = ['parentesco']
    search_fields = ['nombres']

@admin.register(PersonaAutorizada)
class PersonaAutorizadaAdmin(admin.ModelAdmin):
    list_display = ['nombres', 'nino', 'parentesco', 'estado']
    list_filter = ['estado']
    search_fields = ['nombres']

@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ['nino', 'fecha', 'estado', 'hora_ingreso', 'hora_salida']
    list_filter = ['estado', 'fecha']
    search_fields = ['nino__nombres', 'nino__apellidos']

@admin.register(RegistroEntrega)
class RegistroEntregaAdmin(admin.ModelAdmin):
    list_display = ['nino', 'nombre_persona', 'documento_verificado', 'fecha', 'hora']
    list_filter = ['fecha']

@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ['nino', 'fecha', 'estado_animo']
    list_filter = ['fecha', 'estado_animo']

@admin.register(Incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    list_display = ['nino', 'tipo', 'fecha', 'estado']
    list_filter = ['tipo', 'estado', 'fecha']
    search_fields = ['descripcion']

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ['nino', 'concepto', 'periodo', 'monto', 'estado']
    list_filter = ['estado', 'periodo']