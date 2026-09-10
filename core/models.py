from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

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
    foto = models.ImageField(upload_to='fotos_ninos/', blank=True, null=True)
    
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
    estado = models.CharField(max_length=20, choices=ESTADOS, default='presente')
    motivo_ausencia = models.TextField(blank=True)
    usuario_registro = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        unique_together = ['nino', 'fecha']
    
    def __str__(self):
        return f"{self.nino.nombre_completo} - {self.fecha} - {self.estado}"

class RegistroEntrega(models.Model):
    nino = models.ForeignKey(Nino, on_delete=models.CASCADE)
    persona_entrega = models.ForeignKey(PersonaAutorizada, on_delete=models.SET_NULL, null=True)
    nombre_persona = models.CharField(max_length=100)
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