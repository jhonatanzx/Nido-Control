from io import BytesIO
from pathlib import Path

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError


def validar_foto_jpg(foto):
    if Path(foto.name).suffix.lower() != '.jpg':
        raise ValidationError('La foto debe estar en formato .jpg.')

    try:
        foto.seek(0)
        with Image.open(foto) as imagen:
            if imagen.format != 'JPEG':
                raise ValidationError('El archivo seleccionado no es una imagen JPG válida.')
            imagen.verify()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValidationError('El archivo seleccionado no es una imagen JPG válida.') from error
    finally:
        foto.seek(0)


class Usuario(AbstractUser):
    ROLES = [
        ('admin', 'Administrador'),
        ('cuidadora', 'Cuidadora'),
    ]
    rol = models.CharField(max_length=20, choices=ROLES, default='cuidadora')
    telefono = models.CharField(max_length=15, blank=True)
    direccion = models.TextField(blank=True)
    estado = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"

class Aula(models.Model):
    nombre = models.CharField(max_length=50)
    capacidad = models.IntegerField()
    descripcion = models.TextField(blank=True)
    
    def __str__(self):
        return self.nombre

class Nino(models.Model):
    SEXOS = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ]
    nombres = models.CharField(max_length=50)
    apellidos = models.CharField(max_length=50)
    fecha_nacimiento = models.DateField()
    sexo = models.CharField(max_length=1, choices=SEXOS)
    aula = models.ForeignKey(Aula, on_delete=models.SET_NULL, null=True, blank=True)
    alergias = models.TextField(blank=True)
    restricciones = models.TextField(blank=True)
    informacion_medica = models.TextField(blank=True)
    estado_matricula = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    foto = models.ImageField(
        upload_to='fotos_ninos/',
        blank=True,
        null=True,
        validators=[validar_foto_jpg],
    )

    def save(self, *args, **kwargs):
        foto_anterior = None
        if self.pk and (kwargs.get('update_fields') is None or 'foto' in kwargs['update_fields']):
            foto_anterior = type(self).objects.filter(pk=self.pk).values_list('foto', flat=True).first()

        if self.foto and not self.foto._committed:
            validar_foto_jpg(self.foto)
            with Image.open(self.foto) as imagen:
                imagen.seek(0)
                imagen = ImageOps.exif_transpose(imagen)
                if 'A' in imagen.getbands() or 'transparency' in imagen.info:
                    imagen_con_alpha = imagen.convert('RGBA')
                    fondo = Image.new('RGB', imagen_con_alpha.size, 'white')
                    fondo.paste(imagen_con_alpha, mask=imagen_con_alpha.getchannel('A'))
                    imagen = fondo
                else:
                    imagen = imagen.convert('RGB')

                contenido = BytesIO()
                imagen.save(contenido, format='JPEG', quality=85, optimize=True)

            nombre = f'{Path(self.foto.name).stem}.jpg'
            self.foto = ContentFile(contenido.getvalue(), name=nombre)

        super().save(*args, **kwargs)

        if foto_anterior and foto_anterior != self.foto.name:
            self.foto.storage.delete(foto_anterior)
    
    @property
    def edad(self):
        from datetime import date
        today = date.today()
        return today.year - self.fecha_nacimiento.year - ((today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))
    
    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"
    
    def __str__(self):
        return self.nombre_completo

class Apoderado(models.Model):
    PARENTESCOS = [
        ('padre', 'Padre/Madre'),
        ('abuelo', 'Abuelo/Abuela'),
        ('tio', 'Tío/Tía'),
        ('hermano', 'Hermano/Hermana'),
        ('otro', 'Otro'),
    ]
    nino = models.ForeignKey(Nino, on_delete=models.CASCADE, related_name='apoderados')
    nombres = models.CharField(max_length=100)
    parentesco = models.CharField(max_length=20, choices=PARENTESCOS)
    documento = models.CharField(max_length=20)
    telefono = models.CharField(max_length=15)
    correo = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    estado = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.nombres} - {self.nino.nombre_completo}"

class PersonaAutorizada(models.Model):
    nino = models.ForeignKey(Nino, on_delete=models.CASCADE, related_name='autorizados')
    nombres = models.CharField(max_length=100)
    parentesco = models.CharField(max_length=50)
    documento = models.CharField(max_length=20)
    telefono = models.CharField(max_length=15)
    estado = models.BooleanField(default=True)
    fecha_autorizacion = models.DateField(auto_now_add=True)
    observaciones = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.nombres} - {self.nino.nombre_completo}"

class Asistencia(models.Model):
    ESTADOS = [
        ('presente', 'Presente'),
        ('ausente', 'Ausente'),
        ('tardanza', 'Tardanza'),
    ]
    nino = models.ForeignKey(Nino, on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    hora_ingreso = models.TimeField(null=True, blank=True)
    hora_salida = models.TimeField(null=True, blank=True)
    fecha_hora_ingreso = models.DateTimeField(null=True, blank=True)
    fecha_hora_salida = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='presente')
    motivo_ausencia = models.TextField(blank=True)
    usuario_registro = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        unique_together = ['nino', 'fecha']
    
    def __str__(self):
        return f"{self.nino.nombre_completo} - {self.fecha} - {self.estado}"

class RegistroEntrega(models.Model):
    nino = models.ForeignKey(Nino, on_delete=models.CASCADE)
    apoderado = models.ForeignKey('Apoderado', on_delete=models.SET_NULL, null=True, blank=True)
    persona_entrega = models.ForeignKey(PersonaAutorizada, on_delete=models.SET_NULL, null=True)
    nombre_persona = models.CharField(max_length=100)
    documento_verificado = models.CharField(max_length=20, blank=True, default='')
    fecha = models.DateField(default=timezone.now)
    hora = models.TimeField(auto_now_add=True)
    usuario_verifica = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    observaciones = models.TextField(blank=True)
    
    def __str__(self):
        return f"Entrega: {self.nino.nombre_completo} - {self.nombre_persona}"

class Bitacora(models.Model):
    ESTADOS_ANIMO = [
        ('tranquilo', 'Tranquilo'),
        ('alegre', 'Alegre'),
        ('cansado', 'Cansado'),
        ('irritable', 'Irritable'),
        ('otro', 'Otro'),
    ]
    nino = models.ForeignKey(Nino, on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    alimentacion = models.TextField(blank=True)
    descanso = models.TextField(blank=True)
    actividades = models.TextField(blank=True)
    higiene = models.TextField(blank=True)
    estado_animo = models.CharField(max_length=20, choices=ESTADOS_ANIMO, blank=True)
    observaciones = models.TextField(blank=True)
    usuario_registro = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"Bitácora: {self.nino.nombre_completo} - {self.fecha}"


class MenuDiario(models.Model):
    TIPOS_COMIDA = [
        ('desayuno', 'Desayuno'),
        ('almuerzo', 'Almuerzo'),
        ('merienda', 'Merienda'),
    ]
    fecha = models.DateField(default=timezone.localdate)
    tipo_comida = models.CharField(max_length=20, choices=TIPOS_COMIDA)
    descripcion = models.TextField()
    usuario_registro = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'tipo_comida']
        unique_together = ['fecha', 'tipo_comida']

    def __str__(self):
        return f'{self.get_tipo_comida_display()} - {self.fecha}'


class Incidencia(models.Model):
    TIPOS = [
        ('accidente', 'Accidente leve'),
        ('enfermedad', 'Enfermedad'),
        ('comportamiento', 'Comportamiento'),
        ('otro', 'Otro'),
    ]
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('atendido', 'Atendido'),
        ('comunicado', 'Comunicado'),
        ('cerrado', 'Cerrado'),
    ]
    nino = models.ForeignKey(Nino, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    fecha = models.DateField(default=timezone.now)
    hora = models.TimeField(auto_now_add=True)
    descripcion = models.TextField()
    accion_realizada = models.TextField(blank=True)
    comunicacion_apoderado = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    usuario_registro = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"Incidencia: {self.nino.nombre_completo} - {self.get_tipo_display()}"

class Pago(models.Model):
    ESTADOS = [
        ('pagado', 'Pagado'),
        ('pendiente', 'Pendiente'),
        ('vencido', 'Vencido'),
    ]
    nino = models.ForeignKey(Nino, on_delete=models.CASCADE)
    concepto = models.CharField(max_length=100)
    periodo = models.CharField(max_length=50)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    observaciones = models.TextField(blank=True)
    
    def __str__(self):
        return f"Pago: {self.nino.nombre_completo} - {self.periodo}"