from django import forms
from .models import *

class NinoForm(forms.ModelForm):
    class Meta:
        model = Nino
        fields = ['nombres', 'apellidos', 'fecha_nacimiento', 'sexo', 'aula', 
                  'alergias', 'restricciones', 'informacion_medica', 'foto']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'sexo': forms.Select(attrs={'class': 'form-control'}),
            'aula': forms.Select(attrs={'class': 'form-control'}),
            'alergias': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'restricciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'informacion_medica': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ApoderadoForm(forms.ModelForm):
    class Meta:
        model = Apoderado
        fields = ['nombres', 'parentesco', 'documento', 'telefono', 'correo', 'direccion']
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'parentesco': forms.Select(attrs={'class': 'form-control'}),
            'documento': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class PersonaAutorizadaForm(forms.ModelForm):
    class Meta:
        model = PersonaAutorizada
        fields = ['nombres', 'parentesco', 'documento', 'telefono', 'observaciones']
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'parentesco': forms.TextInput(attrs={'class': 'form-control'}),
            'documento': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class BitacoraForm(forms.ModelForm):
    class Meta:
        model = Bitacora
        fields = ['alimentacion', 'descanso', 'actividades', 'higiene', 'estado_animo', 'observaciones']
        widgets = {
            'alimentacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'descanso': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'actividades': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'higiene': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'estado_animo': forms.Select(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class IncidenciaForm(forms.ModelForm):
    class Meta:
        model = Incidencia
        fields = ['nino', 'tipo', 'descripcion', 'accion_realizada', 'comunicacion_apoderado', 'estado']
        widgets = {
            'nino': forms.Select(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'accion_realizada': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'comunicacion_apoderado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
        }